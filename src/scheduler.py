import asyncio
from collections.abc import Callable, Coroutine
from functools import partial
from random import random
from traceback import format_exc, format_exception

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .database import (
    CheckRecord,
    FailureRecord,
    ReportRecord,
    get_failure,
    remove_old_reports,
    remove_unknown_checks,
    update_status,
)
from .executor import ExecutionException, Executor
from .models.config import Check, Executable, MainConfig, Reporter

_INTERNAL_NAME = "_itsumi"


def create_periodic_task(
    func: Callable[[], Coroutine], delay: float, interval: float
) -> Coroutine:
    async def inner_loop():
        await asyncio.sleep(delay)
        while True:
            # if `func_task` completes first, wait for `interval` to pass
            # if `interval` passes first, cancel `func_task` and raise exception
            await asyncio.gather(
                asyncio.wait_for(func(), interval), asyncio.sleep(interval)
            )

    return inner_loop()


class Scheduler:
    def __init__(
        self,
        config: MainConfig,
        executor: Executor,
        session_maker: async_sessionmaker[AsyncSession],
        checks: dict[str, Check],
        reporters: list[Reporter],
    ):
        self.config = config
        self.executor = executor
        self.database = session_maker
        self.checks = checks
        self.reporters = reporters

        self._tasks = set()

        self._create_task(self._clean_database()).add_done_callback(
            self._handle_task_exception
        )

        for check in checks.values():
            self._add_check(check)

    def _add_check(self, check: Check):
        task = self._create_task(
            create_periodic_task(
                partial(self._run_check, check),
                check.interval * random(),
                check.interval,
            )
        )
        task.add_done_callback(self._handle_task_exception)

    async def _clean_database(self):
        async with self.database.begin() as session:
            await remove_unknown_checks(session, list(self.checks))

    def _create_task(self, coro: Coroutine) -> asyncio.Task:
        task = asyncio.get_running_loop().create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.remove)
        return task

    async def _execute(
        self, exe: Executable, env: dict[str, str] | None = None
    ) -> tuple[int, str]:
        try:
            return await self.executor.execute(exe, env=env)
        except ExecutionException:
            return -1, format_exc()

    async def _run_check(self, check: Check):
        code, output = await self._execute(check)
        async with self.database.begin() as session:
            record = CheckRecord(name=check.name, code=code, output=output)
            session.add(record)
            if not await update_status(session, check):
                session.add(
                    FailureRecord(
                        name=check.name,
                        reported=await self._report_failure(session, record),
                    )
                )

    async def _report_failure(
        self,
        session: AsyncSession,
        record: CheckRecord,
        *,
        stop_on_success: bool = False,
    ) -> bool:
        success_count = 0

        for i, reporter in enumerate(self.reporters, start=1):
            code, output = await self._execute(
                reporter,
                {
                    "CHECK_NAME": record.name,
                    "CHECK_CODE": str(record.code),
                    "CHECK_OUTPUT": record.output,
                },
            )
            session.add(ReportRecord(name=f"reporter-{i}", code=code, output=output))
            if code == 0:
                success_count += 1
                if stop_on_success:
                    break

        await remove_old_reports(session, self.config.report_record_limit)

        return success_count >= (1 if stop_on_success else i)

    async def report(
        self, session: AsyncSession, record: CheckRecord, all_reporters: bool
    ) -> bool:
        return await self._report_failure(
            session, record, stop_on_success=not all_reporters
        )

    async def _report_internal_exception(self, exc: Exception):
        async with self.database.begin() as session:
            if await get_failure(session, _INTERNAL_NAME):
                # already recorded
                return

            reported = await self._report_failure(
                session,
                CheckRecord(
                    name=_INTERNAL_NAME, code=-1, output="".join(format_exception(exc))
                ),
            )
            session.add(
                FailureRecord(
                    name=_INTERNAL_NAME,
                    reported=reported,
                )
            )

    def _handle_task_exception(self, task: asyncio.Task):
        if exc := task.exception():
            self._create_task(self._report_internal_exception(exc))

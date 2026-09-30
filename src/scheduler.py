import asyncio
from collections.abc import Callable, Coroutine
from functools import partial
from random import random
from traceback import format_exc, format_exception

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .database import CheckRecord, FailureRecord, ReportRecord, update_status
from .executor import ExecutionException, Executor
from .models.config import Check, Executable, Reporter

_INTERNAL_NAME = "_itsumi"


def create_periodic_task(
    func: Callable[[], Coroutine], delay: float, interval: float
) -> asyncio.Task:
    loop = asyncio.get_running_loop()

    async def inner_loop():
        await asyncio.sleep(delay)
        while True:
            # if `func_task` completes first, wait for `interval` to pass
            # if `interval` passes first, cancel `func_task` and raise exception
            await asyncio.gather(
                asyncio.wait_for(func(), interval), asyncio.sleep(interval)
            )

    return loop.create_task(inner_loop())


class Scheduler:
    def __init__(
        self,
        executor: Executor,
        session_maker: async_sessionmaker[AsyncSession],
        checks: dict[str, Check],
        reporters: list[Reporter],
    ):
        self.executor = executor
        self.database = session_maker
        self.checks = checks
        self.reporters = reporters

        self._tasks = set()

        for check in checks.values():
            self._add_check(check)

    def _add_check(self, check: Check):
        task = create_periodic_task(
            partial(self._run_check, check),
            check.interval * random(),
            check.interval,
        )
        self._tasks.add(task)
        task.add_done_callback(self._check_loop_done)

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

    async def _report_failure(self, session: AsyncSession, record: CheckRecord) -> bool:
        for i, reporter in enumerate(self.reporters):
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
                return True
        return False

    async def _report_internal_exception(self, exc: Exception):
        async with self.database.begin() as session:
            reported = await self._report_failure(
                session,
                CheckRecord(
                    name=_INTERNAL_NAME, code=-1, output="".join(format_exception(exc))
                ),
            )
            # XXX: it may already exist
            session.add(
                FailureRecord(
                    name=_INTERNAL_NAME,
                    reported=reported,
                )
            )

    def _check_loop_done(self, task: asyncio.Task):
        self._tasks.remove(task)
        if exc := task.exception():
            task = asyncio.get_running_loop().create_task(
                self._report_internal_exception(exc)
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.remove)

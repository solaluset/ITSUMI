import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
from datetime import timedelta
from functools import partial
from traceback import format_exc, format_exception

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .database import (
    CheckRecord,
    FailureRecord,
    ReportRecord,
    current_time,
    get_failure,
    get_logs,
    remove_old_reports,
    remove_unknown_checks,
    update_status,
)
from .executor import ExecutionException, Executor
from .models.config import Check, Executable, MainConfig, Reporter

_INTERNAL_NAME = "_itsumi"
_INTERNAL_CODE = -1


def create_periodic_task(
    func: Callable[[], Coroutine], delay: float, interval: float
) -> Coroutine:
    async def inner_loop():
        await asyncio.sleep(delay)
        while True:
            # if `func_task` completes first, wait for `interval` to pass
            await asyncio.gather(func(), asyncio.sleep(interval))

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

        self._locks = defaultdict(asyncio.Lock)
        self._tasks = set()

        self._create_task(self._async_init())

    async def _async_init(self):
        async with self.database.begin() as session:
            await remove_unknown_checks(session, list(self.checks))
        async with self.database() as session:
            await asyncio.gather(
                *(self._add_check(session, check) for check in self.checks.values())
            )

    async def _add_check(self, session: AsyncSession, check: Check):
        last_run = await get_logs(session, CheckRecord, name=check.name, limit=1)
        if last_run:
            delay = (
                last_run[0].time + timedelta(seconds=check.interval) - current_time()
            ).total_seconds()
        else:
            delay = 0
        self._create_task(
            create_periodic_task(
                partial(self._run_check, check),
                delay,
                check.interval,
            )
        )

    async def _execute(
        self, exe: Executable, timeout: float, env: dict[str, str] | None = None
    ) -> tuple[int, str]:
        try:
            async with asyncio.timeout(timeout):
                return await self.executor.execute(exe, env=env)
        except (ExecutionException, TimeoutError):
            return _INTERNAL_CODE, format_exc()

    async def _run_check(self, check: Check):
        code, output = await self._execute(check, check.interval)
        self._create_task(self._handle_check_result(check, code, output))

    async def _handle_check_result(self, check: Check, code: int, output: str):
        async with self._locks[check.name]:
            record = CheckRecord(name=check.name, code=code, output=output)
            async with self.database.begin() as session:
                session.add(record)
                report_needed = not await update_status(session, check)
                session.expunge(record)

            if not report_needed:
                return
            reported = await self._report_failure(record)

            async with self.database.begin() as session:
                session.add(
                    FailureRecord(
                        name=check.name,
                        reported=reported,
                    )
                )

    async def _report_failure(
        self,
        record: CheckRecord,
        *,
        stop_on_success: bool = True,
    ) -> bool:
        reports = []
        success_count = 0

        for i, reporter in enumerate(self.reporters, start=1):
            code, output = await self._execute(
                reporter,
                self.config.report_timeout,
                {
                    "CHECK_NAME": record.name,
                    "CHECK_CODE": str(record.code),
                    "CHECK_OUTPUT": record.output,
                },
            )
            reports.append(ReportRecord(name=f"reporter-{i}", code=code, output=output))
            if code == 0:
                success_count += 1
                if stop_on_success:
                    break

        async with self.database.begin() as session:
            session.add_all(reports)
            await remove_old_reports(session, self.config.report_record_limit)

        return success_count >= (1 if stop_on_success else i)

    async def report(self, record: CheckRecord, all_reporters: bool) -> bool:
        return await self._report_failure(record, stop_on_success=not all_reporters)

    async def _report_internal_exception(self, exc: Exception):
        async with self._locks[_INTERNAL_NAME]:
            async with self.database.begin() as session:
                if await get_failure(session, _INTERNAL_NAME):
                    # already recorded
                    return

            record = CheckRecord(
                name=_INTERNAL_NAME,
                code=_INTERNAL_CODE,
                output="".join(format_exception(exc)),
            )
            reported = await self._report_failure(record)

            async with self.database.begin() as session:
                session.add(record)
                session.add(
                    FailureRecord(
                        name=_INTERNAL_NAME,
                        reported=reported,
                    )
                )

    def stop(self) -> None:
        for task in self._tasks:
            task.cancel()

    def _create_task(
        self, coro: Coroutine, /, *, add_error_handler: bool = True
    ) -> asyncio.Task:
        task = asyncio.get_running_loop().create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.remove)
        if add_error_handler:
            task.add_done_callback(self._handle_task_exception)
        return task

    def _handle_task_exception(self, task: asyncio.Task):
        if task.cancelled():
            return
        if exc := task.exception():
            self._create_task(
                self._report_internal_exception(exc), add_error_handler=False
            )

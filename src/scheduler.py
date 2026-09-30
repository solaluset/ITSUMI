import asyncio
from collections.abc import Callable, Coroutine
from functools import partial
from random import random

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .database import CheckRecord, update_status
from .executor import Executor
from .models.config import Check, Reporter


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
        task.add_done_callback(self._task_done_callback)

    async def _run_check(self, check: Check):
        code, output = await self.executor.execute(check)
        async with self.database.begin() as session:
            session.add(CheckRecord(name=check.name, code=code, output=output))
            print(await update_status(session, check))

    def _task_done_callback(self, task: asyncio.Task):
        self._tasks.remove(task)
        if exc := task.exception():
            print(exc)

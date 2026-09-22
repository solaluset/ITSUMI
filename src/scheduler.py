import asyncio
from collections.abc import Awaitable, Callable
from functools import partial
from random import random

from .executor import Executor, ExitCodeException
from .models.config import Check, Executable


async def _cancel_after(task: asyncio.Task, delay: float) -> None:
    await asyncio.sleep(delay)
    if task.cancel():
        raise TimeoutError("task was running for too long")


def create_periodic_task(
    func: Callable[[], Awaitable], delay: float, interval: float
) -> asyncio.Task:
    loop = asyncio.get_running_loop()

    async def inner_loop():
        await asyncio.sleep(delay)
        while True:
            # if `func_task` completes first, wait for `interval` to pass
            # if `interval` passes first, cancel `func_task` and raise exception
            func_task = loop.create_task(func())
            await asyncio.gather(func_task, _cancel_after(func_task, interval))

    return loop.create_task(inner_loop())


class Scheduler:
    def __init__(self, executor: Executor, checks: dict[str, Check]):
        self.executor = executor
        self.checks = checks
        self._tasks = set()

        for check in checks.values():
            self._add_check(check)

    def _add_check(self, check: Check):
        task = create_periodic_task(
            partial(self._run_executable, check),
            check.interval * random(),
            check.interval,
        )
        self._tasks.add(task)
        task.add_done_callback(self._task_done_callback)

    async def _run_executable(self, exe: Executable):
        try:
            await self.executor.execute(exe)
        except ExitCodeException:
            ...

    def _task_done_callback(self, task: asyncio.Task):
        self._tasks.remove(task)
        if exc := task.exception():
            print(exc)

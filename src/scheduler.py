import asyncio
from collections.abc import Awaitable, Callable
from functools import partial
from random import random

from .executor import Executor, ExitCodeException
from .models.config import Task


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
    def __init__(self, executor: Executor, tasks: dict[str, Task]):
        self.executor = executor
        self.tasks = tasks
        self._async_tasks = set()

        for task in tasks.values():
            self._start_task(task)

    def _start_task(self, task: Task):
        async_task = create_periodic_task(
            partial(self._run_task, task), task.interval * random(), task.interval
        )
        self._async_tasks.add(async_task)
        async_task.add_done_callback(self._task_done_callback)

    async def _run_task(self, task: Task):
        try:
            await self.executor.execute(task)
        except ExitCodeException:
            ...

    def _task_done_callback(self, async_task: asyncio.Task):
        self._async_tasks.remove(async_task)
        if exc := async_task.exception():
            print(exc)

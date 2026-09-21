import asyncio
from collections.abc import Awaitable, Callable


async def _cancel_after(task: asyncio.Task, delay: float) -> None:
    await asyncio.sleep(delay)
    if task.cancel():
        raise TimeoutError("task was running for too long")


async def create_periodic_task(
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

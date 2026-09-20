import asyncio
from collections.abc import Awaitable, Callable


async def create_periodic_task(
    func: Callable[[], Awaitable], delay: float, interval: float
) -> asyncio.Task:
    async def inner_loop():
        await asyncio.sleep(delay)
        while True:
            await asyncio.gather(func(), asyncio.sleep(interval))

    return asyncio.get_running_loop().create_task(inner_loop())

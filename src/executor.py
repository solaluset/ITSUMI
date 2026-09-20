import asyncio
import subprocess


def _call(command: tuple[str, ...], stdin: str) -> int:
    with subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    ) as process:
        process.stdin.write(stdin)
        process.stdin.close()
        return process.wait()


async def run_command(command: tuple[str, ...], stdin: str) -> int:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _call, command, stdin)

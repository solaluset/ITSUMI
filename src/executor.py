import asyncio
import subprocess
from pathlib import Path


def _call(command: tuple[str, ...], cwd: Path, stdin: str) -> int:
    with subprocess.Popen(
        command,
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    ) as process:
        process.stdin.write(stdin)
        process.stdin.close()
        return process.wait()


async def run_command(command: tuple[str, ...], cwd: Path, stdin: str) -> int:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _call, command, cwd, stdin)

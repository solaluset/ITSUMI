import asyncio
import subprocess
from pathlib import Path


def _call(command: tuple[str, ...], cwd: Path, stdin: str) -> tuple[int, str]:
    with subprocess.Popen(
        command,
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    ) as process:
        process.stdin.write(stdin)
        process.stdin.close()
        return process.wait(), process.stdout.read()


async def run_command(
    command: tuple[str, ...], cwd: Path, stdin: str
) -> tuple[int, str]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _call, command, cwd, stdin)

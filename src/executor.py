import asyncio
import subprocess
from pathlib import Path

from .models.config import Executable, Runtime


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


class ExecutionException(Exception):
    pass


class NoSuchRuntimeException(ExecutionException):
    pass


class Executor:
    def __init__(self, workdir: Path, runtimes: dict[str, Runtime]):
        self.workdir = workdir
        self.runtimes = runtimes

    async def execute(self, exe: Executable) -> tuple[int, str]:
        runtime = self.runtimes.get(exe.runtime)
        if not runtime:
            raise NoSuchRuntimeException(exe.runtime)
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(
                None, _call, runtime.command, self.workdir, exe.execute
            )
        except Exception as e:
            raise ExecutionException(e) from e

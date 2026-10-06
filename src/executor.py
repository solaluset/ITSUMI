import asyncio
import os
import subprocess
from functools import partial
from pathlib import Path

from .models.config import Executable, MainConfig, Runtime


class ExecutionException(Exception):
    pass


class NoSuchRuntimeException(ExecutionException):
    pass


class Executor:
    def __init__(self, workdir: Path, config: MainConfig, runtimes: dict[str, Runtime]):
        self.workdir = workdir
        self.pass_env = config.pass_env
        self.runtimes = runtimes

    async def execute(
        self, exe: Executable, /, *, env: dict[str, str] | None = None
    ) -> tuple[int, str]:
        runtime = self.runtimes.get(exe.runtime)
        if not runtime:
            raise NoSuchRuntimeException(exe.runtime)
        loop = asyncio.get_running_loop()
        environ = {
            key: os.getenv(key) for key in self.pass_env if os.getenv(key) is not None
        }
        if env:
            environ.update(env)
        try:
            process = await loop.run_in_executor(
                None,
                partial(
                    subprocess.Popen,
                    runtime.command,
                    cwd=self.workdir,
                    env=environ,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                ),
            )
            try:
                await loop.run_in_executor(None, _communicate, process, exe.execute)
            except asyncio.CancelledError:
                process.kill()
                raise
        except Exception as e:
            raise ExecutionException(e) from e


def _communicate(process: subprocess.Popen, stdin: str) -> tuple[int, str]:
    with process:
        stdout, _ = process.communicate(stdin)
        return process.returncode, stdout

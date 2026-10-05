import asyncio
import os
import subprocess
from pathlib import Path

from .models.config import Executable, MainConfig, Runtime


def _call(
    command: tuple[str, ...], cwd: Path, env: dict[str, str], stdin: str
) -> tuple[int, str]:
    with subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
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
            return await loop.run_in_executor(
                None, _call, runtime.command, self.workdir, environ, exe.execute
            )
        except Exception as e:
            raise ExecutionException(e) from e

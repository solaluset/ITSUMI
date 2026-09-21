import os
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path

from fastapi import FastAPI
from pydantic_yaml import parse_yaml_file_as

from .executor import run_command
from .models.config import Executable, RuntimesConfig, TasksConfig
from .scheduler import create_periodic_task


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.workdir = Path(os.getenv("ITSUMI_WORKDIR", os.getcwd())).absolute()
    app.state.tasks = parse_yaml_file_as(
        TasksConfig, app.state.workdir / "config" / "tasks.yml"
    ).tasks
    app.state.runtimes = parse_yaml_file_as(
        RuntimesConfig, app.state.workdir / "config" / "runtimes.yml"
    ).runtimes

    for task in app.state.tasks.values():
        app.state.t = await create_periodic_task(
            partial(execute, app, task), 5, task.interval
        )
        app.state.t.add_done_callback(
            lambda t: print(e) if (e := t.exception()) else None
        )

    try:
        yield
    finally:
        ...


async def execute(app: FastAPI, exe: Executable) -> int:
    runtime = app.state.runtimes[exe.runtime]
    code, output = await run_command(runtime.command, app.state.workdir, exe.execute)
    print(code, output)
    return code


app = FastAPI(lifespan=lifespan)

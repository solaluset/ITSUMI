import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from pydantic_yaml import parse_yaml_file_as

from .executor import run_command
from .models.config import RuntimesConfig, Task, TasksConfig
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
            lambda task=task: execute_task(app, task), 5, task.interval
        )

    try:
        yield
    finally:
        ...


async def execute_task(app: FastAPI, task: Task) -> None:
    runtime = app.state.runtimes[task.runtime]
    print(await run_command(runtime.command, app.state.workdir, task.execute))


app = FastAPI(lifespan=lifespan)

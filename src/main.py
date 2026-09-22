import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from pydantic_yaml import parse_yaml_file_as

from .executor import Executor
from .models.config import RuntimesConfig, TasksConfig
from .scheduler import Scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.workdir = Path(os.getenv("ITSUMI_WORKDIR", os.getcwd())).absolute()
    app.state.tasks = parse_yaml_file_as(
        TasksConfig, app.state.workdir / "config" / "tasks.yml"
    ).tasks
    runtimes = parse_yaml_file_as(
        RuntimesConfig, app.state.workdir / "config" / "runtimes.yml"
    ).runtimes
    app.state.executor = Executor(app.state.workdir, runtimes)
    app.state.scheduler = Scheduler(app.state.executor, app.state.tasks)

    try:
        yield
    finally:
        ...


app = FastAPI(lifespan=lifespan)

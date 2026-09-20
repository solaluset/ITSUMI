import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from pydantic_yaml import parse_yaml_file_as

from .models.config import TasksConfig


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.workdir = Path(os.getenv("ITSUMI_WORKDIR", os.getcwd())).absolute()
    app.state.tasks = parse_yaml_file_as(
        TasksConfig, app.state.workdir / "config" / "tasks.yml"
    ).tasks
    try:
        yield
    finally:
        ...


app = FastAPI(lifespan=lifespan)

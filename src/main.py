import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from pydantic_yaml import parse_yaml_file_as

from .executor import Executor
from .models.config import ChecksConfig, RuntimesConfig
from .scheduler import Scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.workdir = Path(os.getenv("ITSUMI_WORKDIR", os.getcwd())).absolute()
    checks = parse_yaml_file_as(
        ChecksConfig, app.state.workdir / "config" / "checks.yml"
    ).checks
    runtimes = parse_yaml_file_as(
        RuntimesConfig, app.state.workdir / "config" / "runtimes.yml"
    ).runtimes
    executor = Executor(app.state.workdir, runtimes)
    app.state.scheduler = Scheduler(executor, checks)

    try:
        yield
    finally:
        ...


app = FastAPI(lifespan=lifespan)

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from pydantic_yaml import parse_yaml_file_as

from .database import create_session_maker
from .executor import Executor
from .models.config import ChecksConfig, ReportersConfig, RuntimesConfig
from .scheduler import Scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.workdir = Path(os.getenv("ITSUMI_WORKDIR", os.getcwd())).absolute()
    config_dir = app.state.workdir / "config"
    runtimes = parse_yaml_file_as(RuntimesConfig, config_dir / "runtimes.yml").runtimes
    checks = parse_yaml_file_as(ChecksConfig, config_dir / "checks.yml").checks
    reporters = parse_yaml_file_as(
        ReportersConfig, config_dir / "reporters.yml"
    ).reporters
    executor = Executor(app.state.workdir, runtimes)
    app.state.db = await create_session_maker()
    app.state.scheduler = Scheduler(executor, checks, reporters)

    try:
        yield
    finally:
        pass


app = FastAPI(lifespan=lifespan)

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from pydantic_yaml import parse_yaml_file_as

from .database import create_session_maker, get_unreported_failures
from .executor import Executor
from .models.config import ChecksConfig, MainConfig, ReportersConfig, RuntimesConfig
from .scheduler import Scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.workdir = Path(os.getenv("ITSUMI_WORKDIR", os.getcwd())).absolute()
    os.chdir(app.state.workdir)
    (app.state.workdir / "data").mkdir(exist_ok=True)

    config_dir = app.state.workdir / "config"
    config = parse_yaml_file_as(MainConfig, config_dir / "main.yml")
    runtimes = parse_yaml_file_as(RuntimesConfig, config_dir / "runtimes.yml").runtimes
    checks = parse_yaml_file_as(ChecksConfig, config_dir / "checks.yml").checks
    reporters = parse_yaml_file_as(
        ReportersConfig, config_dir / "reporters.yml"
    ).reporters
    executor = Executor(app.state.workdir, runtimes)

    app.state.db = await create_session_maker(config.database)
    app.state.scheduler = Scheduler(config, executor, app.state.db, checks, reporters)

    try:
        yield
    finally:
        pass


app = FastAPI(lifespan=lifespan)
api_router = APIRouter(prefix="/api")
api_router_v1 = APIRouter(prefix="/v1")


@api_router_v1.get("/status")
async def root():
    async with app.state.db() as session:
        return {"failures": await get_unreported_failures(session)}


api_router.include_router(api_router_v1)
app.include_router(api_router)

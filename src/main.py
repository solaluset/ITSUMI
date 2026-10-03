import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query
from pydantic_yaml import parse_yaml_file_as

from .database import (
    CheckRecord,
    ReportRecord,
    create_session_maker,
    get_logs,
    get_unreported_failures,
)
from .executor import Executor
from .models.api import StatusResponse
from .models.config import ChecksConfig, MainConfig, ReportersConfig, RuntimesConfig
from .scheduler import Scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    workdir = Path(os.getenv("ITSUMI_WORKDIR", os.getcwd())).absolute()
    os.chdir(workdir)
    (workdir / "data").mkdir(exist_ok=True)

    config_dir = workdir / "config"
    config = parse_yaml_file_as(MainConfig, config_dir / "main.yml")
    runtimes = parse_yaml_file_as(RuntimesConfig, config_dir / "runtimes.yml").runtimes
    checks = parse_yaml_file_as(ChecksConfig, config_dir / "checks.yml").checks
    reporters = parse_yaml_file_as(
        ReportersConfig, config_dir / "reporters.yml"
    ).reporters
    executor = Executor(workdir, runtimes)

    app.state.config = config
    app.state.db = await create_session_maker(config.database)
    app.state.scheduler = Scheduler(config, executor, app.state.db, checks, reporters)

    try:
        yield
    finally:
        pass


def auth_v1(token: Annotated[str, Header()]):
    if token not in app.state.config.tokens.values():
        raise HTTPException(401)


app = FastAPI(lifespan=lifespan)
api_router = APIRouter(prefix="/api")
api_router_v1 = APIRouter(prefix="/v1", dependencies=[Depends(auth_v1)])


@api_router_v1.get("/status")
async def status() -> StatusResponse:
    async with app.state.db() as session:
        return StatusResponse(failures=await get_unreported_failures(session))


@api_router_v1.get("/logs")
async def logs(
    record_type: Annotated[Literal["check", "report"], Query(alias="type")],
    name: Annotated[str | None, Query()] = None,
    failed_only: Annotated[bool, Query(alias="failed")] = False,
    limit: Annotated[int, Query()] = 10,
):
    async with app.state.db() as session:
        return await get_logs(
            session,
            {"check": CheckRecord, "report": ReportRecord}[record_type],
            name,
            failed_only,
            limit,
        )


api_router.include_router(api_router_v1)
app.include_router(api_router)

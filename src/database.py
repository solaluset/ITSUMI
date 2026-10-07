from datetime import datetime, timedelta, timezone
from typing import TypeVar
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column
from sqlalchemy.sql import functions as funcs

from .models.config import Check


class Base(DeclarativeBase, MappedAsDataclass):
    pass


def _current_time() -> datetime:
    return datetime.now(timezone.utc)


class Run(MappedAsDataclass):
    name: Mapped[str]
    code: Mapped[int]
    output: Mapped[str]
    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    time: Mapped[datetime] = mapped_column(default_factory=_current_time)


class CheckRecord(Base, Run):
    __tablename__ = "check"


class ReportRecord(Base, Run):
    __tablename__ = "report"


class FailureRecord(Base):
    __tablename__ = "failure"

    name: Mapped[str] = mapped_column(primary_key=True)
    reported: Mapped[bool]


async def create_session_maker(url: str, **kwargs) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(url, **kwargs)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return async_sessionmaker(engine)


async def update_status(session: AsyncSession, check: Check) -> bool:
    await session.execute(
        delete(CheckRecord).where(
            (CheckRecord.name == check.name)
            & (CheckRecord.time < _current_time() - timedelta(seconds=check.retention))
        )
    )

    count_query = select(funcs.count()).where(CheckRecord.name == check.name)
    success_count = await session.scalar(count_query.where(CheckRecord.code == 0))
    failure_count = await session.scalar(count_query.where(CheckRecord.code != 0))
    failed = success_count <= 0 or failure_count > check.max_failures

    if not failed:
        await session.execute(
            delete(FailureRecord).where(FailureRecord.name == check.name)
        )
        return True

    return (
        await session.scalar(
            select(funcs.count()).where(FailureRecord.name == check.name)
        )
    ) > 0


async def get_failure(session: AsyncSession, name: str) -> FailureRecord | None:
    return await session.scalar(select(FailureRecord).where(FailureRecord.name == name))


async def get_unreported_failures(session: AsyncSession) -> list[str]:
    return (
        await session.scalars(
            select(FailureRecord.name).where(FailureRecord.reported.is_(False))
        )
    ).all()


RunT = TypeVar("RunT", bound=Run)


async def get_logs(
    session: AsyncSession,
    type_: type[RunT],
    name: str | None,
    failed_only: bool,
    limit: int,
) -> list[RunT]:
    query = select(type_)
    if name is not None:
        query = query.where(type_.name == name)
    if failed_only:
        query = query.where(type_.code != 0)
    return (await session.scalars(query.order_by(type_.time.desc()).limit(limit))).all()


async def remove_old_reports(session: AsyncSession, limit: int):
    oldest_retain = (
        select(ReportRecord.time)
        .order_by(ReportRecord.time.desc())
        .offset(limit - 1)
        .limit(1)
        .scalar_subquery()
    )
    await session.execute(delete(ReportRecord).where(ReportRecord.time < oldest_retain))


async def remove_unknown_checks(session: AsyncSession, known_checks: list[str]):
    await session.execute(
        delete(FailureRecord).where(FailureRecord.name.not_in(known_checks))
    )
    await session.execute(
        delete(CheckRecord).where(CheckRecord.name.not_in(known_checks))
    )

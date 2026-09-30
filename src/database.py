from datetime import datetime, timedelta, timezone
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


async def create_session_maker(url: str) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(url)

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
    failed = (
        await session.scalar(
            select(funcs.count()).where(
                (CheckRecord.name == check.name) & (CheckRecord.code != 0)
            )
        )
    ) > check.max_failures

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

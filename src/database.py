from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column


class Base(DeclarativeBase):
    pass


class Run(MappedAsDataclass):
    name: Mapped[str]
    code: Mapped[int]
    output: Mapped[str]
    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    time: Mapped[datetime] = mapped_column(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class CheckRecord(Base, Run):
    __tablename__ = "check"


class ReportRecord(Base, Run):
    __tablename__ = "report"


async def create_session_maker() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite://")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return async_sessionmaker(engine)

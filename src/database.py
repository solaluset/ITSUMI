from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Run:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str]
    time: Mapped[datetime] = mapped_column(default=datetime)
    code: Mapped[int]
    output: Mapped[str]


class Check(Base, Run):
    __tablename__ = "check"


class Report(Base, Run):
    __tablename__ = "report"


async def create_session_maker():
    engine = create_async_engine("sqlite+aiosqlite://")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return async_sessionmaker(engine)

from typing import Annotated

from pydantic import BaseModel, BeforeValidator
from timelength import TimeLength


def _parse_duration(value: str) -> float:
    parsed = TimeLength(value)
    if not parsed.result.success:
        raise ValueError(f"invalid duration: {value}")
    return parsed.result.seconds


Duration = Annotated[float, BeforeValidator(_parse_duration)]


class Runtime(BaseModel):
    command: tuple[str, ...]


class RuntimesConfig(BaseModel):
    runtimes: dict[str, Runtime]


class Task(BaseModel):
    interval: Duration
    runtime: str
    execute: str


class TasksConfig(BaseModel):
    tasks: dict[str, Task]

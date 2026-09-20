from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict
from timelength import TimeLength


class Model(BaseModel):
    model_config = ConfigDict(alias_generator=lambda x: x.replace("_", "-"))


def _parse_duration(value: str) -> float:
    parsed = TimeLength(value)
    if not parsed.result.success:
        raise ValueError(f"invalid duration: {value}")
    return parsed.result.seconds


Duration = Annotated[float, BeforeValidator(_parse_duration)]


class Runtime(Model):
    command: tuple[str, ...]


class RuntimesConfig(Model):
    runtimes: dict[str, Runtime]


class Task(Model):
    interval: Duration
    retention: Duration
    max_failures: int
    runtime: str
    execute: str


class TasksConfig(Model):
    tasks: dict[str, Task]

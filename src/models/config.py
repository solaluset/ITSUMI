from pydantic import BaseModel, validator
from timelength import TimeLength


class Runtime(BaseModel):
    command: tuple[str, ...]


class RuntimesConfig(BaseModel):
    runtimes: dict[str, Runtime]


class Task(BaseModel):
    interval: float
    runtime: str
    execute: str

    @validator("interval", pre=True)
    def _parse_interval(cls, value: str) -> float:
        parsed = TimeLength(value)
        if not parsed.result.success:
            raise ValueError(f"invalid interval: {value}")
        return parsed.result.seconds


class TasksConfig(BaseModel):
    tasks: dict[str, Task]

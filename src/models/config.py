from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, model_validator
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


class Executable(Model):
    runtime: str
    execute: str


class Check(Executable):
    interval: Duration
    retention: Duration
    max_failures: int
    name: str = ""


class ChecksConfig(Model):
    checks: dict[str, Check]

    @model_validator(mode="after")
    def _set_check_names(self):
        for name, check in self.checks.items():
            check.name = name
        return self


class Reporter(Executable):
    pass


class ReportersConfig(Model):
    reporters: list[Reporter]


class MainConfig(Model):
    database: str
    report_record_limit: int
    pass_env: list[str]
    tokens: dict[str, str]

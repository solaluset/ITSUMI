if not __debug__:
    raise RuntimeError("disabling assertions is not supported")

__all__ = ("_exec", "os")

import ast
import asyncio
import inspect
import os
from types import FunctionType


def _exec(source: str, namespace: dict):
    code = compile(source, "<source>", "exec", ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
    func = FunctionType(code, namespace)
    result = func()
    if inspect.isawaitable(result):
        asyncio.run(result)

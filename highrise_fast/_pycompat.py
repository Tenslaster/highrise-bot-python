"""Standard-library interfaces with backports for Python 3.10."""

import sys
from asyncio import TimeoutError as TimeoutError
from dataclasses import dataclass as _dataclass

if sys.version_info >= (3, 11):
    from asyncio import TaskGroup as TaskGroup
    from asyncio import timeout as timeout
    from builtins import BaseExceptionGroup as BaseExceptionGroup
    from enum import StrEnum as StrEnum

    dataclass = _dataclass
else:
    from enum import Enum

    from async_timeout import timeout as timeout
    from exceptiongroup import BaseExceptionGroup as BaseExceptionGroup
    from taskgroup import TaskGroup as TaskGroup

    class StrEnum(str, Enum):
        """String enum with the same string conversion as Python 3.11."""

        __str__ = str.__str__

    def dataclass(cls=None, /, *, weakref_slot=False, **kwargs):
        """Ignore the optional weak-reference slot on Python 3.10."""
        return _dataclass(cls, **kwargs)

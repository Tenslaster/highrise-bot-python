from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Callable, Coroutine
from logging import Logger
from typing import Any

from .logger import setup_logger


class LoopTask:
    """Run an async callable on a fixed interval with safe cancellation."""

    __slots__ = ("_coro_fn", "_seconds", "_logger", "_task")

    def __init__(
        self,
        coro_fn: Callable[[], Coroutine[Any, Any, None]],
        seconds: float = 60.0,
        logger: Logger | None = None,
    ) -> None:
        if not inspect.iscoroutinefunction(coro_fn):
            raise TypeError("LoopTask requires an async function")
        if seconds <= 0:
            raise ValueError("LoopTask interval must be greater than zero")
        self._coro_fn = coro_fn
        self._seconds = float(seconds)
        self._logger = logger or setup_logger(name=coro_fn.__name__)
        self._task: asyncio.Task[Any] | None = None

    async def _run_loop(self) -> None:
        while True:
            started = time.monotonic()
            try:
                await self._coro_fn()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._logger.error(
                    "Exception in background loop '%s': %s",
                    self._coro_fn.__name__,
                    exc,
                    exc_info=True,
                )

            remaining = max(0.0, self._seconds - (time.monotonic() - started))
            await asyncio.sleep(remaining)

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(
            self._run_loop(),
            name=f"loop_{self._coro_fn.__name__}",
        )

    async def cancel(self) -> None:
        task = self._task
        if task is None:
            return
        self._task = None
        if task.done():
            return
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    @property
    def get_loop_task(self) -> asyncio.Task[Any] | None:
        return self._task if self._task is not None and not self._task.done() else None

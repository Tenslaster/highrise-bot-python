from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Coroutine
from typing import Any, TYPE_CHECKING

from ..cache.room_users import RoomUsersCache
from ..errors import BotStateError
from ..tools.loop_task import LoopTask

if TYPE_CHECKING:
    from ..base_bot import BaseBot


class TaskManager:
    """Owns SDK tasks with explicit persistent and connection scopes."""

    __slots__ = (
        "bot",
        "_persistent_tasks",
        "_connection_tasks",
        "_loops",
        "_core_started",
    )

    def __init__(self, bot: "BaseBot") -> None:
        self.bot = bot
        self._persistent_tasks: set[asyncio.Task[Any]] = set()
        self._connection_tasks: set[asyncio.Task[Any]] = set()
        self._loops: list[LoopTask] = []
        self._core_started = False

    @property
    def active_tasks(self) -> list[asyncio.Task[Any]]:
        return [t for t in (*self._persistent_tasks, *self._connection_tasks) if not t.done()]

    @property
    def registered_loops(self) -> list[LoopTask]:
        return self._loops

    def start_core_loops(self) -> None:
        if self._core_started:
            return
        self._core_started = True
        self.create_task(self._autosave_roles_loop(), name="autosave_roles", persistent=True)

    def create_task(
        self,
        coro: Coroutine[Any, Any, Any],
        name: str = "fn_task",
        *,
        persistent: bool = False,
    ) -> asyncio.Task[Any]:
        task = asyncio.create_task(coro, name=name)
        target = self._persistent_tasks if persistent else self._connection_tasks
        target.add(task)
        task.add_done_callback(lambda completed: self._on_task_complete(completed, target))
        return task

    def register_loop(
        self,
        seconds: float,
        func: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        if not inspect.iscoroutinefunction(func):
            raise TypeError("@bot.loop requires an async function")
        self._loops.append(LoopTask(coro_fn=func, seconds=seconds, logger=self.bot.logger))

    def start_all_loops(self) -> None:
        for loop in self._loops:
            loop.start()

    async def stop_all_loops(self) -> None:
        await asyncio.gather(*(loop.cancel() for loop in self._loops), return_exceptions=True)

    async def cancel_connection_tasks(self) -> None:
        await self._cancel_and_gather(self._connection_tasks)
        await self.stop_all_loops()

    async def shutdown(self) -> None:
        await self.cancel_connection_tasks()
        await self._cancel_and_gather(self._persistent_tasks)
        self._loops.clear()
        self._core_started = False

    async def _cancel_and_gather(self, tasks: set[asyncio.Task[Any]]) -> None:
        snapshot = tuple(tasks)
        for task in snapshot:
            if not task.done():
                task.cancel()
        if snapshot:
            await asyncio.gather(*snapshot, return_exceptions=True)
        tasks.clear()

    def _on_task_complete(
        self,
        task: asyncio.Task[Any],
        registry: set[asyncio.Task[Any]],
    ) -> None:
        registry.discard(task)
        if task.cancelled():
            return
        try:
            exc = task.exception()
        except asyncio.CancelledError:
            return
        if exc is not None:
            self.bot.logger.error(
                f"Unhandled error in task '{task.get_name()}': {exc}",
                exc_info=(type(exc), exc, exc.__traceback__),
            )

    async def _autosave_roles_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.bot.config.roles.autosave_interval)
                self.bot.roles.save()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.bot.logger.error("Roles autosave loop crashed: %s", exc, exc_info=True)

    def on_first_start(self) -> None:
        self.start_core_loops()

    async def fetch_room_users(self) -> None:
        try:
            response = await self.bot.highrise.get_room_users()
            if response.ok:
                self.bot.cached_users = RoomUsersCache._from_response(response)
            else:
                self.bot.logger.warning(f"Failed to fetch room users to cache: {response.error}")
        except Exception as exc:
            self.bot.logger.warning(f"Failed to fetch room users to cache: {exc}")

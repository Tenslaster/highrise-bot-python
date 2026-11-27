"""Connection-scoped event matching for Highrise bots."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Callable, Hashable, Iterable
from functools import partial
from typing import Any

EVENT_SUBSCRIPTIONS = {
    "chat": "chat",
    "whisper": "chat",
    "emote": "emote",
    "reaction": "reaction",
    "user_join": "user_joined",
    "user_leave": "user_left",
    "user_move": "user_moved",
    "tip": "tip_reaction",
    "channel": "channel",
    "voice": "voice",
    "message": "message",
    "moderation": "moderation",
}


class _Match:
    def __init__(
        self,
        names: frozenset[str],
        predicate: Callable[..., bool] | None,
        count: int,
        unique_by: Callable[..., Hashable] | None,
        mode: str,
    ) -> None:
        self.names = names
        self.predicate = predicate
        self.count = count
        self.unique_by = unique_by
        self.mode = mode
        self.results: list[tuple] = []
        self.seen: set[Hashable] = set()
        self.future = asyncio.get_running_loop().create_future()
        self.timer: asyncio.TimerHandle | None = None

    def add(self, event: str, payload: tuple) -> bool:
        if self.future.done():
            return False
        try:
            args = (event, *payload) if self.mode == "any" else payload
            if self.predicate is not None and not self.predicate(*args):
                return False
            if self.unique_by is not None:
                key = self.unique_by(*payload)
                if key in self.seen:
                    return False
                self.seen.add(key)
            if self.future.done():
                return False
            if self.mode == "many":
                self.results.append(payload)
                if len(self.results) >= self.count:
                    self.future.set_result(self.results)
            else:
                self.future.set_result((event, payload) if self.mode == "any" else payload)
            return True
        except Exception as exc:
            if not self.future.done():
                self.future.set_exception(exc)
            return False

    def expire(self) -> None:
        if not self.future.done():
            self.future.set_result(self.results if self.mode == "many" else None)


class Awaiter:
    """Wait for Highrise events without consuming them from regular bot hooks."""

    def __init__(
        self, events: Iterable[str] = (), *, max_pending: int = 128, max_results: int = 1000
    ) -> None:
        self.events = frozenset((events,) if isinstance(events, str) else events)
        self._check_names(self.events)
        if any(type(limit) is not int or limit < 1 for limit in (max_pending, max_results)):
            raise ValueError("Event limits must be positive integers")
        self.max_pending = max_pending
        self.max_results = max_results
        self._matches: set[_Match] = set()
        self._by_event: dict[str, dict[_Match, None]] = {}

    @staticmethod
    def _check_names(names: frozenset[str]) -> None:
        unknown = names.difference(EVENT_SUBSCRIPTIONS)
        if unknown:
            raise ValueError(f"Unknown Highrise events: {sorted(unknown)}")

    @property
    def subscriptions(self) -> frozenset[str]:
        """Server event subscriptions requested explicitly by this awaiter."""
        return frozenset(EVENT_SUBSCRIPTIONS[name] for name in self.events)

    @property
    def pending_count(self) -> int:
        return len(self._matches)

    def _forget(self, match: _Match, future: asyncio.Future) -> None:
        self._matches.discard(match)
        if match.timer is not None:
            match.timer.cancel()
        for event in match.names:
            waiting = self._by_event.get(event)
            if waiting is not None:
                waiting.pop(match, None)
                if not waiting:
                    self._by_event.pop(event, None)
        if not future.cancelled():
            future.exception()

    def _register(
        self,
        names: frozenset[str],
        predicate: Callable[..., bool] | None,
        timeout: float | None,
        mode: str,
        count: int = 1,
        unique_by: Callable[..., Hashable] | None = None,
    ) -> asyncio.Future:
        self._check_names(names)
        if not names:
            raise ValueError("At least one event is required")
        if len(self._matches) >= self.max_pending:
            raise RuntimeError("Too many pending event waits")
        if timeout is not None and (not math.isfinite(timeout) or timeout < 0):
            raise ValueError("timeout must be finite and nonnegative")
        if not isinstance(count, int) or not 1 <= count <= self.max_results:
            raise ValueError("count must be between 1 and max_results")
        match = _Match(names, predicate, count, unique_by, mode)
        self._matches.add(match)
        for name in names:
            self._by_event.setdefault(name, {})[match] = None
        match.future.add_done_callback(partial(self._forget, match))
        if timeout is not None:
            match.timer = asyncio.get_running_loop().call_later(timeout, match.expire)
        return match.future

    def expect(
        self,
        event: str,
        *,
        predicate: Callable[..., bool] | None = None,
        timeout: float | None = None,
    ) -> asyncio.Future[tuple | None]:
        """Register immediately and return a future for the next matching event."""
        return self._register(frozenset((event,)), predicate, timeout, "one")

    async def wait_for(
        self,
        event: str,
        *,
        predicate: Callable[..., bool] | None = None,
        timeout: float | None = None,
    ) -> tuple | None:
        """Wait for the next matching event, or return None on timeout."""
        return await self.expect(event, predicate=predicate, timeout=timeout)

    async def wait_any(
        self,
        *events: str,
        predicate: Callable[..., bool] | None = None,
        timeout: float | None = None,
    ) -> tuple[str, tuple] | None:
        """Return (event name, hook arguments) for the first match."""
        return await self._register(frozenset(events), predicate, timeout, "any")

    async def collect(
        self,
        event: str,
        *,
        count: int,
        predicate: Callable[..., bool] | None = None,
        unique_by: Callable[..., Hashable] | None = None,
        timeout: float | None = None,
    ) -> list[tuple]:
        """Collect matches, returning any partial results at the deadline."""
        return await self._register(
            frozenset((event,)), predicate, timeout, "many", count, unique_by
        )

    def emit(self, event: str, *args: Any) -> int:
        """Deliver hook arguments to current waits and return the number of matches."""
        waiting = self._by_event.get(event)
        if not waiting:
            return 0
        matched = 0
        for match in tuple(waiting):
            matched += match.add(event, args)
            if match.future.done():
                self._forget(match, match.future)
        return matched

    def cancel_all(self) -> None:
        """Cancel pending waits when this room connection ends."""
        for match in tuple(self._matches):
            match.future.cancel()
            self._forget(match, match.future)

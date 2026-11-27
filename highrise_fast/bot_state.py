"""Reusable local state for occupancy, playtime, and command roles."""

from __future__ import annotations

import asyncio
import json
import math
import os
import tempfile
import time
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

_UNSET = object()


class AtomicJsonStore:
    """Read and atomically replace a JSON file from a background thread."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self._lock = asyncio.Lock()

    async def _run(self, call: Callable, *args: Any) -> Any:
        async def serialized():
            async with self._lock:
                return await asyncio.to_thread(call, *args)

        task = asyncio.create_task(serialized())
        task.add_done_callback(self._finish)
        return await asyncio.shield(task)

    @staticmethod
    def _finish(task: asyncio.Task) -> None:
        if not task.cancelled():
            task.exception()

    def _read(self, default: Any) -> Any:
        try:
            with self.path.open(encoding="utf-8") as source:
                return json.load(source)
        except FileNotFoundError:
            if default is _UNSET:
                raise
            return default

    def _write(self, value: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as target:
                temp_path = Path(target.name)
                json.dump(value, target, ensure_ascii=False, allow_nan=False, indent=2)
                target.write("\n")
                target.flush()
                os.fsync(target.fileno())
            os.replace(temp_path, self.path)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    async def load(self, default: Any = _UNSET) -> Any:
        """Load JSON, returning the supplied default if the file is missing."""
        return await self._run(self._read, default)

    async def save(self, value: Any) -> None:
        """Write a full JSON snapshot and wait for the atomic replacement."""
        await self._run(self._write, value)


class _RosterFilter:
    def __init__(self, exclude_ids: Iterable[str], exclude_usernames: Iterable[str]):
        self.ids = frozenset(exclude_ids)
        self.names = frozenset(name.strip().casefold() for name in exclude_usernames)

    def includes(self, user_id: str, username: str) -> bool:
        return user_id not in self.ids and username.casefold() not in self.names


class PresenceTimer:
    """Accumulate playtime by user ID from authoritative roster snapshots."""

    def __init__(
        self,
        totals: Mapping[str, float] | None = None,
        *,
        exclude_ids: Iterable[str] = (),
        exclude_usernames: Iterable[str] = (),
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._filter = _RosterFilter(exclude_ids, exclude_usernames)
        self._clock = clock
        self._totals: dict[str, float] = {}
        self._active: dict[str, float] = {}
        if totals is not None and not isinstance(totals, Mapping):
            raise ValueError("Presence totals must be an object keyed by user ID")
        for user_id, seconds in (totals or {}).items():
            if not isinstance(user_id, str) or type(seconds) not in (int, float):
                raise ValueError("Presence totals must map user IDs to numeric seconds")
            try:
                valid = math.isfinite(seconds) and seconds >= 0
            except OverflowError:
                valid = False
            if not valid:
                raise ValueError("Presence seconds must be finite and nonnegative")
            self._totals[user_id] = float(seconds)

    def observe(self, roster: Mapping[str, str]) -> None:
        """Apply a snapshot of user IDs and usernames, including any missed leaves."""
        now = self._clock()
        present = {uid for uid, name in roster.items() if self._filter.includes(uid, name)}
        for uid in self._active.keys() - present:
            start = self._active.pop(uid)
            self._totals[uid] = self._totals.get(uid, 0.0) + max(0.0, now - start)
        for uid in present:
            self._active.setdefault(uid, now)

    def pause(self) -> None:
        """Finish all current sessions, for example when disconnected."""
        self.observe({})

    def seconds(self, user_id: str) -> float:
        """Return cumulative time including the current session."""
        elapsed = self._totals.get(user_id, 0.0)
        start = self._active.get(user_id)
        return elapsed if start is None else elapsed + max(0.0, self._clock() - start)

    def snapshot(self) -> dict[str, float]:
        """Return a JSON-ready checkpoint including active sessions."""
        now = self._clock()
        totals = dict(self._totals)
        for uid, start in self._active.items():
            totals[uid] = totals.get(uid, 0.0) + max(0.0, now - start)
        return totals

    def leaderboard(self, limit: int = 10) -> list[tuple[str, float]]:
        """Return the highest totals in descending order, with stable ties."""
        if limit < 0:
            raise ValueError("limit must be nonnegative")
        return sorted(self.snapshot().items(), key=lambda pair: (-pair[1], pair[0]))[:limit]

    def reset(self) -> None:
        """Clear accumulated time and restart current sessions at zero."""
        now = self._clock()
        self._totals.clear()
        self._active = dict.fromkeys(self._active, now)


class RoomOccupancyTrigger:
    """Fire once per confirmed transition from an empty room to an occupied room."""

    def __init__(
        self,
        empty_seconds: float = 10,
        *,
        exclude_ids: Iterable[str] = (),
        exclude_usernames: Iterable[str] = (),
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not math.isfinite(empty_seconds) or empty_seconds < 0:
            raise ValueError("empty_seconds must be finite and nonnegative")
        self.empty_seconds = empty_seconds
        self._clock = clock
        self._filter = _RosterFilter(exclude_ids, exclude_usernames)
        self.reset()

    def reset(self) -> None:
        """Discard observations made before a disconnect or room change."""
        self._empty_since: float | None = None
        self.armed = False

    def observe(self, roster: Mapping[str, str]) -> bool:
        """Return True for the first occupied snapshot after a confirmed empty period."""
        if any(self._filter.includes(uid, name) for uid, name in roster.items()):
            fired = self.armed
            self.reset()
            return fired
        now = self._clock()
        if self._empty_since is None:
            self._empty_since = now
        if now - self._empty_since >= self.empty_seconds:
            self.armed = True
        return False


class RoleStore:
    """Manage local command roles with an optional explicit rank hierarchy."""

    def __init__(self, store: AtomicJsonStore, *, hierarchy: Iterable[str] = ()) -> None:
        self.store = store
        self._users: dict[str, set[str]] = {}
        self._hierarchy = {role.strip().casefold(): index for index, role in enumerate(hierarchy)}

    def grant(self, user_id: str, role: str) -> None:
        role = role.strip().casefold()
        if not user_id or not role:
            raise ValueError("user ID and role must be nonempty")
        self._users.setdefault(user_id, set()).add(role)

    def revoke(self, user_id: str, role: str) -> bool:
        roles = self._users.get(user_id)
        role = role.strip().casefold()
        if roles is None or role not in roles:
            return False
        roles.remove(role)
        if not roles:
            del self._users[user_id]
        return True

    def roles_for(self, user_id: str) -> frozenset[str]:
        return frozenset(self._users.get(user_id, ()))

    def allows(self, user_id: str, rank: str) -> bool:
        roles = self._users.get(user_id)
        if not roles:
            return False
        rank = rank.strip().casefold()
        if rank in roles:
            return True
        required = self._hierarchy.get(rank)
        return required is not None and any(
            self._hierarchy.get(role, -1) >= required for role in roles
        )

    def permission_checker(self, bot, user, rank: str) -> bool:
        """Use as a permission checker in CommandRegistry."""
        return self.allows(user.id, rank)

    async def load(self) -> None:
        payload = await self.store.load(default={})
        if not isinstance(payload, dict):
            raise ValueError("Roles must be a JSON object keyed by user ID")
        users = {}
        for uid, roles in payload.items():
            if (
                not uid
                or not isinstance(roles, list)
                or any(not isinstance(role, str) or not role.strip() for role in roles)
            ):
                raise ValueError("Each user ID must map to a list of role names")
            if roles:
                users[uid] = {role.strip().casefold() for role in roles}
        self._users = users

    async def save(self) -> None:
        await self.store.save({uid: sorted(roles) for uid, roles in self._users.items()})

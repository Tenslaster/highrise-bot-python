"""Extra utilities for highrise_fast: caching, metrics, task management, command routing, room tracking, throttled actions, and chat helpers."""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import math
import time
import types
from collections import OrderedDict, defaultdict
from collections.abc import Callable, Coroutine, Hashable
from typing import Any

try:

    import aiohttp

except ImportError:

    aiohttp = None



__all__ = [

    "MISSING",

    "CachedWebAPI",

    "MetricTracker",

    "Metrics",

    "TTLCache",

    "TaskManager",

    "cached",

    "CommandContext",

    "CommandRegistry",

    "commands",

    "RoomTracker",

    "ThrottledActions",

    "chunk_for_chat",

    "send_long_message",

    "DebouncedSaver",

    "PromptManager",

    "UserResolver",

]



logger = logging.getLogger("highrise_fast.extras")

MISSING = object()





def _stable_repr(value: Any) -> str:

    """Order-insensitive repr for JSON-ish values.



    Dicts are rendered with keys sorted — recursively — so

    {"a": 1, "b": 2} and {"b": 2, "a": 1} produce identical strings,

    both at the top level and nested inside lists/dicts. Sets are sorted

    too (their iteration order is arbitrary). Everything else falls back

    to plain repr(). Used to build stable cache keys.

    """

    if isinstance(value, dict):

        return (

            "{"

            + ", ".join(

                f"{k!r}: {_stable_repr(v)}"

                for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))

            )

            + "}"

        )

    if isinstance(value, (list, tuple)):

        return "[" + ", ".join(_stable_repr(v) for v in value) + "]"

    if isinstance(value, (set, frozenset)):

        return "set(" + ", ".join(sorted(_stable_repr(v) for v in value)) + ")"

    return repr(value)









class TTLCache:
    """Bounded least-recently-used cache with monotonic expiry."""

    __slots__ = ("_maxsize", "_store")

    def __init__(self, maxsize: int = 1024) -> None:
        if maxsize < 0:
            raise ValueError("maxsize must be nonnegative")
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._maxsize = maxsize

    def __len__(self) -> int:
        return len(self._store)

    def get(self, key: str) -> Any:
        """Return the cached value, or MISSING if absent or expired."""
        item = self._store.get(key)
        if item is None:
            return MISSING
        expires_at, value = item
        if time.monotonic() < expires_at:
            self._store.move_to_end(key)
            return value
        del self._store[key]
        return MISSING

    def set(self, key: str, value: Any, ttl: int = 60) -> None:
        """Store a value with a TTL, evicting the LRU entry when full."""
        if self._maxsize == 0 or ttl <= 0:
            self.invalidate(key)
            return
        self._store[key] = (time.monotonic() + ttl, value)
        self._store.move_to_end(key)
        if len(self._store) > self._maxsize:
            self._store.popitem(last=False)

    def invalidate(self, key: str) -> None:
        """Drop a single key."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Drop everything."""
        self._store.clear()


class CachedWebAPI:

    """Optional raw cached WebAPI client."""



    def __init__(

        self,

        base_url: str = "https://webapi.highrise.game",

        timeout: Any = None,

        cache_ttl: int = 60,

    ) -> None:

        """Create a cached WebAPI client."""

        self.base_url = base_url.rstrip("/")

        self.timeout = timeout

        self.cache_ttl = cache_ttl

        self._cache = TTLCache()

        self._session: Any = None



    async def _get_session(self) -> Any:

        """Return the persistent aiohttp session, creating it if needed."""

        if self._session is None or self._session.closed:

            if aiohttp is None:

                raise RuntimeError("Missing dependency: pip install aiohttp")

            headers = {"User-Agent": "highrise-fast/1.0.0 (CachedWebAPI)"}

            self._session = aiohttp.ClientSession(timeout=self.timeout, headers=headers)

        return self._session



    async def _request(

        self, method: str, endpoint: str, **kwargs: Any

    ) -> dict[str, Any]:

        """Send one HTTP request and return the decoded JSON."""

        session = await self._get_session()

        url = f"{self.base_url}{endpoint}"

        async with session.request(method, url, **kwargs) as response:

            if response.status >= 400:

                text = await response.text()

                raise RuntimeError(f"WebAPI error {response.status}: {text}")

            return await response.json()



    async def get(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:

        """GET with caching.



        Cache keys are order-insensitive at every nesting level: top-level

        kwargs and the dicts/lists inside them (e.g. params={"a":1,"b":2}

        vs params={"b":2,"a":1} previously produced different keys and

        bypassed the cache on every call). Unreprable kwargs disable

        caching for that call instead of raising.

        """

        try:

            cache_key = f"GET:{endpoint}:{_stable_repr(kwargs)}"

        except (TypeError, ValueError, RecursionError):

            cache_key = None



        if cache_key is not None:

            cached = self._cache.get(cache_key)

            if cached is not MISSING:

                return cached



        result = await self._request("GET", endpoint, **kwargs)



        if cache_key is not None:

            self._cache.set(cache_key, result, self.cache_ttl)



        return result



    async def close(self) -> None:

        """Close the session if it is not already closed."""

        if self._session is not None and not self._session.closed:

            await self._session.close()



    async def __aenter__(self) -> CachedWebAPI:

        """Enter the context manager."""

        return self



    async def __aexit__(

        self,

        exc_type: type[BaseException] | None,

        exc: BaseException | None,

        tb: types.TracebackType | None,

    ) -> None:

        """Close the resource on exit."""

        await self.close()





WebAPI = CachedWebAPI





class UserResolver:
    """Bidirectional username and ID lookup with bounded, expiring caches."""

    __slots__ = ("_webapi", "_username_cache", "_id_cache", "_ttl")

    def __init__(self, webapi: Any, *, ttl: int = 300, maxsize: int = 1024) -> None:
        self._webapi = webapi
        self._username_cache = TTLCache(maxsize)
        self._id_cache = TTLCache(maxsize)
        self._ttl = max(0, int(ttl))

    def _link(self, uid: str, username: str) -> None:
        self._id_cache.set(str(uid), username, self._ttl)
        self._username_cache.set(username.strip().lower(), str(uid), self._ttl)

    async def username_to_id(self, username: str) -> str | None:
        key = username.strip().lower()
        cached_id = self._username_cache.get(key)
        if cached_id is not MISSING:
            return cached_id
        uid = await self._webapi.username_to_id(username)
        if uid is not None:
            self._link(uid, username)
        return uid

    async def id_to_username(self, user_id: str) -> str | None:
        key = str(user_id)
        cached_name = self._id_cache.get(key)
        if cached_name is not MISSING:
            return cached_name
        username = await self._webapi.id_to_username(key)
        if username is not None:
            self._link(key, username)
        return username

    def clear(self) -> None:
        """Clear both caches."""
        self._username_cache.clear()
        self._id_cache.clear()


class MetricTracker:

    """Tracks count and timing for a specific event."""



    __slots__ = ("count", "max_time", "min_time", "total_time")



    def __init__(self) -> None:

        """Initialize all counters to their neutral values."""

        self.count = 0

        self.total_time = 0.0

        self.min_time = float("inf")

        self.max_time = 0.0



    @property

    def avg(self) -> float:

        """Average time taken by the object."""

        return self.total_time / self.count if self.count else 0.0



    def record(self, duration_ms: float) -> None:

        """Record the duration of a task in milliseconds."""

        self.count += 1

        self.total_time += duration_ms

        self.min_time = min(self.min_time, duration_ms)

        self.max_time = max(self.max_time, duration_ms)





class Metrics:

    """Global metrics collector."""



    def __init__(self) -> None:

        """Start the uptime clock with empty event trackers."""

        self.start_time = time.perf_counter()

        self.event_trackers: dict[str, MetricTracker] = defaultdict(MetricTracker)

        self.errors = 0



    def track(self, event_name: str, duration_ms: float) -> None:

        """Track an event with a specified duration in milliseconds."""

        self.event_trackers[event_name].record(duration_ms)



    def record_error(self) -> None:

        """Record the error in the instance's `errors` attribute."""

        self.errors += 1



    def summary(self) -> dict[str, Any]:

        """Return uptime, error count, and per-event timing statistics."""

        uptime = time.perf_counter() - self.start_time

        return {

            "uptime_seconds": round(uptime, 2),

            "total_errors": self.errors,

            "events": {

                name: {

                    "count": tracker.count,

                    "avg_ms": round(tracker.avg, 3),

                    "min_ms": (

                        round(tracker.min_time, 3)

                        if tracker.min_time != float("inf")

                        else 0

                    ),

                    "max_ms": round(tracker.max_time, 3),

                }

                for name, tracker in self.event_trackers.items()

            },

        }



    def reset(self) -> None:

        """Reset start time, event trackers, and error count."""

        self.start_time = time.perf_counter()

        self.event_trackers.clear()

        self.errors = 0





class _TaskSlot:
    __slots__ = ("lock", "active", "latest")

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.active: set[asyncio.Task[Any]] = set()
        self.latest: asyncio.Task[Any] | None = None


class TaskManager:
    """Track background tasks and run at most one task body per key."""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[Any]] = set()
        self._cancelling: set[asyncio.Task[Any]] = set()
        self._slots: dict[Hashable, _TaskSlot] = {}
        self._closed = False

    def _task_done(self, task: asyncio.Task[Any]) -> None:
        self._tasks.discard(task)
        self._cancelling.discard(task)
        if not task.cancelled():
            exc = task.exception()
            if exc is not None:
                logger.error("Background task crashed: %r", exc, exc_info=exc)

    def _keyed_done(self, key: Hashable, slot: _TaskSlot, task: asyncio.Task[Any]) -> None:
        slot.active.discard(task)
        if not slot.active:
            self._slots.pop(key)
        self._task_done(task)

    def _cancel_task(self, task: asyncio.Task[Any]) -> None:
        if task not in self._cancelling and not task.done():
            self._cancelling.add(task)
            task.cancel()

    def spawn(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        """Spawn a managed background task."""
        try:
            if self._closed:
                raise RuntimeError("Task manager is closed")
            task = asyncio.create_task(coro)
        except BaseException:
            if inspect.iscoroutine(coro):
                coro.close()
            raise
        self._tasks.add(task)
        task.add_done_callback(self._task_done)
        return task

    def replace(
        self, key: Hashable, factory: Callable[[], Coroutine[Any, Any, Any]]
    ) -> asyncio.Task[Any]:
        """Cancel the current task for key and start the new one after cleanup."""
        if self._closed:
            raise RuntimeError("Task manager is closed")
        loop = asyncio.get_running_loop()
        slot = self._slots.get(key)
        if slot is None:
            slot = self._slots[key] = _TaskSlot()
        registered = loop.create_future()

        async def run() -> Any:
            # Eager task factories can start the coroutine inside create_task().
            await registered
            async with slot.lock:
                return await factory()

        previous = slot.latest
        body = run()
        try:
            task = loop.create_task(body)
        except BaseException:
            body.close()
            if not slot.active:
                self._slots.pop(key)
            raise
        if previous is not None:
            self._cancel_task(previous)
        slot.latest = task
        slot.active.add(task)
        self._tasks.add(task)
        task.add_done_callback(functools.partial(self._keyed_done, key, slot))
        registered.set_result(None)
        return task

    async def cancel_key(self, key: Hashable) -> bool:
        """Cancel a task by key and wait for its pending cleanup."""
        slot = self._slots.get(key)
        if slot is None:
            return False
        if asyncio.current_task() in slot.active:
            raise RuntimeError("A keyed task cannot await its own cancellation")
        tasks = tuple(slot.active)
        for task in tasks:
            self._cancel_task(task)
        await asyncio.shield(asyncio.gather(*tasks, return_exceptions=True))
        return True

    async def cancel_all(self) -> None:
        """Cancel tasks active at the time of the call and wait for cleanup."""
        current = asyncio.current_task()
        tasks = self._tasks - {current}
        for task in tasks:
            self._cancel_task(task)
        if tasks:
            await asyncio.shield(asyncio.gather(*tasks, return_exceptions=True))

    async def close(self) -> None:
        """Stop accepting tasks and cancel the current tasks."""
        self._closed = True
        await self.cancel_all()


def cached(ttl: int = 60) -> Callable[[Callable[..., Any]], Callable[..., Any]]:

    """Simple caching decorator for synchronous functions.



    Cache keys are stable across call sites: keyword arguments are sorted

    by name, so ``f(a=1, b=2)`` and ``f(b=2, a=1)`` share a single entry.



    Safety guard: arguments whose repr contains a memory address (the

    default object repr) disable caching for that call. This prevents

    both useless misses and — worse — false HITS when an object is

    garbage-collected and a different object is allocated at the same

    address. Do not use this decorator on instance methods.

    """

    cache = TTLCache()



    def _repr_is_stable(value: Any) -> bool:

        """True when the repr contains no memory address."""

        try:

            return " object at 0x" not in repr(value)

        except Exception:

            return False



    def _stable_key(func_name: str, args: tuple, kwargs: dict) -> str | None:

        """Build a stable cache key, or None to skip caching for this call."""

        try:

            if not all(_repr_is_stable(a) for a in args):

                return None

            if not all(_repr_is_stable(v) for v in kwargs.values()):

                return None

            stable_kwargs = sorted(kwargs.items(), key=lambda kv: str(kv[0]))

            return f"{func_name}:{_stable_repr(args)}:{_stable_repr(stable_kwargs)}"

        except (TypeError, ValueError, RecursionError):

            return None



    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:

        """Wrap func with a cache lookup keyed on its stable arguments."""



        @functools.wraps(func)

        def wrapper(*args: Any, **kwargs: Any) -> Any:

            """Return the cached result when available, else compute it."""

            key = _stable_key(func.__name__, args, kwargs)

            if key is not None:

                val = cache.get(key)

                if val is not MISSING:

                    return val

            result = func(*args, **kwargs)

            if key is not None:

                cache.set(key, result, ttl)

            return result



        return wrapper



    return decorator









class CommandContext:

    """Passed to every command handler — replaces *args, **kwargs boilerplate."""



    __slots__ = (

        "bot",

        "user",

        "message",

        "command",

        "args",

        "raw",

        "source",

        "conversation_id",

    )



    def __init__(

        self,

        bot,

        user,

        message: str,

        command: str,

        args: list[str],

        source: str = "chat",

        conversation_id: str | None = None,

    ):

        """Store the command invocation context and its routing source."""

        self.bot = bot

        self.user = user

        self.message = message

        self.command = command

        self.args = args

        self.raw = message

        self.source = source

        self.conversation_id = conversation_id



    @property

    def highrise(self):

        """Returns the highrise instance associated with the bot, or None if not set."""

        return getattr(self.bot, "highrise", None)



    async def reply(self, text: str):

        """Smart reply: routes to DM, whisper, or chat based on command source."""

        if not self.highrise:

            return



        chunks = chunk_for_chat(str(text), limit=250)



        if self.source == "dm" and self.conversation_id:

            for index, chunk in enumerate(chunks):

                try:

                    await self.highrise.send_message(self.conversation_id, chunk)

                    if index < len(chunks) - 1:

                        await asyncio.sleep(0.3)

                except Exception:

                    pass



        elif self.source == "whisper":

            for index, chunk in enumerate(chunks):

                try:

                    await self.highrise.send_whisper(self.user.id, chunk)

                    if index < len(chunks) - 1:

                        await asyncio.sleep(0.3)

                except Exception:

                    pass



        else:

            for index, chunk in enumerate(chunks):

                try:

                    await self.highrise.chat(chunk)

                    if index < len(chunks) - 1:

                        await asyncio.sleep(0.3)

                except Exception:

                    pass





class CommandRegistry:

    """Discord.py-style command routing for Highrise bots."""



    def __init__(self, prefix: str = "!"):

        """Initialize with a command prefix and empty registries."""

        self.prefix = prefix

        self._commands: dict[str, Callable[..., Coroutine]] = {}

        self._meta: dict[str, dict[str, Any]] = {}

        self._cooldowns: dict[tuple[str, str], float] = {}

        self._permission_checker: Callable | None = None



    @property
    def has_commands(self) -> bool:
        """Return whether the registry has any registered commands."""
        return bool(self._commands)

    def set_permission_checker(self, checker: Callable):

        """Optional: async def checker(bot, user, rank) -> bool"""

        self._permission_checker = checker



    def command(

        self,

        name: str,

        *,

        aliases: list[str] | None = None,

        cooldown: float = 0.0,

        rank: str | None = None,

        hidden: bool = False,

    ):

        """Register a command handler under a name (and optional aliases)."""



        def decorator(func: Callable[..., Coroutine]):

            """Attach command metadata and register ``func``."""

            meta = {

                "name": name,

                "aliases": list(aliases or ()),

                "cooldown": float(cooldown),

                "rank": rank,

                "hidden": hidden,

                "description": (func.__doc__ or "").strip().splitlines()[0]

                if func.__doc__

                else "",

            }

            func._command_meta = meta  # type: ignore[attr-defined]



            for key in (name, *(aliases or ())):

                self._commands[key] = func

                self._meta[key] = meta



            return func



        return decorator



    def _check_cooldown(self, user_id: str, cmd_name: str) -> float:

        """Return seconds remaining on cooldown, or 0.0 when ready."""

        meta = self._meta.get(cmd_name, {})

        if meta.get("cooldown", 0) <= 0:

            return 0.0

        key = (user_id, meta["name"])

        now = time.monotonic()

        last = self._cooldowns.get(key, 0)

        remaining = (last + meta["cooldown"]) - now

        if remaining > 0:

            return remaining

        self._cooldowns[key] = now

        if len(self._cooldowns) > 10000:

            self._cleanup_cooldowns(now)

        return 0.0



    def _cleanup_cooldowns(self, now: float):

        """Remove cooldown entries older than one hour."""

        expired = [k for k, v in self._cooldowns.items() if now - v > 3600]

        for k in expired:

            del self._cooldowns[k]



    async def handle(

        self,

        bot,

        user,

        message: str,

        source: str = "chat",

        conversation_id: str | None = None,

    ) -> bool:

        """Route a chat/whisper/dm message. Returns True if a command was executed."""

        if not message.startswith(self.prefix):

            return False



        parts = message[len(self.prefix) :].split()

        if not parts:

            return False



        cmd_name = parts[0].lower()

        if cmd_name not in self._commands:

            return False



        meta = self._meta[cmd_name]

        func = self._commands[cmd_name]



        async def _send_response(text: str):

            """Send a response routed by source (dm/whisper/chat)."""

            if not text:

                return



            hr = getattr(bot, "highrise", None)

            if not hr:

                return



            chunks = chunk_for_chat(str(text), limit=250)



            if source == "dm" and conversation_id:

                for index, chunk in enumerate(chunks):

                    try:

                        await hr.send_message(conversation_id, chunk)

                        if index < len(chunks) - 1:

                            await asyncio.sleep(0.3)

                    except Exception:

                        pass



            elif source == "whisper":

                for index, chunk in enumerate(chunks):

                    try:

                        await hr.send_whisper(user.id, chunk)

                        if index < len(chunks) - 1:

                            await asyncio.sleep(0.3)

                    except Exception:

                        pass



            else:

                for index, chunk in enumerate(chunks):

                    try:

                        await hr.chat(chunk)

                        if index < len(chunks) - 1:

                            await asyncio.sleep(0.3)

                    except Exception:

                        pass



        if meta.get("rank") and self._permission_checker:

            allowed = await self._permission_checker(bot, user, meta["rank"])

            if not allowed:

                await _send_response(

                    f"⛔ You don't have permission for {self.prefix}{cmd_name}"

                )

                return True



        remaining = self._check_cooldown(user.id, cmd_name)

        if remaining > 0:

            await _send_response(

                f"⏳ Wait {remaining:.1f}s before using {self.prefix}{cmd_name}"

            )

            return True



        ctx = CommandContext(

            bot,

            user,

            message,

            cmd_name,

            parts[1:],

            source=source,

            conversation_id=conversation_id,

        )



        try:

            result = await func(ctx)



            if isinstance(result, str) and result.strip():

                await _send_response(result)



        except Exception as e:

            logging.getLogger("highrise_fast.commands").error(

                "Command %s%s crashed: %r", self.prefix, cmd_name, e, exc_info=e

            )

            await _send_response(

                f"❌ Internal error in {self.prefix}{cmd_name}: {type(e).__name__}"

            )



        return True



    def get_help(self) -> list[str]:

        """Returns command list for help — excludes hidden commands."""

        seen = set()

        lines = []



        for meta in self._meta.values():

            name = meta.get("name", "")

            if meta["hidden"] or not name or name in seen:

                continue



            seen.add(name)



            desc = meta.get("description", "")

            line = f"{self.prefix}{name}"



            aliases = [alias for alias in (meta.get("aliases") or []) if alias != name]

            if aliases:

                line += f" (or {self.prefix}{aliases[0]})"



            if desc:

                line += f" — {desc}"



            lines.append(line)



        return lines





commands = CommandRegistry()





class RoomTracker:
    """Maintains real-time user positions locally via spatial hashing."""

    def __init__(self, cell_size: float = 4.0):
        if not math.isfinite(cell_size) or cell_size <= 0:
            raise ValueError("cell_size must be finite and positive")
        self.cell_size = cell_size
        self._grid: dict[tuple[int, int], set[str]] = defaultdict(set)
        self._cells: dict[str, tuple[int, int]] = {}
        self._positions: dict[str, tuple[float, float, float]] = {}
        self._users: dict[str, str] = {}
        self._anchors: dict[str, tuple[str, int]] = {}

    def replace_roster(self, rows) -> None:
        """Replace the local roster with a complete room snapshot."""
        snapshot = RoomTracker(self.cell_size)
        for user, position in rows:
            snapshot.add(user, position)
        self._grid = snapshot._grid
        self._cells = snapshot._cells
        self._positions = snapshot._positions
        self._users = snapshot._users
        self._anchors = snapshot._anchors

    def _cell(self, x: float, z: float) -> tuple[int, int]:
        return (int(x // self.cell_size), int(z // self.cell_size))

    def add(self, user, position=None) -> None:
        """Track a user, including joins without a position."""
        self._users[user.id] = user.username
        if position:
            self.move(user.id, position)

    def remove(self, user_id: str) -> None:
        """Remove a user's name, anchor, and floor position."""
        self._users.pop(user_id, None)
        self._anchors.pop(user_id, None)
        self.remove_position(user_id)

    def move(self, user_id: str, destination) -> None:
        """Update a user's floor position or anchor."""
        if destination is None:
            return
        if hasattr(destination, "entity_id"):
            self._anchors[user_id] = (destination.entity_id, destination.anchor_ix)
            self.remove_position(user_id)
        elif hasattr(destination, "x"):
            x, y, z = destination.x, destination.y, destination.z
            cell = self._cell(x, z)
            if self._cells.get(user_id) != cell:
                self.remove_position(user_id)
                self._cells[user_id] = cell
                self._grid[cell].add(user_id)
            self._anchors.pop(user_id, None)
            self._positions[user_id] = (x, y, z)

    def remove_position(self, user_id: str) -> None:
        """Drop a floor position and clean up its grid cell."""
        self._positions.pop(user_id, None)
        cell = self._cells.pop(user_id, None)
        if cell is not None:
            users = self._grid[cell]
            users.discard(user_id)
            if not users:
                del self._grid[cell]

    def get_position(self, user_id: str) -> tuple[float, float, float] | None:
        """Return the user's floor coordinates, if known."""
        return self._positions.get(user_id)

    def get_anchor(self, user_id: str) -> tuple[str, int] | None:
        """Return the user's (entity ID, anchor index), if seated at an anchor."""
        return self._anchors.get(user_id)

    def get_username(self, user_id: str) -> str | None:
        """Return a user's locally tracked username."""
        return self._users.get(user_id)

    def get_nearby(self, x: float, z: float, radius: float) -> list[str]:
        """Return floor-positioned user IDs within radius on the XZ plane."""
        if radius < 0:
            return []
        if not math.isfinite(radius):
            raise ValueError("radius must be finite")

        grid = self._grid
        r_cells = math.ceil(radius / self.cell_size)
        cx, cz = self._cell(x, z)
        low_x, high_x = cx - r_cells, cx + r_cells
        low_z, high_z = cz - r_cells, cz + r_cells

        if (2 * r_cells + 1) ** 2 > len(grid):
            candidates = (
                grid[cell] for cell in sorted(grid)
                if low_x <= cell[0] <= high_x and low_z <= cell[1] <= high_z
            )
        else:
            candidates = (
                grid.get((cell_x, cell_z), ())
                for cell_x in range(low_x, high_x + 1)
                for cell_z in range(low_z, high_z + 1)
            )
        positions = self._positions
        nearby = []
        for users in candidates:
            for uid in users:
                ux, _, uz = positions[uid]
                if math.hypot(ux - x, uz - z) <= radius:
                    nearby.append(uid)
        return nearby

    def find_empty_spot(
        self, center_x: float, center_z: float, radius: float, min_spacing: float = 1.5
    ) -> tuple[float, float] | None:
        """Find an unoccupied spot near a center, or None after 20 tries."""
        import random

        for _ in range(20):
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(0, radius)
            x = center_x + distance * math.cos(angle)
            z = center_z + distance * math.sin(angle)
            if not self.get_nearby(x, z, min_spacing):
                return x, z
        return None

    @property
    def user_count(self) -> int:
        """Return the number of tracked users."""
        return len(self._users)

    @property
    def usernames(self) -> dict[str, str]:
        """Return a copy of the user ID to username map."""
        return dict(self._users)


class _TokenBucket:

    """Token-bucket rate limiter."""



    def __init__(self, rate: float, capacity: float = 1.0):

        """Create a bucket refilling at `rate` tokens/second."""

        self.rate = rate

        self.capacity = capacity

        self.tokens = capacity

        self.last_refill = time.monotonic()

        self._lock = asyncio.Lock()



    async def acquire(self):

        """Consume one token, waiting for a refill when the bucket is empty."""

        async with self._lock:

            now = time.monotonic()

            elapsed = now - self.last_refill

            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

            self.last_refill = now

            if self.tokens < 1.0:

                wait = (1.0 - self.tokens) / self.rate

                await asyncio.sleep(wait)

                self.tokens = 0.0

            else:

                self.tokens -= 1.0





class ThrottledActions:

    """Wraps Highrise's chat/whisper/teleport with a bounded queue + token buckets."""



    def __init__(

        self,

        bot,

        chat_rate: float = 8.0,

        teleport_rate: float = 10.0,

        *,

        queue_size: int = 1024,

    ):

        """Create the action manager with per-channel rate limits."""

        self.bot = bot

        self._chat_bucket = _TokenBucket(chat_rate, chat_rate)

        self._teleport_bucket = _TokenBucket(teleport_rate, teleport_rate)

        self._action_queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)

        self._worker_task: asyncio.Task | None = None

        self.dropped_actions = 0



    def start(self) -> None:

        """Start the worker task; drops stale actions from a previous connection."""

        if self._worker_task is not None and not self._worker_task.done():

            return



        try:

            asyncio.get_running_loop()

        except RuntimeError:

            logger.debug(

                "ThrottledActions.start() called outside a running event loop; worker not started"

            )

            return



        self._drain_queue()



        self._worker_task = asyncio.create_task(

            self._worker(),

            name="highrise_fast.throttled_actions",

        )



    def _drain_queue(self) -> None:

        """Drains the action queue until it is empty."""

        while True:

            try:

                self._action_queue.get_nowait()

            except asyncio.QueueEmpty:

                return

            else:

                self._action_queue.task_done()



    def _enqueue(self, item: tuple[str, tuple]) -> None:

        """Enqueue an action; drops (and counts) it when the queue is full."""

        try:

            self._action_queue.put_nowait(item)

        except asyncio.QueueFull:

            self.dropped_actions += 1

            logger.warning(

                "ThrottledActions queue full; dropping action: %s",

                item[0],

            )



    async def _worker(self) -> None:

        """Consume queued actions, applying per-channel rate limits.



        The token bucket handles pacing — this loop never needs to sleep

        between items. ``chat``/``whisper`` share ``_chat_bucket`` and

        ``teleport`` uses ``_teleport_bucket``. Failures are logged at

        debug level so a mid-flight bot disconnect doesn't spam the log.

        """

        while True:

            action_type, args = await self._action_queue.get()

            try:

                if action_type == "chat":

                    await self._chat_bucket.acquire()

                    hr = getattr(self.bot, "highrise", None)

                    if hr is not None:

                        await hr.chat(*args)



                elif action_type == "whisper":

                    await self._chat_bucket.acquire()

                    hr = getattr(self.bot, "highrise", None)

                    if hr is not None:

                        await hr.send_whisper(*args)



                elif action_type == "teleport":

                    await self._teleport_bucket.acquire()

                    hr = getattr(self.bot, "highrise", None)

                    if hr is not None:

                        await hr.teleport(*args)



            except asyncio.CancelledError:

                raise

            except Exception:

                logger.debug(

                    "Throttled action %r failed (bot disconnect?)",

                    action_type,

                    exc_info=True,

                )

            finally:

                self._action_queue.task_done()



    async def chat(self, message: str):

        """Enqueue a chat message for processing."""

        self._enqueue(("chat", (message,)))



    async def whisper(self, user_id: str, message: str):

        """Enqueue a whisper message for the specified user."""

        self._enqueue(("whisper", (user_id, message)))



    async def teleport(self, user_id: str, dest):

        """Enqueue a teleport action for the specified user."""

        self._enqueue(("teleport", (user_id, dest)))



    async def stop(self):

        """Stop the worker task and drain the queue."""

        if self._worker_task is not None:

            self._worker_task.cancel()



            try:

                await self._worker_task

            except asyncio.CancelledError:

                pass



            self._worker_task = None



        self._drain_queue()





def chunk_for_chat(text: str, limit: int = 250, prefix: str = "") -> list[str]:

    """Splits text into Highrise-safe chunks without breaking words.



    Every returned chunk fits within `limit` characters including the

    prefix. Short texts that fit with the prefix are returned as a

    single chunk without the prefix (matching the original behavior

    for prefix-less calls).

    """

    if len(text) + len(prefix) <= limit:

        return [text] if not prefix else [prefix + text]



    effective_limit = limit - len(prefix)

    if effective_limit <= 0:

        return [text]



    chunks = []

    lines = text.split("\n")

    current = prefix



    for line in lines:

        while len(line) > effective_limit:

            space_idx = line.rfind(" ", 0, effective_limit)

            if space_idx <= 0:

                space_idx = effective_limit

            chunks.append(prefix + line[:space_idx])

            line = line[space_idx:].lstrip()



        test = current + ("\n" if current != prefix else "") + line

        if len(test) > limit:

            if current.strip():

                chunks.append(current)

            current = prefix + line

        else:

            current = test



    if current.strip():

        chunks.append(current)

    if not chunks:

        step = max(1, effective_limit)

        chunks = [text[i : i + step] for i in range(0, len(text), step)]

    return chunks





async def send_long_message(

    highrise,

    text: str,

    *,

    whisper_to: str | None = None,

    delay: float = 0.6,

    limit: int = 250,

):

    """Sends long text as multiple messages with spacing.



    The "(n/m)" footer is reserved up front so every emitted message,

    footer included, stays within `limit` characters. The 10-char

    reservation covers counters up to 999 chunks.

    """

    probe = chunk_for_chat(text, limit=limit)

    # Re-chunk with 10 chars reserved for the "(n/m)" footer.
    chunks = (
        chunk_for_chat(text, limit=limit - 10)
        if len(probe) > 1 and limit > 20
        else probe
    )



    total = len(chunks)

    for i, chunk in enumerate(chunks):

        footer = f"\n({i+1}/{total})" if total > 1 else ""

        msg = chunk + footer

        if whisper_to:

            await highrise.send_whisper(whisper_to, msg)

        else:

            await highrise.chat(msg)

        if i < len(chunks) - 1:

            await asyncio.sleep(delay)





class DebouncedSaver:
    """Coalesce writes within a delay window and serialize writes in progress."""

    def __init__(self, save_func: Callable, delay: float = 3.0):
        self._save_func = save_func
        self._delay = delay
        self._task: asyncio.Task | None = None
        self._pending: Any = None
        self._dirty = False
        self._lock = asyncio.Lock()
        self._flush_requested = asyncio.Event()

    def trigger(self, data: Any) -> None:
        """Schedule the newest data for saving."""
        self._pending = data
        self._dirty = True
        if self._task is None or self._task.done():
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return
            self._task = loop.create_task(self._worker())

    async def _worker(self) -> None:
        while self._dirty:
            if self._delay > 0 and not self._flush_requested.is_set():
                try:
                    await asyncio.wait_for(self._flush_requested.wait(), self._delay)
                except asyncio.TimeoutError:
                    pass
            if not await self._do_save():
                return

    async def _do_save(self) -> bool:
        async with self._lock:
            if not self._dirty:
                return True
            data = self._pending
            self._dirty = False
            try:
                result = self._save_func(data)
                if inspect.isawaitable(result):
                    await result
            except BaseException as exc:
                # A trigger may have supplied a newer state while saving.
                if not self._dirty:
                    self._pending = data
                    self._dirty = True
                if not isinstance(exc, Exception):
                    raise
                logger.exception("Debounced save failed")
                return False
            return True

    async def flush(self) -> None:
        """Save the latest pending state immediately, after any active write."""
        await self._do_save()

    async def stop(self) -> None:
        """Finish the current write and flush pending state."""
        self._flush_requested.set()
        try:
            if self._task is not None:
                await asyncio.shield(self._task)
            await self.flush()
        finally:
            self._flush_requested.clear()


class PromptManager:
    """Send a private prompt and consume the matching user's next reply."""

    def __init__(self):
        self._waiters: dict[str, asyncio.Future[str | None]] = {}

    async def ask(self, bot, user, question: str, timeout: float = 15.0) -> str | None:
        """Wait for a reply, returning None on timeout or replacement."""
        user_id = user.id
        connection = getattr(bot, "highrise", None)
        future = asyncio.get_running_loop().create_future()
        previous = self._waiters.get(user_id)
        if previous is not None and not previous.done():
            previous.set_result(None)
        self._waiters[user_id] = future
        try:
            if connection is not None:
                await connection.send_whisper(user_id, question)
            try:
                return await asyncio.wait_for(future, timeout)
            except asyncio.TimeoutError:
                if (
                    connection is not None
                    and getattr(bot, "highrise", None) is connection
                    and self._waiters.get(user_id) is future
                ):
                    await connection.send_whisper(user_id, "⏰ Timed out.")
                return None
        finally:
            if self._waiters.get(user_id) is future:
                self._waiters.pop(user_id, None)
            if not future.done():
                future.cancel()

    def resolve(self, user_id: str, message: str) -> bool:
        """Resolve the current prompt for this user."""
        future = self._waiters.get(user_id)
        if future is not None and not future.done():
            future.set_result(message.strip())
            return True
        return False

    def cancel(self, user_id: str) -> bool:
        """Cancel the current prompt for this user."""
        future = self._waiters.pop(user_id, None)
        if future is not None and not future.done():
            future.cancel()
            return True
        return False

    def cancel_all(self) -> None:
        """Cancel prompts when the room connection ends."""
        waiters, self._waiters = self._waiters, {}
        for future in waiters.values():
            if not future.done():
                future.cancel()

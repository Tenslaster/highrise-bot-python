"""Extra utilities for highrise_fast: caching, metrics, task management, command routing, room tracking, throttled actions, and chat helpers."""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import math
import random
import time
import types
from collections import OrderedDict, defaultdict
from collections.abc import Awaitable, Callable, Coroutine, Hashable
from dataclasses import dataclass
from typing import Any

from .bot_state import AtomicJsonStore, PresenceTimer, RoleStore, RoomOccupancyTrigger
from .events import Awaiter

try:

    import aiohttp

except ImportError:

    aiohttp = None



__all__ = [

    "AtomicJsonStore",
    "Awaiter",
    "ChangeDetector",
    "PeriodicJob",
    "PresenceTimer",
    "RoleStore",
    "RetryPolicy",
    "RoomOccupancyTrigger",
    "MISSING",

    "CachedWebAPI",

    "MetricTracker",

    "Metrics",

    "TTLCache",

    "TaskManager",

    "cached",
    "async_cached",

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





_ATOMIC_KEY_TYPES = {str, bytes, int, bool, type(None)}


def _freeze_key(value: Any) -> Hashable:
    """Build a typed key that preserves the shape of nested arguments."""
    kind = type(value)
    if kind in _ATOMIC_KEY_TYPES:
        return kind, value
    if kind is dict:
        return dict, frozenset((_freeze_key(key), _freeze_key(item)) for key, item in value.items())
    if kind in (tuple, list):
        return kind, tuple(map(_freeze_key, value))
    if kind in (set, frozenset):
        return kind, frozenset(map(_freeze_key, value))
    rendered = repr(value)
    if " object at 0x" in rendered:
        raise TypeError("Identity-based cache key")
    return kind, rendered


def _call_key(args: tuple, kwargs: dict) -> Hashable | None:
    try:
        return tuple(map(_freeze_key, args)), _freeze_key(kwargs) if kwargs else ()
    except Exception:
        return None


class TTLCache:
    """Bounded least-recently-used cache with monotonic expiry."""

    __slots__ = ("_maxsize", "_store")

    def __init__(self, maxsize: int = 1024) -> None:
        if maxsize < 0:
            raise ValueError("maxsize must be nonnegative")
        self._store: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._maxsize = maxsize

    def __len__(self) -> int:
        return len(self._store)

    def get(self, key: Hashable) -> Any:
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

    def set(self, key: Hashable, value: Any, ttl: float = 60) -> None:
        """Store a value with a TTL, evicting the LRU entry when full."""
        if self._maxsize == 0 or ttl <= 0:
            self.invalidate(key)
            return
        self._store[key] = (time.monotonic() + ttl, value)
        self._store.move_to_end(key)
        if len(self._store) > self._maxsize:
            self._store.popitem(last=False)

    def invalidate(self, key: Hashable) -> None:
        """Drop a single key."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Drop everything."""
        self._store.clear()


class _AsyncReadCache:
    """Share reads within an event loop and retain successful results."""

    def __init__(self, ttl: float, maxsize: int):
        self.ttl = ttl
        self.cache = TTLCache(maxsize)
        self.pending: dict[tuple[asyncio.AbstractEventLoop, Hashable], asyncio.Task] = {}
        self.tasks: set[asyncio.Task] = set()

    async def read(self, key: Hashable | None, fetch: Callable[[], Coroutine]) -> Any:
        if key is None or self.ttl <= 0:
            return await fetch()
        cached_value = self.cache.get(key)
        if cached_value is not MISSING:
            return cached_value
        loop_key = asyncio.get_running_loop(), key
        task = self.pending.get(loop_key)
        if task is None:
            task = asyncio.create_task(fetch())
            self.pending[loop_key] = task
            self.tasks.add(task)
            task.add_done_callback(functools.partial(self._done, loop_key))
        return await asyncio.shield(task)

    def _done(self, loop_key: tuple, task: asyncio.Task) -> None:
        self.tasks.discard(task)
        successful = not task.cancelled() and task.exception() is None
        if self.pending.get(loop_key) is task:
            self.pending.pop(loop_key)
            if successful:
                self.cache.set(loop_key[1], task.result(), self.ttl)

    def clear(self) -> None:
        self.cache.clear()
        self.pending.clear()

    async def close(self) -> None:
        self.clear()
        tasks = tuple(self.tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


class CachedWebAPI:
    """Raw JSON Web API client with pooling and coalesced GETs."""

    def __init__(
        self,
        base_url: str = "https://webapi.highrise.game",
        timeout: Any = None,
        cache_ttl: int = 60,
        *,
        cache_size: int = 1024,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self._reads = _AsyncReadCache(cache_ttl, cache_size)
        self._session: Any = None

    async def _get_session(self) -> Any:
        if self._session is None or self._session.closed:
            if aiohttp is None:
                raise RuntimeError("Missing dependency: pip install aiohttp")
            from . import USER_AGENT

            timeout = self.timeout
            if isinstance(timeout, (int, float)):
                timeout = aiohttp.ClientTimeout(total=timeout)
            self._session = aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": USER_AGENT})
        return self._session

    async def _request(self, method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        session = await self._get_session()
        async with session.request(method, f"{self.base_url}{endpoint}", **kwargs) as response:
            if response.status >= 400:
                body = await response.text()
                raise RuntimeError(f"WebAPI error {response.status}: {body}")
            return await response.json()

    async def get(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """GET raw JSON, sharing simultaneous requests with equivalent arguments."""
        self._reads.ttl = self.cache_ttl
        key = _call_key((endpoint,), kwargs) if kwargs else endpoint
        return await self._reads.read(key, lambda: self._request("GET", endpoint, **kwargs))

    def invalidate_cache(self) -> None:
        """Discard cached responses and detach outstanding reads."""
        self._reads.clear()

    async def close(self) -> None:
        """Cancel outstanding shared reads and close the session."""
        session, self._session = self._session, None
        try:
            await self._reads.close()
        finally:
            if session is not None and not session.closed:
                await session.close()

    async def __aenter__(self) -> CachedWebAPI:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: types.TracebackType | None,
    ) -> None:
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


class PeriodicJob:
    """Run a periodic coroutine without overlap, skipping missed ticks."""

    def __init__(
        self, interval: float, callback: Callable[[], Awaitable[Any]], *,
        immediate: bool = True, continue_on_error: bool = True,
    ) -> None:
        if not math.isfinite(interval) or interval <= 0:
            raise ValueError("interval must be finite and positive")
        self.interval = interval
        self.callback = callback
        self.immediate = immediate
        self.continue_on_error = continue_on_error
        self._ready = asyncio.Event()
        self._ready.set()
        self._manager: TaskManager | None = None
        self._task: asyncio.Task | None = None
        self.runs = 0
        self.failures = 0
        self.missed_ticks = 0

    def start(self, manager: TaskManager | None = None) -> asyncio.Task:
        """Start the job once, optionally tying its lifetime to a bot or room."""
        if self._task is not None and not self._task.done():
            return self._task
        owner = manager if manager is not None else TaskManager()
        self._task = owner.replace(self, self._run)
        self._manager = owner
        return self._task

    def pause(self) -> None:
        """Pause future ticks while an active callback finishes."""
        self._ready.clear()

    def resume(self) -> None:
        """Resume on the schedule, skipping ticks that elapsed while paused."""
        self._ready.set()

    async def stop(self) -> None:
        """Cancel the job and wait for cleanup."""
        if self._manager is not None:
            await self._manager.cancel_key(self)

    async def _run(self) -> None:
        now = asyncio.get_running_loop().time
        deadline = now() + (0.0 if self.immediate else self.interval)
        while True:
            await asyncio.sleep(max(0.0, deadline - now()))
            await self._ready.wait()
            started = now()
            skipped = max(0, math.floor((started - deadline) / self.interval))
            self.missed_ticks += skipped
            deadline += (skipped + 1) * self.interval
            self.runs += 1
            try:
                await self.callback()
            except Exception:
                self.failures += 1
                if not self.continue_on_error:
                    raise
                logger.exception("Periodic job failed")

            # Skip all ticks that elapsed during the callback.
            finished = now()
            if deadline < finished:
                skipped = math.ceil((finished - deadline) / self.interval)
                self.missed_ticks += skipped
                deadline += skipped * self.interval


class ChangeDetector:
    """Report whether a value's comparison key has changed."""

    def __init__(self, *, key: Callable[[Any], Any] | None = None, emit_initial: bool = True):
        self._key = key
        self._emit_initial = emit_initial
        self._last = MISSING

    def update(self, value: Any) -> bool:
        current = value if self._key is None else self._key(value)
        prior, self._last = self._last, current
        return self._emit_initial if prior is MISSING else current != prior

    def reset(self) -> None:
        self._last = MISSING


class RetryPolicy:
    """Bounded exponential backoff for operations that are safe to repeat."""

    def __init__(
        self, *, attempts: int = 3, delay: float = 0.25,
        max_delay: float = 5.0, jitter: float = 0.2,
    ) -> None:
        if not isinstance(attempts, int) or attempts < 1:
            raise ValueError("attempts must be a positive integer")
        if not all(math.isfinite(value) and value >= 0 for value in (delay, max_delay)):
            raise ValueError("retry delays must be finite and nonnegative")
        if not 0 <= jitter <= 1:
            raise ValueError("jitter must be between 0 and 1")
        self.attempts = attempts
        self.delay = delay
        self.max_delay = max_delay
        self.jitter = jitter

    async def run(
        self, operation: Callable[[], Awaitable[Any]], *,
        retry_on: tuple[type[Exception], ...] = (OSError, asyncio.TimeoutError),
    ) -> Any:
        """Retry only the supplied exception types and propagate the final error."""
        delay = min(self.delay, self.max_delay)
        for attempt in range(1, self.attempts + 1):
            try:
                return await operation()
            except retry_on:
                if attempt == self.attempts:
                    raise
                spread = delay * self.jitter
                await asyncio.sleep(min(self.max_delay, random.uniform(delay - spread, delay + spread)))
                delay = min(self.max_delay, delay * 2)


def async_cached(ttl: float = 60, *, maxsize: int = 1024) -> Callable:
    """Cache async results and share concurrent calls with the same arguments."""

    def decorator(func: Callable[..., Coroutine]) -> Callable[..., Awaitable[Any]]:
        reads = _AsyncReadCache(ttl, maxsize)

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = _call_key(args, kwargs)
            return await reads.read(key, lambda: func(*args, **kwargs))

        wrapper.cache_clear = reads.clear
        return wrapper

    return decorator


def cached(ttl: float = 60, *, maxsize: int = 1024) -> Callable:
    """Cache function results with a bounded lifetime and cache_clear()."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if inspect.iscoroutinefunction(func):
            return async_cached(ttl, maxsize=maxsize)(func)
        cache = TTLCache(maxsize)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = _call_key(args, kwargs)
            if key is None or ttl <= 0:
                return func(*args, **kwargs)
            value = cache.get(key)
            if value is MISSING:
                value = func(*args, **kwargs)
                cache.set(key, value, ttl)
            return value

        wrapper.cache_clear = cache.clear
        return wrapper

    return decorator


class CommandContext:
    """Command arguments, caller information, and source-aware replies."""

    __slots__ = (
        "bot", "user", "message", "command", "args", "raw", "source", "conversation_id",
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
        self.bot = bot
        self.user = user
        self.message = self.raw = message
        self.command = command
        self.args = args
        self.source = source
        self.conversation_id = conversation_id

    @property
    def highrise(self):
        """Return the bot's current room client."""
        return getattr(self.bot, "highrise", None)

    async def _reply(self, text: str, source: str) -> None:
        hr = self.highrise
        if hr is None:
            return
        if source == "dm" and self.conversation_id:
            send = functools.partial(hr.send_message, self.conversation_id)
        elif source == "whisper":
            send = functools.partial(hr.send_whisper, self.user.id)
        else:
            send = hr.chat
        await _send_chunks(send, chunk_for_chat(str(text)), 0.3, ignore_errors=True)

    async def reply(self, text: str) -> None:
        """Reply via DM, whisper, or room chat according to the command source."""
        await self._reply(text, self.source)

    async def reply_private(self, text: str) -> None:
        """Reply privately to a command invoked from any source."""
        await self._reply(text, "dm" if self.source == "dm" and self.conversation_id else "whisper")


class CommandRegistry:
    """Register commands, aliases, permissions, and bounded per-user cooldowns."""

    def __init__(self, prefix: str = "!", *, cooldown_maxsize: int = 10_000):
        self.prefix = prefix
        self._commands: dict[str, Callable[..., Coroutine]] = {}
        self._meta: dict[str, dict[str, Any]] = {}
        self._cooldowns = TTLCache(cooldown_maxsize)
        self._permission_checker: Callable | None = None

    @property
    def has_commands(self) -> bool:
        return bool(self._commands)

    def handles_source(self, source: str) -> bool:
        """Return whether a registered command accepts this message source."""
        return any(meta["sources"] is None or source in meta["sources"] for meta in self._meta.values())

    def set_permission_checker(self, checker: Callable) -> None:
        """Set a synchronous or async checker accepting (bot, user, rank)."""
        self._permission_checker = checker

    def command(
        self,
        name: str,
        *,
        aliases: list[str] | None = None,
        cooldown: float = 0.0,
        rank: str | None = None,
        hidden: bool = False,
        sources: set[str] | None = None,
    ):
        """Register commands and aliases case-insensitively."""
        names = [part.strip().lower() for part in [name, *(aliases or ())]]
        if any(not part or len(part.split()) != 1 for part in names):
            raise ValueError("Command names and aliases must be single words")
        allowed = None if sources is None else frozenset(sources)
        if allowed is not None and not allowed <= {"chat", "whisper", "dm"}:
            raise ValueError("sources must contain chat, whisper, or dm")
        cooldown = float(cooldown)
        if not math.isfinite(cooldown) or cooldown < 0:
            raise ValueError("cooldown must be finite and nonnegative")

        def decorator(func: Callable[..., Coroutine]):
            previous = self._meta.get(names[0])
            if previous is not None and previous["name"] == names[0]:
                self.remove_command(names[0])
            meta = {
                "name": names[0],
                "aliases": names[1:],
                "cooldown": cooldown,
                "rank": rank,
                "hidden": hidden,
                "sources": allowed,
                "description": (func.__doc__ or "").strip().partition("\n")[0],
            }
            func._command_meta = meta  # type: ignore[attr-defined]
            for key in names:
                self._commands[key] = func
                self._meta[key] = meta
            return func

        return decorator

    def get_command(self, name: str) -> Callable | None:
        """Look up a command or alias by name."""
        return self._commands.get(name.strip().lower())

    def remove_command(self, name: str) -> bool:
        """Remove a command and the aliases still pointing to it."""
        meta = self._meta.get(name.strip().lower())
        if meta is None:
            return False
        for key in (meta["name"], *meta["aliases"]):
            if self._meta.get(key) is meta:
                del self._commands[key]
                del self._meta[key]
        return True

    def _check_cooldown(self, user_id: str, cmd_name: str) -> float:
        meta = self._meta[cmd_name]
        seconds = meta["cooldown"]
        if not seconds:
            return 0.0
        key = (user_id, meta["name"])
        now = time.monotonic()
        until = self._cooldowns.get(key)
        if until is not MISSING and until > now:
            return until - now
        self._cooldowns.set(key, now + seconds, seconds)
        return 0.0

    async def handle(
        self,
        bot,
        user,
        message: str,
        source: str = "chat",
        conversation_id: str | None = None,
    ) -> bool:
        """Handle a registered command and report whether it consumed the message."""
        if not message.startswith(self.prefix):
            return False
        parts = message[len(self.prefix):].split(None, 1)
        if not parts:
            return False
        name = parts[0].lower()
        func = self._commands.get(name)
        if func is None:
            return False
        context = CommandContext(
            bot, user, message, name, parts[1].split() if len(parts) == 2 else [],
            source=source, conversation_id=conversation_id,
        )
        meta = self._meta[name]
        allowed_sources = meta["sources"]
        if allowed_sources is not None and source not in allowed_sources:
            await context.reply_private(f"⛔ {self.prefix}{name} is unavailable from {source}.")
            return True
        if meta["rank"] and self._permission_checker:
            allowed = self._permission_checker(bot, user, meta["rank"])
            if inspect.isawaitable(allowed):
                allowed = await allowed
            if not allowed:
                await context.reply(f"⛔ You don't have permission for {self.prefix}{name}")
                return True

        remaining = self._check_cooldown(user.id, name)
        if remaining > 0:
            await context.reply(f"⏳ Wait {remaining:.1f}s before using {self.prefix}{name}")
            return True
        try:
            result = await func(context)
            if isinstance(result, str) and result.strip():
                await context.reply(result)
        except Exception as error:
            logging.getLogger("highrise_fast.commands").exception(
                "Command %s%s crashed", self.prefix, name,
            )
            await context.reply(f"❌ Internal error in {self.prefix}{name}: {type(error).__name__}")
        return True

    def get_help(self) -> list[str]:
        """Return visible commands with their first active alias and description."""
        seen = set()
        lines = []
        for meta in self._meta.values():
            name = meta["name"]
            if meta["hidden"] or name in seen:
                continue
            seen.add(name)
            line = f"{self.prefix}{name}"
            for alias in meta["aliases"]:
                if alias != name and self._meta.get(alias) is meta:
                    line += f" (or {self.prefix}{alias})"
                    break
            if meta["description"]:
                line += f" — {meta['description']}"
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
        self._roster_revision = 0
        self._roster_waiters: set[asyncio.Future[None]] = set()

    def replace_roster(self, rows) -> None:
        """Replace the local roster with a complete room snapshot."""
        snapshot = RoomTracker(self.cell_size)
        for user, position in rows:
            snapshot._users[user.id] = user.username
            if position:
                snapshot.move(user.id, position)
        changed = self._users != snapshot._users
        self._grid = snapshot._grid
        self._cells = snapshot._cells
        self._positions = snapshot._positions
        self._users = snapshot._users
        self._anchors = snapshot._anchors
        if changed:
            self._roster_changed()

    @property
    def roster_revision(self) -> int:
        """Revision of room membership and usernames."""
        return self._roster_revision

    def _roster_changed(self) -> None:
        self._roster_revision += 1
        for waiter in self._roster_waiters:
            if not waiter.done():
                waiter.set_result(None)

    async def wait_for_roster_change(self, since: int, timeout: float | None = None) -> int:
        """Return the latest revision once membership or a username changes."""
        if since != self._roster_revision:
            return self._roster_revision
        waiter = asyncio.get_running_loop().create_future()
        self._roster_waiters.add(waiter)
        try:
            await asyncio.wait_for(waiter, timeout)
            return self._roster_revision
        finally:
            self._roster_waiters.discard(waiter)

    def _cell(self, x: float, z: float) -> tuple[int, int]:
        return (int(x // self.cell_size), int(z // self.cell_size))

    def add(self, user, position=None) -> None:
        """Track a user, including joins without a position."""
        if position:
            self.move(user.id, position)
        if self._users.get(user.id) != user.username:
            self._users[user.id] = user.username
            self._roster_changed()

    def remove(self, user_id: str) -> None:
        """Remove a user's name, anchor, and floor position."""
        known_user = self._users.pop(user_id, MISSING)
        self._anchors.pop(user_id, None)
        self.remove_position(user_id)
        if known_user is not MISSING:
            self._roster_changed()

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

    def get_user_id(self, username: str) -> str | None:
        """Find a tracked user's ID by case-insensitive exact username."""
        target = username.strip().casefold()
        return next((uid for uid, name in self._users.items() if name.casefold() == target), None)

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
    def __init__(self, rate: float):
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError("Action rates must be finite and positive")
        self.rate = rate
        self.capacity = max(1.0, rate)
        self.tokens = self.capacity
        self.last_refill = time.monotonic()

    async def acquire(self) -> None:
        while True:
            now = time.monotonic()
            self.tokens = min(self.capacity, self.tokens + (now - self.last_refill) * self.rate)
            self.last_refill = now
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return
            await asyncio.sleep((1.0 - self.tokens) / self.rate)


@dataclass(slots=True)
class _QueuedAction:
    method: str
    args: tuple
    key: Hashable | None
    deadline: float | None
    cancelled: bool = False

    def expired(self) -> bool:
        return self.deadline is not None and time.monotonic() >= self.deadline


class ThrottledActions:
    """Queue room actions on independent chat, movement, and interaction workers."""

    def __init__(
        self,
        bot,
        chat_rate: float = 8.0,
        teleport_rate: float = 10.0,
        *,
        queue_size: int = 1024,
        interaction_rate: float = 4.0,
    ):
        self.bot = bot
        self._buckets = {
            "chat": _TokenBucket(chat_rate),
            "movement": _TokenBucket(teleport_rate),
            "interaction": _TokenBucket(interaction_rate),
        }
        self._queue_size = queue_size
        self._queues: dict[str, asyncio.Queue[_QueuedAction]] = {}
        self._waiting: dict[str, _QueuedAction] = {}
        self._workers: dict[str, asyncio.Task] = {}
        self._running = False
        self._queued = 0
        self.dropped_actions = 0
        self.sent_actions = 0
        self.failed_actions = 0

    def start(self) -> None:
        """Enable action submission for this connection."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        self._running = True

    def _enqueue(
        self, lane: str, method: str, *args, key: Hashable | None = None,
        expires_in: float | None = None,
    ) -> bool:
        if expires_in is not None and (not math.isfinite(expires_in) or expires_in < 0):
            raise ValueError("expires_in must be finite and nonnegative")
        if not self._running or (self._queue_size > 0 and self._queued >= self._queue_size):
            self.dropped_actions += 1
            return False
        queue = self._queues.get(lane)
        if queue is None:
            queue = self._queues[lane] = asyncio.Queue()
            self._workers[lane] = asyncio.create_task(
                self._worker(lane, queue, self._buckets[lane]),
                name=f"highrise-fast-actions-{lane}",
            )
        deadline = None if expires_in is None else time.monotonic() + expires_in
        queue.put_nowait(_QueuedAction(method, args, key, deadline))
        self._queued += 1
        return True

    async def _worker(
        self, lane: str, queue: asyncio.Queue[_QueuedAction], bucket: _TokenBucket,
    ) -> None:
        while True:
            action = await queue.get()
            self._queued -= 1
            try:
                if action.expired():
                    self.dropped_actions += 1
                    continue
                if action.key is not None:
                    self._waiting[lane] = action
                await bucket.acquire()
                if self._waiting.get(lane) is action:
                    del self._waiting[lane]
                if action.cancelled or action.expired():
                    bucket.tokens = min(bucket.capacity, bucket.tokens + 1)
                    if not action.cancelled:
                        self.dropped_actions += 1
                    continue
                hr = getattr(self.bot, "highrise", None)
                if hr is not None:
                    await getattr(hr, action.method)(*action.args)
                    self.sent_actions += 1
                else:
                    self.dropped_actions += 1
            except asyncio.CancelledError:
                if not action.cancelled:
                    self.dropped_actions += 1
                raise
            except Exception:
                self.failed_actions += 1
                logger.debug("Throttled action %s failed", action.method, exc_info=True)
            finally:
                if self._waiting.get(lane) is action:
                    del self._waiting[lane]
                queue.task_done()

    async def chat(self, message: str) -> None:
        """Queue a room chat message."""
        self._enqueue("chat", "chat", message)

    async def whisper(self, user_id: str, message: str) -> None:
        """Queue a private room message."""
        self._enqueue("chat", "send_whisper", user_id, message)

    async def teleport(self, user_id: str, dest) -> None:
        """Queue a teleport."""
        self._enqueue("movement", "teleport", user_id, dest)

    async def emote(
        self, emote_id: str, target_user_id: str | None = None, *,
        key: Hashable | None = None, expires_in: float | None = None,
    ) -> bool:
        """Queue an emote with an optional cancellation key and lifetime."""
        return self._enqueue(
            "interaction", "send_emote", emote_id, target_user_id, key=key, expires_in=expires_in
        )

    async def react(
        self, reaction: str, target_user_id: str, *,
        key: Hashable | None = None, expires_in: float | None = None,
    ) -> bool:
        """Queue a reaction with an optional cancellation key and lifetime."""
        return self._enqueue(
            "interaction", "react", reaction, target_user_id, key=key, expires_in=expires_in
        )

    def cancel_pending(self, key: Hashable) -> int:
        """Remove matching actions before they are sent, including rate-limit waiters."""
        if key is None:
            raise ValueError("A cancellation key is required")
        cancelled = 0
        for waiting in self._waiting.values():
            if waiting.key == key and not waiting.cancelled:
                waiting.cancelled = True
                cancelled += 1
        for queue in self._queues.values():
            # Keep unfinished counts nonzero until surviving actions are restored.
            entries = [queue.get_nowait() for _ in range(queue.qsize())]
            for action in entries:
                if action.key == key:
                    cancelled += 1
                    self._queued -= 1
                else:
                    queue.put_nowait(action)
                queue.task_done()
        self.dropped_actions += cancelled
        return cancelled

    def stats(self) -> dict[str, int]:
        """Report queue depth, completed sends, failures, and drops."""
        return {
            "queued": self._queued,
            "sent": self.sent_actions,
            "failed": self.failed_actions,
            "dropped": self.dropped_actions,
        }

    async def flush(self) -> None:
        """Wait for the current workers to process their queues."""
        await asyncio.gather(*(queue.join() for queue in self._queues.values()))

    async def stop(self) -> None:
        """Cancel workers and discard pending actions for this connection."""
        self._running = False
        workers, self._workers = self._workers, {}
        queues, self._queues = self._queues, {}
        for task in workers.values():
            task.cancel()
        for queue in queues.values():
            # Single-loop operation: these queues now have no producers.
            while not queue.empty():
                queue.get_nowait()
                queue.task_done()
                self._queued -= 1
                self.dropped_actions += 1
        if workers:
            await asyncio.gather(*workers.values(), return_exceptions=True)


def chunk_for_chat(text: str, limit: int = 250, prefix: str = "") -> list[str]:
    """Split text in order and keep each chunk within the character limit."""
    if limit < 1:
        raise ValueError("limit must be positive")
    if len(text) + len(prefix) <= limit:
        return [prefix + text]
    available = limit - len(prefix)
    if available <= 0:
        raise ValueError("prefix must leave space for text")

    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(line) > available and current:
            chunks.append(prefix + current)
            current = ""

        start = 0
        while len(line) - start > available:
            boundary = start + available
            split = line.rfind(" ", start, boundary + 1)
            if split <= start:
                split = boundary
            chunks.append(prefix + line[start:split])
            start = split
            while start < len(line) and line[start].isspace():
                start += 1

        rest = line[start:]
        if not current:
            current = rest
        elif len(current) + 1 + len(rest) <= available:
            current += "\n" + rest
        else:
            chunks.append(prefix + current)
            current = rest
    if current:
        chunks.append(prefix + current)
    return chunks or [prefix]


async def _send_chunks(
    send: Callable[[str], Awaitable[Any]],
    chunks: list[str],
    delay: float,
    *,
    ignore_errors: bool = False,
) -> None:
    for index, chunk in enumerate(chunks):
        try:
            await send(chunk)
        except Exception:
            if not ignore_errors:
                raise
            continue
        if delay > 0 and index + 1 < len(chunks):
            await asyncio.sleep(delay)


async def send_long_message(
    highrise,
    text: str,
    *,
    whisper_to: str | None = None,
    delay: float = 0.6,
    limit: int = 250,
) -> None:
    """Send long text with optional numbering and pacing."""
    chunks = chunk_for_chat(text, limit=limit)
    if len(chunks) > 1:
        digits = len(str(len(chunks)))
        # Reserve digits for both the index and total in the footer.
        while 4 + 2 * digits < limit:
            numbered = chunk_for_chat(text, limit=limit - 4 - 2 * digits)
            total = len(numbered)
            if len(str(total)) <= digits:
                chunks = [
                    f"{chunk}\n({index}/{total})" for index, chunk in enumerate(numbered, 1)
                ]
                break
            digits = len(str(total))
    send = functools.partial(highrise.send_whisper, whisper_to) if whisper_to else highrise.chat
    await _send_chunks(send, chunks, delay)


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

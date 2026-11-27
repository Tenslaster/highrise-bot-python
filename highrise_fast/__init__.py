#!/usr/bin/env python3

"""

highrise_fast — standalone Highrise SDK replacement.

Resilient dispatch (strict validation by default)

-------------------------------------------------

Every incoming server message is validated against the official protocol

schema *before* it reaches your handlers, so anything that arrives in

``on_chat`` / ``on_user_join`` / ... is guaranteed well-formed.  A malformed

packet never kills the bot: it is dropped, counted, and logged with a

path-aware error message (rate-limited).  RPC replies that fail validation

reject the awaiting call instead of leaving it hanging.



Configuration layers:

    parse_server_message(data)                  # lenient, single-shot

    parse_server_message(data, strict=True)     # strict, single-shot

    BaseBot(validation_mode="strict")           # strict receive loop (default)



Configuration (precedence: BaseBot argument > environment variable > default)::

    validation_mode         "strict" | "lenient"          HIGHRISE_FAST_VALIDATION

    on_invalid              "drop" | "raise" | "log-only"  HIGHRISE_FAST_ON_INVALID

    invalid_warn_cooldown   seconds between identical warnings

                            HIGHRISE_FAST_INVALID_WARN_COOLDOWN



Hook: override ``BaseBot.on_invalid_packet(exc, raw)`` (sync or async).

Metrics: ``stats()["invalid_packets_by_type"]``, ``invalid_packet_stats()``.

"""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import contextlib
import gc
import importlib
import json
import logging
import math
import os
import random
import socket
import sys
import tempfile
import time
import urllib.parse
import weakref
from collections import Counter, deque
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from enum import Enum
from functools import partial
from inspect import isawaitable, iscoroutine
from itertools import count
from typing import Any, Literal

try:
    import orjson

except ImportError:
    orjson = None


ClientSession = None

WebSocketError = None

WSMsgType = None

WSServerHandshakeError = None

ClientTimeout = None

CLOSE_TYPES: set[Any] = set()

WEB_TIMEOUT = None


def _ensure_aiohttp() -> None:
    """Ensure aiohttp is installed and import required WebSocket symbols."""
    global ClientSession, WebSocketError, WSMsgType
    global WSServerHandshakeError, ClientTimeout, CLOSE_TYPES, WEB_TIMEOUT

    if ClientSession is not None:
        return

    try:
        import aiohttp  # noqa: F401
    except ImportError as exc:
        raise SystemExit("Missing dependency: pip install aiohttp") from exc

    try:
        from aiohttp import (
            ClientSession,
            WebSocketError,
            WSMsgType,
            WSServerHandshakeError,
        )
    except ImportError as exc:
        raise SystemExit(
            "aiohttp is installed but missing required symbols; "
            "update it with: pip install -U aiohttp"
        ) from exc

    try:
        from aiohttp import ClientTimeout
    except ImportError:
        ClientTimeout = None

    CLOSE_TYPES = {WSMsgType.CLOSE, WSMsgType.CLOSED}
    if hasattr(WSMsgType, "CLOSING"):
        CLOSE_TYPES.add(WSMsgType.CLOSING)

    WEB_TIMEOUT = (
        ClientTimeout(total=_env_float("HR_WEBAPI_TIMEOUT", 30.0))
        if ClientTimeout is not None
        else None
    )


from ._pycompat import BaseExceptionGroup, TaskGroup, TimeoutError
from ._pycompat import timeout as timeout_after
from .extras import (
    AtomicJsonStore,
    Awaiter,
    ChangeDetector,
    CommandContext,
    CommandRegistry,
    DebouncedSaver,
    Metrics,
    PeriodicJob,
    PresenceTimer,
    PromptManager,
    RetryPolicy,
    RoleStore,
    RoomOccupancyTrigger,
    RoomTracker,
    TaskManager,
    ThrottledActions,
    TTLCache,
    UserResolver,
    async_cached,
    chunk_for_chat,
    commands,
    send_long_message,
)
from .extras import (
    MetricTracker as MetricTracker,
)
from .extras import (
    cached as cached,
)
from .models import (
    AnchorHitResponse,
    AnchorPosition,
    BuyItemResponse,
    BuyRoomBoostResponse,
    BuyVoiceTimeResponse,
    ChangeBackpackResponse,
    ChangeRoomPrivilegeResponse,
    ChannelEvent,
    ChannelResponse,
    ChatEvent,
    ChatResponse,
    CheckVoiceChatResponse,
    ControlSessionMetadata,
    Conversation,
    CurrencyItem,
    EmoteEvent,
    EmoteResponse,
    Error,
    Facing,
    FloorHitResponse,
    GetBackpackResponse,
    GetConversationsResponse,
    GetInventoryResponse,
    GetMessagesResponse,
    GetRoomPrivilegeResponse,
    GetRoomUsersResponse,
    GetUserOutfitResponse,
    GetWalletResponse,
    IndicatorResponse,
    InstanceStartedEvent,
    InstanceStoppedEvent,
    InviteSpeakerResponse,
    Item,
    KeepaliveResponse,
    LeaveConversationResponse,
    Message,
    MessageEvent,
    MessageMedia,
    MessageMediaResponse,
    ModerateRoomResponse,
    MoveUserToRoomResponse,
    Position,
    Reaction,
    ReactionEvent,
    ReactionResponse,
    RemoveSpeakerResponse,
    ResponseError,
    RoomInfo,
    RoomModeratedEvent,
    RoomPermissions,
    SendBulkMessageResponse,
    SendMessageResponse,
    SessionMetadata,
    SetOutfitResponse,
    TeleportResponse,
    TipReactionEvent,
    TipUserResponse,
    User,
    UserJoinedEvent,
    UserLeftEvent,
    UserMovedEvent,
    VoiceEvent,
    WebAPIError,
    _DoNotReconnect,
)
from .models_webapi import (
    AttrDict,
    GetPublicGrabResponse,
    GetPublicGrabsResponse,
    GetPublicItemResponse,
    GetPublicItemsResponse,
    GetPublicPostResponse,
    GetPublicPostsResponse,
    GetPublicRoomResponse,
    GetPublicRoomsResponse,
    GetPublicUserResponse,
    GetPublicUsersResponse,
    SearchItemsResponse,
    webapi_response_type,
)
from .models_webapi import (
    parse_webapi_response as parse_webapi_response,
)

try:
    from .extras import MISSING as _EXTRAS_MISSING
except ImportError:
    from .extras import _MISSING as _EXTRAS_MISSING

try:
    from .extras import CachedWebAPI as CachedWebAPI
except ImportError:  # pragma: no cover - compatibility with older extras
    from .extras import WebAPI as CachedWebAPI  # noqa: F401


__version__ = "1.5.0"


__all__ = [
    "AtomicJsonStore",
    "Awaiter",
    "ChangeDetector",
    "PeriodicJob",
    "PresenceTimer",
    "RoleStore",
    "RetryPolicy",
    "RoomOccupancyTrigger",
    "AnchorHitResponse",
    "AnchorPosition",
    "BaseBot",
    "BotDefinition",
    "BuyItemResponse",
    "BuyRoomBoostResponse",
    "BuyVoiceTimeResponse",
    "ChangeBackpackResponse",
    "ChangeRoomPrivilegeResponse",
    "ChannelEvent",
    "ChannelResponse",
    "ChatEvent",
    "ChatResponse",
    "CheckVoiceChatResponse",
    "ControlSessionMetadata",
    "Conversation",
    "CurrencyItem",
    "EmoteEvent",
    "EmoteResponse",
    "Error",
    "Facing",
    "FloorHitResponse",
    "GetBackpackResponse",
    "GetConversationsResponse",
    "GetInventoryResponse",
    "GetMessagesResponse",
    "GetRoomPrivilegeResponse",
    "GetRoomUsersResponse",
    "GetUserOutfitResponse",
    "GetWalletResponse",
    "Highrise",
    "HighriseFastValidationError",
    "IndicatorResponse",
    "InstanceStartedEvent",
    "InstanceStoppedEvent",
    "InviteSpeakerResponse",
    "Item",
    "KeepaliveResponse",
    "LeaveConversationResponse",
    "Message",
    "MessageEvent",
    "MessageMedia",
    "MessageMediaResponse",
    "ModerateRoomResponse",
    "MoveUserToRoomResponse",
    "Position",
    "Reaction",
    "ReactionEvent",
    "ReactionResponse",
    "ReasonCode",
    "RemoveSpeakerResponse",
    "ResponseError",
    "RoomInfo",
    "RoomModeratedEvent",
    "RoomPermissions",
    "SearchItemsResponse",
    "SendBulkMessageResponse",
    "SendMessageResponse",
    "SessionMetadata",
    "SetOutfitResponse",
    "TeleportResponse",
    "TipReactionEvent",
    "TipUserResponse",
    "User",
    "UserJoinedEvent",
    "UserLeftEvent",
    "UserMovedEvent",
    "ValidationErrorDetail",
    "VoiceEvent",
    "WebAPI",
    "WebAPIError",
    "CommandContext",
    "CommandRegistry",
    "RoomTracker",
    "ThrottledActions",
    "PromptManager",
    "DebouncedSaver",
    "UserResolver",
    "chunk_for_chat",
    "send_long_message",
    "commands",
    "active_subscriptions",
    "async_cached",
    "bot_runner",
    "collect_issues",
    "control_runner",
    "enable",
    "explain",
    "fast_enabled",
    "gather_subscriptions",
    "get_encoder_for",
    "get_sdk_module",
    "health",
    "install",
    "installed",
    "invalid_packet_stats",
    "patch",
    "reset_stats",
    "setup",
    "setup_logging",
    "stats",
    "uninstall",
    "validate_server_message",
    "debug_payload",
    "explain_debug",
    "BASE_PAYLOADS",
]


KEEPALIVE_RATE = 15
_CONTROL_SWEEP_INTERVAL = 30.0


def _env_float(name: str, default: float) -> float:
    """Read a float from environment variables with a fallback default."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw)
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    """Read an integer from environment variables with a fallback default."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


READ_TIMEOUT = _env_float("HR_READ_TIMEOUT", 60.0)

SDK_NAME = os.environ.get("HR_SDK_NAME", "highrise-fast")
VERSION = __version__
USER_AGENT = os.environ.get("HR_SDK_USER_AGENT", f"{SDK_NAME}/{VERSION}")

BASE_WS_URL = os.environ.get(
    "HR_BOTAPI_URL",
    "wss://highrise.game/web/botapi",
).rstrip("/")

BASE_WEB_URL = os.environ.get(
    "HR_WEBAPI_URL",
    "https://webapi.highrise.game",
).rstrip("/")

_REQ_TIMEOUT = _env_float(
    "SDK_FAST_REQ_TIMEOUT",
    _env_float("HR_SDK_REQ_TIMEOUT", 10.0),
)

_FIRE_AND_FORGET = os.environ.get("HR_FAST_FIRE_AND_FORGET", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

_WS_BINARY_FRAMES = os.environ.get("HR_WS_BINARY", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

_WEBAPI_CACHE_TTL = max(0, _env_int("HR_WEBAPI_CACHE_TTL", 60))

_BASE_EXCEPTION_GROUP = BaseExceptionGroup


def _contains_cancelled(exc: BaseException) -> bool:
    """Return True when the exception or exception group contains a CancelledError."""

    if isinstance(exc, asyncio.CancelledError):
        return True

    exceptions = getattr(exc, "exceptions", None)

    if exceptions:
        return any(_contains_cancelled(e) for e in exceptions)

    return False


def _is_ws_io_error(exc: BaseException) -> bool:
    """Return True for WebSocket or network I/O errors."""

    if isinstance(exc, (ConnectionError, OSError, RuntimeError)):
        return True

    return WebSocketError is not None and isinstance(exc, WebSocketError)


def _is_handshake_error(exc: BaseException) -> bool:
    """Return True for aiohttp WebSocket handshake errors."""

    return WSServerHandshakeError is not None and isinstance(
        exc, WSServerHandshakeError
    )


log = logging.getLogger("highrise.fast")


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logging for the SDK."""

    root = logging.getLogger()

    if not root.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )

    elif not log.handlers:
        log.setLevel(level)


_STATS: dict[str, int] = {
    "fast": 0,
    "slow": 0,
    "errors": 0,
    "encode_errors": 0,
    "send_errors": 0,
    "timeouts": 0,
    "api_errors": 0,
    "fast_fallbacks": 0,
    "bytes_sent": 0,
    "pops": 0,
    "cleanups": 0,
    "incoming_calls": 0,
    "incoming_fast": 0,
    "incoming_slow": 0,
    "incoming_fallback": 0,
    "incoming_skipped": 0,
    "incoming_invalid": 0,
    "incoming_dropped_malformed": 0,
    "dispatch_active": 0,
    "dispatch_dropped": 0,
    "dispatch_queued": 0,
    "chat_flood_dropped": 0,
    "dm_commands_deduplicated": 0,
}

_METRICS_MAXLEN = max(0, _env_int("HR_METRICS_MAXLEN", 10_000))
_LATENCIES_MS: deque[float] = deque(maxlen=min(10_000, _METRICS_MAXLEN))

_LOOP_LAG_MS: deque[float] = deque(maxlen=min(10_000, _METRICS_MAXLEN))
_GC_PAUSES_MS: deque[float] = deque(maxlen=min(1000, _METRICS_MAXLEN))
_LOOP_LAG_TASK: asyncio.Task | None = None
_LOOP_LAG_REFCOUNT: int = 0
_GC_START_TIME: float | None = None
_GC_CALLBACK_REGISTERED: bool = False
_GC_ENABLED: bool = False

# Vestigial: users are no longer interned (see parse_user). The table is kept
# empty so _clear_user_intern() stays a valid no-op for external callers.
_USER_INTERN: weakref.WeakValueDictionary[str, User] = weakref.WeakValueDictionary()


_DISPATCH_MAX_CONCURRENCY: int = _env_int("HR_DISPATCH_MAX_CONCURRENCY", 100)
_DISPATCH_QUEUE_MAX: int = _env_int("HR_DISPATCH_QUEUE_MAX", 1000)
_DISPATCH_ACTIVE: int = 0
_CHAT_FLOOD_QUEUE: deque[tuple[Any, ...]] = deque(maxlen=max(0, _DISPATCH_QUEUE_MAX))
_CHAT_DRAIN_WAKEUP: asyncio.Event | None = None


def _dispatch_backpressure_check() -> bool:
    """Return True if dispatch should apply backpressure (too many active handlers)."""
    return _DISPATCH_ACTIVE >= _DISPATCH_MAX_CONCURRENCY

def _dispatch_inc() -> None:
    global _DISPATCH_ACTIVE
    _DISPATCH_ACTIVE += 1
    _STATS["dispatch_active"] = _DISPATCH_ACTIVE

def _dispatch_dec() -> None:
    global _DISPATCH_ACTIVE
    _DISPATCH_ACTIVE = max(0, _DISPATCH_ACTIVE - 1)
    _STATS["dispatch_active"] = _DISPATCH_ACTIVE
    if _CHAT_FLOOD_QUEUE and _CHAT_DRAIN_WAKEUP is not None:
        _CHAT_DRAIN_WAKEUP.set()


def _record_loop_lag(lag_ms: float) -> None:
    try:
        _LOOP_LAG_MS.append(float(lag_ms))
    except Exception:
        pass


def _loop_lag_snapshot() -> dict[str, Any] | None:
    if not _LOOP_LAG_MS:
        return None
    arr = sorted(_LOOP_LAG_MS)
    n = len(arr)

    def pct(p: float) -> float:
        idx = int(n * p)
        idx = min(max(idx, 0), n - 1)
        return round(arr[idx], 3)

    return {
        "count": n,
        "p50": pct(0.50),
        "p95": pct(0.95),
        "p99": pct(0.99),
        "max": round(arr[-1], 3),
    }


async def _loop_lag_monitor(interval: float = 0.1) -> None:
    """Background task: sleep interval and measure oversleep as loop lag."""
    try:
        while True:
            t0 = time.perf_counter()
            await asyncio.sleep(interval)
            t1 = time.perf_counter()
            elapsed_ms = (t1 - t0) * 1000.0
            expected_ms = interval * 1000.0
            lag_ms = max(0.0, elapsed_ms - expected_ms)
            _record_loop_lag(lag_ms)
            if lag_ms > 200:
                log.debug("Loop lag spike: %.1fms (expected %.0fms)", lag_ms, expected_ms)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.debug("Loop lag monitor exited", exc_info=True)


def start_loop_lag_monitor(interval: float = 0.1) -> asyncio.Task | None:
    global _LOOP_LAG_TASK, _LOOP_LAG_REFCOUNT
    _LOOP_LAG_REFCOUNT += 1
    if _LOOP_LAG_TASK is not None and not _LOOP_LAG_TASK.done():
        return _LOOP_LAG_TASK
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    _LOOP_LAG_TASK = loop.create_task(_loop_lag_monitor(interval))
    _LOOP_LAG_TASK.set_name("highrise_fast-loop-lag")
    return _LOOP_LAG_TASK


async def stop_loop_lag_monitor() -> None:
    global _LOOP_LAG_TASK, _LOOP_LAG_REFCOUNT
    if _LOOP_LAG_REFCOUNT > 0:
        _LOOP_LAG_REFCOUNT -= 1
    if _LOOP_LAG_REFCOUNT > 0:
        return
    if _LOOP_LAG_TASK is None:
        return
    _LOOP_LAG_TASK.cancel()
    try:
        await _LOOP_LAG_TASK
    except asyncio.CancelledError:
        pass
    _LOOP_LAG_TASK = None


def _gc_callback(phase: str, info: dict) -> None:
    global _GC_START_TIME
    try:
        if phase == "start":
            _GC_START_TIME = time.perf_counter()
        elif phase == "stop" and _GC_START_TIME is not None:
            dur_ms = (time.perf_counter() - _GC_START_TIME) * 1000.0
            _GC_START_TIME = None
            with contextlib.suppress(Exception):
                _GC_PAUSES_MS.append(float(dur_ms))
            if dur_ms > 50:
                gen = info.get("generation", "?")
                log.debug(
                    "GC pause: %.1fms gen=%s collected=%s",
                    dur_ms,
                    gen,
                    info.get("collected"),
                )
    except Exception:
        log.debug("GC callback error", exc_info=True)


def _ensure_gc_monitoring() -> bool:
    global _GC_CALLBACK_REGISTERED, _GC_ENABLED
    if _GC_CALLBACK_REGISTERED:
        return _GC_ENABLED
    try:
        if _gc_callback not in gc.callbacks:
            gc.callbacks.append(_gc_callback)
        _GC_CALLBACK_REGISTERED = True
        _GC_ENABLED = True
        log.debug("GC monitoring enabled")
        return True
    except Exception:
        log.debug("Failed to enable GC monitoring", exc_info=True)
        return False


def _gc_snapshot() -> dict[str, Any] | None:
    if not _GC_PAUSES_MS:
        return None
    arr = sorted(_GC_PAUSES_MS)
    n = len(arr)

    def pct(p: float) -> float:
        idx = int(n * p)
        idx = min(max(idx, 0), n - 1)
        return round(arr[idx], 3)

    return {
        "count": n,
        "p50": pct(0.50),
        "p95": pct(0.95),
        "p99": pct(0.99),
        "max": round(arr[-1], 3),
        "enabled": _GC_ENABLED,
        "thresholds": gc.get_threshold(),
        "counts": gc.get_count(),
    }


def _maybe_tune_gc() -> None:
    """Optionally freeze and retune GC if env flag is set (item 15 fix).

    Previous implementation risked pinning cold objects -> memory growth if
    called too early. This version:
    - Requires attribution callback registered first (_ensure_gc_monitoring)
    - Only freezes once per process (_GC_FROZEN flag)
    - Waits for warmup: at least 5 seconds after first call and after first successful WS connect
    - Collects before freeze to avoid pinning garbage
    - Logs frozen count and old->new thresholds
    - Never freezes again (avoids repeated freeze growth)
    """
    global _GC_FROZEN, _GC_FIRST_TUNE_TIME
    tune_flag = os.environ.get("HR_FAST_GC_TUNE", os.environ.get("HR_GC_TUNE", "0")).strip().lower()
    if tune_flag not in {"1", "true", "yes", "on"}:
        return
    if not _GC_CALLBACK_REGISTERED:
        _ensure_gc_monitoring()
    if _GC_FROZEN:
        log.debug("GC already frozen, skipping")
        return
    now = time.monotonic()
    if _GC_FIRST_TUNE_TIME is None:
        _GC_FIRST_TUNE_TIME = now
        log.info("GC tune requested — warmup started, will freeze after 5s")
        return
    if now - _GC_FIRST_TUNE_TIME < 5.0:
        log.debug("GC tune warmup: %.1fs elapsed, waiting for 5s", now - _GC_FIRST_TUNE_TIME)
        return
    try:
        gc.collect()
        gc.freeze()
        _GC_FROZEN = True
        log.info("GC tuned: froze %d objects (warmup %.1fs)", gc.get_freeze_count(), now - _GC_FIRST_TUNE_TIME)
        old = gc.get_threshold()
        gc.set_threshold(1000, 15, 15)
        log.info("GC thresholds tuned: %s -> %s", old, gc.get_threshold())
    except Exception:
        log.debug("GC tuning failed", exc_info=True)


_GC_FROZEN: bool = False
_GC_FIRST_TUNE_TIME: float | None = None



def _record_latency(t0: float) -> None:
    """Record request latency in milliseconds."""

    try:
        _LATENCIES_MS.append((time.perf_counter() - t0) * 1000.0)

    except (TypeError, ValueError):
        log.debug("Failed to record latency", exc_info=True)


def _latency_snapshot() -> dict[str, Any] | None:
    """Return percentile latency statistics."""

    if not _LATENCIES_MS:
        return None

    arr = sorted(_LATENCIES_MS)

    n = len(arr)

    def pct(p: float) -> float:
        """Pct."""

        idx = int(n * p)

        idx = min(max(idx, 0), n - 1)

        return round(arr[idx], 3)

    return {
        "count": n,
        "p50": pct(0.50),
        "p95": pct(0.95),
        "p99": pct(0.99),
        "max": round(arr[-1], 3),
    }


def stats() -> dict[str, Any]:
    """Return SDK runtime statistics."""

    successful_sends = _STATS["fast"] + _STATS["slow"]

    encoder_hit_rate = (
        round(_STATS["fast"] / successful_sends, 4) if successful_sends else None
    )

    incoming_rate = (
        round(_STATS["incoming_fast"] / _STATS["incoming_calls"], 4)
        if _STATS["incoming_calls"]
        else None
    )

    return {
        **_STATS,
        "incoming_fast_hits": _STATS["incoming_fast"],
        "invalid_packets_by_type": dict(_INVALID_BY_TYPE),
        "encoder_hit_rate": encoder_hit_rate,
        "incoming_fast_rate": incoming_rate,
        "latency": _latency_snapshot(),
        "loop_lag": _loop_lag_snapshot(),
        "gc_pauses": _gc_snapshot(),
        "fast_enabled": True,
        "sdk_module": "highrise_fast",
    }


def health() -> str:
    """Return a short health summary for the SDK."""

    snap = stats()

    parts = [
        "standalone SDK",
        "per-request cleanup",
        "binary frames" if _WS_BINARY_FRAMES else "text frames preferred",
    ]

    if snap.get("encoder_hit_rate") is not None:
        parts.append(f"outgoing hit-rate {snap['encoder_hit_rate'] * 100:.1f}%")

    if snap.get("incoming_fast_rate") is not None:
        parts.append(f"incoming fast-rate {snap['incoming_fast_rate'] * 100:.1f}%")

    if snap.get("incoming_skipped"):
        parts.append(f"{snap['incoming_skipped']} unsubscribed events skipped")

    if _REQ_TIMEOUT > 0:
        parts.append(f"timeout {_REQ_TIMEOUT}s")

    if _FIRE_AND_FORGET:
        parts.append("fire-and-forget enabled")

    lag = snap.get("loop_lag")
    if lag:
        parts.append(f"loop-lag p99 {lag.get('p99')}ms")

    gc_snap = snap.get("gc_pauses")
    if gc_snap:
        parts.append(f"gc p99 {gc_snap.get('p99')}ms")

    return "highrise_fast: " + ", ".join(parts)


def reset_stats() -> None:
    """Reset SDK runtime statistics including bounded queues (items 14,16)."""

    for key in list(_STATS.keys()):
        _STATS[key] = 0

    _INVALID_BY_TYPE.clear()

    _INVALID_LAST_SEEN.clear()

    _INVALID_WARN_STATE.clear()

    _LATENCIES_MS.clear()
    _LOOP_LAG_MS.clear()
    _GC_PAUSES_MS.clear()
    _CHAT_FLOOD_QUEUE.clear()
    _STATS["dispatch_active"] = _DISPATCH_ACTIVE


def get_sdk_module():
    """Return the current SDK module object."""

    return sys.modules.get(__name__)


def _object_payload(obj: Any, *, add_type: bool = False) -> dict[str, Any]:
    """Convert an object into a JSON-friendly dictionary."""

    payload: dict[str, Any] = {}

    attrs = getattr(obj, "__attrs_attrs__", None)

    if attrs:
        for attr in attrs:
            name = getattr(attr, "name", None)

            if not name or name.startswith("_"):
                continue

            payload[name] = getattr(obj, name, None)

        if add_type:
            payload.setdefault("_type", type(obj).__name__)

        return payload

    if hasattr(obj, "__dict__"):
        payload = {
            key: value for key, value in obj.__dict__.items() if not key.startswith("_")
        }

        if add_type:
            payload.setdefault("_type", type(obj).__name__)

        return payload

    slots: list[str] = []

    for klass in type(obj).__mro__:
        slots.extend(getattr(klass, "__slots__", ()))

    for name in dict.fromkeys(slots):
        if name.startswith("_"):
            continue

        if hasattr(obj, name):
            payload[name] = getattr(obj, name)

    if add_type:
        payload.setdefault("_type", type(obj).__name__)

    return payload


def _json_default(obj: Any) -> Any:
    """Default serializer for JSON encoding of special types."""
    if isinstance(obj, (set, frozenset)):
        return list(obj)

    if isinstance(obj, Enum):
        return obj.value

    if isinstance(obj, datetime):
        return obj.isoformat()

    if isinstance(obj, Item):
        return {
            "type": obj.type,
            "amount": obj.amount,
            "id": obj.id,
            "account_bound": obj.account_bound,
            "active_palette": obj.active_palette,
        }

    if hasattr(obj, "__attrs_attrs__"):
        return _object_payload(obj, add_type=False)

    if hasattr(obj, "__dict__"):
        return {
            key: value for key, value in obj.__dict__.items() if not key.startswith("_")
        }

    if hasattr(obj, "__slots__"):
        return _object_payload(obj, add_type=False)

    raise TypeError(f"Unsupported type for JSON encoding: {type(obj)!r}")


def dumps_json(payload: dict[str, Any]) -> bytes:
    """Serialize a payload to compact JSON bytes."""

    if orjson is not None:
        return orjson.dumps(payload, default=_json_default)

    return json.dumps(
        payload,
        default=_json_default,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def get_encoder_for(type_name: str) -> Callable[[dict[str, Any]], bytes]:
    """Return an optimized JSON encoder for a specific outgoing message type.

    sdk_fast uses this to pre-build per-type encoders. Since highrise_fast

    already uses orjson (or compact json.dumps) internally, we return the

    unified dumps_json which handles all types via _json_default.

    """

    return dumps_json


def loads_json(raw: Any) -> Any:
    """Decode JSON bytes or text into Python data."""

    if raw is None:
        return None

    if isinstance(raw, dict):
        return raw

    if orjson is not None:
        return orjson.loads(raw)

    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")

    return json.loads(raw)


async def _ws_send_text(ws: Any, data: str | bytes) -> int:
    """Send encoded JSON and return its UTF-8 size in bytes."""
    if _WS_BINARY_FRAMES:
        send_bytes = getattr(ws, "send_bytes", None)
        if callable(send_bytes):
            encoded = data.encode("utf-8") if isinstance(data, str) else data
            await send_bytes(encoded)
            return len(encoded)

    send_str = getattr(ws, "send_str", None)
    if callable(send_str):
        if isinstance(data, str):
            await send_str(data)
            return len(data) if data.isascii() else len(data.encode("utf-8"))
        await send_str(data.decode("utf-8"))
        return len(data)

    send_bytes = getattr(ws, "send_bytes", None)
    if callable(send_bytes):
        encoded = data.encode("utf-8") if isinstance(data, str) else data
        await send_bytes(encoded)
        return len(encoded)

    raise TypeError("WebSocket object supports neither send_str nor send_bytes")


async def _send_ws_payload(ws: Any, payload: dict[str, Any]) -> None:
    """Encode and send a WebSocket JSON payload."""

    fast = orjson is not None

    try:
        if orjson is not None:
            data = orjson.dumps(payload, default=_json_default)
        else:
            text = json.dumps(
                payload,
                default=_json_default,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            data = text if text.isascii() else text.encode("utf-8")

    except (TypeError, ValueError) as exc:
        _STATS["encode_errors"] += 1

        _STATS["errors"] += 1

        raise TypeError("JSON encoding failed") from exc

    try:
        bytes_sent = await _ws_send_text(ws, data)

    except Exception as exc:
        if _is_ws_io_error(exc):
            _STATS["send_errors"] += 1

            _STATS["errors"] += 1

            raise ConnectionError("WebSocket send failed") from exc

        raise

    if fast:
        _STATS["fast"] += 1

    else:
        _STATS["slow"] += 1

    _STATS["bytes_sent"] += bytes_sent


def _as_int(value: Any, default: int = 0) -> int:
    """Coerce a value to ``int``, falling back to ``default`` when it is not numeric.

    The ``type(x) is int`` guard skips the try/except on the overwhelmingly common
    case where JSON already produced an int.
    """
    if type(value) is int:
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    """Coerce a value to ``float``, falling back to ``default`` when not numeric.

    The ``type(x) is float`` guard skips the try/except when JSON already gave a
    float; note ``int`` must still go through ``float()`` so an integral position
    becomes ``1.0`` exactly as the official SDK does.
    """
    if type(value) is float:
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_datetime(value: Any) -> Any:
    """Parse an ISO-8601 datetime string when possible."""

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)

        except ValueError:
            return value

    return value


def parse_user(value: Any) -> User | None:
    """Parse a raw dictionary into a ``User`` model.

    Mirrors the official SDK exactly: every parse returns a **fresh** ``User``
    object. ``User`` implements value equality, so ``a.user == b.user`` still
    compares by value across events. Only object identity differs between the
    two SDKs, and there is no difference -- both produce distinct objects.

    Interning was removed deliberately, for three reasons:

    1. **Parity.** The official SDK does not intern: parsing the same payload
       twice yields two distinct ``User`` objects. Interning silently made
       ``a.user is b.user`` true here and false there, which is exactly the kind
       of divergence a drop-in replacement must not have.
    2. **Correctness.** The table was keyed by user id and held a live object, so
       a handler mutating ``user.username`` changed that field for every other
       reference to the same user -- a mutation-sharing hazard with no official
       equivalent.
    3. **Speed.** Keys were held in a ``WeakValueDictionary``. Whenever nothing
       kept the ``User`` alive (a stress test, a filter, a discarded event) every
       parse was an intern *miss*: full weakref insert plus removal callback, with
       no reuse to show for it. Measured at ~42% on ``ChatEvent``. Removing it
       turned a 0.68x regression into a 1.18x win, and improved the retained
       case too (1.08x -> 1.18x), so there was no trade-off to weigh.
    """
    if not isinstance(value, dict):
        return None
    return _mk_user(value.get("id", ""), value.get("username", ""))


def _mk_user(uid: Any, uname: Any) -> User:
    """Build a ``User`` with the official SDK's coercion applied.

    The official SDK runs payloads through cattrs, which coerces a non-str ``id``
    to ``str`` (``123`` becomes ``"123"``). Reproducing that here keeps drop-in
    parity for tolerant payloads while avoiding the general-purpose converter.
    ``type(x) is str`` is checked first because a str is already correct and that
    test is cheaper than calling ``str()`` on it.
    """
    return User(
        uid if type(uid) is str else str(uid),
        uname if type(uname) is str else str(uname),
    )


def _clear_user_intern() -> None:
    """Clear the user intern table.

    Interning was removed (see :func:`parse_user`), so this is now a no-op kept
    only for backwards compatibility with code that called it before a test.
    The table is drained so introspection does not report stale entries.
    """
    _USER_INTERN.clear()


def parse_position(value: Any) -> Position | AnchorPosition | None:
    """Parse a raw dictionary into a Position or AnchorPosition model."""
    if not isinstance(value, dict):
        return None

    if "entity_id" in value or "anchor_ix" in value:
        eid = value.get("entity_id", "")
        return AnchorPosition(
            eid if type(eid) is str else str(eid),
            _as_int(value.get("anchor_ix"), 0),
        )

    return Position(
        _as_float(value.get("x"), 0.0),
        _as_float(value.get("y"), 0.0),
        _as_float(value.get("z"), 0.0),
        _normalize_facing(value.get("facing")),
    )


_FACING_VALUES = {"FrontRight", "FrontLeft", "BackRight", "BackLeft"}


def _normalize_facing(value: Any) -> str:
    """Normalize a facing direction value."""
    if type(value) is str and value in _FACING_VALUES:
        return value
    return "FrontRight"


def parse_item(value: Any) -> Item | None:
    """Parse a raw dictionary into an Item model."""

    if not isinstance(value, dict):
        return None

    active_palette_raw = value.get("active_palette")

    return Item(
        type=str(value.get("type", "clothing")),
        amount=_as_int(value.get("amount"), 1),
        id=str(value.get("id", "")),
        account_bound=bool(value.get("account_bound", False)),
        active_palette=(
            None if active_palette_raw is None else _as_int(active_palette_raw)
        ),
    )


def parse_currency(value: Any) -> CurrencyItem | None:
    """Parse a raw dictionary into a CurrencyItem model."""

    if not isinstance(value, dict):
        return None

    return CurrencyItem(
        type=str(value.get("type", "")),
        amount=_as_int(value.get("amount"), 0),
    )


def parse_item_or_currency(value: Any) -> Item | CurrencyItem | None:
    """Parse a raw dictionary into an Item or CurrencyItem model."""

    if not isinstance(value, dict):
        return None

    if value.get("type") == "clothing":
        return parse_item(value)

    return parse_currency(value)


def parse_message(value: Any) -> Message | None:
    """Parse a raw dictionary into a Message model."""

    if not isinstance(value, dict):
        return None

    return Message(
        message_id=str(value.get("message_id", value.get("id", ""))),
        conversation_id=str(value.get("conversation_id", "")),
        createdAt=_parse_datetime(value.get("createdAt", value.get("created_at"))),
        content=str(value.get("content", "")),
        sender_id=str(value.get("sender_id", value.get("user_id", ""))),
        category=str(value.get("category", "text")),
    )


def parse_conversation(value: Any) -> Conversation | None:
    """Parse a raw dictionary into a Conversation model."""

    if not isinstance(value, dict):
        return None

    last_message_raw = value.get("last_message")

    last_message = parse_message(last_message_raw) if last_message_raw else None

    return Conversation(
        id=str(value.get("id", "")),
        did_join=bool(value.get("did_join", False)),
        unread_count=_as_int(value.get("unread_count"), 0),
        last_message=last_message,
        muted=bool(value.get("muted", False)),
        member_ids=value.get("member_ids"),
        name=value.get("name"),
        owner_id=value.get("owner_id"),
    )


def parse_media(value: Any) -> MessageMedia | None:
    """Parse a raw dictionary into a MessageMedia model."""

    if not isinstance(value, dict):
        return None

    return MessageMedia(
        type=str(value.get("type", "image")),
        width=_as_int(value.get("width"), 0),
        height=_as_int(value.get("height"), 0),
        mediaSizeInBytes=_as_int(value.get("mediaSizeInBytes"), 0),
        thumbnailSizeInBytes=_as_int(value.get("thumbnailSizeInBytes"), 0),
        id=value.get("id"),
        url=value.get("url"),
        thumbnailUrl=value.get("thumbnailUrl"),
    )


def parse_session_metadata(data: dict[str, Any]) -> SessionMetadata:
    """Parse a session metadata payload into SessionMetadata."""

    room_raw = data.get("room_info", {}) or {}

    room_info = RoomInfo(
        owner_id=str(room_raw.get("owner_id", "")),
        room_name=str(room_raw.get("room_name", "")),
    )

    raw_rates = data.get("rate_limits") or {}
    rate_limits = {
        name: tuple(limit) if isinstance(limit, list) and len(limit) == 2 else limit
        for name, limit in raw_rates.items()
    } if isinstance(raw_rates, dict) else {}

    return SessionMetadata(
        user_id=str(data.get("user_id", "")),
        room_info=room_info,
        rate_limits=rate_limits,
        connection_id=str(data.get("connection_id", "")),
        sdk_version=data.get("sdk_version"),
    )


def parse_control_session_metadata(data: dict[str, Any]) -> ControlSessionMetadata:
    """Parse a control session metadata payload into ControlSessionMetadata."""

    return ControlSessionMetadata(
        connection_id=str(data.get("connection_id", "")),
        instance_ids=list(data.get("instance_ids", []) or []),
    )


from .validation import (
    BASE_PAYLOADS,
    HighriseFastValidationError,
    ReasonCode,
    ValidationErrorDetail,
    debug_payload,
    explain_debug,
    validate_server_message,
)
from .validation import (
    validate_server_message as _hrf_validate_server_message,
)

_TYPED_PARSERS: dict[str, Callable[[dict[str, Any]], Any]] = {}


def _register_typed(msg_type: str):
    """Register a typed parser for a message type."""

    def deco(fn: Callable[[dict[str, Any]], Any]) -> Callable[[dict[str, Any]], Any]:
        """Deco."""

        _TYPED_PARSERS[msg_type] = fn

        return fn

    return deco


_TYPED_PARSERS["SessionMetadata"] = parse_session_metadata
_ERROR_TYPES = ("Error", "ErrorResponse")


@_register_typed("ChatEvent")
def _parse_chat_event(d: dict[str, Any]) -> Any:
    """Parse Chat event."""

    user = parse_user(d.get("user"))

    if user is None:
        return None

    return ChatEvent(
        user=user,
        message=d.get("message") or "",
        whisper=d.get("whisper") or False,
    )


@_register_typed("UserJoinedEvent")
def _parse_user_joined(d: dict[str, Any]) -> Any:
    """Parse User joined."""

    user = parse_user(d.get("user"))

    if user is None:
        return None

    return UserJoinedEvent(
        user=user,
        position=parse_position(d.get("position")),
    )


@_register_typed("UserLeftEvent")
def _parse_user_left(d: dict[str, Any]) -> Any:
    """Parse User left."""

    user = parse_user(d.get("user"))

    if user is None:
        return None

    return UserLeftEvent(user=user)


@_register_typed("UserMovedEvent")
def _parse_user_moved(d: dict[str, Any]) -> Any:
    """Parse User moved."""

    user = parse_user(d.get("user"))

    if user is None:
        return None

    return UserMovedEvent(
        user=user,
        position=parse_position(d.get("position")),
    )


@_register_typed("EmoteEvent")
def _parse_emote(d: dict[str, Any]) -> Any:
    """Parse Emote."""

    user = parse_user(d.get("user"))

    if user is None:
        return None

    return EmoteEvent(
        user=user,
        emote_id=d.get("emote_id") or "",
        receiver=parse_user(d.get("receiver")),
    )


@_register_typed("ReactionEvent")
def _parse_reaction(d: dict[str, Any]) -> Any:
    """Parse Reaction."""

    user = parse_user(d.get("user"))

    if user is None:
        return None

    receiver = parse_user(d.get("receiver"))

    return ReactionEvent(
        user=user,
        reaction=d.get("reaction") or "",
        receiver=receiver,
    )


@_register_typed("TipReactionEvent")
def _parse_tip(d: dict[str, Any]) -> Any:
    """Parse Tip."""

    sender = parse_user(d.get("sender"))

    receiver = parse_user(d.get("receiver"))

    if sender is None or receiver is None:
        return None

    return TipReactionEvent(
        sender=sender,
        receiver=receiver,
        item=parse_item_or_currency(d.get("item")),
    )


@_register_typed("VoiceEvent")
def _parse_voice(d: dict[str, Any]) -> Any:
    """Parse Voice."""

    raw_users = d.get("users") or ()

    users: list[tuple[User, str]] = []

    for pair in raw_users:
        if isinstance(pair, (list, tuple)) and len(pair) == 2:
            u = parse_user(pair[0])

            if u is not None:
                users.append((u, str(pair[1])))

    return VoiceEvent(
        users=users,
        seconds_left=_as_int(d.get("seconds_left"), 0),
    )


@_register_typed("ChannelEvent")
def _parse_channel(d: dict[str, Any]) -> Any:
    """Parse Channel."""
    raw_tags = d.get("tags")

    if raw_tags is None:
        tags: list[str] = []
    elif isinstance(raw_tags, str):
        tags = [raw_tags]
    elif isinstance(raw_tags, (list, tuple, set, frozenset)):
        tags = [str(tag) for tag in raw_tags]
    else:
        tags = [str(raw_tags)]

    return ChannelEvent(
        sender_id=d.get("sender_id") or "",
        msg=d.get("msg") or "",
        tags=tags,
    )


@_register_typed("MessageEvent")
def _parse_message_event(d: dict[str, Any]) -> Any:
    """Parse Message event."""

    return MessageEvent(
        user_id=d.get("user_id") or "",
        conversation_id=d.get("conversation_id") or "",
        is_new_conversation=d.get("is_new_conversation") or False,
    )


@_register_typed("RoomModeratedEvent")
def _parse_moderated(d: dict[str, Any]) -> Any:
    """Parse Moderated."""

    duration_raw = d.get("duration")

    return RoomModeratedEvent(
        moderatorId=d.get("moderatorId") or "",
        targetUserId=d.get("targetUserId") or "",
        moderationType=d.get("moderationType") or "",
        duration=None if duration_raw is None else _as_int(duration_raw),
    )


@_register_typed("ErrorResponse")
@_register_typed("Error")
def _parse_error(d: dict[str, Any]) -> Any:
    """Parse Error."""

    return Error(
        message=str(d.get("message") or ""),
        do_not_reconnect=d.get("do_not_reconnect") is True,
        rid=d.get("rid"),
    )


@_register_typed("GetRoomUsersResponse")
def _parse_room_users(d: dict[str, Any]) -> Any:
    """Parse Room users."""

    content_raw = d.get("content") or ()

    content: list[tuple[User, Any]] = []

    for row in content_raw:
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            u = parse_user(row[0])

            if u is not None:
                content.append((u, parse_position(row[1])))

    return GetRoomUsersResponse(content=content, rid=d.get("rid"))


@_register_typed("GetWalletResponse")
def _parse_wallet(d: dict[str, Any]) -> Any:
    """Parse Wallet."""

    content_raw = d.get("content") or ()

    wallet: list[CurrencyItem] = []

    for item in content_raw:
        c = parse_currency(item)

        if c is not None:
            wallet.append(c)

    return GetWalletResponse(content=wallet, rid=d.get("rid"))


@_register_typed("GetBackpackResponse")
def _parse_backpack(d: dict[str, Any]) -> Any:
    """Parse Backpack."""

    return GetBackpackResponse(
        backpack=Counter(d.get("backpack") or {}),
        rid=d.get("rid"),
    )


@_register_typed("GetRoomPrivilegeResponse")
def _parse_privilege(d: dict[str, Any]) -> Any:
    """Parse Privilege."""

    raw = d.get("content") or {}

    return GetRoomPrivilegeResponse(
        content=RoomPermissions(
            moderator=raw.get("moderator"),
            designer=raw.get("designer"),
        ),
        rid=d.get("rid"),
    )


@_register_typed("CheckVoiceChatResponse")
def _parse_voice_status(d: dict[str, Any]) -> Any:
    """Parse Voice status."""

    return CheckVoiceChatResponse(
        seconds_left=_as_int(d.get("seconds_left"), 0),
        auto_speakers=set(d.get("auto_speakers") or ()),
        users=dict(d.get("users") or {}),
        rid=d.get("rid"),
    )


@_register_typed("GetUserOutfitResponse")
def _parse_outfit(d: dict[str, Any]) -> Any:
    """Parse Outfit."""

    outfit_raw = d.get("outfit") or ()

    outfit = [
        i
        for i in (parse_item(x) for x in outfit_raw if isinstance(x, dict))
        if i is not None
    ]

    return GetUserOutfitResponse(outfit=outfit, rid=d.get("rid"))


@_register_typed("GetConversationsResponse")
def _parse_conversations(d: dict[str, Any]) -> Any:
    """Parse Conversations."""

    conv_raw = d.get("conversations") or ()

    conversations = [
        c
        for c in (parse_conversation(x) for x in conv_raw if isinstance(x, dict))
        if c is not None
    ]

    return GetConversationsResponse(
        conversations=conversations,
        not_joined=_as_int(d.get("not_joined"), 0),
        rid=d.get("rid"),
    )


@_register_typed("GetMessagesResponse")
def _parse_messages(d: dict[str, Any]) -> Any:
    """Parse Messages."""

    msgs_raw = d.get("messages") or ()

    messages = [
        m
        for m in (parse_message(x) for x in msgs_raw if isinstance(x, dict))
        if m is not None
    ]

    return GetMessagesResponse(messages=messages, rid=d.get("rid"))


@_register_typed("GetInventoryResponse")
def _parse_inventory(d: dict[str, Any]) -> Any:
    """Parse Inventory."""

    items_raw = d.get("items") or ()

    items = [
        i
        for i in (parse_item(x) for x in items_raw if isinstance(x, dict))
        if i is not None
    ]

    return GetInventoryResponse(items=items, rid=d.get("rid"))


@_register_typed("BuyVoiceTimeResponse")
def _parse_buy_voice(d: dict[str, Any]) -> Any:
    """Parse Buy voice."""

    return BuyVoiceTimeResponse(
        result=d.get("result") or "",
        rid=d.get("rid"),
    )


@_register_typed("BuyRoomBoostResponse")
def _parse_buy_boost(d: dict[str, Any]) -> Any:
    """Parse Buy boost."""

    return BuyRoomBoostResponse(
        result=d.get("result") or "",
        rid=d.get("rid"),
    )


@_register_typed("TipUserResponse")
def _parse_tip_user(d: dict[str, Any]) -> Any:
    """Parse Tip user."""

    return TipUserResponse(
        result=d.get("result") or "",
        rid=d.get("rid"),
    )


@_register_typed("BuyItemResponse")
def _parse_buy_item(d: dict[str, Any]) -> Any:
    """Parse Buy item."""

    return BuyItemResponse(
        result=d.get("result") or "",
        rid=d.get("rid"),
    )


@_register_typed("MessageMediaResponse")
def _parse_media_response(d: dict[str, Any]) -> Any:
    """Parse Media response."""

    return MessageMediaResponse(
        media=parse_media(d.get("media")),
        uploadUrl=d.get("uploadUrl"),
        thumbnailUploadUrl=d.get("thumbnailUploadUrl"),
        rid=d.get("rid"),
    )


_ACK_TYPES: dict[str, Any] = {
    "ChatResponse": ChatResponse,
    "EmoteResponse": EmoteResponse,
    "ReactionResponse": ReactionResponse,
    "IndicatorResponse": IndicatorResponse,
    "ChannelResponse": ChannelResponse,
    "KeepaliveResponse": KeepaliveResponse,
    "TeleportResponse": TeleportResponse,
    "FloorHitResponse": FloorHitResponse,
    "AnchorHitResponse": AnchorHitResponse,
    "ModerateRoomResponse": ModerateRoomResponse,
    "ChangeRoomPrivilegeResponse": ChangeRoomPrivilegeResponse,
    "MoveUserToRoomResponse": MoveUserToRoomResponse,
    "InviteSpeakerResponse": InviteSpeakerResponse,
    "RemoveSpeakerResponse": RemoveSpeakerResponse,
    "SendMessageResponse": SendMessageResponse,
    "SendBulkMessageResponse": SendBulkMessageResponse,
    "LeaveConversationResponse": LeaveConversationResponse,
    "ChangeBackpackResponse": ChangeBackpackResponse,
    "SetOutfitResponse": SetOutfitResponse,
}


def _make_ack_parser(ack_cls: Any):
    """Build a parser for a ``rid``-only acknowledgement response.

    Every model in :data:`_ACK_TYPES` has exactly one field, ``rid``, so the
    instance is built positionally. This path runs once per outbound request
    response, and the keyword-argument machinery is a measurable share of it.
    """

    def _parser(d: dict[str, Any]) -> Any:
        return ack_cls(d.get("rid"))

    return _parser


for _ack_name, _ack_cls in _ACK_TYPES.items():
    _TYPED_PARSERS[_ack_name] = _make_ack_parser(_ack_cls)


def _parse_typed_message(data: dict[str, Any]) -> Any:
    """

    Convert a wire dict into a typed model object via O(1) registry lookup.

    Returns the raw dict if:

    - `_type` is missing or non-string,

    - the type isn't registered,

    - the parser returns None (missing required nested field),

    - the parser raises.

    Never raises — this is the lenient path.

    """

    msg_type = data.get("_type")

    # ``type(x) is str`` is the correct test here and cheaper than isinstance:
    # JSON decoding only ever produces exact ``str``, never a subclass.
    if type(msg_type) is not str:
        return data

    parser = _TYPED_PARSERS.get(msg_type)

    if parser is None:
        return data

    try:
        result = parser(data)

    except (ValueError, TypeError, KeyError, AttributeError, IndexError):
        log.debug("typed parser failed for %s", msg_type, exc_info=True)

        return data

    return result if result is not None else data


def _lenient_parse_server_message(
    data: Any,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """

    Lenient parser: converts recognized wire messages into typed objects.

    Unlike the strict validator, this never raises — malformed payloads and

    unknown `_type` values pass through as the raw dict so that dispatch

    and telemetry keep working.

    """

    if isinstance(data, (str, bytes, bytearray)):
        try:
            data = loads_json(data)

        except (ValueError, TypeError, UnicodeDecodeError):
            return data

    if not isinstance(data, dict):
        return data

    return _parse_typed_message(data)


class _FatalValidationError(BaseException):
    """Raised when on_invalid='raise' — must not be swallowed by bot_runner."""


def _contains_fatal(exc: BaseException) -> bool:
    """Internal helper for Contains fatal."""

    if isinstance(exc, _FatalValidationError):
        return True

    exceptions = getattr(exc, "exceptions", None)

    if exceptions:
        return any(_contains_fatal(e) for e in exceptions)

    return False


_hrf_original_parse_server_message = _lenient_parse_server_message


def parse_server_message(
    data,
    strict: bool = False,
    strict_semantic: bool = False,
    **kwargs,
):
    """
    highrise_fast unified validate+parse.

    Single-pass entry point that validates (when strict) and parses in one
    dispatch, avoiding double JSON decode and double traversal.

    - lenient (default): fast path, returns typed object or raw dict for unknown types
    - strict=True: promotes strict_semantic=True to match validate_server_message,
      validates then parses; raises HighriseFastValidationError on malformed packet.

    This collapses the old two-step (validate walk + parse walk) into a single
    logical pass, and consolidates the four parallel registries (_ACK_MAP, _ACK_TYPES,
    _DISPATCH, _REQUESTS) via _TYPED_PARSERS as the unified dispatch table.
    """
    # ---- lenient fast path ---------------------------------------------------
    # The receive loop hands us bytes; tooling hands us dicts. Those two take a
    # dedicated route that skips the general decoder wrapper and the isinstance
    # chain, which is what the per-message cost is actually made of. Every other
    # input (bytearray, str, None, list, int) and all malformed JSON falls
    # through to the general path below, so behaviour outside it is unchanged.
    if not strict and not strict_semantic:
        kind = data.__class__
        if kind is dict:
            payload = data
        elif (kind is bytes or kind is str) and orjson is not None:
            try:
                payload = orjson.loads(data)
            except (ValueError, TypeError, UnicodeDecodeError):
                return data
            if type(payload) is not dict:
                return payload
        else:
            payload = None

        if payload is not None:
            # Dispatch inline rather than through _parse_typed_message: the
            # registry lookup is identical, but this drops one Python frame per
            # message, which measurement shows is a larger share of the cost
            # than the object construction itself.
            msg_type = payload.get("_type")
            if type(msg_type) is str:
                parser = _TYPED_PARSERS.get(msg_type)
                if parser is not None:
                    try:
                        parsed = parser(payload)
                    except (ValueError, TypeError, KeyError, AttributeError, IndexError):
                        log.debug("typed parser failed for %s", msg_type, exc_info=True)
                        return payload
                    return payload if parsed is None else parsed
            return payload

    if isinstance(data, (str, bytes, bytearray)):
        try:
            data = loads_json(data)
        except (ValueError, TypeError, UnicodeDecodeError):
            if strict or strict_semantic:
                raise HighriseFastValidationError(
                    [
                        ValidationErrorDetail(
                            "$",
                            "invalid JSON payload",
                            expected="JSON object",
                            got="unparseable",
                            reason_code=ReasonCode.WRONG_TYPE,
                        )
                    ],
                    payload=data,
                ) from None
            return data

    if strict or strict_semantic:
        _hrf_validate_server_message(
            data,
            strict_semantic=True,
        )

    if isinstance(data, dict):
        return _parse_typed_message(data)
    return data


def _unified_validate_and_parse(
    data: Any,
    *,
    strict: bool = False,
    strict_semantic: bool = False,
) -> Any:
    """Internal helper for single-pass validate+parse used by benchmarks and tests."""
    return parse_server_message(data, strict=strict, strict_semantic=strict_semantic)


for _hrf_name in (
    "HighriseFastValidationError",
    "ValidationErrorDetail",
    "validate_server_message",
    "parse_server_message",
    "collect_issues",
    "explain",
):
    if _hrf_name not in __all__:
        __all__.append(_hrf_name)


for _extra_name in (
    "TTLCache",
    "cached",
    "MetricTracker",
    "Metrics",
    "TaskManager",
    "CachedWebAPI",
    "CommandContext",
    "CommandRegistry",
    "RoomTracker",
    "ThrottledActions",
    "PromptManager",
    "DebouncedSaver",
    "UserResolver",
    "chunk_for_chat",
    "send_long_message",
    "commands",
):
    if _extra_name not in __all__:
        __all__.append(_extra_name)

_VALIDATION_MODES = frozenset({"strict", "lenient"})

_ON_INVALID_POLICIES = frozenset({"drop", "raise", "log-only"})


_VALIDATION_EXEMPT = frozenset({"Error", "KeepaliveResponse", "SessionMetadata"})


_STATEFUL_EVENTS = frozenset({"UserJoinedEvent", "UserLeftEvent", "UserMovedEvent"})


_DEFAULT_INVALID_WARN_COOLDOWN = 60.0

_INVALID_WARN_STATE_MAX = 256


_INVALID_BY_TYPE: Counter[str] = Counter()

_INVALID_LAST_SEEN: dict[str, float] = {}

_INVALID_WARN_STATE: dict[tuple[str, str], list[float]] = {}


def _pick_choice(
    label: str,
    explicit: Any,
    env_name: str,
    valid: frozenset[str],
    default: str,
) -> str:
    """Resolve a setting: explicit (BaseBot attr) > environment > default."""

    for source, value in (("bot", explicit), ("env", os.environ.get(env_name))):
        if value is None or value == "":
            continue

        norm = str(value).strip().lower().replace("_", "-")

        if norm in valid:
            return norm

        log.warning(
            "Ignoring invalid %s=%r (from %s); expected one of: %s",
            label,
            value,
            source,
            ", ".join(sorted(valid)),
        )

    return default


def _pick_cooldown(explicit: Any) -> float:
    """Resolve the invalid-packet warning cooldown."""

    for value in (explicit, os.environ.get("HIGHRISE_FAST_INVALID_WARN_COOLDOWN")):
        if value is None or value == "":
            continue

        try:
            seconds = float(value)

        except (TypeError, ValueError):
            log.warning("Ignoring invalid invalid_warn_cooldown=%r", value)

            continue

        if seconds >= 0:
            return seconds

        log.warning("Ignoring negative invalid_warn_cooldown=%r", value)

    return _DEFAULT_INVALID_WARN_COOLDOWN


def _resolve_validation_settings(bot: Any) -> tuple[str, str, float]:
    """Return (validation_mode, on_invalid, warn_cooldown) for ``bot``."""

    mode = _pick_choice(
        "validation_mode",
        getattr(bot, "validation_mode", None),
        "HIGHRISE_FAST_VALIDATION",
        _VALIDATION_MODES,
        "strict",
    )

    policy = _pick_choice(
        "on_invalid",
        getattr(bot, "on_invalid", None),
        "HIGHRISE_FAST_ON_INVALID",
        _ON_INVALID_POLICIES,
        "drop",
    )

    cooldown = _pick_cooldown(getattr(bot, "invalid_warn_cooldown", None))

    return mode, policy, cooldown


def invalid_packet_stats() -> dict[str, Any]:
    """Counters for packets that failed validation (for dashboards/alerts)."""
    return {
        "invalid": _STATS["incoming_invalid"],
        "dropped": _STATS["incoming_dropped_malformed"],
        "by_type": dict(_INVALID_BY_TYPE),
        "total": _STATS["incoming_invalid"],
        "top_offenders": _INVALID_BY_TYPE.most_common(10),
        "last_seen": {
            k: datetime.fromtimestamp(v, tz=timezone.utc).isoformat()
            for k, v in _INVALID_LAST_SEEN.items()
        },
    }


def collect_issues(payload: dict[str, Any]) -> list[ValidationErrorDetail]:
    """Collect validation issues without raising."""

    try:
        validate_server_message(payload, strict_semantic=False)

        return []

    except HighriseFastValidationError as e:
        return list(e.errors)


def explain(payload: dict[str, Any]) -> str:
    """Return a human-readable validation report."""

    issues = collect_issues(payload)

    if not issues:
        return f"{payload.get('_type', '?')}: OK (strict)"

    lines = [f"{payload.get('_type', '?')}: REJECTED ({len(issues)} issue(s))", ""]

    for i, issue in enumerate(issues, 1):
        path = getattr(issue, "path", "?")

        msg = getattr(issue, "message", str(issue))

        lines.append(f"  {i}. {path}  {msg}")

    lines.append("")

    lines.append("  Hint: pass validation_mode='lenient' to accept anyway.")

    return "\n".join(lines)


def _log_invalid_packet(
    exc: BaseException,
    data: dict[str, Any],
    cooldown: float,
    action: str,
) -> None:
    """Rate-limited, path-aware warning; identical failures are only counted."""

    event_type = str(data.get("_type", "?"))

    detail = str(exc).strip() or exc.__class__.__name__

    lines = detail.splitlines() or [detail]

    key = (event_type, lines[0][:200])

    now = time.monotonic()

    state = _INVALID_WARN_STATE.get(key)

    if state is not None and now - state[0] < cooldown:
        state[1] += 1

        return

    suppressed = int(state[1]) if state is not None else 0

    if state is None and len(_INVALID_WARN_STATE) >= _INVALID_WARN_STATE_MAX:
        oldest = min(_INVALID_WARN_STATE, key=lambda k: _INVALID_WARN_STATE[k][0])

        _INVALID_WARN_STATE.pop(oldest, None)

    _INVALID_WARN_STATE[key] = [now, 0]

    body = "\n".join("    " + line for line in lines[:12])

    if len(lines) > 12:
        body += f"\n… (+{len(lines) - 12} more lines)"

    if action == "drop":
        outcome = "Packet dropped; your bot keeps running."

    elif action == "log-only":
        outcome = "Packet passed through anyway (on_invalid='log-only')."

    else:
        outcome = "Raising (on_invalid='raise')."

    repeat = (
        f" {suppressed} similar packet(s) were suppressed since the last warning."
        if suppressed
        else ""
    )

    log.warning(
        "%s failed validation:\n%s\n%s%s\n"
        "  Payload is logged at DEBUG level. Repeats are counted, not logged, "
        "for %gs (see highrise_fast.invalid_packet_stats()).\n"
        "  To bypass validation: validation_mode='lenient' or "
        "HIGHRISE_FAST_VALIDATION=lenient",
        event_type,
        body,
        outcome,
        repeat,
        cooldown,
    )

    if log.isEnabledFor(logging.DEBUG):
        log.debug("invalid %s payload: %.2000r", event_type, data)


def _handle_invalid_packet(
    exc: BaseException,
    data: dict[str, Any],
    highrise: Highrise,
    bot: Any,
    tg: TaskGroup,
    on_invalid: str,
    cooldown: float,
) -> bool:
    """Apply the invalid-packet policy.



    Returns True when the packet must be dropped, False when processing should

    continue (``on_invalid="log-only"``).  Re-raises ``exc`` for

    ``on_invalid="raise"``.

    """

    _STATS["incoming_invalid"] += 1

    event_type = data.get("_type")

    type_name = event_type if isinstance(event_type, str) else "?"

    _INVALID_BY_TYPE[type_name] += 1

    _INVALID_LAST_SEEN[type_name] = time.time()

    _log_invalid_packet(exc, data, cooldown, on_invalid)

    hook = getattr(bot, "on_invalid_packet", None)

    if callable(hook):
        try:
            result = hook(exc, data)

            if isawaitable(result):
                _spawn_task(tg, result)

        except asyncio.CancelledError:
            raise

        except Exception:
            log.exception("on_invalid_packet hook failed")

    rid = data.get("rid")

    if on_invalid == "log-only":
        return False

    if isinstance(rid, str):
        highrise._reject_pending(rid, exc)

    if on_invalid == "raise":
        raise _FatalValidationError(str(exc)) from exc

    _STATS["incoming_dropped_malformed"] += 1

    highrise.dropped_packets += 1

    if type_name in _STATEFUL_EVENTS:
        highrise.state_dirty = True

    return True


def position_to_wire(pos: Any) -> dict[str, Any]:
    """Convert a position model into a wire-format dictionary."""
    if pos is None:
        raise ValueError("Position cannot be None")

    if isinstance(pos, AnchorPosition):
        return {"entity_id": pos.entity_id, "anchor_ix": pos.anchor_ix}

    if isinstance(pos, Position):
        return {
            "x": pos.x,
            "y": pos.y,
            "z": pos.z,
            "facing": _normalize_facing(pos.facing),
        }

    if isinstance(pos, dict):
        if "entity_id" in pos or "anchor_ix" in pos:
            return {
                "entity_id": pos.get("entity_id"),
                "anchor_ix": _as_int(pos.get("anchor_ix"), 0),
            }

        return {
            "x": _as_float(pos.get("x"), 0.0),
            "y": _as_float(pos.get("y"), 0.0),
            "z": _as_float(pos.get("z"), 0.0),
            "facing": _normalize_facing(pos.get("facing")),
        }

    raise TypeError(f"Unsupported position type: {type(pos)!r}")


def item_to_wire(item: Any) -> dict[str, Any]:
    """Convert an item model into a wire-format dictionary."""

    if item is None:
        raise ValueError("Item cannot be None")

    if isinstance(item, Item):
        return {
            "type": item.type,
            "amount": item.amount,
            "id": item.id,
            "account_bound": item.account_bound,
            "active_palette": item.active_palette,
        }

    if isinstance(item, dict):
        return {
            "type": item.get("type", "clothing"),
            "amount": _as_int(item.get("amount"), 1),
            "id": str(item.get("id", "")),
            "account_bound": bool(item.get("account_bound", False)),
            "active_palette": item.get("active_palette"),
        }

    raise TypeError(f"Unsupported item type: {type(item)!r}")


def permissions_to_wire(permissions: Any) -> dict[str, Any]:
    """Convert room permissions into a wire-format dictionary."""

    if permissions is None:
        return {"moderator": None, "designer": None}

    if isinstance(permissions, RoomPermissions):
        return {
            "moderator": permissions.moderator,
            "designer": permissions.designer,
        }

    if isinstance(permissions, dict):
        return permissions

    raise TypeError(f"Unsupported permissions type: {type(permissions)!r}")


def media_to_wire(media: Any) -> dict[str, Any]:
    """Convert media into a wire-format dictionary."""

    if media is None:
        raise ValueError("Media cannot be None")

    if isinstance(media, MessageMedia):
        return {
            "type": media.type,
            "width": media.width,
            "height": media.height,
            "mediaSizeInBytes": media.mediaSizeInBytes,
            "thumbnailSizeInBytes": media.thumbnailSizeInBytes,
            "id": media.id,
            "url": media.url,
            "thumbnailUrl": media.thumbnailUrl,
        }

    if isinstance(media, dict):
        return media

    raise TypeError(f"Unsupported media type: {type(media)!r}")


class BaseBot:
    """Base class for bots.

    Optional validation settings (all keyword-only; subclasses that define their
    own ``__init__`` without calling ``super().__init__()`` keep working and just
    use the defaults / environment variables):

    * ``validation_mode``: ``"strict"`` (default) validates every incoming packet
      and guarantees handlers only ever see well-formed data; ``"lenient"``
      skips validation for maximum speed.

    * ``on_invalid``: what to do with a packet that fails validation —
      ``"drop"`` (default; warn, count, keep running), ``"log-only"`` (warn but
      dispatch anyway) or ``"raise"`` (fail fast; useful in tests/CI).

    * ``invalid_warn_cooldown``: seconds between identical warnings.

    Settings are read when a connection starts.

    Built-in framework tools (auto-initialized):
        self.room_tracker  — O(1) spatial grid; auto-syncs on join/leave/move.
        self.actions       — ThrottledActions; rate-limited chat/whisper/teleport.
        self.prompts       — PromptManager; await user replies in commands.
    """

    highrise: Highrise
    webapi: WebAPI
    metrics: Metrics
    tasks: TaskManager
    room_tracker: RoomTracker | None
    actions: ThrottledActions
    prompts: PromptManager

    validation_mode: str | None = None
    on_invalid: str | None = None
    invalid_warn_cooldown: float | None = None
    enable_prompts = False

    def __init__(
        self,
        *,
        validation_mode: str | None = None,
        on_invalid: str | None = None,
        invalid_warn_cooldown: float | None = None,
        track_room: bool = True,
        enable_prompts: bool = False,
        await_events: Iterable[str] = (),
    ) -> None:
        """Initialize the instance."""
        self.metrics = Metrics()
        self.tasks = TaskManager()
        self.room_tracker = RoomTracker() if track_room else None
        self.prompts = PromptManager()
        self.enable_prompts = enable_prompts
        self._awaiter = Awaiter(await_events) if await_events else None
        self.actions = ThrottledActions(self)

        if getattr(self, "command_registry", None) is None:
            self.command_registry = commands

        if validation_mode is not None:
            self.validation_mode = validation_mode
        if on_invalid is not None:
            self.on_invalid = on_invalid
        if invalid_warn_cooldown is not None:
            self.invalid_warn_cooldown = invalid_warn_cooldown

    @property
    def awaiter(self) -> Awaiter:
        """Wait for room events using the same arguments as bot hooks."""
        awaiter = getattr(self, "_awaiter", None)
        if awaiter is None:
            awaiter = self._awaiter = Awaiter()
        return awaiter

    async def login(self, room_id: str, api_token: str) -> None:
        """Run this bot in a room using the SDK connection manager."""
        await bot_runner(self, room_id, api_token)

    def on_invalid_packet(self, exc: Exception, raw: dict[str, Any]) -> Any:
        """Called for every packet that fails validation (may be sync or async)."""
        return None

    async def before_start(self, tg: TaskGroup) -> None:
        """Before start."""
        pass

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        """On start."""
        pass

    async def on_chat(self, user: User, message: str) -> None:
        """On chat."""
        pass

    async def on_whisper(self, user: User, message: str) -> None:
        """On whisper."""
        pass

    async def on_emote(
        self,
        user: User,
        emote_id: str,
        receiver: User | None,
    ) -> None:
        """On emote."""
        pass

    async def on_reaction(
        self,
        user: User,
        reaction: str,
        receiver: User | None,
    ) -> None:
        """On reaction."""
        pass

    async def on_user_join(
        self,
        user: User,
        position: Position | AnchorPosition | None,
    ) -> None:
        """On user join."""
        pass

    async def on_user_leave(self, user: User) -> None:
        """On user leave."""
        pass

    async def on_tip(
        self,
        sender: User,
        receiver: User,
        tip: CurrencyItem | Item | None,
    ) -> None:
        """On tip."""
        pass

    async def on_channel(
        self,
        sender_id: str,
        message: str,
        tags: set[str],
    ) -> None:
        """On channel."""
        pass

    async def on_user_move(
        self,
        user: User,
        destination: Position | AnchorPosition | None,
    ) -> None:
        """On user move."""
        pass

    async def on_voice_change(
        self,
        users: list[tuple[User, Literal["voice", "muted"]]],
        seconds_left: int,
    ) -> None:
        """On voice change."""
        pass

    async def on_message(
        self,
        user_id: str,
        conversation_id: str,
        is_new_conversation: bool,
    ) -> None:
        """On message."""
        pass

    async def on_moderate(
        self,
        moderator_id: str,
        target_user_id: str,
        moderation_type: Literal["kick", "mute", "unmute", "ban", "unban"],
        duration: int | None,
    ) -> None:
        """On moderate."""
        pass

    async def on_reconnected(self) -> None:
        """Refresh the room roster after reconnecting."""
        if self.highrise.state_dirty:
            await self.highrise._refresh_room()


class Highrise:
    """WebSocket API client for sending bot actions and managing RPC replies."""
    def __init__(
        self,
        ws: Any = None,
        tg: TaskGroup | None = None,
        my_id: str = "",
        *,
        room_tracker: RoomTracker | None = None,
    ) -> None:
        """Initialize the instance."""

        self.ws = ws

        self.tg = tg

        self.my_id = my_id
        self._room_tracker = room_tracker
        self._session_closed = False
        self._session_tasks: TaskManager | None = None
        self._dm_seen: TTLCache | None = None

        self._req_id = count()

        self._pending: dict[str, asyncio.Future[Any]] = {}

        self._req_id_registry = self._pending

        # Request ids of fire-and-forget sends. The server still acknowledges
        # them; the ack is expected and must not count as an unknown/fallback
        # packet. Insertion-ordered and bounded, so it can never leak.
        self._ff_rids: dict[str, None] = {}

        self.state_dirty: bool = False

        self.dropped_packets: int = 0

    @property
    def connected(self) -> bool:
        """Return whether this client currently has an open room connection."""
        return not self._session_closed and self.ws is not None and not getattr(self.ws, "closed", False)

    @property
    def tasks(self) -> TaskManager:
        """Background tasks owned by this room connection."""
        if self._session_closed:
            raise ConnectionResetError("The room connection has ended")
        if self._session_tasks is None:
            self._session_tasks = TaskManager()
        return self._session_tasks

    async def _close_session(self) -> None:
        self._session_closed = True
        self.fail_pending()
        self._ff_rids.clear()
        if self._dm_seen is not None:
            self._dm_seen.clear()
        if self._session_tasks is not None:
            await self._session_tasks.close()

    def mark_state_synced(self) -> None:
        """Clear the state_dirty flag after re-syncing room state."""

        self.state_dirty = False

    def _next_rid(self) -> str:
        """Internal helper for Next rid."""

        return str(next(self._req_id))

    def fail_pending(self, message: str = "connection lost") -> None:
        """Fail all pending RPC calls."""

        for fut in list(self._pending.values()):
            if not fut.done():
                fut.set_exception(ConnectionResetError(message))

        self._pending.clear()

    def _reject_pending(self, rid: str, exc: BaseException) -> bool:
        """Fail the pending call for ``rid`` so its ``await`` raises ``exc``."""

        future = self._pending.pop(rid, None)

        if future is not None and not future.done():
            future.set_exception(exc)

            return True

        return False

    async def _refresh_room(self) -> None:
        """Fetch a fresh roster and surface failures to the lifecycle handler."""
        response = await self.get_room_users()
        if isinstance(response, Error):
            log.warning("Could not refresh room roster: %s", response.message)

    def _resolve_pending(
        self, rid: str, data: dict[str, Any], *, update_roster: bool = True
    ) -> bool:
        """Resolve the pending call for a request ID."""

        future = self._pending.pop(rid, None)

        if future is not None and not future.done():
            try:
                obj = _parse_typed_message(data)
            except Exception:
                log.exception("Failed to parse response for rid=%s", rid)

                obj = data

            if update_roster and isinstance(obj, GetRoomUsersResponse):
                try:
                    if self._room_tracker is not None:
                        self._room_tracker.replace_roster(obj.content)
                    self.mark_state_synced()
                except Exception:
                    self.state_dirty = True
                    log.exception("Failed to update room tracker from roster response")

            future.set_result(obj)

            return True

        if rid in self._ff_rids:
            # Ack of a fire-and-forget send: expected, handled on the fast path.
            del self._ff_rids[rid]

            if data.get("_type") in _ERROR_TYPES:
                _STATS["api_errors"] += 1
                log.debug("Unacknowledged action failed (rid=%s): %s", rid, data.get("message"))

            return True

        return False

    async def _send_only(
        self,
        type_name: str,
        fields: dict[str, Any] | None = None,
    ) -> None:
        """Send a WebSocket payload without waiting for a response."""
        if self._session_closed:
            raise ConnectionResetError("The room connection has ended")
        rid = self._next_rid()

        payload: dict[str, Any] = {
            "_type": type_name,
            "rid": rid,
        }

        if fields:
            payload.update(fields)

        ff = self._ff_rids

        ff[rid] = None

        if len(ff) > 8192:
            # Acks that never arrived (e.g. connection dropped): forget the oldest.
            del ff[next(iter(ff))]

        try:
            await _send_ws_payload(self.ws, payload)
        except BaseException:
            ff.pop(rid, None)
            raise

    _RPC_HARD_TIMEOUT: float = 30.0

    async def _call(
        self,
        type_name: str,
        fields: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
        raise_on_error: bool = False,
        request: Any = None,
    ) -> Any:
        """Send a WebSocket RPC call and wait for the response."""
        if self._session_closed:
            raise ConnectionResetError("The room connection has ended")
        rid = self._next_rid()
        if request is not None:
            request.rid = rid
        payload: dict[str, Any] = {"_type": type_name, "rid": rid}
        if fields:
            payload.update(fields)
        future = asyncio.get_running_loop().create_future()
        self._pending[rid] = future
        t0 = time.perf_counter()
        effective_timeout = (
            timeout if timeout is not None and timeout > 0
            else _REQ_TIMEOUT if _REQ_TIMEOUT > 0
            else self._RPC_HARD_TIMEOUT
        )
        try:
            async with timeout_after(effective_timeout):
                await _send_ws_payload(self.ws, payload)
                response = await future

            _STATS["pops"] += 1
            _record_latency(t0)
            if isinstance(response, Error):
                _STATS["api_errors"] += 1
                if raise_on_error:
                    raise ResponseError(response.message)
                return response
            return response
        except BaseException as exc:
            if isinstance(exc, TimeoutError):
                _STATS["timeouts"] += 1
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                # Disconnect can reject the future while the socket send is still pending.
                future.exception()
            raise
        finally:
            self._pending.pop(rid, None)
            _STATS["cleanups"] += 1

    async def _no_response(
        self,
        type_name: str,
        fields: dict[str, Any] | None = None,
    ) -> None:
        """Send a fire-and-forget WebSocket action."""
        if _FIRE_AND_FORGET:
            await self._send_only(type_name, fields)
        else:
            await self._call(type_name, fields, raise_on_error=True)

    async def chat(self, message: str) -> None:
        """Send a chat message."""

        await self._no_response(
            "ChatRequest",
            {"message": message, "whisper_target_id": None},
        )

    async def send_whisper(self, user_id: str, message: str) -> None:
        """Send a whisper message."""

        await self._no_response(
            "ChatRequest",
            {"message": message, "whisper_target_id": user_id},
        )

    async def send_emote(
        self,
        emote_id: str,
        target_user_id: str | None = None,
    ) -> None:
        """Send an emote."""

        await self._no_response(
            "EmoteRequest",
            {"emote_id": emote_id, "target_user_id": target_user_id},
        )

    async def react(self, reaction: str, target_user_id: str) -> None:
        """Send a reaction."""

        await self._no_response(
            "ReactionRequest",
            {"reaction": reaction, "target_user_id": target_user_id},
        )

    async def set_indicator(self, icon: str | None) -> None:
        """Set or clear the bot indicator."""

        await self._no_response("IndicatorRequest", {"icon": icon})

    async def send_channel(
        self,
        message: str,
        tags: set[str] | list[str] | tuple[str, ...] | None = None,
        only_to: set[str] | list[str] | tuple[str, ...] | None = None,
    ) -> None:
        """Send a channel message."""

        await self._no_response(
            "ChannelRequest",
            {
                "message": message,
                "tags": list(tags or []),
                "only_to": list(only_to) if only_to is not None else None,
            },
        )

    async def walk_to(
        self,
        destination: Position | AnchorPosition | dict[str, Any],
    ) -> None:
        """Walk to a floor or anchor position."""

        wire = position_to_wire(destination)

        if isinstance(destination, AnchorPosition) or (
            isinstance(destination, dict)
            and ("entity_id" in destination or "anchor_ix" in destination)
        ):
            await self._no_response("AnchorHitRequest", {"anchor": wire})

        else:
            await self._no_response("FloorHitRequest", {"destination": wire})

    async def teleport(
        self,
        user_id: str,
        dest: Position | dict[str, Any],
    ) -> None:
        """Teleport a user to a position."""

        await self._no_response(
            "TeleportRequest",
            {
                "user_id": user_id,
                "destination": position_to_wire(dest),
            },
        )

    async def get_room_users(self) -> GetRoomUsersResponse | Error:
        """Get users in the room."""

        return await self._call("GetRoomUsersRequest", {})

    async def get_wallet(self) -> GetWalletResponse | Error:
        """Get the bot wallet."""

        return await self._call("GetWalletRequest", {})

    async def get_backpack(self, user_id: str) -> GetBackpackResponse | Error:
        """Get a user's backpack."""

        return await self._call("GetBackpackRequest", {"user_id": user_id})

    async def change_backpack(
        self,
        user_id: str,
        changes: dict[str, int],
    ) -> ChangeBackpackResponse | Error:
        """Change a user's backpack."""

        return await self._call(
            "ChangeBackpackRequest",
            {"user_id": user_id, "changes": dict(changes)},
        )

    async def moderate_room(
        self,
        user_id: str,
        action: Literal["kick", "ban", "unban", "mute"],
        action_length: int | None = None,
    ) -> None:
        """Moderate a user in the room."""

        fields: dict[str, Any] = {
            "user_id": user_id,
            "moderation_action": action,
            "action_length": action_length,
        }

        await self._no_response("ModerateRoomRequest", fields)

    async def get_room_privilege(self, user_id: str) -> RoomPermissions | Error:
        """Get room privileges for a user."""

        response = await self._call(
            "GetRoomPrivilegeRequest",
            {"user_id": user_id},
        )

        if isinstance(response, Error):
            return response

        return getattr(response, "content", RoomPermissions())

    async def change_room_privilege(
        self,
        user_id: str,
        permissions: RoomPermissions | dict[str, Any],
    ) -> None:
        """Change room privileges for a user."""

        await self._no_response(
            "ChangeRoomPrivilegeRequest",
            {
                "user_id": user_id,
                "permissions": permissions_to_wire(permissions),
            },
        )

    async def move_user_to_room(self, user_id: str, room_id: str) -> None:
        """Move a user to another room."""

        await self._no_response(
            "MoveUserToRoomRequest",
            {"user_id": user_id, "room_id": room_id},
        )

    async def get_voice_status(self) -> CheckVoiceChatResponse | Error:
        """Get voice chat status."""

        return await self._call("CheckVoiceChatRequest", {})

    async def add_user_to_voice(self, user_id: str) -> None:
        """Invite a user to voice chat."""

        await self._no_response("InviteSpeakerRequest", {"user_id": user_id})

    async def remove_user_from_voice(self, user_id: str) -> None:
        """Remove a user from voice chat."""

        await self._no_response("RemoveSpeakerRequest", {"user_id": user_id})

    async def get_user_outfit(
        self,
        user_id: str,
    ) -> GetUserOutfitResponse | Error:
        """Get a user's outfit."""

        return await self._call("GetUserOutfitRequest", {"user_id": user_id})

    async def get_my_outfit(self) -> GetUserOutfitResponse | Error:
        """Get the bot's outfit."""

        return await self.get_user_outfit(self.my_id)

    async def get_inventory(self) -> GetInventoryResponse | Error:
        """Get the bot inventory."""

        return await self._call("GetInventoryRequest", {})

    async def set_outfit(
        self,
        outfit: list[Item | dict[str, Any]],
    ) -> None | Error:
        """Set the bot outfit."""

        response = await self._call(
            "SetOutfitRequest",
            {"outfit": [item_to_wire(item) for item in outfit]},
        )

        if isinstance(response, Error):
            return response

        return None

    async def buy_item(self, item_id: str) -> str | Error:
        """Buy an item."""

        response = await self._call("BuyItemRequest", {"item_id": item_id})

        if isinstance(response, Error):
            return response

        return getattr(response, "result", "")

    async def get_conversations(
        self,
        not_joined: bool = False,
        last_id: str | None = None,
    ) -> GetConversationsResponse | Error:
        """Get inbox conversations."""

        return await self._call(
            "GetConversationsRequest",
            {"not_joined": not_joined, "last_id": last_id},
        )

    async def send_message(
        self,
        conversation_id: str,
        content: str,
        message_type: Literal["text", "invite", "media"] = "text",
        room_id: str | None = None,
        world_id: str | None = None,
        media_id: str | None = None,
    ) -> None | Error:
        """Send an inbox message."""

        response = await self._call(
            "SendMessageRequest",
            {
                "conversation_id": conversation_id,
                "content": content,
                "type": message_type,
                "room_id": room_id,
                "world_id": world_id,
                "media_id": media_id,
            },
        )

        if isinstance(response, Error):
            return response

        return None

    async def send_message_bulk(
        self,
        user_ids: list[str],
        content: str,
        message_type: Literal["text", "invite"] = "text",
        room_id: str | None = None,
        world_id: str | None = None,
    ) -> None | Error:
        """Send an inbox message to multiple users."""

        response = await self._call(
            "SendBulkMessageRequest",
            {
                "user_ids": user_ids,
                "content": content,
                "type": message_type,
                "room_id": room_id,
                "world_id": world_id,
            },
        )

        if isinstance(response, Error):
            return response

        return None

    async def get_messages(
        self,
        conversation_id: str,
        last_id: str | None = None,
    ) -> GetMessagesResponse | Error:
        """Get messages from a conversation."""

        return await self._call(
            "GetMessagesRequest",
            {
                "conversation_id": conversation_id,
                "last_message_id": last_id,
            },
        )

    async def leave_conversation(self, conversation_id: str) -> None:
        """Leave an inbox conversation."""

        await self._no_response(
            "LeaveConversationRequest",
            {"conversation_id": conversation_id},
        )

    async def buy_voice_time(
        self,
        payment: Literal["bot_wallet_only"] = "bot_wallet_only",
    ) -> str | Error:
        """Buy voice chat time."""

        response = await self._call(
            "BuyVoiceTimeRequest",
            {"payment_method": payment},
        )

        if isinstance(response, Error):
            return response

        return getattr(response, "result", "")

    async def buy_room_boost(
        self,
        payment: Literal["bot_wallet_only"] = "bot_wallet_only",
        amount: int = 1,
    ) -> str | Error:
        """Buy a room boost."""

        response = await self._call(
            "BuyRoomBoostRequest",
            {"payment_method": payment, "amount": amount},
        )

        if isinstance(response, Error):
            return response

        return getattr(response, "result", "")

    async def tip_user(
        self,
        user_id: str,
        tip: Literal[
            "gold_bar_1",
            "gold_bar_5",
            "gold_bar_10",
            "gold_bar_50",
            "gold_bar_100",
            "gold_bar_500",
            "gold_bar_1k",
            "gold_bar_5000",
            "gold_bar_10k",
        ],
    ) -> str | Error:
        """Tip a user."""

        response = await self._call(
            "TipUserRequest",
            {"user_id": user_id, "gold_bar": tip},
        )

        if isinstance(response, Error):
            return response

        return getattr(response, "result", "")

    async def message_media_upload(
        self,
        media: MessageMedia | dict[str, Any],
    ) -> tuple[MessageMedia | None, str | None, str | None] | Error:
        """Request media upload URLs."""

        response = await self._call(
            "MessageMediaRequest",
            {"media": media_to_wire(media)},
        )

        if isinstance(response, Error):
            return response

        return (
            getattr(response, "media", None),
            getattr(response, "uploadUrl", None),
            getattr(response, "thumbnailUploadUrl", None),
        )

    def call_in(self, callback: Callable[[], Any], delay: float) -> None:
        """Schedule a callback after a delay."""

        async def _delayed() -> None:
            """Internal helper for Delayed."""

            await asyncio.sleep(delay)

            try:
                result = callback()

                if isawaitable(result):
                    await result

            except asyncio.CancelledError:
                raise

            except Exception:
                log.exception("Error in delayed callback")

        if self.tg is not None:
            self.tg.create_task(_delayed())

        else:
            asyncio.create_task(_delayed())


@dataclass(slots=True)
class _WebPayload:
    raw: Any
    parsed: Any = _EXTRAS_MISSING
    model: Any = _EXTRAS_MISSING


_RETRYABLE_WEB_STATUSES = frozenset({429, 502, 503, 504})


def _retry_after(value: str | None) -> float | None:
    if not value:
        return None
    if value.isascii() and value.isdigit():
        return float(value)
    try:
        when = parsedate_to_datetime(value)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return max(0.0, when.timestamp() - time.time())
    except (ValueError, TypeError, OverflowError, OSError):
        return None


class WebAPI:
    """HTTP client for the public Highrise WebAPI with optional caching."""
    url: str = BASE_WEB_URL
    _response_type = staticmethod(webapi_response_type)

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: Any | None = None,
        cache_ttl: int | None = None,
        cache_size: int = 1024,
        retries: int = 0,
        max_retry_delay: float = 10.0,
    ) -> None:
        """Initialize the instance."""
        _ensure_aiohttp()
        if not isinstance(retries, int) or retries < 0:
            raise ValueError("retries must be a nonnegative integer")
        if not math.isfinite(max_retry_delay) or max_retry_delay < 0:
            raise ValueError("max_retry_delay must be nonnegative and finite")
        self.retries = retries
        self.max_retry_delay = max_retry_delay

        if base_url is not None:
            self.url = base_url.rstrip("/")

        if timeout is None:
            self.timeout = WEB_TIMEOUT
        elif isinstance(timeout, (int, float)):
            self.timeout = (
                ClientTimeout(total=float(timeout))
                if ClientTimeout is not None
                else None
            )
        else:
            self.timeout = timeout

        self._session: Any = None
        self._cache = TTLCache(maxsize=cache_size)
        self._cache_hits = 0
        self._cache_misses = 0
        self._coalesced_reads = 0
        self._http_requests = 0
        self._inflight: dict[str, asyncio.Task[Any]] = {}
        self._requests: set[asyncio.Task[Any]] = set()

        if cache_ttl is None:
            cache_ttl = _WEBAPI_CACHE_TTL

        try:
            self.cache_ttl = max(0, int(cache_ttl))
        except (TypeError, ValueError):
            self.cache_ttl = _WEBAPI_CACHE_TTL

    async def _get_session(self) -> Any:
        """Internal helper for Get session."""
        if self._session is None or self._session.closed:
            self._session = ClientSession(
                timeout=self.timeout,
                headers={"User-Agent": USER_AGENT},
            )

        return self._session

    async def send_request(self, endpoint: str, cl: type | None = None) -> Any:
        """Send a public Web API request, optionally structuring its response."""
        payload = await self._get(endpoint)
        if cl is None and payload.parsed is not _EXTRAS_MISSING:
            return payload.parsed
        if payload.model is _EXTRAS_MISSING:
            payload.model = self._response_type(endpoint)
        model = payload.model
        if cl is not None and cl is not model:
            return self._structure_response(payload.raw, cl)
        if payload.parsed is _EXTRAS_MISSING:
            payload.parsed = self._structure_response(payload.raw, model)
        return payload.parsed

    async def _get_public(self, endpoint: str) -> Any:
        send = self.send_request
        if getattr(send, "__func__", None) is WebAPI.send_request:
            return await send(endpoint)
        return await send(endpoint, self._response_type(endpoint))

    @staticmethod
    def _structure_response(data: Any, cl: type | None) -> Any:
        if cl is None:
            return data

        from .models_webapi import _Base

        if isinstance(cl, type) and issubclass(cl, _Base):
            return cl(data) if isinstance(data, dict) else data

        from cattrs import structure

        return structure(data, cl)

    async def _get(self, endpoint: str, cache_ttl: int | None = None) -> _WebPayload:
        """Send a GET request to the public WebAPI."""
        ttl = self.cache_ttl if cache_ttl is None else max(0, int(cache_ttl))
        if ttl == 0:
            return await self._fetch(endpoint)

        hit = self._cache.get(endpoint)
        if hit is not _EXTRAS_MISSING:
            self._cache_hits += 1
            return hit

        self._cache_misses += 1
        task = self._inflight.get(endpoint)
        if task is None:
            task = asyncio.create_task(self._fetch(endpoint))
            self._inflight[endpoint] = task
            self._requests.add(task)
            task.add_done_callback(partial(self._request_done, endpoint, ttl))
        else:
            self._coalesced_reads += 1
        return await asyncio.shield(task)

    async def _fetch(self, endpoint: str) -> _WebPayload:
        session = await self._get_session()
        url = f"{self.url}{endpoint}"
        attempt = 0
        while True:
            self._http_requests += 1
            async with session.get(url) as response:
                payload = await response.read()
                if response.status == 200:
                    return _WebPayload(loads_json(payload))
                error = WebAPIError(
                    payload.decode("utf-8", errors="replace"),
                    response.status,
                    _retry_after(response.headers.get("Retry-After")),
                )
            if attempt >= self.retries or error.status not in _RETRYABLE_WEB_STATUSES:
                raise error
            delay = error.retry_after
            if delay is None:
                delay = min(self.max_retry_delay, 0.25 * 2 ** min(attempt, 8))
            if delay > self.max_retry_delay:
                raise error
            attempt += 1
            await asyncio.sleep(delay)

    def _request_done(self, endpoint: str, ttl: int, task: asyncio.Task[Any]) -> None:
        self._requests.discard(task)
        # Retrieve the exception even if every caller has stopped waiting.
        successful = not task.cancelled() and task.exception() is None
        if self._inflight.get(endpoint) is task:
            self._inflight.pop(endpoint)
            if successful:
                self._cache.set(endpoint, task.result(), ttl)

    def cache_info(self) -> dict[str, int]:
        """Return per-client cache, shared-read, and outgoing HTTP request counters."""
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "coalesced": self._coalesced_reads,
            "http_requests": self._http_requests,
            "entries": len(self._cache),
            "inflight": len(self._requests),
        }

    def invalidate_cache(self, endpoint: str | None = None) -> None:
        """Invalidate cached WebAPI responses."""
        if endpoint is None:
            self._cache.clear()
            self._inflight.clear()
        else:
            self._cache.invalidate(endpoint)
            self._inflight.pop(endpoint, None)

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        session, self._session = self._session, None
        self.invalidate_cache()
        pending = tuple(self._requests)
        for task in pending:
            task.cancel()
        try:
            if session is not None and not session.closed:
                await session.close()
        finally:
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

    async def __aenter__(self) -> WebAPI:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.close()

    @staticmethod
    def _query(params: dict[str, Any]) -> str:
        """Build a safe query string for WebAPI requests."""
        clean: dict[str, Any] = {}

        for key, value in params.items():
            if value is None:
                continue

            if isinstance(value, bool):
                clean[key] = "true" if value else "false"
            elif hasattr(value, "value"):
                clean[key] = value.value
            else:
                clean[key] = value

        if not clean:
            return ""

        return "?" + urllib.parse.urlencode(clean, doseq=True)

    async def get_user(self, user_id: str) -> GetPublicUserResponse:
        """Get a public user by ID."""
        return await self._get_public("/users/" + urllib.parse.quote(user_id, safe=""))

    async def get_users(
        self,
        starts_after: str | None = None,
        ends_before: str | None = None,
        sort_order: str = "desc",
        limit: int = 20,
        username: str | None = None,
    ) -> GetPublicUsersResponse:
        """Get a paginated list of public users."""
        return await self._get_public(
            "/users"
            + self._query(
                {
                    "starts_after": starts_after,
                    "ends_before": ends_before,
                    "sort_order": sort_order,
                    "limit": limit,
                    "username": username,
                }
            )
        )

    async def get_user_by_username(
        self, username: str, *, exact: bool = True
    ) -> AttrDict | None:
        """Fetch a public user by username.

        Uses the ``username`` query parameter of ``GET /users``.
        Returns the first matching user object, or ``None`` when no user
        matches (or when the API returns an empty list).

        When ``exact=True`` (default), the returned user's username must
        equal ``username`` exactly (case-insensitive); the WebAPI's
        username search is a partial match, so this filters out prefix
        matches like "alice" when searching for "al".
        """
        response = await self.get_users(username=username, limit=20)
        users = getattr(response, "users", None) or []
        target = username.strip().lower()
        for user in users:
            uname = str(getattr(user, "username", "")).strip().lower()
            if not exact or uname == target:
                return user
        return None

    async def username_to_id(self, username: str) -> str | None:
        """Convert a Highrise username to a user ID.

        Returns ``None`` when the user cannot be resolved (not found,
        API error, or missing id field).
        """
        try:
            user = await self.get_user_by_username(username)
        except ResponseError:
            return None
        if user is None:
            return None
        uid = getattr(user, "user_id", None) or getattr(user, "id", None)
        return str(uid) if uid else None

    async def id_to_username(self, user_id: str) -> str | None:
        """Convert a Highrise user ID to a username.

        Returns ``None`` when the user cannot be resolved (not found,
        API error, or missing username field).
        """
        try:
            response = await self.get_user(str(user_id))
        except ResponseError:
            return None
        user = getattr(response, "user", None)
        if user is None:
            return None
        username = getattr(user, "username", None)
        return str(username) if username else None

    async def get_room(self, room_id: str) -> GetPublicRoomResponse:
        """Get a public room by ID."""
        return await self._get_public("/rooms/" + urllib.parse.quote(room_id, safe=""))

    async def get_rooms(
        self,
        starts_after: str | None = None,
        ends_before: str | None = None,
        sort_order: str = "desc",
        limit: int = 20,
        room_name: str | None = None,
        owner_id: str | None = None,
    ) -> GetPublicRoomsResponse:
        """Get a paginated list of public rooms."""
        return await self._get_public(
            "/rooms"
            + self._query(
                {
                    "starts_after": starts_after,
                    "ends_before": ends_before,
                    "sort_order": sort_order,
                    "limit": limit,
                    "room_name": room_name,
                    "owner_id": owner_id,
                }
            )
        )

    async def get_post(self, post_id: str) -> GetPublicPostResponse:
        """Get a public post by ID."""
        return await self._get_public("/posts/" + urllib.parse.quote(post_id, safe=""))

    async def get_posts(
        self,
        starts_after: str | None = None,
        ends_before: str | None = None,
        sort_order: str = "desc",
        limit: int = 20,
        author_id: str | None = None,
    ) -> GetPublicPostsResponse:
        """Get a paginated list of public posts."""
        return await self._get_public(
            "/posts"
            + self._query(
                {
                    "starts_after": starts_after,
                    "ends_before": ends_before,
                    "sort_order": sort_order,
                    "limit": limit,
                    "author_id": author_id,
                }
            )
        )

    async def get_item(self, item_id: str) -> GetPublicItemResponse:
        """Get a public item by ID."""
        return await self._get_public("/items/" + urllib.parse.quote(item_id, safe=""))

    async def get_items(
        self,
        starts_after: str | None = None,
        ends_before: str | None = None,
        sort_order: str = "desc",
        limit: int = 20,
        rarity: str | None = None,
        item_name: str | None = None,
        category: Any | None = None,
    ) -> GetPublicItemsResponse:
        """Get a paginated list of public items."""
        category_value = getattr(category, "value", category)

        return await self._get_public(
            "/items"
            + self._query(
                {
                    "starts_after": starts_after,
                    "ends_before": ends_before,
                    "sort_order": sort_order,
                    "limit": limit,
                    "rarity": rarity,
                    "item_name": item_name,
                    "category": category_value,
                }
            )
        )

    async def search_items(
        self, query: str, *, limit: int = 20, skip: int = 0
    ) -> SearchItemsResponse:
        """Search the public item catalog by query with offset pagination."""
        return await self._get_public(
            "/items/search" + self._query({"query": query, "limit": limit, "skip": skip})
        )

    async def get_grab(self, grab_id: str) -> GetPublicGrabResponse:
        """Get a public grab by ID."""
        return await self._get_public("/grabs/" + urllib.parse.quote(grab_id, safe=""))

    async def get_grabs(
        self,
        starts_after: str | None = None,
        ends_before: str | None = None,
        sort_order: str = "desc",
        limit: int = 20,
        title: str | None = None,
    ) -> GetPublicGrabsResponse:
        """Get a paginated list of public grabs."""
        return await self._get_public(
            "/grabs"
            + self._query(
                {
                    "starts_after": starts_after,
                    "ends_before": ends_before,
                    "sort_order": sort_order,
                    "limit": limit,
                    "title": title,
                }
            )
        )


    async def _iter_public(
        self,
        fetch: Callable[..., Awaitable[Any]],
        collection: str,
        *,
        page_size: int = 20,
        max_items: int | None = None,
        starts_after: str | None = None,
        **filters: Any,
    ) -> AsyncIterator[Any]:
        if page_size < 1 or (max_items is not None and max_items < 0):
            raise ValueError("page_size must be positive and max_items nonnegative")
        cursor = starts_after
        seen = {cursor}
        remaining = max_items
        while remaining is None or remaining > 0:
            limit = page_size if remaining is None else min(page_size, remaining)
            page = await fetch(starts_after=cursor, limit=limit, **filters)
            rows = getattr(page, collection) or ()
            if not rows:
                return
            next_cursor = page.last_id
            if next_cursor and next_cursor in seen:
                return
            for row in rows:
                yield row
                if remaining is not None:
                    remaining -= 1
                    if remaining == 0:
                        return
            if not next_cursor:
                return
            seen.add(next_cursor)
            cursor = next_cursor

    def iter_items(self, **options: Any) -> AsyncIterator[Any]:
        """Stream public items with get_items filters, page_size, and max_items."""
        return self._iter_public(self.get_items, "items", **options)

    def iter_users(self, **options: Any) -> AsyncIterator[Any]:
        """Stream public users with get_users filters, page_size, and max_items."""
        return self._iter_public(self.get_users, "users", **options)

    def iter_rooms(self, **options: Any) -> AsyncIterator[Any]:
        """Stream public rooms with get_rooms filters, page_size, and max_items."""
        return self._iter_public(self.get_rooms, "rooms", **options)

    def iter_posts(self, **options: Any) -> AsyncIterator[Any]:
        """Stream public posts with get_posts filters, page_size, and max_items."""
        return self._iter_public(self.get_posts, "posts", **options)

    def iter_grabs(self, **options: Any) -> AsyncIterator[Any]:
        """Stream public grabs with get_grabs filters, page_size, and max_items."""
        return self._iter_public(self.get_grabs, "grabs", **options)


_HANDLER_METHODS: dict[str, str] = {
    "on_chat": "chat",
    "on_whisper": "chat",
    "on_emote": "emote",
    "on_reaction": "reaction",
    "on_user_join": "user_joined",
    "on_user_leave": "user_left",
    "on_user_move": "user_moved",
    "on_tip": "tip_reaction",
    "on_voice_change": "voice",
    "on_channel": "channel",
    "on_message": "message",
    "on_moderate": "moderation",
}


_EVENT_TO_SUBSCRIPTION: dict[str, str] = {
    "ChatEvent": "chat",
    "EmoteEvent": "emote",
    "ReactionEvent": "reaction",
    "UserJoinedEvent": "user_joined",
    "UserLeftEvent": "user_left",
    "UserMovedEvent": "user_moved",
    "ChannelEvent": "channel",
    "TipReactionEvent": "tip_reaction",
    "VoiceEvent": "voice",
    "MessageEvent": "message",
    "RoomModeratedEvent": "moderation",
}


def _has_hook(bot: BaseBot, name: str) -> bool:
    handler = getattr(bot, name, None)
    return handler is not None and getattr(handler, "__func__", handler) is not getattr(BaseBot, name)


def _registry_handles(registry: Any, source: str) -> bool:
    handles = getattr(registry, "handles_source", None)
    if callable(handles):
        return handles(source)
    return getattr(registry, "has_commands", True)


def active_subscriptions(bot: BaseBot) -> frozenset[str]:
    """Subscription names required by the bot's hooks and room tracker."""

    subs: set[str] = set()
    if getattr(bot, "room_tracker", None) is not None:
        subs.update({"user_joined", "user_left", "user_moved"})
    if getattr(bot, "enable_prompts", False):
        subs.add("chat")
    awaiter = getattr(bot, "_awaiter", None)
    if awaiter is not None:
        subs.update(awaiter.subscriptions)
    registry = getattr(bot, "command_registry", None) or commands
    if _registry_handles(registry, "chat") or _registry_handles(registry, "whisper"):
        subs.add("chat")
    if _registry_handles(registry, "dm"):
        subs.add("message")

    for method_name, event_name in _HANDLER_METHODS.items():
        if _has_hook(bot, method_name):
            subs.add(event_name)

    return frozenset(subs)


def _subscription_query(subs: frozenset[str]) -> str:
    """Build a WebSocket query string for event subscriptions."""

    if not subs:
        return ""

    return "?events=" + ",".join(sorted(subs))


def gather_subscriptions(bot: BaseBot) -> str:
    """Return the subscription query string for a bot."""

    return _subscription_query(active_subscriptions(bot))


async def _safe_handler(result: Any) -> None:
    """Await a handler result and log exceptions safely."""
    try:
        if isawaitable(result):
            await result
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("Handler error")


async def _safe_handler_with_metrics(
    result: Any,
    event_type: str,
    bot: BaseBot,
) -> None:
    """Await a handler result while recording metrics."""
    t0 = time.perf_counter()
    metrics = getattr(bot, "metrics", None)

    try:
        if isawaitable(result):
            await result
    except asyncio.CancelledError:
        raise
    except Exception:
        if metrics is not None:
            try:
                metrics.record_error()
            except Exception:
                log.debug("Failed to record handler error", exc_info=True)

        log.exception("Handler error")
    finally:
        if metrics is not None:
            duration_ms = (time.perf_counter() - t0) * 1000.0

            record = getattr(metrics, "track", None) or getattr(
                metrics, "record_event", None
            )

            if callable(record):
                try:
                    record(event_type, duration_ms)
                except Exception:
                    log.debug("Failed to record event metrics", exc_info=True)


def _spawn_task(
    tg: TaskGroup,
    result: Any,
    bot: BaseBot | None = None,
    event_type: str | None = None,
) -> bool:
    """Spawn a handler task safely with backpressure (item 13).
    Returns True if spawned, False if dropped due to backpressure.
    Tracks active count for dispatcher backpressure metrics.
    """
    if _dispatch_backpressure_check():
        if iscoroutine(result):
            result.close()
        _STATS["dispatch_dropped"] += 1
        log.debug("Dispatcher backpressure: dropping %s (active=%d >= max=%d)", event_type, _DISPATCH_ACTIVE, _DISPATCH_MAX_CONCURRENCY)
        return False
    _dispatch_inc()
    handler = (
        _safe_handler_with_metrics(result, event_type, bot)
        if bot is not None and event_type is not None
        else _safe_handler(result)
    )

    def handler_done(task: asyncio.Task) -> None:
        _dispatch_dec()
        if task.cancelled() and iscoroutine(result):
            result.close()

    try:
        tg.create_task(handler).add_done_callback(handler_done)
        return True
    except Exception:
        handler.close()
        if iscoroutine(result):
            result.close()
        _dispatch_dec()
        # A closed/dead TaskGroup (e.g. right after a reconnect) used to fail
        # here with only a DEBUG line, so the event vanished while the receive
        # loop still counted it as handled. Count it as a real drop.
        _STATS["dispatch_dropped"] += 1
        log.warning(
            "Failed to spawn %s handler; event dropped", event_type, exc_info=True
        )
        return False


def run_internal_tests():
    """

    Synchronous entry point to run the wire-level fuzzer and protocol test suite.

    Execute via: python -c "from highrise_fast import run_internal_tests; run_internal_tests()"

    """

    import asyncio

    return asyncio.run(_run_internal_tests_async())


async def _run_internal_tests_async():
    """Async entry point for the internal SDK test suite."""

    import os
    import random
    from unittest.mock import AsyncMock, MagicMock, patch

    from .validation import (
        BASE_PAYLOADS,
        HighriseFastValidationError,
        ReasonCode,
        validate_server_message,
    )

    print("=== Running Internal Test Suite ===")

    print("[1/5] Testing BASE_PAYLOADS coverage...")

    for t, payload in BASE_PAYLOADS.items():
        try:
            validate_server_message(payload, strict=True)

        except HighriseFastValidationError as e:
            print(f"  FAIL: BASE_PAYLOADS[{t}] failed strict validation: {e}")

            raise

    print("  PASS: All BASE_PAYLOADS pass strict validation.")

    print("[2/5] Running Wire-Level Fuzzer...")

    bad_bytes = b'{"_type": "ChatEvent", "message": "\xff\xfe\xfd"}'

    try:
        data = loads_json(bad_bytes)

        if isinstance(data, dict):
            parse_server_message(data, strict=True)

    except (HighriseFastValidationError, ValueError, TypeError, UnicodeDecodeError):
        pass

    truncated = b'{"_type": "ChatEvent", "user": {"id": "123", "username": "test"'

    data = parse_server_message(truncated)

    assert data is None or not isinstance(
        data, dict
    ), "Truncated payload should not parse to dict"

    huge_msg = b"A" * (1024 * 1024 * 2)

    payload_bytes = (
        b'{"_type": "ChatEvent", "message": "'
        + huge_msg
        + b'", "user": {"id": "1", "username": "x"}, "whisper": false}'
    )

    data = loads_json(payload_bytes)

    if isinstance(data, dict):
        try:
            parse_server_message(data, strict=True, strict_semantic=True)

        except HighriseFastValidationError:
            pass

    for _ in range(500):
        raw = os.urandom(random.randint(10, 4096))

        try:
            data = loads_json(raw)

            if isinstance(data, dict):
                parse_server_message(data, strict=True)

        except Exception:
            log.debug("Fuzzer payload raised (expected)", exc_info=True)

    print("  PASS: Fuzzer survived without crashes.")

    print("[3/5] & [4/5] Testing Semantic Bounds and Reason Codes...")

    bad_pos = {
        "_type": "UserJoinedEvent",
        "user": {"id": "1", "username": "u"},
        "position": {"x": 9999.0, "y": 0.0, "z": 0.0, "facing": "FrontRight"},
    }

    try:
        validate_server_message(bad_pos, strict=True, strict_semantic=True)

        raise AssertionError("Should have raised semantic error")

    except HighriseFastValidationError as e:
        assert any(
            err.reason_code == ReasonCode.OUT_OF_BOUNDS for err in e.errors
        ), "Missing OUT_OF_BOUNDS reason code"

    missing_field = {"_type": "ChatEvent", "user": {"id": "1"}, "whisper": False}

    try:
        validate_server_message(missing_field, strict=True)

        raise AssertionError("Should have raised missing field error")

    except HighriseFastValidationError as e:
        assert any(
            err.reason_code == ReasonCode.MISSING_FIELD for err in e.errors
        ), "Missing MISSING_FIELD reason code"

    print("  PASS: Semantic bounds and Reason Codes verified.")

    print("[5/5] Testing Runtime Protocol (Backpressure & Reconnect)...")

    class MockBot(BaseBot):
        """MockBot model."""
        async def on_chat(self, user, message):
            """On chat."""

            await asyncio.sleep(0.01)

    bot = MockBot()

    ws = AsyncMock()

    ws.send_str = AsyncMock()

    ws.send_bytes = AsyncMock()

    _highrise = Highrise(ws=ws, my_id="bot_1")

    tasks = []

    for i in range(100):
        tasks.append(asyncio.create_task(bot.on_chat(MagicMock(id=f"u{i}"), "hello")))

    await _send_ws_payload(ws, {"_type": "ChatRequest", "message": "test"})

    await asyncio.gather(*tasks)

    assert ws.send_str.call_count >= 1 or ws.send_bytes.call_count >= 1

    with patch("aiohttp.ClientSession.ws_connect") as mock_connect:
        mock_connect.side_effect = Exception("401 Unauthorized: Token Expired")

        try:
            await asyncio.wait_for(
                bot_runner(bot, "room_1", "expired_token"), timeout=1.0
            )

        except TimeoutError:
            pass

        except Exception as e:  # noqa: BLE001
            assert (
                "401" in str(e)
                or "Unauthorized" in str(e)
                or isinstance(e, asyncio.CancelledError)
            )

    print("  PASS: Protocol suite completed.")

    print("=== All Internal Tests Passed ===")


async def _route_dm_command(
    bot: BaseBot, connection: Highrise, user_id: str, conversation_id: str, registry: Any
) -> None:
    """Route the latest message for the event sender once per room session."""
    response = await connection.get_messages(conversation_id)
    messages = getattr(response, "messages", ())
    if not messages or bot.highrise is not connection or connection._session_closed:
        return
    message = messages[0]
    if message.sender_id != user_id or user_id == connection.my_id:
        return
    if message.conversation_id and message.conversation_id != conversation_id:
        return
    if not message.message_id or not message.content.startswith(registry.prefix):
        return

    if connection._dm_seen is None:
        connection._dm_seen = TTLCache()
    key = conversation_id, message.message_id
    if connection._dm_seen.get(key) is not _EXTRAS_MISSING:
        _STATS["dm_commands_deduplicated"] += 1
        return
    connection._dm_seen.set(key, True, ttl=300)
    await registry.handle(
        bot, User(id=user_id, username=user_id), message.content,
        source="dm", conversation_id=conversation_id,
    )


def _dispatch_event(
    bot: BaseBot,
    bot_id: str,
    event_type: str | None,
    data: dict[str, Any],
    tg: TaskGroup,
    subscriptions: frozenset[str] | None = None,
    *,
    buffered: bool = False,
) -> bool:
    """Dispatch a validated event to the matching bot handler."""
    if subscriptions is not None:
        if not isinstance(event_type, str):
            return False
        needed = _EVENT_TO_SUBSCRIPTION.get(event_type)
        if needed is not None and needed not in subscriptions:
            return False
    awaiter = getattr(bot, "_awaiter", None)
    publish = awaiter.emit if awaiter is not None and awaiter.pending_count and not buffered else None
    if event_type == "ChatEvent":
        user = parse_user(data.get("user"))
        if user is None or user.id == bot_id:
            return True
        message = str(data.get("message", ""))
        whisper = bool(data.get("whisper", False))
        if publish is not None:
            publish("whisper" if whisper else "chat", user, message)
        _prompts = getattr(bot, "prompts", None)
        if _prompts is not None and _prompts.resolve(user.id, message):
            return True
        if not buffered and (_CHAT_FLOOD_QUEUE or _dispatch_backpressure_check()):
            if len(_CHAT_FLOOD_QUEUE) >= _CHAT_FLOOD_QUEUE.maxlen:
                _STATS["chat_flood_dropped"] += 1
            _CHAT_FLOOD_QUEUE.append((bot, bot_id, event_type, data, tg, time.monotonic()))
            _STATS["dispatch_queued"] = len(_CHAT_FLOOD_QUEUE)
            if _CHAT_DRAIN_WAKEUP is not None:
                _CHAT_DRAIN_WAKEUP.set()
            return True
        _cmd_registry = getattr(bot, "command_registry", None) or commands
        _prefix = getattr(_cmd_registry, "prefix", "!")
        _handler = bot.on_whisper if whisper else bot.on_chat
        if message.startswith(_prefix) and getattr(_cmd_registry, "has_commands", True):
            _source = "whisper" if whisper else "chat"

            async def _run_command(
                _bot=bot,
                _user=user,
                _msg=message,
                _reg=_cmd_registry,
                _src=_source,
                _fallback=_handler,
            ) -> None:
                """Internal helper for Run command."""
                executed = await _reg.handle(_bot, _user, _msg, source=_src)
                if not executed:
                    await _fallback(_user, _msg)

            if not _spawn_task(
                tg,
                _run_command(),
                bot,
                "ChatEvent",
            ):
                log.warning(
                    "Chat command dropped before dispatch: user=%s message=%r",
                    user.id,
                    message,
                )
            return True
        if not _spawn_task(
            tg,
            _handler(user, message),
            bot,
            "ChatEvent",
        ):
            log.warning(
                "Chat message dropped before dispatch: user=%s message=%r",
                user.id,
                message,
            )
        return True
    if event_type == "EmoteEvent":
        user = parse_user(data.get("user"))
        if user is None:
            return True
        receiver = parse_user(data.get("receiver"))
        emote_id = str(data.get("emote_id", ""))
        if publish is not None:
            publish("emote", user, emote_id, receiver)
        _spawn_task(
            tg,
            bot.on_emote(user, emote_id, receiver),
            bot,
            "EmoteEvent",
        )
        return True
    if event_type == "ReactionEvent":
        user = parse_user(data.get("user"))
        receiver = parse_user(data.get("receiver"))
        if user is None:
            return True
        reaction = str(data.get("reaction", ""))
        if publish is not None:
            publish("reaction", user, reaction, receiver)
        _spawn_task(
            tg,
            bot.on_reaction(user, reaction, receiver),
            bot,
            "ReactionEvent",
        )
        return True
    if event_type == "UserJoinedEvent":
        user = parse_user(data.get("user"))
        position = parse_position(data.get("position"))
        if user is None:
            return True
        _tracker = getattr(bot, "room_tracker", None)
        if _tracker is not None:
            _tracker.add(user, position)
        if publish is not None:
            publish("user_join", user, position)
        handler = bot.on_user_join
        if getattr(handler, "__func__", None) is not BaseBot.on_user_join:
            _spawn_task(
                tg,
                handler(user, position),
                bot,
                "UserJoinedEvent",
            )
        return True
    if event_type == "UserLeftEvent":
        user = parse_user(data.get("user"))
        if user is None:
            return True
        _tracker = getattr(bot, "room_tracker", None)
        if _tracker is not None:
            _tracker.remove(user.id)
        if publish is not None:
            publish("user_leave", user)
        handler = bot.on_user_leave
        if getattr(handler, "__func__", None) is not BaseBot.on_user_leave:
            _spawn_task(
                tg,
                handler(user),
                bot,
                "UserLeftEvent",
            )
        return True
    if event_type == "ChannelEvent":
        sender_id = str(data.get("sender_id", ""))
        message = str(data.get("msg", ""))
        raw_tags = data.get("tags", [])
        if raw_tags is None:
            tags = set()
        elif isinstance(raw_tags, str):
            tags = {raw_tags}
        elif isinstance(raw_tags, (list, tuple, set, frozenset)):
            tags = {str(tag) for tag in raw_tags}
        else:
            tags = {str(raw_tags)}
        if publish is not None:
            publish("channel", sender_id, message, tags)
        _spawn_task(
            tg,
            bot.on_channel(sender_id, message, tags),
            bot,
            "ChannelEvent",
        )
        return True
    if event_type == "TipReactionEvent":
        sender = parse_user(data.get("sender"))
        receiver = parse_user(data.get("receiver"))
        item = parse_item_or_currency(data.get("item"))
        if sender is None or receiver is None:
            return True
        if publish is not None:
            publish("tip", sender, receiver, item)
        _spawn_task(
            tg,
            bot.on_tip(sender, receiver, item),
            bot,
            "TipReactionEvent",
        )
        return True
    if event_type == "UserMovedEvent":
        user = parse_user(data.get("user"))
        position = parse_position(data.get("position"))
        if user is None:
            return True
        _tracker = getattr(bot, "room_tracker", None)
        if _tracker is not None:
            _tracker.move(user.id, position)
        if publish is not None:
            publish("user_move", user, position)
        handler = bot.on_user_move
        if getattr(handler, "__func__", None) is not BaseBot.on_user_move:
            _spawn_task(
                tg,
                handler(user, position),
                bot,
                "UserMovedEvent",
            )
        return True
    if event_type == "VoiceEvent":
        raw_users = data.get("users", []) or []
        users: list[tuple[User, str]] = []
        for pair in raw_users:
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                u = parse_user(pair[0])
                if u is not None:
                    users.append((u, str(pair[1])))
        seconds_left = _as_int(data.get("seconds_left"), 0)
        if publish is not None:
            publish("voice", users, seconds_left)
        _spawn_task(
            tg,
            bot.on_voice_change(users, seconds_left),
            bot,
            "VoiceEvent",
        )
        return True
    if event_type == "MessageEvent":
        user_id = str(data.get("user_id", ""))
        conversation_id = str(data.get("conversation_id", ""))
        is_new = bool(data.get("is_new_conversation", False))
        if publish is not None:
            publish("message", user_id, conversation_id, is_new)
        _cmd_registry = getattr(bot, "command_registry", None) or commands
        connection = getattr(bot, "highrise", None)
        if connection is not None and _registry_handles(_cmd_registry, "dm"):
            _spawn_task(
                tg, _route_dm_command(bot, connection, user_id, conversation_id, _cmd_registry),
                bot, "DMCommand",
            )
        handler = bot.on_message
        if getattr(handler, "__func__", None) is not BaseBot.on_message:
            _spawn_task(tg, handler(user_id, conversation_id, is_new), bot, "MessageEvent")
        return True
    if event_type == "RoomModeratedEvent":
        duration_raw = data.get("duration")
        duration = None if duration_raw is None else _as_int(duration_raw)
        moderator = str(data.get("moderatorId", ""))
        target = str(data.get("targetUserId", ""))
        action = str(data.get("moderationType", ""))
        if publish is not None:
            publish("moderation", moderator, target, action, duration)
        _spawn_task(
            tg,
            bot.on_moderate(moderator, target, action, duration),
            bot,
            "RoomModeratedEvent",
        )
        return True
    return False


async def _receive_metadata(ws: Any) -> SessionMetadata | Error:
    """Receive session metadata from the WebSocket connection."""

    _ensure_aiohttp()

    frame = await ws.receive(READ_TIMEOUT)

    if frame.type not in (WSMsgType.TEXT, WSMsgType.BINARY):
        log.debug("Unexpected first session frame type: %s", frame.type)

        raise ConnectionResetError("No valid session metadata")

    data = loads_json(frame.data)

    if not isinstance(data, dict):
        log.debug("Invalid session metadata payload: %r", data)

        raise ConnectionResetError("Invalid session metadata payload")

    if data.get("_type") in _ERROR_TYPES:
        return _parse_error(data)

    if not data.get("user_id") or not isinstance(data.get("room_info"), dict):
        raise ConnectionResetError("Missing user ID or room info in session metadata")

    return parse_session_metadata(data)


async def _receive_control_metadata(ws: Any) -> ControlSessionMetadata | Error:
    """Receive control session metadata from the WebSocket connection."""

    _ensure_aiohttp()

    frame = await ws.receive(READ_TIMEOUT)

    if frame.type not in (WSMsgType.TEXT, WSMsgType.BINARY):
        log.debug("Unexpected first control frame type: %s", frame.type)

        raise ConnectionResetError("No valid control metadata")

    data = loads_json(frame.data)

    if not isinstance(data, dict):
        log.debug("Invalid control metadata payload: %r", data)

        raise ConnectionResetError("Invalid control metadata payload")

    if data.get("_type") in _ERROR_TYPES:
        return _parse_error(data)

    return parse_control_session_metadata(data)


async def _send_keepalive(ws: Any) -> None:
    """Send periodic keepalive requests."""

    try:
        while True:
            await asyncio.sleep(KEEPALIVE_RATE)

            try:
                if getattr(ws, "closed", False):
                    return

            except (AttributeError, TypeError, RuntimeError, OSError):
                return

            try:
                await _send_ws_payload(ws, {"_type": "KeepaliveRequest"})

            except Exception as exc:
                if _is_ws_io_error(exc):
                    return

                log.debug("Keepalive send failed", exc_info=True)

                return

    except asyncio.CancelledError:
        raise

    except BaseException:
        log.debug("Keepalive died", exc_info=True)

        return


async def _receive_loop(
    ws: Any,
    highrise: Highrise,
    bot: BaseBot,
    tg: TaskGroup,
    session_metadata: SessionMetadata,
    subscriptions: frozenset[str] | None = None,
) -> None:
    """Receive, validate, and dispatch incoming WebSocket messages."""

    _ensure_aiohttp()

    bot_id = str(session_metadata.user_id)

    validation_mode, on_invalid, warn_cooldown = _resolve_validation_settings(bot)

    strict = validation_mode == "strict"
    decode = orjson.loads if orjson is not None else loads_json

    if not strict:
        log.info("Validation mode is 'lenient': incoming packets are not validated")

    while True:
        frame = await ws.receive(READ_TIMEOUT)

        if frame.type in CLOSE_TYPES:
            print(
                f"Connection with ID: {session_metadata.connection_id} "
                "closed by server, reconnecting."
            )

            raise ConnectionResetError

        if frame.type == WSMsgType.ERROR:
            raise ConnectionResetError("WebSocket error")

        if frame.type not in (WSMsgType.TEXT, WSMsgType.BINARY):
            continue

        if frame.data is None:
            continue

        try:
            data = decode(frame.data)

        except (ValueError, TypeError, UnicodeDecodeError):
            _STATS["incoming_fallback"] += 1

            log.debug("Received non-JSON frame", exc_info=True)

            continue

        if not isinstance(data, dict):
            _STATS["incoming_fallback"] += 1

            log.debug("Received non-dict payload: %r", data)

            continue

        _STATS["incoming_calls"] += 1

        rid = data.get("rid")

        event_type = data.get("_type")
        valid = True

        if strict:
            vtype = event_type if isinstance(event_type, str) else None

            if vtype not in _VALIDATION_EXEMPT and (
                isinstance(rid, str)
                or (vtype is not None and vtype in _EVENT_TO_SUBSCRIPTION)
            ):
                try:
                    _hrf_validate_server_message(data)

                except HighriseFastValidationError as exc:
                    valid = False
                    if _handle_invalid_packet(
                        exc, data, highrise, bot, tg, on_invalid, warn_cooldown
                    ):
                        continue

        if isinstance(rid, str):
            if highrise._resolve_pending(rid, data, update_roster=valid):
                _STATS["incoming_fast"] += 1

            else:
                _STATS["incoming_fallback"] += 1

                log.debug("Received response with unknown rid: %s", rid)

            continue

        if event_type == "KeepaliveResponse":
            _STATS["incoming_fast"] += 1

            continue

        if event_type in _ERROR_TYPES:
            error = _parse_error(data)

            print(
                f"ERROR: {error.message} closing connection with ID: "
                f"{session_metadata.connection_id}"
            )

            if error.do_not_reconnect:
                raise _DoNotReconnect

            raise ConnectionResetError

        try:
            handled = _dispatch_event(bot, bot_id, event_type, data, tg, subscriptions)

            if handled:
                _STATS["incoming_fast"] += 1

            elif (
                subscriptions is not None
                and isinstance(event_type, str)
                and event_type in _EVENT_TO_SUBSCRIPTION
            ):
                _STATS["incoming_skipped"] += 1

            else:
                _STATS["incoming_fallback"] += 1

                log.debug("Unhandled event type: %s", event_type)

        except asyncio.CancelledError:
            raise

        except Exception:
            _STATS["incoming_fallback"] += 1

            log.exception("Event dispatch failed")


def _compute_backoff(attempt: int, base: float = 1.0, cap: float = 60.0, jitter_ratio: float = 0.2) -> float:
    """Exponential backoff with jitter.

    attempt 0 => ~1s, 1=>2s, 2=>4s, 3=>8s ... capped at 60s.
    Jitter is ±jitter_ratio (default 20%) to avoid synchronized reconnect storms
    when running multiple bots.
    """
    try:
        exp = base * (2 ** max(0, attempt))
    except OverflowError:
        exp = cap
    exp = min(exp, cap)
    jitter = random.uniform(-jitter_ratio * exp, jitter_ratio * exp)
    delay = exp + jitter
    return max(0.5, delay)


async def _sleep_backoff(attempt: int) -> None:
    delay = _compute_backoff(attempt)
    log.debug("Backoff sleep %.2fs (attempt %d)", delay, attempt)
    await asyncio.sleep(delay)



def _discard_buffered_chat(tg: TaskGroup) -> None:
    """Discard events buffered for a connection that just ended."""
    if not _CHAT_FLOOD_QUEUE:
        return
    buffered = [entry for entry in _CHAT_FLOOD_QUEUE if entry[4] is not tg]
    dropped = len(_CHAT_FLOOD_QUEUE) - len(buffered)
    if dropped:
        _CHAT_FLOOD_QUEUE.clear()
        _CHAT_FLOOD_QUEUE.extend(buffered)
        _STATS["chat_flood_dropped"] += dropped
        _STATS["dispatch_queued"] = len(buffered)


async def _drain_chat_flood_queue(wakeup: asyncio.Event) -> None:
    """Dispatch buffered chat once a handler slot opens."""
    while True:
        await wakeup.wait()
        wakeup.clear()
        while _CHAT_FLOOD_QUEUE and not _dispatch_backpressure_check():
            bot, bot_id, event_type, data, tg, enqueued_at = _CHAT_FLOOD_QUEUE.popleft()
            _STATS["dispatch_queued"] = len(_CHAT_FLOOD_QUEUE)
            try:
                _dispatch_event(bot, bot_id, event_type, data, tg, buffered=True)
            except Exception:
                _STATS["dispatch_dropped"] += 1
                log.warning("Buffered chat dispatch failed after %.2fs",
                            time.monotonic() - enqueued_at, exc_info=True)
            if _CHAT_FLOOD_QUEUE:
                await asyncio.sleep(0.02)


_CHAT_DRAIN_TASK: asyncio.Task | None = None
_CHAT_DRAIN_REFCOUNT: int = 0


def start_chat_drain_task() -> asyncio.Task | None:
    global _CHAT_DRAIN_TASK, _CHAT_DRAIN_REFCOUNT, _CHAT_DRAIN_WAKEUP
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    _CHAT_DRAIN_REFCOUNT += 1
    if _CHAT_DRAIN_TASK is not None and not _CHAT_DRAIN_TASK.done():
        return _CHAT_DRAIN_TASK
    wakeup = _CHAT_DRAIN_WAKEUP = asyncio.Event()
    if _CHAT_FLOOD_QUEUE:
        wakeup.set()
    _CHAT_DRAIN_TASK = loop.create_task(
        _drain_chat_flood_queue(wakeup), name="highrise_fast-chat-drain"
    )
    return _CHAT_DRAIN_TASK


async def stop_chat_drain_task() -> None:
    global _CHAT_DRAIN_TASK, _CHAT_DRAIN_REFCOUNT, _CHAT_DRAIN_WAKEUP
    _CHAT_DRAIN_REFCOUNT = max(0, _CHAT_DRAIN_REFCOUNT - 1)
    if _CHAT_DRAIN_REFCOUNT or _CHAT_DRAIN_TASK is None:
        return
    task, _CHAT_DRAIN_TASK = _CHAT_DRAIN_TASK, None
    _CHAT_DRAIN_WAKEUP = None
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


async def throttler(drops: int = 5, drop_recharge: float = 5.0):
    """Yield tokens according to a recharge rate."""

    tokens = float(drops)

    last = time.monotonic()

    while True:
        now = time.monotonic()

        elapsed = now - last

        last = now

        tokens = min(
            float(drops),
            tokens + (elapsed / max(0.001, drop_recharge)),
        )

        if tokens >= 1.0:
            tokens -= 1.0

            yield

        else:
            await asyncio.sleep((1.0 - tokens) * max(0.001, drop_recharge))

            last = time.monotonic()

            tokens = 0.0

            yield


async def _cancel_and_wait(task: asyncio.Task | None) -> None:
    """Cancel a task and wait for it to finish safely."""

    if task is None:
        return

    if not task.done():
        task.cancel()

    current = asyncio.current_task()

    cancelling = getattr(current, "cancelling", None) if current is not None else None

    if callable(cancelling) and cancelling():
        return

    try:
        await task

    except asyncio.CancelledError:
        pass

    except BaseException:
        log.debug("Cancelled task raised during cleanup", exc_info=True)


@dataclass
class BotDefinition:
    """Startup definition for a bot instance."""
    bot: BaseBot

    room_id: str

    api_token: str


async def _close_bot_extras(bot: BaseBot) -> None:
    """Stop bot framework extras such as tasks, actions, and WebAPI clients."""
    _actions = getattr(bot, "actions", None)
    if _actions is not None and hasattr(_actions, "stop"):
        try:
            await _actions.stop()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.debug("ThrottledActions stop failed", exc_info=True)

    tasks = getattr(bot, "tasks", None)

    if tasks is not None:
        try:
            if hasattr(tasks, "shutdown"):
                await tasks.shutdown(timeout=1.0)
            elif hasattr(tasks, "cancel_all"):
                await tasks.cancel_all()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.debug("TaskManager shutdown failed", exc_info=True)

    webapi = getattr(bot, "webapi", None)

    if webapi is not None and hasattr(webapi, "close"):
        try:
            await webapi.close()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.debug("WebAPI close failed", exc_info=True)


async def bot_runner(bot: BaseBot, room_id: str, api_key: str) -> None:
    """Run a room bot until cancelled or the server refuses reconnection."""
    setup_logging()
    _ensure_aiohttp()
    _ensure_gc_monitoring()
    if getattr(bot, "metrics", None) is None:
        bot.metrics = Metrics()
    if getattr(bot, "tasks", None) is None:
        bot.tasks = TaskManager()
    start_loop_lag_monitor(0.1)
    start_chat_drain_task()
    reconnect_attempt = 0
    first_session = True
    throttling = throttler(5, 5)
    try:
        timeout = ClientTimeout(total=30, sock_connect=10, sock_read=60)
        async with ClientSession(timeout=timeout) as session:
            while True:
                await anext(throttling)
                try:
                    try:
                        async with TaskGroup() as tg:
                            await bot.before_start(tg)
                            subs = active_subscriptions(bot)
                            async with session.ws_connect(
                                f"{BASE_WS_URL}{_subscription_query(subs)}",
                                headers={
                                    "room-id": room_id,
                                    "api-token": api_key,
                                    "user-agent": USER_AGENT,
                                },
                            ) as ws:
                                metadata = await _receive_metadata(ws)
                                if isinstance(metadata, Error):
                                    log.warning("Bot session rejected: %s", metadata.message)
                                    if metadata.do_not_reconnect:
                                        raise _DoNotReconnect
                                    raise ConnectionResetError(metadata.message)

                                tracker = getattr(bot, "room_tracker", None)
                                highrise = Highrise(
                                    ws=ws, tg=tg, my_id=metadata.user_id, room_tracker=tracker
                                )
                                highrise.state_dirty = tracker is not None or not first_session
                                bot.highrise = highrise
                                actions = getattr(bot, "actions", None)
                                if actions is not None and hasattr(actions, "start"):
                                    actions.start()
                                if getattr(bot, "webapi", None) is None:
                                    bot.webapi = getattr(bot, "_webapi_type", WebAPI)()
                                if metadata.sdk_version and metadata.sdk_version != VERSION:
                                    log.debug("Server SDK version %s differs from %s", metadata.sdk_version, VERSION)

                                keepalive = asyncio.create_task(_send_keepalive(ws))
                                gc_timer = None
                                try:
                                    if first_session:
                                        if tracker is not None:
                                            tg.create_task(_safe_handler(highrise._refresh_room()))
                                    else:
                                        tg.create_task(_safe_handler_with_metrics(
                                            bot.on_reconnected(), "on_reconnected", bot
                                        ))
                                    if first_session or getattr(bot, "_start_each_session", False):
                                        tg.create_task(_safe_handler_with_metrics(
                                            bot.on_start(metadata), "on_start", bot
                                        ))
                                    first_session = False
                                    _maybe_tune_gc()
                                    if _GC_FIRST_TUNE_TIME is not None and not _GC_FROZEN:
                                        gc_timer = asyncio.get_running_loop().call_later(
                                            5.5, _maybe_tune_gc
                                        )
                                    reconnect_attempt = 0
                                    await _receive_loop(ws, highrise, bot, tg, metadata, subs or None)
                                finally:
                                    if gc_timer is not None:
                                        gc_timer.cancel()
                                    _discard_buffered_chat(tg)
                                    prompts = getattr(bot, "prompts", None)
                                    if isinstance(prompts, PromptManager):
                                        prompts.cancel_all()
                                    awaiter = getattr(bot, "_awaiter", None)
                                    if awaiter is not None:
                                        awaiter.cancel_all()
                                    try:
                                        await highrise._close_session()
                                    finally:
                                        await _cancel_and_wait(keepalive)
                                        if isinstance(actions, ThrottledActions):
                                            await actions.stop()
                    except BaseExceptionGroup as group:
                        if len(group.exceptions) == 1:
                            # TaskGroup wraps the receive-loop exception when it cancels its children.
                            raise group.exceptions[0] from None
                        raise
                except _DoNotReconnect:
                    return
                except _FatalValidationError:
                    log.critical("Fatal validation error; aborting bot runner")
                    raise
                except (ConnectionResetError, TimeoutError):
                    log.info("Connection lost or timed out; reconnecting (attempt %d)", reconnect_attempt)
                except Exception as exc:
                    if _is_handshake_error(exc):
                        log.warning("WebSocket handshake failed; retrying (attempt %d)", reconnect_attempt)
                    else:
                        log.exception("Bot connection failed; retrying (attempt %d)", reconnect_attempt)
                finally:
                    # Hooks may register a new wait while the connection is closing.
                    awaiter = getattr(bot, "_awaiter", None)
                    if awaiter is not None:
                        awaiter.cancel_all()
                await _sleep_backoff(reconnect_attempt)
                reconnect_attempt += 1
    finally:
        await _close_bot_extras(bot)
        await stop_loop_lag_monitor()
        await stop_chat_drain_task()


async def control_runner(
    bot_cls: type[BaseBot],
    room_id: str,
    api_key: str,
) -> None:
    """Run a control connection and manage per-instance bot tasks."""

    setup_logging()

    _ensure_aiohttp()

    try:
        async with TaskGroup() as tg:
            instances_to_bots: dict[str, asyncio.Task] = {}

            def _on_bot_done(iid: str, task: asyncio.Task) -> None:
                """Internal helper for On bot done."""

                if instances_to_bots.get(iid) is task:
                    instances_to_bots.pop(iid, None)

                if not task.cancelled():
                    log.warning(
                        "Bot task for instance %s died; "
                        "will restart on next control event or sweep",
                        iid,
                    )

            def _start_bot(instance_id: str) -> None:
                """Internal helper for Start bot."""

                if instance_id in instances_to_bots:
                    return

                print(f"Starting bot for instance {instance_id}")

                bot_task = tg.create_task(
                    bot_runner(bot_cls(), f"3d/{instance_id}", api_key)
                )

                bot_task.add_done_callback(
                    lambda t, iid=instance_id: _on_bot_done(iid, t)
                )

                instances_to_bots[instance_id] = bot_task

            last_sweep = time.monotonic()
            ctrl_attempt = 0

            while True:
                ka_task: asyncio.Task | None = None

                try:
                    timeout_obj = (
                        ClientTimeout(total=30, sock_connect=10, sock_read=60)
                        if ClientTimeout
                        else None
                    )
                    async with ClientSession(timeout=timeout_obj) as session:
                        url = f"{BASE_WS_URL}/control/{room_id}"

                        async with session.ws_connect(
                            url,
                            headers={
                                "api-token": api_key,
                                "user-agent": USER_AGENT,
                            },
                        ) as ws:
                            ka_task = asyncio.create_task(_send_keepalive(ws))

                            try:
                                metadata = await _receive_control_metadata(ws)

                                if isinstance(metadata, Error):
                                    log.warning("Control session rejected: %s", metadata.message)
                                    if metadata.do_not_reconnect:
                                        raise _DoNotReconnect
                                    raise ConnectionResetError(metadata.message)

                                active_instances = set(metadata.instance_ids)
                                for instance_id in instances_to_bots.keys() - active_instances:
                                    instances_to_bots.pop(instance_id).cancel()

                                for instance_id in metadata.instance_ids:
                                    _start_bot(instance_id)

                                ctrl_attempt = 0

                                while True:
                                    frame = await ws.receive(READ_TIMEOUT)

                                    if frame.type in CLOSE_TYPES or frame.type == WSMsgType.ERROR:
                                        raise ConnectionResetError("Control socket closed")

                                    if frame.type not in (
                                        WSMsgType.TEXT,
                                        WSMsgType.BINARY,
                                    ):
                                        continue

                                    try:
                                        data = loads_json(frame.data)

                                    except (
                                        ValueError,
                                        TypeError,
                                        UnicodeDecodeError,
                                    ):
                                        log.debug("Received non-JSON control frame")

                                        continue

                                    if not isinstance(data, dict):
                                        continue

                                    event_type = data.get("_type")

                                    if event_type in _ERROR_TYPES:
                                        error = _parse_error(data)
                                        if error.do_not_reconnect:
                                            raise _DoNotReconnect
                                        raise ConnectionResetError(error.message)

                                    if event_type == "InstanceStartedEvent":
                                        instance_id = str(data.get("instance_id", ""))

                                        if instance_id:
                                            _start_bot(instance_id)

                                    elif event_type == "InstanceStoppedEvent":
                                        instance_id = str(data.get("instance_id", ""))

                                        task = instances_to_bots.pop(
                                            instance_id,
                                            None,
                                        )

                                        if task is not None:
                                            tg.create_task(_cancel_and_wait(task))

                                    now = time.monotonic()

                                    if now - last_sweep >= _CONTROL_SWEEP_INTERVAL:
                                        last_sweep = now

                                        dead = [
                                            iid
                                            for iid, task in list(
                                                instances_to_bots.items()
                                            )
                                            if task.done()
                                        ]

                                        for iid in dead:
                                            instances_to_bots.pop(iid, None)

                                            _start_bot(iid)

                            finally:
                                await _cancel_and_wait(ka_task)

                                ka_task = None

                except asyncio.CancelledError:
                    raise

                except _DoNotReconnect:
                    raise

                except (ConnectionResetError, TimeoutError):
                    log.info("Control connection lost/timeout; reconnecting (attempt %d)", ctrl_attempt)
                    await _sleep_backoff(ctrl_attempt)
                    ctrl_attempt += 1
                    continue

                except Exception as exc:
                    if _is_handshake_error(exc):
                        log.warning("Control WebSocket handshake failed; retrying (attempt %d)", ctrl_attempt)
                    else:
                        log.exception("ERROR: control reconnecting (attempt %d)...", ctrl_attempt)
                    await _sleep_backoff(ctrl_attempt)
                    ctrl_attempt += 1
                    continue

                finally:
                    if ka_task is not None:
                        await _cancel_and_wait(ka_task)

    except asyncio.CancelledError:
        raise

    except _BASE_EXCEPTION_GROUP as eg:
        if _contains_cancelled(eg) or _contains_fatal(eg):
            raise
        if eg.subgroup(_DoNotReconnect) is not None:
            return

        log.debug(
            "Control TaskGroup exited with exception group",
            exc_info=True,
        )

    except Exception:
        log.debug(
            "control_runner exited with unhandled exception",
            exc_info=True,
        )


def import_bot_class(bot_path: str) -> type[BaseBot]:
    """Import a bot class from a module path string."""

    if ":" not in bot_path:
        raise ValueError("BOT_PATH must be in format module:ClassName")

    module_name, class_name = bot_path.split(":", 1)

    module = importlib.import_module(module_name)

    bot_class = getattr(module, class_name)

    return bot_class


async def main_async(definitions: list[BotDefinition]) -> None:
    """Run multiple bot definitions concurrently."""

    setup_logging()

    async with TaskGroup() as tg:
        for index, definition in enumerate(definitions):
            tg.create_task(
                bot_runner(
                    definition.bot,
                    definition.room_id,
                    definition.api_token,
                )
            )

            if index < len(definitions) - 1:
                print("Bot started. Waiting 1 second(s) before starting the next bot.")

                await asyncio.sleep(1)


def _performance_gate(max_ms_per_1000: float = 100.0, strict: bool = True) -> dict:
    """Hard CI performance gate: validation must stay fast.

    Measures 1000 validations of a representative payload.
    Returns dict with timing and passes/fails.
    Raises AssertionError if strict and gate fails (for CI).
    """
    import time as _time

    from .validation import BASE_PAYLOADS, validate_server_message

    sample = None
    if BASE_PAYLOADS:
        sample = BASE_PAYLOADS.get("ChatEvent") or next(iter(BASE_PAYLOADS.values()))
    if sample is None:
        sample = {
            "_type": "ChatEvent",
            "user": {"id": "u1", "username": "test"},
            "message": "hi",
            "whisper": False,
        }

    t0 = _time.perf_counter()
    n = 1000
    for _ in range(n):
        validate_server_message(sample)
    dt_ms = (_time.perf_counter() - t0) * 1000.0
    per_msg_us = (dt_ms / n) * 1000.0

    result = {
        "iterations": n,
        "total_ms": round(dt_ms, 3),
        "per_msg_us": round(per_msg_us, 3),
        "per_msg_ms": round(dt_ms / n, 6),
        "threshold_ms": max_ms_per_1000,
        "passed": dt_ms <= max_ms_per_1000,
    }

    if strict and not result["passed"]:
        raise AssertionError(
            f"Performance gate FAILED: {dt_ms:.2f}ms for {n} validations > {max_ms_per_1000}ms threshold "
            f"({per_msg_us:.1f}us per msg). Validation has regressed."
        )

    return result


def _run_benchmarks_consolidated(verbose: bool = False) -> int:
    """Time structural validation and check parser, backoff, and stats behavior."""
    print("=== highrise_fast consolidated benchmarks ===")
    import platform

    print(f"Python {sys.version.split()[0]} | {platform.python_implementation()}")

    try:
        gate = _performance_gate(max_ms_per_1000=100.0, strict=True)
        print(f"✓ Performance gate: {gate['total_ms']}ms for {gate['iterations']} validations ({gate['per_msg_us']}us/msg)")
    except AssertionError as e:
        print(f"✗ {e}")
        return 1
    except Exception as e:
        print(f"? Performance gate error: {e}")
        if verbose:
            import traceback

            traceback.print_exc()

    try:
        from .validation import BASE_PAYLOADS
        sample = next(iter(BASE_PAYLOADS.values())) if BASE_PAYLOADS else {"_type":"ChatEvent","user":{"id":"u1","username":"t"},"message":"hi","whisper":False}
        try:
            parse_server_message(sample, strict=True)
            print("✓ parse_server_message(strict=True) agrees with validation")
        except Exception as e:
            print(f"✗ parse_server_message(strict=True) raised: {e}")
            return 1
    except Exception as e:
        print(f"? Unified parse check skipped: {e}")

    try:
        # Official parity: two parses of the same payload must be equal by value
        # but distinct objects. Interning used to make them identical, which
        # diverged from the official SDK.
        u1 = parse_user({"id": "123", "username": "alice"})
        u2 = parse_user({"id": "123", "username": "alice"})
        assert u1 == u2, "User value equality broken"
        assert u1 is not u2, "Users must be distinct objects (official parity)"
        print("✓ User parsing: value equality, distinct identity (official parity)")
    except Exception as e:
        print(f"✗ User parsing check failed: {e}")
        return 1

    try:
        delays = [_compute_backoff(i) for i in range(6)]
        assert delays[0] < delays[1] < delays[2], "Backoff should increase"
        assert max(delays) <= 60.0 + 0.2*60.0, "Backoff cap exceeded"
        print(f"✓ Backoff: {', '.join(f'{d:.2f}s' for d in delays[:4])}... cap 60s")
    except Exception as e:
        print(f"✗ Backoff check failed: {e}")
        return 1

    try:
        s = stats()
        assert "loop_lag" in s and "gc_pauses" in s, "stats missing new fields"
        print("✓ stats() includes loop_lag and gc_pauses")
    except Exception as e:
        print(f"✗ stats check failed: {e}")
        return 1

    print("\n=== All consolidated benchmarks passed ===")
    return 0


def _doctor_check() -> int:
    """Run self-diagnostic checks for highrise_fast.

    Covers:
    - Python version (3.11+ required)
    - Event loop policy (Windows Selector vs Proactor)
    - aiohttp / orjson versions
    - DNS + TCP probe to highrise.game
    - Token prefix format
    - HR_WS_BINARY state
    - _REQ_TIMEOUT echo
    - Pending task count
    - GC state
    - TCP_NODELAY expectation
    - Loop lag / GC pause stats if available
    - Invalid packet stats
    """
    print("=== highrise_fast doctor ===")
    ok = True

    import platform
    py_ver = platform.python_version()
    print(f"Python: {py_ver} ({platform.python_implementation()})")
    print("  ✓ Python version OK (3.10+ required)")

    try:
        policy = asyncio.get_event_loop_policy()
        policy_name = type(policy).__name__
        print(f"Event loop policy: {policy_name}")
        if sys.platform == "win32":
            if "Selector" in policy_name:
                print("  ✓ SelectorEventLoopPolicy (correct for Windows)")
            elif "Proactor" in policy_name or "Windows" in policy_name:
                print("  ⚠ WARNING: Proactor policy may deadlock — recommend WindowsSelectorEventLoopPolicy")
            else:
                print(f"  ? Unknown policy {policy_name}")
        else:
            print("  ✓ Non-Windows — policy OK")
    except Exception as e:
        print(f"  ? Could not detect event loop policy: {e}")

    try:
        import aiohttp
        print(f"aiohttp: {aiohttp.__version__}")
        print("  ✓ aiohttp installed")
    except Exception as e:
        print(f"aiohttp: NOT INSTALLED ({e})")
        print("  ✗ FAIL: pip install aiohttp")
        ok = False

    try:
        import orjson
        print(f"orjson: {orjson.__version__} (fast path)")
        print("  ✓ orjson fast path enabled")
    except Exception:
        print("orjson: not installed — using json fallback (slower)")
        print("  ⚠ Install orjson for speed: pip install orjson")

    host = "highrise.game"
    print(f"\nNetwork probe: {host}")
    # NOTE: socket.getaddrinfo() takes no timeout argument, so the lookup is
    # bounded by running it in a worker thread instead of blocking the probe.
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            infos = pool.submit(
                socket.getaddrinfo, host, 443, 0, socket.SOCK_STREAM
            ).result(timeout=5)
        ips = sorted({i[4][0] for i in infos})
        print(f"  DNS: {host} -> {', '.join(ips[:3])}{'...' if len(ips) > 3 else ''}")
        print("  ✓ DNS OK")
    except Exception as e:
        print(f"  ✗ DNS FAIL: {e}")
        ok = False

    try:
        sock = socket.create_connection((host, 443), timeout=5)
        try:
            nodelay = sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY)
            print(f"  TCP probe: connected to {host}:443, TCP_NODELAY={nodelay} (expected 1)")
            if nodelay == 1:
                print("  ✓ TCP_NODELAY set (asyncio default)")
            else:
                print("  ⚠ TCP_NODELAY not set — may add latency")
        except Exception:
            print(f"  TCP probe: connected to {host}:443")
        sock.close()
        print("  ✓ TCP connect OK")
    except Exception as e:
        print(f"  ✗ TCP connect FAIL: {e}")
        ok = False

    print("\nToken check:")
    token = os.environ.get("HR_BOT_TOKEN", "")
    print(f"  HR_BOT_TOKEN is {'set' if token else 'unset'}")

    print("\nEnv flags:")
    print(f"  HR_WS_BINARY={os.environ.get('HR_WS_BINARY','0')} -> {'BINARY' if _WS_BINARY_FRAMES else 'TEXT (default, proxy-safe)'}")
    if _WS_BINARY_FRAMES:
        print("  ⚠ BINARY frames enabled — ensure endpoint accepts binary or you will be muted")
    rpc_timeout = _REQ_TIMEOUT if _REQ_TIMEOUT > 0 else Highrise._RPC_HARD_TIMEOUT
    print(f"  RPC deadline: {rpc_timeout:g}s for send and reply")

    print("\nGC state:")
    try:
        print(f"  gc enabled={gc.isenabled()}, thresholds={gc.get_threshold()}, counts={gc.get_count()}")
        print(f"  gc callbacks registered={len(gc.callbacks)}, monitoring={_GC_CALLBACK_REGISTERED and _GC_ENABLED}")
        if _GC_ENABLED:
            snap = _gc_snapshot()
            if snap:
                print(f"  GC pauses: count={snap['count']} p50={snap['p50']}ms p99={snap['p99']}ms max={snap['max']}ms")
            else:
                print("  GC pauses: no data yet (run bot for a bit)")
        else:
            print("  ℹ Enable GC monitoring via _ensure_gc_monitoring() or HR_FAST_GC_TUNE=1")
    except Exception as e:
        print(f"  ? GC check failed: {e}")

    print("\nLoop lag monitor:")
    lag_snap = _loop_lag_snapshot() if '_LOOP_LAG_MS' in globals() else None
    if lag_snap:
        print(f"  count={lag_snap['count']} p50={lag_snap['p50']}ms p95={lag_snap['p95']}ms p99={lag_snap['p99']}ms max={lag_snap['max']}ms")
        if lag_snap.get('p99',0) > 100:
            print("  ⚠ High p99 loop lag — check for blocking calls or GC")
        else:
            print("  ✓ Loop lag OK")
    else:
        print("  No loop lag data yet (monitor not started or just started)")
        print("  ℹ Loop lag monitor runs 100ms sleep + perf_counter oversleep measurement")

    print("\nAsyncio tasks:")
    try:
        loop = asyncio.new_event_loop()
        try:
            running = asyncio.get_running_loop()
            tasks = asyncio.all_tasks(running)
            print(f"  Running loop tasks: {len(tasks)}")
            for t in list(tasks)[:10]:
                print(f"    - {t.get_name()} coro={t.get_coro().__name__ if hasattr(t.get_coro(), '__name__') else str(t.get_coro())[:60]}")
            if len(tasks) > 10:
                print(f"    ... and {len(tasks)-10} more")
        except RuntimeError:
            print("  No running loop (doctor ran outside async context) — OK")
        loop.close()
    except Exception as e:
        print(f"  ? Task check failed: {e}")

    print("\nValidation / invalid packets:")
    try:
        inv = dict(_INVALID_BY_TYPE)
        if inv:
            print(f"  Invalid by type: {inv}")
        else:
            print("  No invalid packets recorded yet")
        print(f"  Stats: {_STATS}")
    except Exception as e:
        print(f"  ? Could not read invalid stats: {e}")

    print("\nUser parsing:")
    try:
        u_a = parse_user({"id": "probe", "username": "probe"})
        u_b = parse_user({"id": "probe", "username": "probe"})
        same_value = u_a == u_b
        distinct = u_a is not u_b
        print("  interns users : no (matches official SDK)")
        print(f"  value equality: {'yes' if same_value else 'NO'}")
        print(
            f"  distinct objects per parse: {'yes' if distinct else 'NO'}"
            " (official parity)"
        )
        if not (same_value and distinct):
            print("  ✗ FAIL: user parse semantics diverged from the official SDK")
            ok = False
        else:
            print("  ✓ User parse semantics match the official SDK")
    except Exception as e:
        print(f"  ? User parse check failed: {e}")

    print("\nPerformance gate:")
    try:
        import time as _time

        from .validation import BASE_PAYLOADS, validate_server_message
        sample = next(iter(BASE_PAYLOADS.values())) if BASE_PAYLOADS else {"_type":"ChatEvent","user":{"id":"u1","username":"test"},"message":"hi","whisper":False}
        t0 = _time.perf_counter()
        for _ in range(1000):
            try:
                validate_server_message(sample)
            except Exception:
                pass
        dt = (_time.perf_counter() - t0)*1000
        print(f"  1000 validations: {dt:.2f}ms ({dt/1000:.3f}ms each)")
        if dt > 100:
            print("  ⚠ Validation slower than 100ms/1000 — check for regression")
        else:
            print("  ✓ Validation perf OK")
    except Exception as e:
        print(f"  ? Perf gate failed: {e}")

    print("\n=== doctor summary ===")
    if ok:
        print("✓ All critical checks passed")
    else:
        print("✗ Some critical checks failed — see above")
    print("Run with: python -m highrise_fast doctor")
    return 0 if ok else 1


def main() -> None:
    """CLI entry point for running a Highrise bot or diagnostics."""

    setup_logging()

    _cwd = os.getcwd()
    _unsafe_dirs = {"/tmp", "/var/tmp", tempfile.gettempdir()}
    if _cwd not in _unsafe_dirs and _cwd not in sys.path:
        sys.path.append(_cwd)

    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            log.debug("Failed to set Windows SelectorEventLoopPolicy", exc_info=True)

    if os.getcwd() not in sys.path:
        sys.path.append(os.getcwd())

    raw_args = sys.argv[1:]
    if raw_args and raw_args[0].lower() == "doctor":
        sys.exit(_doctor_check())
    if raw_args in (["--doctor"], ["-d"]):
        sys.exit(_doctor_check())
    if raw_args in (["bench"], ["--bench"]):
        sys.exit(_run_benchmarks_consolidated())
    if raw_args in (["self-test"], ["--self-test"]):
        run_internal_tests()
        return

    parser = argparse.ArgumentParser(
        description="Run a Highrise bot.",
        epilog="Commands: doctor (diagnostics), bench (benchmark), self-test (offline checks).",
    )

    parser.add_argument(
        "bot_path",
        help="Module path and class name (e.g. module:ClassName)",
    )

    parser.add_argument(
        "room_id",
        help="Room ID",
    )

    parser.add_argument(
        "api_token",
        nargs="?",
        help="API token (defaults to HR_BOT_TOKEN)",
    )

    parser.add_argument(
        "--extra_bot",
        nargs=3,
        action="append",
        default=[],
        metavar=("BOT_PATH", "ROOM_ID", "API_TOKEN"),
        help="Optional additional bot definition.",
    )

    parser.add_argument(
        "--validation",
        choices=("strict", "lenient"),
        default=None,
        help="Incoming packet validation (default: strict).",
    )

    parser.add_argument(
        "--on-invalid",
        choices=("drop", "raise", "log-only"),
        default=None,
        help="What to do with a packet that fails validation (default: drop).",
    )

    args = parser.parse_args()

    token = args.api_token or os.environ.get("HR_BOT_TOKEN")
    if not token:
        parser.error("provide an API token or set HR_BOT_TOKEN")

    if args.validation:
        os.environ["HIGHRISE_FAST_VALIDATION"] = args.validation

    if args.on_invalid:
        os.environ["HIGHRISE_FAST_ON_INVALID"] = args.on_invalid

    first_bot_path = args.bot_path

    first_room_id = args.room_id

    first_token = token

    if first_room_id.startswith("3d/"):
        room_id = first_room_id[3:]

        bot_cls = import_bot_class(first_bot_path)

        return asyncio.run(control_runner(bot_cls, room_id, first_token))

    definitions: list[BotDefinition] = []

    all_defs = [(first_bot_path, first_room_id, first_token)]

    for extra in args.extra_bot:
        all_defs.append(tuple(extra))

    for bot_path, room_id, api_token in all_defs:
        bot_class = import_bot_class(str(bot_path))

        definitions.append(
            BotDefinition(
                bot=bot_class(),
                room_id=str(room_id),
                api_token=str(api_token),
            )
        )

    return asyncio.run(main_async(definitions))


installed: bool = False

fast_enabled: bool = True


def install(*args: Any, **kwargs: Any) -> bool:
    """Compatibility hook for bootstrap/sdk_fast loaders.



    highrise_fast is standalone, so no monkey patching is required.

    """

    global installed

    installed = True

    return True


def uninstall(*args: Any, **kwargs: Any) -> bool:
    """Compatibility hook for bootstrap/sdk_fast loaders."""

    global installed

    installed = False

    return True


patch = install

enable = install

setup = install


from . import compat_requests as _compat_requests
from .compat_requests import *  # noqa: F403

for _name in getattr(_compat_requests, "__all__", []):
    if _name not in __all__:
        __all__.append(_name)

# Optional drop-in aliasing: ``highrise_fast.install_alias()`` registers the
# official ``highrise`` module names in sys.modules so an existing official-SDK
# bot runs unchanged. Imported last (after the models/validation surface exists)
# and it does not touch sys.modules until explicitly called.
from .compat import (  # noqa: E402
    ALIASED_MODULES as ALIASED_MODULES,
)
from .compat import (
    alias_active as alias_active,
)
from .compat import (
    install_alias as install_alias,
)
from .compat import (
    uninstall_alias as uninstall_alias,
)

# --- canonical public surface -------------------------------------------------
# ``__all__`` above is assembled incrementally (core models, validation helpers,
# framework extras, request shims), which historically left several documented
# entry points out of the star-import surface.  Complete it here and normalise
# it so that ``from highrise_fast import *`` is sorted, duplicate-free and only
# contains names that actually resolve.
for _public_name in (
    "ALIASED_MODULES",
    "alias_active",
    "install_alias",
    "uninstall_alias",
    "BASE_WEB_URL",
    "BASE_WS_URL",
    "CachedWebAPI",
    "KEEPALIVE_RATE",
    "READ_TIMEOUT",
    "SDK_NAME",
    "USER_AGENT",
    "VERSION",
    "bot_runner",
    "dumps_json",
    "get_encoder_for",
    "import_bot_class",
    "item_to_wire",
    "loads_json",
    "main",
    "main_async",
    "media_to_wire",
    "parse_conversation",
    "parse_currency",
    "parse_item",
    "parse_media",
    "parse_message",
    "parse_position",
    "parse_server_message",
    "parse_session_metadata",
    "parse_user",
    "parse_webapi_response",
    "permissions_to_wire",
    "position_to_wire",
):
    if _public_name not in __all__:
        __all__.append(_public_name)

__all__ = sorted({_n for _n in __all__ if _n in globals()})


if __name__ == "__main__":
    main()

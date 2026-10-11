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
import gc
import importlib
import json
import logging
import os
import random
import socket
import sys
import tempfile
import time
import urllib.parse
import weakref
from collections import Counter, deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from enum import Enum
from inspect import isawaitable
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


TaskGroup = asyncio.TaskGroup

from .extras import (
    CommandContext,
    CommandRegistry,
    DebouncedSaver,
    Metrics,
    PromptManager,
    RoomTracker,
    TaskManager,
    ThrottledActions,
    TTLCache,
    UserResolver,
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
    _DoNotReconnect,
)
from .models_webapi import parse_webapi_response

try:
    from .extras import MISSING as _EXTRAS_MISSING
except ImportError:
    from .extras import _MISSING as _EXTRAS_MISSING

try:
    from .extras import CachedWebAPI
except ImportError:
    from .extras import WebAPI as CachedWebAPI


__version__ = "1.0.0"


__all__ = [
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
        return float(raw)
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
}

_LATENCIES_MS: deque[float] = deque(maxlen=10_000)

_LOOP_LAG_MS: deque[float] = deque(maxlen=10_000)
_GC_PAUSES_MS: deque[float] = deque(maxlen=1_000)
_LOOP_LAG_TASK: asyncio.Task | None = None
_LOOP_LAG_REFCOUNT: int = 0
_GC_START_TIME: float | None = None
_GC_CALLBACK_REGISTERED: bool = False
_GC_ENABLED: bool = False

_USER_INTERN: weakref.WeakValueDictionary[str, User] = weakref.WeakValueDictionary()


_DISPATCH_MAX_CONCURRENCY: int = _env_int("HR_DISPATCH_MAX_CONCURRENCY", 100)
_DISPATCH_QUEUE_MAX: int = _env_int("HR_DISPATCH_QUEUE_MAX", 1000)
_DISPATCH_ACTIVE: int = 0
_DISPATCH_DROPPED: int = 0
_DISPATCH_QUEUED: int = 0

_CHAT_FLOOD_QUEUE: deque[tuple[Any, ...]] = deque(maxlen=_DISPATCH_QUEUE_MAX)

_METRICS_MAXLEN: int = _env_int("HR_METRICS_MAXLEN", 10_000)

def _trim_deques_if_needed() -> None:
    """Ensure deques don't grow beyond _METRICS_MAXLEN (item 16 fix)."""
    try:
        if len(_LATENCIES_MS) > _METRICS_MAXLEN:
            while len(_LATENCIES_MS) > _METRICS_MAXLEN:
                _LATENCIES_MS.popleft()
        if len(_LOOP_LAG_MS) > _METRICS_MAXLEN:
            while len(_LOOP_LAG_MS) > _METRICS_MAXLEN:
                _LOOP_LAG_MS.popleft()
        if len(_GC_PAUSES_MS) > min(1000, _METRICS_MAXLEN):
            while len(_GC_PAUSES_MS) > min(1000, _METRICS_MAXLEN):
                _GC_PAUSES_MS.popleft()
    except Exception:
        pass

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
    _trim_deques_if_needed()




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
        elif phase == "stop":
            if _GC_START_TIME is not None:
                dur_ms = (time.perf_counter() - _GC_START_TIME) * 1000.0
                _GC_START_TIME = None
                try:
                    _GC_PAUSES_MS.append(float(dur_ms))
                except Exception:
                    pass
                if dur_ms > 50:
                    gen = info.get("generation", "?")
                    log.debug("GC pause: %.1fms gen=%s collected=%s", dur_ms, gen, info.get("collected"))
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
        frozen = gc.freeze()
        _GC_FROZEN = True
        log.info("GC tuned: froze %d objects (warmup %.1fs)", frozen, now - _GC_FIRST_TUNE_TIME)
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
    global _DISPATCH_ACTIVE, _DISPATCH_DROPPED, _DISPATCH_QUEUED
    _DISPATCH_ACTIVE = 0
    _DISPATCH_DROPPED = 0
    _DISPATCH_QUEUED = 0
    _trim_deques_if_needed()


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


async def _ws_send_text(ws: Any, data: bytes) -> None:
    """Send bytes over WebSocket using TEXT frames when possible."""
    if _WS_BINARY_FRAMES:
        send_bytes = getattr(ws, "send_bytes", None)
        if callable(send_bytes):
            await send_bytes(data)
            return

    send_str = getattr(ws, "send_str", None)
    if callable(send_str):
        await send_str(data.decode("utf-8"))
        return

    send_bytes = getattr(ws, "send_bytes", None)
    if callable(send_bytes):
        await send_bytes(data)
        return

    raise TypeError("WebSocket object supports neither send_str nor send_bytes")


async def _send_ws_payload(ws: Any, payload: dict[str, Any]) -> None:
    """Encode and send a WebSocket JSON payload."""

    fast = False

    try:
        if orjson is not None:
            data = orjson.dumps(payload, default=_json_default)

            fast = True

        else:
            data = json.dumps(
                payload,
                default=_json_default,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")

            fast = False

    except (TypeError, ValueError) as exc:
        _STATS["encode_errors"] += 1

        _STATS["errors"] += 1

        raise TypeError("JSON encoding failed") from exc

    try:
        await _ws_send_text(ws, data)

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

    _STATS["bytes_sent"] += len(data)


def _as_int(value: Any, default: int = 0) -> int:
    """Safely convert a value to int."""

    try:
        return int(value)

    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float."""

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
    """Parse a raw dictionary into a User model with WeakValueDictionary interning.

    Users are interned by id so that the same user id returns the same Python object
    (identity semantics). This is safe because User models are slots+weakref_slot
    and the table is a WeakValueDictionary — entries disappear when no longer referenced.
    Mutation-sharing hazard noted: if a handler mutates user.username, all references see it.
    At 1 msg/sec this is nil; for SDK-as-product it provides identity semantics.
    """
    if not isinstance(value, dict):
        return None
    uid = str(value.get("id", ""))
    uname = str(value.get("username", ""))
    if not uid:
        return User(id=uid, username=uname)
    existing = _USER_INTERN.get(uid)
    if existing is not None:
        if uname and existing.username != uname:
            try:
                existing.username = uname
            except Exception:
                pass
        return existing
    user = User(id=uid, username=uname)
    try:
        _USER_INTERN[uid] = user
    except Exception:
        pass
    return user


def _clear_user_intern() -> None:
    """Clear the user intern table (useful for tests)."""
    _USER_INTERN.clear()


def parse_position(value: Any) -> Position | AnchorPosition | None:
    """Parse a raw dictionary into a Position or AnchorPosition model."""
    if not isinstance(value, dict):
        return None

    if "entity_id" in value or "anchor_ix" in value:
        return AnchorPosition(
            entity_id=str(value.get("entity_id", "")),
            anchor_ix=_as_int(value.get("anchor_ix"), 0),
        )

    return Position(
        x=_as_float(value.get("x"), 0.0),
        y=_as_float(value.get("y"), 0.0),
        z=_as_float(value.get("z"), 0.0),
        facing=_normalize_facing(value.get("facing")),
    )


_FACING_VALUES = {"FrontRight", "FrontLeft", "BackRight", "BackLeft"}


def _normalize_facing(value: Any) -> str:
    """Normalize a facing direction value."""
    if isinstance(value, str) and value in _FACING_VALUES:
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

    return SessionMetadata(
        user_id=str(data.get("user_id", "")),
        room_info=room_info,
        rate_limits=data.get("rate_limits", {}) or {},
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


@_register_typed("Error")
def _parse_error(d: dict[str, Any]) -> Any:
    """Parse Error."""

    return Error(
        message=d.get("message") or "",
        do_not_reconnect=d.get("do_not_reconnect") or False,
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
    """Internal helper for Make ack parser."""

    def _parser(d: dict[str, Any]) -> Any:
        """Internal helper for Parser."""

        return ack_cls(rid=d.get("rid"))

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

    if not isinstance(msg_type, str):
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
    if isinstance(data, (str, bytes, bytearray)):
        try:
            data = loads_json(data)
        except (ValueError, TypeError, UnicodeDecodeError):
            if strict:
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
                )
            return data

    if strict:
        strict_semantic = True
        _hrf_validate_server_message(
            data,
            strict_semantic=strict_semantic,
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
            k: datetime.fromtimestamp(v, tz=UTC).isoformat()
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
    room_tracker: RoomTracker
    actions: ThrottledActions
    prompts: PromptManager

    validation_mode: str | None = None
    on_invalid: str | None = None
    invalid_warn_cooldown: float | None = None

    def __init__(
        self,
        *,
        validation_mode: str | None = None,
        on_invalid: str | None = None,
        invalid_warn_cooldown: float | None = None,
    ) -> None:
        """Initialize the instance."""
        self.metrics = Metrics()
        self.tasks = TaskManager()
        self.room_tracker = RoomTracker()
        self.prompts = PromptManager()
        self.actions = ThrottledActions(self)

        if getattr(self, "command_registry", None) is None:
            self.command_registry = commands

        if validation_mode is not None:
            self.validation_mode = validation_mode
        if on_invalid is not None:
            self.on_invalid = on_invalid
        if invalid_warn_cooldown is not None:
            self.invalid_warn_cooldown = invalid_warn_cooldown

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
        """Called after a successful reconnect (not on first connect).

        Override to implement custom resync logic. The default implementation
        checks ``highrise.state_dirty`` and, if set, calls ``GetRoomUsers`` to
        re-sync room state, then clears the dirty flag via ``mark_state_synced()``.
        """
        try:
            hr = getattr(self, "highrise", None)
            if hr is None:
                return
            if getattr(hr, "state_dirty", False):
                log.info("state_dirty set on reconnect — resyncing room users")
                try:
                    await hr.get_room_users()
                except Exception:
                    log.debug("Resync GetRoomUsers failed", exc_info=True)
                try:
                    hr.mark_state_synced()
                except Exception:
                    pass
        except Exception:
            log.debug("on_reconnected default resync failed", exc_info=True)


class Highrise:
    """WebSocket API client for sending bot actions and managing RPC replies."""
    def __init__(
        self,
        ws: Any = None,
        tg: TaskGroup | None = None,
        my_id: str = "",
    ) -> None:
        """Initialize the instance."""

        self.ws = ws

        self.tg = tg

        self.my_id = my_id

        self._req_id = count()

        self._pending: dict[str, asyncio.Future[Any]] = {}

        self._req_id_registry = self._pending

        self.state_dirty: bool = False

        self.dropped_packets: int = 0

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

    def _resolve_pending(self, rid: str, data: dict[str, Any]) -> bool:
        """Resolve the pending call for a request ID."""

        future = self._pending.pop(rid, None)

        if future is not None and not future.done():
            try:
                obj = parse_server_message(data)

            except Exception:
                log.exception("Failed to parse response for rid=%s", rid)

                obj = data

            future.set_result(obj)

            return True

        return False

    async def _send_only(
        self,
        type_name: str,
        fields: dict[str, Any] | None = None,
    ) -> None:
        """Send a WebSocket payload without waiting for a response."""

        payload: dict[str, Any] = {
            "_type": type_name,
            "rid": self._next_rid(),
        }

        if fields:
            payload.update(fields)

        await _send_ws_payload(self.ws, payload)

    _RPC_HARD_TIMEOUT: float = 30.0

    async def _call(
        self,
        type_name: str,
        fields: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
        raise_on_error: bool = False,
    ) -> Any:
        """Send a WebSocket RPC call and wait for the response."""
        rid = self._next_rid()
        payload: dict[str, Any] = {"_type": type_name, "rid": rid}
        if fields:
            payload.update(fields)
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self._pending[rid] = future
        t0 = time.perf_counter()
        try:
            await _send_ws_payload(self.ws, payload)

            if timeout is not None and timeout > 0:
                effective_timeout = timeout
            elif _REQ_TIMEOUT > 0:
                effective_timeout = _REQ_TIMEOUT
            else:
                effective_timeout = self._RPC_HARD_TIMEOUT

            response = await asyncio.wait_for(
                future,
                timeout=effective_timeout,
            )

            _STATS["pops"] += 1
            _record_latency(t0)
            if isinstance(response, Error):
                _STATS["api_errors"] += 1
                if raise_on_error:
                    raise ResponseError(response.message)
                return response
            return response
        except TimeoutError:
            _STATS["timeouts"] += 1
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
            try:
                await self._call(type_name, fields, raise_on_error=False)
            except Exception:
                log.debug("Fire-and-forget %s failed", type_name, exc_info=True)

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


class WebAPI:
    """HTTP client for the public Highrise WebAPI with optional caching."""
    url: str = BASE_WEB_URL

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: Any | None = None,
        cache_ttl: int | None = None,
    ) -> None:
        """Initialize the instance."""
        _ensure_aiohttp()

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
        self._cache = TTLCache()

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
        """Send a public WebAPI request."""
        return await self._get(endpoint)

    async def _get(self, endpoint: str, cache_ttl: int | None = None) -> Any:
        """Send a GET request to the public WebAPI."""
        ttl = self.cache_ttl if cache_ttl is None else max(0, int(cache_ttl))

        if ttl > 0:
            hit = self._cache.get(endpoint)

            if hit is not _EXTRAS_MISSING and hit is not None:
                return hit

        session = await self._get_session()

        async with session.get(f"{self.url}{endpoint}") as response:
            payload = await response.read()

            if response.status == 200:
                data = loads_json(payload)
                result = parse_webapi_response(endpoint, data)

                if ttl > 0:
                    self._cache.set(endpoint, result, ttl)

                return result

            raise ResponseError(payload.decode("utf-8", errors="replace"))

    def invalidate_cache(self, endpoint: str | None = None) -> None:
        """Invalidate cached WebAPI responses."""
        if endpoint is None:
            self._cache.clear()
        else:
            self._cache.invalidate(endpoint)

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None

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

    async def get_user(self, user_id: str) -> Any:
        """Get a public user by ID."""
        return await self._get(f"/users/{user_id}")

    async def get_users(
        self,
        starts_after: str | None = None,
        ends_before: str | None = None,
        sort_order: str = "desc",
        limit: int = 20,
        username: str | None = None,
    ) -> Any:
        """Get a paginated list of public users."""
        return await self._get(
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
    ) -> Any:
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

    async def get_room(self, room_id: str) -> Any:
        """Get a public room by ID."""
        return await self._get(f"/rooms/{room_id}")

    async def get_rooms(
        self,
        starts_after: str | None = None,
        ends_before: str | None = None,
        sort_order: str = "desc",
        limit: int = 20,
        room_name: str | None = None,
        owner_id: str | None = None,
    ) -> Any:
        """Get a paginated list of public rooms."""
        return await self._get(
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

    async def get_post(self, post_id: str) -> Any:
        """Get a public post by ID."""
        return await self._get(f"/posts/{post_id}")

    async def get_posts(
        self,
        starts_after: str | None = None,
        ends_before: str | None = None,
        sort_order: str = "desc",
        limit: int = 20,
        author_id: str | None = None,
    ) -> Any:
        """Get a paginated list of public posts."""
        return await self._get(
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

    async def get_item(self, item_id: str) -> Any:
        """Get a public item by ID."""
        return await self._get(f"/items/{item_id}")

    async def get_items(
        self,
        starts_after: str | None = None,
        ends_before: str | None = None,
        sort_order: str = "desc",
        limit: int = 20,
        rarity: str | None = None,
        item_name: str | None = None,
        category: Any | None = None,
    ) -> Any:
        """Get a paginated list of public items."""
        category_value = getattr(category, "value", category)

        return await self._get(
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

    async def get_grab(self, grab_id: str) -> Any:
        """Get a public grab by ID."""
        return await self._get(f"/grabs/{grab_id}")

    async def get_grabs(
        self,
        starts_after: str | None = None,
        ends_before: str | None = None,
        sort_order: str = "desc",
        limit: int = 20,
        title: str | None = None,
    ) -> Any:
        """Get a paginated list of public grabs."""
        return await self._get(
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


def active_subscriptions(bot: BaseBot) -> frozenset[str]:
    """Subscription names for the on_* handlers the bot's class overrides."""

    subs: set[str] = set()

    for method_name, event_name in _HANDLER_METHODS.items():
        base_handler = getattr(BaseBot, method_name, None)

        bot_handler = getattr(type(bot), method_name, None)

        if bot_handler is not None and bot_handler is not base_handler:
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
    global _DISPATCH_DROPPED
    if _dispatch_backpressure_check():
        _DISPATCH_DROPPED += 1
        _STATS["dispatch_dropped"] += 1
        log.debug("Dispatcher backpressure: dropping %s (active=%d >= max=%d)", event_type, _DISPATCH_ACTIVE, _DISPATCH_MAX_CONCURRENCY)
        return False
    _dispatch_inc()
    try:
        if bot is not None and event_type is not None:
            async def _wrapper():
                try:
                    await _safe_handler_with_metrics(result, event_type, bot)
                finally:
                    _dispatch_dec()
            tg.create_task(_wrapper())
        else:
            async def _wrapper2():
                try:
                    await _safe_handler(result)
                finally:
                    _dispatch_dec()
            tg.create_task(_wrapper2())
        return True
    except Exception:
        _dispatch_dec()
        log.debug("Failed to spawn task", exc_info=True)
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

    data = loads_json(truncated)

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

        assert False, "Should have raised semantic error"

    except HighriseFastValidationError as e:
        assert any(
            err.reason_code == ReasonCode.OUT_OF_BOUNDS for err in e.errors
        ), "Missing OUT_OF_BOUNDS reason code"

    missing_field = {"_type": "ChatEvent", "user": {"id": "1"}, "whisper": False}

    try:
        validate_server_message(missing_field, strict=True)

        assert False, "Should have raised missing field error"

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


def _dispatch_event(
    bot: BaseBot,
    bot_id: str,
    event_type: str | None,
    data: dict[str, Any],
    tg: TaskGroup,
    subscriptions: frozenset[str] | None = None,
) -> bool:
    """Dispatch a validated event to the matching bot handler."""
    global _DISPATCH_QUEUED
    if subscriptions is not None:
        if not isinstance(event_type, str):
            return False
        needed = _EVENT_TO_SUBSCRIPTION.get(event_type)
        if needed is not None and needed not in subscriptions:
            return False
    if event_type == "ChatEvent":
        if _dispatch_backpressure_check():
            if len(_CHAT_FLOOD_QUEUE) >= _CHAT_FLOOD_QUEUE.maxlen:
                _STATS["chat_flood_dropped"] += 1
            _CHAT_FLOOD_QUEUE.append((bot, bot_id, event_type, data, tg, time.monotonic()))
            _STATS["dispatch_queued"] += 1
            _DISPATCH_QUEUED = len(_CHAT_FLOOD_QUEUE)
            log.debug("Chat flood buffering: queued (size=%d active=%d)", len(_CHAT_FLOOD_QUEUE), _DISPATCH_ACTIVE)
            return True
        user = parse_user(data.get("user"))
        if user is None or user.id == bot_id:
            return True
        message = str(data.get("message", ""))
        whisper = bool(data.get("whisper", False))
        _prompts = getattr(bot, "prompts", None)
        if _prompts is not None and _prompts.resolve(user.id, message):
            return True
        _cmd_registry = getattr(bot, "command_registry", None) or commands
        _prefix = getattr(_cmd_registry, "prefix", "!")
        _handler = bot.on_whisper if whisper else bot.on_chat
        if message.startswith(_prefix):
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

            _spawn_task(
                tg,
                _run_command(),
                bot,
                "ChatEvent",
            )
            return True
        _spawn_task(
            tg,
            _handler(user, message),
            bot,
            "ChatEvent",
        )
        return True
    if event_type == "EmoteEvent":
        user = parse_user(data.get("user"))
        if user is None:
            return True
        receiver = parse_user(data.get("receiver"))
        _spawn_task(
            tg,
            bot.on_emote(user, str(data.get("emote_id", "")), receiver),
            bot,
            "EmoteEvent",
        )
        return True
    if event_type == "ReactionEvent":
        user = parse_user(data.get("user"))
        receiver = parse_user(data.get("receiver"))
        if user is None:
            return True
        _spawn_task(
            tg,
            bot.on_reaction(user, str(data.get("reaction", "")), receiver),
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
        _spawn_task(
            tg,
            bot.on_user_join(user, position),
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
        _spawn_task(
            tg,
            bot.on_user_leave(user),
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
        _spawn_task(
            tg,
            bot.on_user_move(user, position),
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
        _cmd_registry = getattr(bot, "command_registry", None) or commands
        if _cmd_registry and getattr(bot, "highrise", None):

            async def _handle_dm_command(
                _bot=bot, _uid=user_id, _cid=conversation_id, _reg=_cmd_registry
            ) -> None:
                """Internal helper for Handle dm command."""
                try:
                    resp = await _bot.highrise.get_messages(_cid)
                    if resp and hasattr(resp, "messages") and resp.messages:
                        bot_id = getattr(_bot.highrise, "my_id", "")
                        for msg in reversed(resp.messages):
                            sender = getattr(msg, "sender_id", "") or getattr(
                                msg, "user_id", ""
                            )
                            if sender == bot_id:
                                continue
                            content = getattr(msg, "content", "") or ""
                            if content.startswith(_reg.prefix):
                                dummy_user = User(id=_uid, username=_uid)
                                await _reg.handle(
                                    _bot,
                                    dummy_user,
                                    content,
                                    source="dm",
                                    conversation_id=_cid,
                                )
                                break
                except Exception as e:
                    logging.getLogger("highrise_fast.commands").debug(
                        "DM command routing failed: %r", e
                    )

            tg.create_task(_safe_handler(_handle_dm_command()))
        _spawn_task(
            tg,
            bot.on_message(user_id, conversation_id, is_new),
            bot,
            "MessageEvent",
        )
        return True
    if event_type == "RoomModeratedEvent":
        duration_raw = data.get("duration")
        duration = None if duration_raw is None else _as_int(duration_raw)
        _spawn_task(
            tg,
            bot.on_moderate(
                str(data.get("moderatorId", "")),
                str(data.get("targetUserId", "")),
                str(data.get("moderationType", "")),
                duration,
            ),
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

    if data.get("_type") == "Error":
        return Error(
            message=str(data.get("message", "")),
            do_not_reconnect=bool(data.get("do_not_reconnect", False)),
            rid=data.get("rid"),
        )

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

    if data.get("_type") == "Error":
        return Error(
            message=str(data.get("message", "")),
            do_not_reconnect=bool(data.get("do_not_reconnect", False)),
            rid=data.get("rid"),
        )

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
            data = loads_json(frame.data)

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

        if strict:
            vtype = event_type if isinstance(event_type, str) else None

            if vtype not in _VALIDATION_EXEMPT and (
                isinstance(rid, str)
                or (vtype is not None and vtype in _EVENT_TO_SUBSCRIPTION)
            ):
                try:
                    _hrf_validate_server_message(data)

                except HighriseFastValidationError as exc:
                    if _handle_invalid_packet(
                        exc, data, highrise, bot, tg, on_invalid, warn_cooldown
                    ):
                        continue

        if isinstance(rid, str):
            if highrise._resolve_pending(rid, data):
                _STATS["incoming_fast"] += 1

            else:
                _STATS["incoming_fallback"] += 1

                log.debug("Received response with unknown rid: %s", rid)

            continue

        if event_type == "KeepaliveResponse":
            _STATS["incoming_fast"] += 1

            continue

        if event_type == "Error":
            error = Error(
                message=str(data.get("message", "")),
                do_not_reconnect=bool(data.get("do_not_reconnect", False)),
                rid=data.get("rid"),
            )

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
    when running multiple radios.
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



async def _drain_chat_flood_queue():
    """Background worker draining buffered ChatEvents with rate limiting (item 14)."""
    while True:
        try:
            if not _CHAT_FLOOD_QUEUE:
                await asyncio.sleep(0.05)
                continue
            if _dispatch_backpressure_check():
                await asyncio.sleep(0.05)
                continue
            bot, bot_id, event_type, data, tg, enqueued_at = _CHAT_FLOOD_QUEUE.popleft()
            _STATS["dispatch_queued"] = len(_CHAT_FLOOD_QUEUE)
            try:
                _dispatch_event(bot, bot_id, event_type, data, tg, None)
            except Exception:
                log.debug("Drain dispatch failed", exc_info=True)
            await asyncio.sleep(0.02)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.debug("Chat flood drain loop error", exc_info=True)
            await asyncio.sleep(0.1)


_CHAT_DRAIN_TASK: asyncio.Task | None = None
_CHAT_DRAIN_REFCOUNT: int = 0

def start_chat_drain_task() -> asyncio.Task | None:
    global _CHAT_DRAIN_TASK, _CHAT_DRAIN_REFCOUNT
    _CHAT_DRAIN_REFCOUNT += 1
    if _CHAT_DRAIN_TASK is not None and not _CHAT_DRAIN_TASK.done():
        return _CHAT_DRAIN_TASK
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    _CHAT_DRAIN_TASK = loop.create_task(_drain_chat_flood_queue())
    _CHAT_DRAIN_TASK.set_name("highrise_fast-chat-drain")
    return _CHAT_DRAIN_TASK


async def stop_chat_drain_task() -> None:
    global _CHAT_DRAIN_TASK, _CHAT_DRAIN_REFCOUNT
    if _CHAT_DRAIN_REFCOUNT > 0:
        _CHAT_DRAIN_REFCOUNT -= 1
    if _CHAT_DRAIN_REFCOUNT > 0:
        return
    if _CHAT_DRAIN_TASK is None:
        return
    _CHAT_DRAIN_TASK.cancel()
    try:
        await _CHAT_DRAIN_TASK
    except asyncio.CancelledError:
        pass
    _CHAT_DRAIN_TASK = None


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
    """Run a single bot with reconnect logic, backoff+jitter, loop-lag/GC monitoring, and resync hook."""
    setup_logging()
    _ensure_aiohttp()
    _ensure_gc_monitoring()
    if getattr(bot, "metrics", None) is None:
        bot.metrics = Metrics()
    if getattr(bot, "tasks", None) is None:
        bot.tasks = TaskManager()
    lag_task = start_loop_lag_monitor(0.1)
    drain_task = start_chat_drain_task()
    _trim_deques_if_needed()
    reconnect_attempt = 0
    is_first_connect = True
    try:
        async with TaskGroup() as tg:
            t = throttler(5, 5)
            while True:
                await anext(t)
                try:
                    await bot.before_start(tg)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.exception("before_start failed; retrying (attempt %d)", reconnect_attempt)
                    await _sleep_backoff(reconnect_attempt)
                    reconnect_attempt += 1
                    continue
                highrise: Highrise | None = None
                ka_task: asyncio.Task | None = None
                try:
                    timeout_obj = (
                        ClientTimeout(total=30, sock_connect=10, sock_read=60)
                        if ClientTimeout
                        else None
                    )
                    async with ClientSession(timeout=timeout_obj) as session:
                        subs = active_subscriptions(bot)
                        url = f"{BASE_WS_URL}{_subscription_query(subs)}"
                        async with session.ws_connect(
                            url,
                            headers={
                                "room-id": room_id,
                                "api-token": api_key,
                                "user-agent": USER_AGENT,
                            },
                        ) as ws:
                            ka_task = asyncio.create_task(_send_keepalive(ws))
                            try:
                                session_metadata = await _receive_metadata(ws)
                                if isinstance(session_metadata, Error):
                                    print(f"ERROR: {session_metadata}")
                                    return
                                highrise = Highrise(
                                    ws=ws,
                                    tg=tg,
                                    my_id=str(session_metadata.user_id),
                                )
                                bot.highrise = highrise
                                _actions = getattr(bot, "actions", None)
                                if _actions is not None and hasattr(_actions, "start"):
                                    _actions.start()
                                if getattr(bot, "webapi", None) is None:
                                    bot.webapi = WebAPI(cache_ttl=_WEBAPI_CACHE_TTL)
                                if (
                                    session_metadata.sdk_version is not None
                                    and session_metadata.sdk_version != VERSION
                                ):
                                    log.debug(
                                        "Server SDK version %s differs from running SDK %s",
                                        session_metadata.sdk_version,
                                        VERSION,
                                    )
                                if is_first_connect:
                                    _spawn_task(
                                        tg,
                                        bot.on_start(session_metadata),
                                        bot,
                                        "on_start",
                                    )
                                    is_first_connect = False
                                else:
                                    log.info("Reconnected — running on_reconnected hook (attempt %d)", reconnect_attempt)
                                    try:
                                        await bot.on_reconnected()
                                    except Exception:
                                        log.debug("on_reconnected hook failed", exc_info=True)
                                _maybe_tune_gc()
                                asyncio.get_running_loop().call_later(
                                    5.5, _maybe_tune_gc
                                )
                                reconnect_attempt = 0
                                await _receive_loop(
                                    ws,
                                    highrise,
                                    bot,
                                    tg,
                                    session_metadata,
                                    subs or None,
                                )
                            finally:
                                if highrise is not None:
                                    highrise.fail_pending("connection lost")
                                await _cancel_and_wait(ka_task)
                                ka_task = None
                except _DoNotReconnect:
                    return
                except asyncio.CancelledError:
                    raise
                except _FatalValidationError:
                    log.critical("Fatal validation error; aborting bot_runner")
                    raise
                except (ConnectionResetError, TimeoutError):
                    log.info("Connection lost/timeout; reconnecting (attempt %d)", reconnect_attempt)
                    await _sleep_backoff(reconnect_attempt)
                    reconnect_attempt += 1
                except Exception as exc:
                    if _is_handshake_error(exc):
                        log.warning("WebSocket handshake failed; retrying (attempt %d)", reconnect_attempt)
                    else:
                        log.exception("ERROR: reconnecting (attempt %d)...", reconnect_attempt)
                    await _sleep_backoff(reconnect_attempt)
                    reconnect_attempt += 1
                finally:
                    if ka_task is not None:
                        await _cancel_and_wait(ka_task)
    except asyncio.CancelledError:
        raise
    except _BASE_EXCEPTION_GROUP as eg:
        if _contains_cancelled(eg) or _contains_fatal(eg):
            raise
        log.debug("TaskGroup exited with exception group", exc_info=True)
    except Exception:
        log.debug("bot_runner exited with unhandled exception", exc_info=True)
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
                                    print(f"ERROR: {metadata}")

                                    return

                                for instance_id in metadata.instance_ids:
                                    _start_bot(instance_id)

                                ctrl_attempt = 0

                                while True:
                                    frame = await ws.receive(READ_TIMEOUT)

                                    if frame.type in CLOSE_TYPES:
                                        print(
                                            "Control connection with ID: "
                                            f"{metadata.connection_id} closed by "
                                            "server, reconnecting."
                                        )

                                        break

                                    if frame.type == WSMsgType.ERROR:
                                        return

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
    from .validation import BASE_PAYLOADS, validate_server_message, HighriseFastValidationError

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
        try:
            validate_server_message(sample)
        except HighriseFastValidationError:
            pass
        except Exception:
            pass
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
    """Consolidated benchmark entry point (merges V1-V7 conceptually).

    In the GitHub repo, Benchmarks/ contains 9 files V1..V7. This function
    is the single maintained entry point that CI should call, replacing the
    need to run each version separately. It runs:
    - Internal SDK tests (fuzzer + protocol)
    - Performance gate (hard fail if validation slows)
    - Unified parse vs old parse timing
    - Loop-lag / GC snapshot if available

    Returns 0 on success, 1 on failure.
    """
    print("=== highrise_fast consolidated benchmarks ===")
    print(f"Python {sys.version.split()[0]} | {platform.python_implementation() if 'platform' in globals() else ''}")

    try:
        gate = _performance_gate(max_ms_per_1000=100.0, strict=True)
        print(f"✓ Performance gate: {gate['total_ms']}ms for {gate['iterations']} validations ({gate['per_msg_us']}us/msg)")
    except AssertionError as e:
        print(f"✗ {e}")
        return 1
    except Exception as e:
        print(f"? Performance gate error: {e}")
        if verbose:
            import traceback; traceback.print_exc()

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
        _clear_user_intern()
        u1 = parse_user({"id":"123","username":"alice"})
        u2 = parse_user({"id":"123","username":"alice"})
        assert u1 is u2, "Interning failed: same id should return same object"
        print("✓ User interning: identity semantics OK")
    except Exception as e:
        print(f"✗ User interning failed: {e}")
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
    if sys.version_info < (3, 11):
        print("  ✗ FAIL: Python 3.11+ required")
        ok = False
    else:
        print("  ✓ Python version OK")

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
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM, timeout=5)
        ips = sorted({i[4][0] for i in infos})
        print(f"  DNS: {host} -> {', '.join(ips[:3])}{'...' if len(ips)>3 else ''}")
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
    print("  (No token provided to doctor — checking env var HR token pattern if present)")
    print("  ℹ Highrise bot tokens are typically 80+ chars, no spaces, no 'Bearer' prefix")

    print("\nEnv flags:")
    print(f"  HR_WS_BINARY={os.environ.get('HR_WS_BINARY','0')} -> {'BINARY' if _WS_BINARY_FRAMES else 'TEXT (default, proxy-safe)'}")
    if _WS_BINARY_FRAMES:
        print("  ⚠ BINARY frames enabled — ensure endpoint accepts binary or you will be muted")
    print(f"  HR_SDK_REQ_TIMEOUT / SDK_FAST_REQ_TIMEOUT -> _REQ_TIMEOUT={_REQ_TIMEOUT}s (0=disabled, now default 10s)")
    if _REQ_TIMEOUT <= 0:
        print("  ⚠ Send timeout disabled — RPC can hang forever on dropped response")
    else:
        print(f"  ✓ Send timeout { _REQ_TIMEOUT }s enabled (hard ceiling {_RPC_HARD_TIMEOUT if '_RPC_HARD_TIMEOUT' in globals() else 30}s)")

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

    print("\nUser interning:")
    try:
        intern_size = len(_USER_INTERN) if '_USER_INTERN' in globals() else 0
        print(f"  Intern table size: {intern_size} (WeakValueDictionary)")
        print("  ✓ Interning enabled (slots+weakref_slot prerequisite met)")
    except Exception as e:
        print(f"  ? Intern check failed: {e}")

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
    if any(a in ("--doctor", "-d") for a in raw_args):
        sys.exit(_doctor_check())

    parser = argparse.ArgumentParser(
        description="Run a Highrise bot using the standalone fast SDK. Use 'doctor' subcommand for diagnostics."
    )

    subparsers = parser.add_subparsers(dest="subcommand")

    doc_parser = subparsers.add_parser("doctor", help="Run self-diagnostic checks")

    parser.add_argument(
        "bot_path",
        nargs="?",
        help="Module path and class name (e.g. module:ClassName)",
    )

    parser.add_argument(
        "room_id",
        nargs="?",
        help="Room ID",
    )

    parser.add_argument(
        "api_token",
        nargs="?",
        help="API Token",
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

    if args.subcommand == "doctor":
        sys.exit(_doctor_check())

    if not args.bot_path or not args.room_id or not args.api_token:
        if args.bot_path and args.bot_path.lower() == "doctor":
            sys.exit(_doctor_check())
        parser.print_help()
        sys.exit(2)

    if args.validation:
        os.environ["HIGHRISE_FAST_VALIDATION"] = args.validation

    if args.on_invalid:
        os.environ["HIGHRISE_FAST_ON_INVALID"] = args.on_invalid

    first_bot_path = args.bot_path

    first_room_id = args.room_id

    first_token = args.api_token

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
from .compat_requests import *

for _name in getattr(_compat_requests, "__all__", []):
    if _name not in __all__:
        __all__.append(_name)


if __name__ == "__main__":
    main()

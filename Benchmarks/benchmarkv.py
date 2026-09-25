#!/usr/bin/env python3
"""
benchmark_all.py

Comprehensive benchmark suite for highrise_fast.

Covers 100+ benchmark targets:
- core event-loop parsing throughput
- strict / semantic validation overhead
- sad-path exception generation
- malicious payloads
- memory and GC pressure
- asyncio dynamics
- outbound serialization
- optional comparisons against orjson / ujson / msgspec / pydantic / official SDK

Usage:
    python benchmark_all.py --quick
    python benchmark_all.py
    python benchmark_all.py --full
    python benchmark_all.py --category 05_malicious
    python benchmark_all.py --filter UserMoved
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import gc
import importlib.util
import json
import os
import sys
import time
import tracemalloc
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from typing import Any

# -----------------------------------------------------------------------------
# SDK imports
# -----------------------------------------------------------------------------

try:
    import highrise_fast as hf
    from highrise_fast.validation import (
        BASE_PAYLOADS,
        HighriseFastValidationError,
        validate_server_message,
    )
except Exception as exc:
    sys.exit(f"Cannot import highrise_fast: {exc}")

parse_server_message = getattr(hf, "parse_server_message", None)
if parse_server_message is None:
    sys.exit("highrise_fast.parse_server_message not found")

hf_dumps = getattr(hf, "dumps_json", None)
hf_loads = getattr(hf, "loads_json", None)

if hf_dumps is None:

    def hf_dumps(payload: dict) -> bytes:
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )


if hf_loads is None:

    def hf_loads(raw: Any) -> Any:
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
        return json.loads(raw)


# Optional third-party engines.
try:
    import orjson
except ImportError:
    orjson = None

try:
    import ujson
except ImportError:
    ujson = None

try:
    import msgspec
except ImportError:
    msgspec = None

try:
    from pydantic import BaseModel
except ImportError:
    BaseModel = None


# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------


def safe_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(name))


def deep_getsizeof(obj: Any, seen: set[int] | None = None) -> int:
    """Recursive-ish sizeof for dicts/lists/sets. Good enough for benchmarks."""
    if seen is None:
        seen = set()

    oid = id(obj)
    if oid in seen:
        return 0
    seen.add(oid)

    size = sys.getsizeof(obj)

    if isinstance(obj, dict):
        size += sum(
            deep_getsizeof(k, seen) + deep_getsizeof(v, seen) for k, v in obj.items()
        )
    elif isinstance(obj, (list, tuple, set, frozenset, deque)):
        size += sum(deep_getsizeof(item, seen) for item in obj)

    return size


def clean_obj(obj: Any) -> Any:
    """
    Strip accidental trailing spaces from keys and string values.

    This is useful if BASE_PAYLOADS came from a copy/paste source that
    introduced artifacts like:
        "ChatEvent "
        "_type "
        "FrontRight "
    """
    if isinstance(obj, dict):
        return {str(k).strip(): clean_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_obj(v) for v in obj]
    if isinstance(obj, str):
        return obj.strip()
    return obj


# -----------------------------------------------------------------------------
# Payload corpus
# -----------------------------------------------------------------------------

FALLBACK_PAYLOADS: dict[str, dict[str, Any]] = {
    "ChatEvent": {
        "_type": "ChatEvent",
        "user": {"id": "u1", "username": "tester"},
        "message": "hello world",
        "whisper": False,
    },
    "EmoteEvent": {
        "_type": "EmoteEvent",
        "user": {"id": "u1", "username": "tester"},
        "emote_id": "emote-1",
    },
    "ReactionEvent": {
        "_type": "ReactionEvent",
        "user": {"id": "u1", "username": "tester"},
        "reaction": "heart",
        "receiver": {"id": "u2", "username": "receiver"},
    },
    "UserJoinedEvent": {
        "_type": "UserJoinedEvent",
        "user": {"id": "u1", "username": "tester"},
        "position": {"x": 1.0, "y": 0.0, "z": 2.0, "facing": "FrontRight"},
    },
    "UserLeftEvent": {
        "_type": "UserLeftEvent",
        "user": {"id": "u1", "username": "tester"},
    },
    "UserMovedEvent": {
        "_type": "UserMovedEvent",
        "user": {"id": "u1", "username": "tester"},
        "position": {"x": 1.5, "y": 0.0, "z": 2.5, "facing": "FrontLeft"},
    },
    "ChannelEvent": {
        "_type": "ChannelEvent",
        "sender_id": "u1",
        "msg": "channel message",
        "tags": [],
    },
    "TipReactionEvent": {
        "_type": "TipReactionEvent",
        "sender": {"id": "u1", "username": "sender"},
        "receiver": {"id": "u2", "username": "receiver"},
        "item": {"type": "gold", "amount": 1},
    },
    "VoiceEvent": {
        "_type": "VoiceEvent",
        "users": [[{"id": "u1", "username": "tester"}, "voice"]],
        "seconds_left": 10,
    },
    "MessageEvent": {
        "_type": "MessageEvent",
        "user_id": "u1",
        "conversation_id": "conv-1",
        "is_new_conversation": False,
    },
    "RoomModeratedEvent": {
        "_type": "RoomModeratedEvent",
        "moderatorId": "mod1",
        "targetUserId": "u2",
        "moderationType": "mute",
        "duration": 60,
    },
    "Error": {
        "_type": "Error",
        "message": "timeout",
        "do_not_reconnect": False,
        "rid": "1",
    },
    "GetRoomUsersResponse": {
        "_type": "GetRoomUsersResponse",
        "content": [
            [
                {"id": "u1", "username": "tester"},
                {"x": 1.0, "y": 0.0, "z": 2.0, "facing": "FrontRight"},
            ],
            [
                {"id": "u2", "username": "tester2"},
                {"x": 3.0, "y": 0.0, "z": 4.0, "facing": "BackLeft"},
            ],
        ],
        "rid": "1",
    },
    "GetWalletResponse": {
        "_type": "GetWalletResponse",
        "content": [{"type": "gold", "amount": 100}],
        "rid": "1",
    },
    "GetBackpackResponse": {
        "_type": "GetBackpackResponse",
        "backpack": {"item1": 1},
        "rid": "1",
    },
    "GetInventoryResponse": {
        "_type": "GetInventoryResponse",
        "items": [
            {
                "type": "clothing",
                "amount": 1,
                "id": "shirt_1",
                "account_bound": False,
                "active_palette": 0,
            }
        ],
        "rid": "1",
    },
    "ChatResponse": {
        "_type": "ChatResponse",
        "rid": "1",
    },
    "KeepaliveResponse": {
        "_type": "KeepaliveResponse",
        "rid": "1",
    },
}


def build_base_payloads() -> dict[str, dict[str, Any]]:
    base: dict[str, dict[str, Any]] = {}

    try:
        if isinstance(BASE_PAYLOADS, dict) and BASE_PAYLOADS:
            for k, v in BASE_PAYLOADS.items():
                base[str(k).strip()] = clean_obj(v)
    except Exception:
        base = {}

    # Ensure important hot events always exist.
    for k, v in FALLBACK_PAYLOADS.items():
        base.setdefault(k, clean_obj(v))

    return base


def get_payload(base: dict[str, dict[str, Any]], name: str) -> dict[str, Any]:
    return base.get(name) or FALLBACK_PAYLOADS[name]


# -----------------------------------------------------------------------------
# Payload mutation helpers
# -----------------------------------------------------------------------------

IMPORTANT_KEYS = (
    "user",
    "position",
    "message",
    "whisper",
    "emote_id",
    "reaction",
    "receiver",
    "sender",
    "item",
    "users",
    "seconds_left",
    "sender_id",
    "msg",
    "moderatorId",
    "targetUserId",
    "moderationType",
    "duration",
    "user_id",
    "conversation_id",
    "is_new_conversation",
    "content",
    "backpack",
    "result",
    "items",
    "outfit",
    "conversations",
    "not_joined",
    "messages",
    "media",
    "rid",
)


def corrupt_payload(payload: dict[str, Any]) -> dict[str, Any]:
    d = copy.deepcopy(payload)

    for key in IMPORTANT_KEYS:
        if key in d:
            value = d[key]
            if isinstance(value, dict):
                d[key] = ["wrong", "list"]
            elif isinstance(value, list):
                d[key] = {"wrong": "dict"}
            elif isinstance(value, bool):
                d[key] = "true"
            elif isinstance(value, int):
                d[key] = "not-int"
            elif isinstance(value, float):
                d[key] = "not-float"
            else:
                d[key] = ["wrong"]
            return d

    d["_type"] = 123
    return d


def missing_required_payload(payload: dict[str, Any]) -> dict[str, Any]:
    d = copy.deepcopy(payload)

    for key in IMPORTANT_KEYS:
        if key in d:
            del d[key]
            return d

    d.pop("_type", None)
    return d


def extra_keys_payload(payload: dict[str, Any], count: int) -> dict[str, Any]:
    d = copy.deepcopy(payload)
    for i in range(count):
        d[f"extra_{i}"] = "x"
    return d


def type_last_payload(payload: dict[str, Any]) -> dict[str, Any]:
    d = {k: v for k, v in payload.items() if k != "_type"}
    if "_type" in payload:
        d["_type"] = payload["_type"]
    return d


def validates_ok(payload: dict[str, Any]) -> bool:
    try:
        validate_server_message(payload, strict=True)
        return True
    except Exception:
        return False


# -----------------------------------------------------------------------------
# Benchmark timing engine
# -----------------------------------------------------------------------------


def time_sync(fn: Callable[[], Any], iterations: int) -> dict[str, Any]:
    warmup = max(1, min(5, iterations // 10))

    for _ in range(warmup):
        fn()

    start = time.perf_counter()
    for _ in range(iterations):
        fn()
    elapsed = max(time.perf_counter() - start, 1e-12)

    return {
        "iterations": iterations,
        "total_s": elapsed,
        "ops_per_s": iterations / elapsed,
        "avg_us": (elapsed / iterations) * 1_000_000.0,
    }


def time_async(async_fn: Callable[[], Any], iterations: int) -> dict[str, Any]:
    async def runner() -> None:
        for _ in range(iterations):
            await async_fn()

    # Warmup.
    asyncio.run(runner())

    start = time.perf_counter()
    asyncio.run(runner())
    elapsed = max(time.perf_counter() - start, 1e-12)

    return {
        "iterations": iterations,
        "total_s": elapsed,
        "ops_per_s": iterations / elapsed,
        "avg_us": (elapsed / iterations) * 1_000_000.0,
    }


def bench_memory(fn: Callable[[], Any], iterations: int) -> dict[str, Any]:
    gc.collect()

    try:
        gc.disable()
    except Exception:
        pass

    tracemalloc.start()
    start_blocks = sys.getallocatedblocks()
    start = time.perf_counter()

    try:
        for _ in range(iterations):
            fn()
    finally:
        duration = max(time.perf_counter() - start, 1e-12)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        end_blocks = sys.getallocatedblocks()

        try:
            gc.enable()
        except Exception:
            pass

    return {
        "iterations": iterations,
        "total_s": duration,
        "ops_per_s": iterations / duration,
        "tracemalloc_current_kb": current / 1024.0,
        "tracemalloc_peak_kb": peak / 1024.0,
        "allocated_blocks_delta": max(0, end_blocks - start_blocks),
        "allocated_blocks_per_call": max(0.0, (end_blocks - start_blocks) / iterations),
    }


def run_case(case: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    kind = case["kind"]
    fn = case["fn"]

    if case.get("iterations") is not None:
        iterations = case["iterations"]
    elif kind == "sync":
        iterations = args.iterations
    elif kind == "async":
        iterations = args.async_iterations
    elif kind == "memory":
        iterations = args.memory_iterations
    else:
        iterations = 1

    try:
        if kind == "sync":
            metrics = time_sync(fn, iterations)
        elif kind == "async":
            metrics = time_async(fn, iterations)
        elif kind == "memory":
            metrics = bench_memory(fn, iterations)
        elif kind == "custom":
            metrics = fn()
            if not isinstance(metrics, dict):
                metrics = {"result": metrics}
        else:
            raise ValueError(f"unknown kind: {kind}")

        metrics["status"] = "ok"
        return metrics

    except Exception as exc:
        return {
            "status": "error",
            "error": repr(exc),
        }


# -----------------------------------------------------------------------------
# Case builder
# -----------------------------------------------------------------------------


def build_cases(args: argparse.Namespace) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    base = build_base_payloads()

    def add_case(
        name: str,
        category: str,
        kind: str,
        fn: Callable[[], Any],
        iterations: int | None = None,
        description: str = "",
    ) -> None:
        cases.append(
            {
                "name": name,
                "category": category,
                "kind": kind,
                "fn": fn,
                "iterations": iterations,
                "description": description,
            }
        )

    # -------------------------------------------------------------------------
    # 00 environment / diagnostics
    # -------------------------------------------------------------------------

    def env_metrics() -> dict[str, Any]:
        return {
            "python": sys.version.split()[0],
            "platform": sys.platform,
            "pypy": hasattr(sys, "pypy_version_info"),
            "asyncio_policy": type(asyncio.get_event_loop_policy()).__name__,
            "orjson": orjson is not None,
            "ujson": ujson is not None,
            "msgspec": msgspec is not None,
            "pydantic": BaseModel is not None,
            "uvloop_available": importlib.util.find_spec("uvloop") is not None,
            "highrise_fast_version": getattr(hf, "__version__", None),
        }

    add_case(
        "env_environment",
        "00_environment",
        "custom",
        env_metrics,
        description="Runtime environment capabilities.",
    )

    def validation_health() -> dict[str, Any]:
        failed = []
        for name, payload in base.items():
            try:
                validate_server_message(payload, strict=True)
            except Exception as exc:
                failed.append({"type": name, "error": str(exc)[:200]})

        return {
            "total_base_payloads": len(base),
            "failed_count": len(failed),
            "failed_examples": failed[:20],
        }

    add_case(
        "env_validation_health",
        "00_environment",
        "custom",
        validation_health,
        description="Checks whether cleaned BASE_PAYLOADS pass strict validation.",
    )

    def sdk_stats_snapshot() -> dict[str, Any]:
        try:
            return dict(hf.stats())
        except Exception as exc:
            return {"error": repr(exc)}

    add_case(
        "env_sdk_stats_snapshot",
        "00_environment",
        "custom",
        sdk_stats_snapshot,
        description="highrise_fast.stats() snapshot before load.",
    )

    # -------------------------------------------------------------------------
    # 01 core event loop + 02 validation overhead for all known event types
    # -------------------------------------------------------------------------

    HOT_TYPES = {
        "ChatEvent",
        "UserJoinedEvent",
        "UserLeftEvent",
        "UserMovedEvent",
        "EmoteEvent",
        "ReactionEvent",
        "TipReactionEvent",
        "VoiceEvent",
        "ChannelEvent",
        "GetRoomUsersResponse",
        "GetWalletResponse",
        "GetInventoryResponse",
    }

    for event_type, payload in base.items():
        safe = safe_name(event_type)

        # 1. Lenient parse.
        add_case(
            f"core_parse_lenient_{safe}",
            "01_core_event_loop",
            "sync",
            lambda p=payload: parse_server_message(p),
            description="Lenient parse / typed conversion.",
        )

        # 2. Strict structural validation, if the payload is currently valid.
        if validates_ok(payload):
            add_case(
                f"core_validate_struct_{safe}",
                "02_validation_overhead",
                "sync",
                lambda p=payload: validate_server_message(p, strict=True),
                description="Strict structural validation.",
            )

        # 3. Sad path: corrupted payload.
        bad = corrupt_payload(payload)

        def invalid_validator(b=bad) -> None:
            try:
                validate_server_message(b, strict=True)
            except HighriseFastValidationError:
                pass
            except Exception:
                pass

        add_case(
            f"sad_invalid_corrupt_{safe}",
            "02_validation_overhead",
            "sync",
            invalid_validator,
            description="Corrupted payload rejection path.",
        )

        # 4. Extra variants for hot types.
        if event_type in HOT_TYPES:
            raw = hf_dumps(payload)

            if validates_ok(payload):
                add_case(
                    f"core_parse_strict_{safe}",
                    "01_core_event_loop",
                    "sync",
                    lambda p=payload: parse_server_message(p, strict=True),
                    description="parse_server_message(strict=True).",
                )

                add_case(
                    f"core_validate_semantic_{safe}",
                    "02_validation_overhead",
                    "sync",
                    lambda p=payload: validate_server_message(
                        p,
                        strict=True,
                        strict_semantic=True,
                    ),
                    description="Strict + semantic validation.",
                )

            add_case(
                f"core_parse_bytes_{safe}",
                "01_core_event_loop",
                "sync",
                lambda r=raw: parse_server_message(r),
                description="Parse raw JSON bytes.",
            )

            last = type_last_payload(payload)
            add_case(
                f"core_key_order_type_last_{safe}",
                "01_core_event_loop",
                "sync",
                lambda p=last: parse_server_message(p),
                description="_type is last key instead of first.",
            )

            extra = extra_keys_payload(payload, args.extra_keys)
            add_case(
                f"core_extra_keys_{args.extra_keys}_{safe}",
                "01_core_event_loop",
                "sync",
                lambda p=extra: parse_server_message(p),
                description="Payload with many unknown keys.",
            )

            miss = missing_required_payload(payload)

            def missing_validator(m=miss) -> None:
                try:
                    validate_server_message(m, strict=True)
                except HighriseFastValidationError:
                    pass
                except Exception:
                    pass

            add_case(
                f"sad_missing_required_{safe}",
                "02_validation_overhead",
                "sync",
                missing_validator,
                description="Missing required field rejection path.",
            )

    # -------------------------------------------------------------------------
    # 03 memory / GC / object economics
    # -------------------------------------------------------------------------

    chat = get_payload(base, "ChatEvent")
    move = get_payload(base, "UserMovedEvent")
    room_users = get_payload(base, "GetRoomUsersResponse")
    wallet = get_payload(base, "GetWalletResponse")

    add_case(
        "memory_chat_parse",
        "03_memory_gc",
        "memory",
        lambda: parse_server_message(chat),
        description="Memory behavior for ChatEvent parsing.",
    )

    add_case(
        "memory_user_moved_parse",
        "03_memory_gc",
        "memory",
        lambda: parse_server_message(move),
        description="Memory behavior for UserMovedEvent parsing.",
    )

    add_case(
        "memory_room_users_parse",
        "03_memory_gc",
        "memory",
        lambda: parse_server_message(room_users),
        description="Memory behavior for GetRoomUsersResponse parsing.",
    )

    bad_chat = missing_required_payload(chat)

    def raise_catch_validation_error() -> None:
        try:
            validate_server_message(bad_chat, strict=True)
        except HighriseFastValidationError:
            pass
        except Exception:
            pass

    add_case(
        "memory_validation_error_raise_catch",
        "03_memory_gc",
        "memory",
        raise_catch_validation_error,
        description="Memory behavior for raising/catching structured validation errors.",
    )

    def bench_gc_parse(payload: dict[str, Any], iterations: int) -> dict[str, Any]:
        gc.collect()

        try:
            gc.disable()
        except Exception:
            pass

        start = time.perf_counter()
        for _ in range(iterations):
            parse_server_message(payload)
        parse_duration = max(time.perf_counter() - start, 1e-12)

        gc_start = time.perf_counter()
        collected = gc.collect()
        gc_duration = max(time.perf_counter() - gc_start, 1e-12)

        try:
            gc.enable()
        except Exception:
            pass

        return {
            "iterations": iterations,
            "parse_total_s": parse_duration,
            "ops_per_s": iterations / parse_duration,
            "avg_us": (parse_duration / iterations) * 1_000_000.0,
            "gc_collect_s": gc_duration,
            "gc_collected": collected,
        }

    add_case(
        "gc_stutter_chat",
        "03_memory_gc",
        "custom",
        lambda: bench_gc_parse(chat, args.gc_iterations),
        description="GC pressure after many ChatEvent parses.",
    )

    add_case(
        "gc_stutter_user_moved",
        "03_memory_gc",
        "custom",
        lambda: bench_gc_parse(move, args.gc_iterations),
        description="GC pressure after many UserMovedEvent parses.",
    )

    def bench_allocation_blocks(
        payload: dict[str, Any], iterations: int
    ) -> dict[str, Any]:
        gc.collect()

        try:
            gc.disable()
        except Exception:
            pass

        before = sys.getallocatedblocks()
        start = time.perf_counter()

        for _ in range(iterations):
            parse_server_message(payload)

        duration = max(time.perf_counter() - start, 1e-12)
        after = sys.getallocatedblocks()

        try:
            gc.enable()
        except Exception:
            pass

        delta = max(0, after - before)

        return {
            "iterations": iterations,
            "total_s": duration,
            "ops_per_s": iterations / duration,
            "allocated_blocks_delta": delta,
            "allocated_blocks_per_call": delta / iterations,
        }

    add_case(
        "allocation_blocks_chat",
        "03_memory_gc",
        "custom",
        lambda: bench_allocation_blocks(chat, args.memory_iterations),
        description="Python allocator block delta for ChatEvent parsing.",
    )

    def object_sizes() -> dict[str, Any]:
        parsed = parse_server_message(chat)
        return {
            "payload_deep_size_kb": deep_getsizeof(chat) / 1024.0,
            "parsed_deep_size_kb": deep_getsizeof(parsed) / 1024.0,
            "payload_sys_getsizeof": sys.getsizeof(chat),
            "parsed_sys_getsizeof": sys.getsizeof(parsed),
        }

    add_case(
        "object_size_chat",
        "03_memory_gc",
        "custom",
        object_sizes,
        description="Approximate object size of ChatEvent payload vs parsed result.",
    )

    def error_object_size() -> dict[str, Any]:
        try:
            validate_server_message(bad_chat, strict=True)
            return {"error": "expected validation error did not raise"}
        except HighriseFastValidationError as exc:
            return {
                "error_deep_size_kb": deep_getsizeof(exc) / 1024.0,
                "errors_count": len(getattr(exc, "errors", [])),
            }
        except Exception as exc:
            return {"error": repr(exc)}

    add_case(
        "object_size_validation_error",
        "03_memory_gc",
        "custom",
        error_object_size,
        description="Approximate size of structured validation exception.",
    )

    def ref_cycle_test() -> dict[str, Any]:
        iterations = 500

        for _ in range(iterations):
            try:
                validate_server_message({"_type": "FakeEvent"}, strict=True)
            except HighriseFastValidationError as exc:
                # Intentionally create a reference cycle to see if GC cleans it.
                exc.payload = {"exception": exc}
            except Exception:
                pass

        collected = gc.collect()

        return {
            "iterations": iterations,
            "gc_collected": collected,
            "gc_garbage_len": len(gc.garbage),
        }

    add_case(
        "ref_cycle_validation_error",
        "03_memory_gc",
        "custom",
        ref_cycle_test,
        description="Reference-cycle cleanup behavior for validation exceptions.",
    )

    def deque_buffer_test() -> dict[str, Any]:
        n = args.deque_size
        dq: deque[Any] = deque(maxlen=n)

        start = time.perf_counter()
        for _ in range(n):
            dq.append(parse_server_message(chat))
        duration = max(time.perf_counter() - start, 1e-12)

        return {
            "buffer_size": len(dq),
            "total_s": duration,
            "events_per_s": n / duration,
            "deep_size_kb": deep_getsizeof(dq) / 1024.0,
        }

    add_case(
        "history_deque_buffer",
        "03_memory_gc",
        "custom",
        deque_buffer_test,
        description="Memory cost of retaining recent parsed events in a deque.",
    )

    # -------------------------------------------------------------------------
    # 04 Highrise-specific game logic spikes
    # -------------------------------------------------------------------------

    def burst_parse(payloads: list[dict[str, Any]]) -> None:
        for p in payloads:
            parse_server_message(p)

    dance_floor = []
    for i in range(20):
        dance_floor.append(copy.deepcopy(move))
        dance_floor.append(copy.deepcopy(get_payload(base, "EmoteEvent")))

    add_case(
        "spike_dance_floor_40_events",
        "04_highrise_game_logic",
        "sync",
        lambda: burst_parse(dance_floor),
        iterations=max(10, args.iterations // 10),
        description="20 UserMovedEvent + 20 EmoteEvent burst.",
    )

    raid = []
    join = get_payload(base, "UserJoinedEvent")
    leave = get_payload(base, "UserLeftEvent")
    for i in range(25):
        raid.append(copy.deepcopy(join))
        raid.append(copy.deepcopy(leave))

    add_case(
        "spike_raid_50_join_leave",
        "04_highrise_game_logic",
        "sync",
        lambda: burst_parse(raid),
        iterations=max(10, args.iterations // 10),
        description="25 joins + 25 leaves burst.",
    )

    tips = []
    tip = get_payload(base, "TipReactionEvent")
    for i in range(100):
        t = copy.deepcopy(tip)
        t["item"]["amount"] = i + 1
        tips.append(t)

    add_case(
        "spike_tip_burst_100",
        "04_highrise_game_logic",
        "sync",
        lambda: burst_parse(tips),
        iterations=max(10, args.iterations // 10),
        description="100 TipReactionEvents burst.",
    )

    voice = get_payload(base, "VoiceEvent")
    voice_spam = []
    for i in range(20):
        v = copy.deepcopy(voice)
        v["users"] = [
            [{"id": f"u{i}", "username": f"user{i}"}, "voice" if i % 2 else "muted"]
        ]
        voice_spam.append(v)

    add_case(
        "spike_voice_toggle_20",
        "04_highrise_game_logic",
        "sync",
        lambda: burst_parse(voice_spam),
        iterations=max(10, args.iterations // 10),
        description="Rapid voice mute/unmute event parsing.",
    )

    big_room_users = {
        "_type": "GetRoomUsersResponse",
        "rid": "1",
        "content": [
            [
                {"id": f"u{i}", "username": f"user{i}"},
                {
                    "x": float(i % 20),
                    "y": 0.0,
                    "z": float(i % 15),
                    "facing": "FrontRight",
                },
            ]
            for i in range(50)
        ],
    }

    add_case(
        "heavy_room_users_50",
        "04_highrise_game_logic",
        "sync",
        lambda: parse_server_message(big_room_users),
        description="Parse 50-user GetRoomUsersResponse.",
    )

    big_inventory = {
        "_type": "GetInventoryResponse",
        "rid": "1",
        "items": [
            {
                "type": "clothing",
                "amount": 1,
                "id": f"item_{i}",
                "account_bound": False,
                "active_palette": i % 10,
            }
            for i in range(args.bulk_size)
        ],
    }

    add_case(
        f"heavy_inventory_{args.bulk_size}",
        "04_highrise_game_logic",
        "sync",
        lambda: parse_server_message(big_inventory),
        description="Parse large inventory response.",
    )

    # -------------------------------------------------------------------------
    # 05 malicious / adversarial payloads
    # -------------------------------------------------------------------------

    def loads_catch(raw: Any) -> None:
        try:
            hf_loads(raw)
        except Exception:
            pass

    # JSON bomb: deeply nested object.
    deep_obj: dict[str, Any] = {"leaf": 1}
    for _ in range(100):
        deep_obj = {"child": deep_obj}
    deep_json = json.dumps(deep_obj)

    add_case(
        "malicious_json_bomb_depth_100",
        "05_malicious",
        "sync",
        lambda: loads_catch(deep_json),
        description="Deeply nested JSON payload.",
    )

    # JSON bomb: deeply nested array.
    deep_array_json = "[" * 100 + "1" + "]" * 100

    add_case(
        "malicious_json_array_bomb_depth_100",
        "05_malicious",
        "sync",
        lambda: loads_catch(deep_array_json),
        description="Deeply nested JSON array payload.",
    )

    # Extreme string length.
    extreme_chat = copy.deepcopy(chat)
    extreme_chat["message"] = "A" * 100_000

    add_case(
        "malicious_extreme_string_100k_parse",
        "05_malicious",
        "sync",
        lambda: parse_server_message(extreme_chat),
        description="Chat message with 100,000 chars, lenient parse.",
    )

    def semantic_extreme_string() -> None:
        try:
            validate_server_message(extreme_chat, strict=True, strict_semantic=True)
        except HighriseFastValidationError:
            pass
        except Exception:
            pass

    add_case(
        "malicious_extreme_string_100k_semantic",
        "05_malicious",
        "sync",
        semantic_extreme_string,
        description="Chat message with 100,000 chars, semantic rejection.",
    )

    # Null injection where list expected.
    null_voice = copy.deepcopy(voice)
    null_voice["users"] = None

    def null_injection() -> None:
        try:
            validate_server_message(null_voice, strict=True)
        except HighriseFastValidationError:
            pass
        except Exception:
            pass

    add_case(
        "malicious_null_injection_users",
        "05_malicious",
        "sync",
        null_injection,
        description="users=null where list is expected.",
    )

    # High precision floats.
    precision_move = copy.deepcopy(move)
    precision_move["position"]["x"] = "1.000000000000000000000000000001"

    add_case(
        "malicious_high_precision_float",
        "05_malicious",
        "sync",
        lambda: parse_server_message(precision_move),
        description="High precision coordinate parsing.",
    )

    # Integer overflow-ish amount.
    overflow_wallet = copy.deepcopy(wallet)
    overflow_wallet["content"][0]["amount"] = 10**100

    add_case(
        "malicious_integer_overflow_amount",
        "05_malicious",
        "sync",
        lambda: parse_server_message(overflow_wallet),
        description="Very large wallet amount.",
    )

    # Unicode / Zalgo-ish spam.
    zalgo_chat = copy.deepcopy(chat)
    zalgo_chat["message"] = (
        "Ẕ̴̢̛̛̤̹̲̫̻̪̖̞̠̦̞̯̣̥̩̫̯̹̞̠̦̞̯̣̥̩̫̯̹̞̠̦̞̯̣̥̩̫̯̹̞̠̦̮̮̮̮̮̮" * 200
    )

    add_case(
        "malicious_unicode_zalgo_message",
        "05_malicious",
        "sync",
        lambda: parse_server_message(zalgo_chat),
        description="Heavy combining-character Unicode message.",
    )

    # Extraneous key spam.
    spammy = extra_keys_payload(chat, 1000)

    add_case(
        "malicious_extraneous_key_spam_1000",
        "05_malicious",
        "sync",
        lambda: parse_server_message(spammy),
        description="Payload with 1,000 unknown keys.",
    )

    # Invalid UTF-8 bytes.
    add_case(
        "malicious_invalid_utf8_bytes",
        "05_malicious",
        "sync",
        lambda: loads_catch(b'{"bad": "\xff"}'),
        description="Invalid UTF-8 JSON bytes.",
    )

    # Fragmented frame reassembly.
    raw_chat = hf_dumps(chat)
    chunks = [raw_chat[i : i + 10] for i in range(0, len(raw_chat), 10)]

    def fragmented_reassembly() -> None:
        hf_loads(b"".join(chunks))

    add_case(
        "malicious_fragmented_frame_reassembly",
        "05_malicious",
        "sync",
        fragmented_reassembly,
        description="Reassemble 10-byte chunks then parse.",
    )

    # Invalid enum.
    bad_reaction = copy.deepcopy(get_payload(base, "ReactionEvent"))
    bad_reaction["reaction"] = "not_a_real_reaction"

    def invalid_enum() -> None:
        try:
            validate_server_message(bad_reaction, strict=True)
        except HighriseFastValidationError:
            pass
        except Exception:
            pass

    add_case(
        "malicious_invalid_enum_reaction",
        "05_malicious",
        "sync",
        invalid_enum,
        description="Invalid reaction enum value.",
    )

    # Empty dict payload.
    def empty_dict() -> None:
        try:
            validate_server_message({}, strict=True)
        except HighriseFastValidationError:
            pass
        except Exception:
            pass

    add_case(
        "malicious_empty_dict_payload",
        "05_malicious",
        "sync",
        empty_dict,
        description="Empty JSON object.",
    )

    # Zero-byte frame.
    add_case(
        "malicious_zero_byte_frame",
        "05_malicious",
        "sync",
        lambda: loads_catch(b""),
        description="Zero-byte WebSocket frame.",
    )

    # Trailing comma invalid JSON.
    add_case(
        "malicious_trailing_comma_json",
        "05_malicious",
        "sync",
        lambda: loads_catch(b'{"a": 1,}'),
        description="Invalid JSON with trailing comma.",
    )

    # Boolean coercion.
    bool_chat = copy.deepcopy(chat)
    bool_chat["whisper"] = "true"

    add_case(
        "malicious_boolean_string_coercion",
        "05_malicious",
        "sync",
        lambda: parse_server_message(bool_chat),
        description='whisper="true" instead of true.',
    )

    # Integer where float expected.
    int_float_move = copy.deepcopy(move)
    int_float_move["position"]["x"] = 1

    add_case(
        "malicious_int_where_float_expected",
        "05_malicious",
        "sync",
        lambda: parse_server_message(int_float_move),
        description="x=1 instead of x=1.0.",
    )

    # Negative coordinate semantic.
    negative_move = copy.deepcopy(move)
    negative_move["position"]["x"] = -9999.0

    def negative_coordinate_semantic() -> None:
        try:
            validate_server_message(negative_move, strict=True, strict_semantic=True)
        except HighriseFastValidationError:
            pass
        except Exception:
            pass

    add_case(
        "malicious_negative_coordinate_semantic",
        "05_malicious",
        "sync",
        negative_coordinate_semantic,
        description="x=-9999 semantic out-of-bounds rejection.",
    )

    # Long dictionary key.
    long_key_chat = copy.deepcopy(chat)
    long_key_chat["x" * 500] = "long key"

    add_case(
        "malicious_long_dict_key_500",
        "05_malicious",
        "sync",
        lambda: parse_server_message(long_key_chat),
        description="Payload with 500-char unknown key.",
    )

    # Whitespace username.
    ws_chat = copy.deepcopy(chat)
    ws_chat["user"]["username"] = "   spaced user   "

    add_case(
        "malicious_whitespace_username",
        "05_malicious",
        "sync",
        lambda: parse_server_message(ws_chat),
        description="Username with surrounding whitespace.",
    )

    # Numeric user ID.
    numeric_chat = copy.deepcopy(chat)
    numeric_chat["user"]["id"] = 123456789

    add_case(
        "malicious_numeric_user_id",
        "05_malicious",
        "sync",
        lambda: parse_server_message(numeric_chat),
        description="Numeric user id instead of string.",
    )

    # Unknown root parameter.
    unknown_root = copy.deepcopy(chat)
    unknown_root["event_id"] = "evt-123"

    add_case(
        "malicious_unknown_root_parameter",
        "05_malicious",
        "sync",
        lambda: parse_server_message(unknown_root),
        description="Unknown root-level event_id key.",
    )

    # Duplicate JSON keys.
    add_case(
        "malicious_duplicate_json_keys",
        "05_malicious",
        "sync",
        lambda: loads_catch(b'{"a": 1, "a": 2}'),
        description="Duplicate JSON keys.",
    )

    # -------------------------------------------------------------------------
    # 06 asyncio dynamics
    # -------------------------------------------------------------------------

    async def spawn_tasks(n: int) -> None:
        async def noop() -> None:
            return None

        tasks = [asyncio.create_task(noop()) for _ in range(n)]
        await asyncio.gather(*tasks)

    add_case(
        "async_task_spawn_100",
        "06_asyncio",
        "async",
        lambda: spawn_tasks(100),
        description="Create and await 100 noop tasks.",
    )

    async def queue_roundtrip(n: int) -> None:
        q: asyncio.Queue[int] = asyncio.Queue()

        for i in range(n):
            await q.put(i)

        for _ in range(n):
            await q.get()

    add_case(
        "async_queue_roundtrip_100",
        "06_asyncio",
        "async",
        lambda: queue_roundtrip(100),
        description="asyncio.Queue put/get 100 items.",
    )

    async def parse_and_handle() -> None:
        evt = parse_server_message(chat)

        async def handler(event: Any) -> Any:
            return event

        await handler(evt)

    add_case(
        "async_parse_then_handler",
        "06_asyncio",
        "async",
        parse_and_handle,
        description="Parse event then await handler.",
    )

    async def backlog_queue_nowait(n: int) -> None:
        q: asyncio.Queue[Any] = asyncio.Queue()

        for _ in range(n):
            q.put_nowait(parse_server_message(chat))

        for _ in range(n):
            q.get_nowait()

    add_case(
        "async_backlog_queue_200",
        "06_asyncio",
        "async",
        lambda: backlog_queue_nowait(200),
        description="Queue backlog with 200 parsed events.",
    )

    async def yield_sleep0() -> None:
        await asyncio.sleep(0)

    add_case(
        "async_yield_sleep0",
        "06_asyncio",
        "async",
        yield_sleep0,
        description="Cost of yielding control once.",
    )

    async def keepalive_interference() -> None:
        async def send_keepalive() -> None:
            hf_dumps({"_type": "KeepaliveRequest"})

        async def parse_events() -> None:
            for _ in range(25):
                parse_server_message(chat)

        await asyncio.gather(send_keepalive(), parse_events())

    add_case(
        "async_keepalive_interference",
        "06_asyncio",
        "async",
        keepalive_interference,
        description="Keepalive serialization while parsing 25 chats.",
    )

    async def thread_offload_parse() -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, parse_server_message, chat)

    add_case(
        "async_thread_offload_parse",
        "06_asyncio",
        "async",
        thread_offload_parse,
        description="Parse in default ThreadPoolExecutor.",
    )

    async def mixed_inbound_outbound() -> None:
        for _ in range(10):
            parse_server_message(chat)
            hf_dumps({"_type": "ChatRequest", "message": "test", "rid": "1"})

    add_case(
        "async_mixed_inbound_outbound",
        "06_asyncio",
        "async",
        mixed_inbound_outbound,
        description="Interleaved inbound parse + outbound serialize.",
    )

    async def livelock_spam() -> None:
        sent = 0
        parsed = 0

        for _ in range(100):
            parse_server_message(move)
            parsed += 1

            if parsed % 10 == 0:
                hf_dumps({"_type": "KeepaliveRequest"})
                sent += 1

    add_case(
        "async_livelock_spam_100",
        "06_asyncio",
        "async",
        livelock_spam,
        description="Parse 100 movements while periodically serializing sends.",
    )

    # -------------------------------------------------------------------------
    # 07 outbound serialization
    # -------------------------------------------------------------------------

    out_chat = {
        "_type": "ChatRequest",
        "message": "hello world",
        "whisper_target_id": None,
        "rid": "1",
    }

    out_walk = {
        "_type": "FloorHitRequest",
        "destination": {"x": 1.0, "y": 0.0, "z": 2.0, "facing": "FrontRight"},
        "rid": "1",
    }

    out_bulk = {
        "_type": "SendBulkMessageRequest",
        "user_ids": [f"user_{i}" for i in range(100)],
        "content": "bulk message",
        "type": "text",
        "room_id": None,
        "world_id": None,
        "rid": "1",
    }

    out_outfit = {
        "_type": "SetOutfitRequest",
        "outfit": [
            {
                "type": "clothing",
                "amount": 1,
                "id": f"item_{i}",
                "account_bound": False,
                "active_palette": i % 5,
            }
            for i in range(50)
        ],
        "rid": "1",
    }

    add_case(
        "outbound_dumps_chat_hf",
        "07_outbound",
        "sync",
        lambda: hf_dumps(out_chat),
        description="highrise_fast outbound chat serialization.",
    )

    add_case(
        "outbound_dumps_walk_hf",
        "07_outbound",
        "sync",
        lambda: hf_dumps(out_walk),
        description="highrise_fast outbound walk serialization.",
    )

    add_case(
        "outbound_dumps_bulk100_hf",
        "07_outbound",
        "sync",
        lambda: hf_dumps(out_bulk),
        description="Serialize bulk message with 100 user ids.",
    )

    add_case(
        "outbound_dumps_outfit50_hf",
        "07_outbound",
        "sync",
        lambda: hf_dumps(out_outfit),
        description="Serialize 50-item outfit.",
    )

    add_case(
        "outbound_json_dumps_chat",
        "07_outbound",
        "sync",
        lambda: json.dumps(out_chat, separators=(",", ":"), ensure_ascii=False),
        description="stdlib json chat serialization.",
    )

    if orjson is not None:
        add_case(
            "outbound_orjson_dumps_chat",
            "07_outbound",
            "sync",
            lambda: orjson.dumps(out_chat),
            description="orjson chat serialization.",
        )

    if ujson is not None:
        add_case(
            "outbound_ujson_dumps_chat",
            "07_outbound",
            "sync",
            lambda: ujson.dumps(out_chat),
            description="ujson chat serialization.",
        )

    position_cls = getattr(hf, "Position", None)
    if position_cls is not None and is_dataclass(position_cls):
        pos_obj = position_cls(x=1.0, y=0.0, z=2.0, facing="FrontRight")

        add_case(
            "outbound_dataclass_asdict_position",
            "07_outbound",
            "sync",
            lambda: asdict(pos_obj),
            description="dataclasses.asdict(Position).",
        )

    add_case(
        "outbound_construct_position_dict",
        "07_outbound",
        "sync",
        lambda: {"x": 1.0, "y": 0.0, "z": 2.0, "facing": "FrontRight"},
        description="Construct raw position dict.",
    )

    large_escape_message = {
        "_type": "ChatRequest",
        "message": 'quote" newline\n tab\t unicode🙂 backslash\\' * 100,
        "rid": "1",
    }

    add_case(
        "outbound_string_escaping_large",
        "07_outbound",
        "sync",
        lambda: hf_dumps(large_escape_message),
        description="Serialize message with many escape characters.",
    )

    # -------------------------------------------------------------------------
    # 08 parser engine comparisons
    # -------------------------------------------------------------------------

    raw_chat = hf_dumps(chat)

    add_case(
        "compare_hf_loads_chat_bytes",
        "08_comparisons",
        "sync",
        lambda: hf_loads(raw_chat),
        description="highrise_fast loads_json on chat bytes.",
    )

    add_case(
        "compare_std_json_loads_chat_bytes",
        "08_comparisons",
        "sync",
        lambda: json.loads(raw_chat),
        description="stdlib json.loads on chat bytes.",
    )

    if orjson is not None:
        add_case(
            "compare_orjson_loads_chat_bytes",
            "08_comparisons",
            "sync",
            lambda: orjson.loads(raw_chat),
            description="orjson.loads on chat bytes.",
        )

    if ujson is not None:
        add_case(
            "compare_ujson_loads_chat_bytes",
            "08_comparisons",
            "sync",
            lambda: ujson.loads(raw_chat),
            description="ujson.loads on chat bytes.",
        )

    if msgspec is not None:
        try:

            class MsgUser(msgspec.Struct):
                id: str
                username: str

            class MsgChat(msgspec.Struct):
                user: MsgUser
                message: str
                whisper: bool

            msgspec_decoder = msgspec.json.Decoder(MsgChat)

            add_case(
                "compare_msgspec_decode_chat_bytes",
                "08_comparisons",
                "sync",
                lambda: msgspec_decoder.decode(raw_chat),
                description="msgspec JSON decode into typed struct.",
            )
        except Exception:
            pass

    if BaseModel is not None:
        try:

            class PydUser(BaseModel):
                id: str
                username: str

            class PydChat(BaseModel):
                user: PydUser
                message: str
                whisper: bool

            def bench_pydantic() -> Any:
                if hasattr(PydChat, "model_validate"):
                    return PydChat.model_validate(chat)
                return PydChat.parse_obj(chat)

            add_case(
                "compare_pydantic_parse_chat",
                "08_comparisons",
                "sync",
                bench_pydantic,
                description="pydantic parse of ChatEvent payload.",
            )
        except Exception:
            pass

    # Try official SDK if it happens to be importable.
    official_parse = None
    for module_name in ("highrise", "highrise_sdk", "highrise.parser"):
        try:
            mod = importlib.import_module(module_name)
            candidate = getattr(mod, "parse_server_message", None)
            if callable(candidate):
                official_parse = candidate
                break
        except Exception:
            continue

    if official_parse is not None:
        add_case(
            "compare_official_sdk_parse_chat",
            "08_comparisons",
            "sync",
            lambda: official_parse(chat),
            description="Official SDK parse_server_message, if available.",
        )

    # -------------------------------------------------------------------------
    # 09 latency percentiles / micro cases
    # -------------------------------------------------------------------------

    def p50_p99_sample() -> dict[str, Any]:
        samples: list[float] = []

        iterations = max(500, args.iterations)

        for _ in range(iterations):
            start = time.perf_counter()
            parse_server_message(chat)
            samples.append((time.perf_counter() - start) * 1_000_000.0)

        samples.sort()
        n = len(samples)

        return {
            "iterations": n,
            "p50_us": samples[int(n * 0.50)],
            "p95_us": samples[int(n * 0.95)],
            "p99_us": samples[int(n * 0.99)],
            "p999_us": samples[min(int(n * 0.999), n - 1)],
            "max_us": samples[-1],
        }

    add_case(
        "latency_percentiles_chat",
        "09_latency",
        "custom",
        p50_p99_sample,
        description="Per-call latency percentiles for ChatEvent.",
    )

    def cold_first_call() -> dict[str, Any]:
        # Not a true process cold start, but measures first call in this process.
        start = time.perf_counter()
        parse_server_message(chat)
        first_us = (time.perf_counter() - start) * 1_000_000.0

        start = time.perf_counter()
        for _ in range(100):
            parse_server_message(chat)
        warm_avg_us = ((time.perf_counter() - start) / 100.0) * 1_000_000.0

        return {
            "first_call_us": first_us,
            "warm_avg_us": warm_avg_us,
        }

    add_case(
        "latency_cold_vs_warm",
        "09_latency",
        "custom",
        cold_first_call,
        description="First-call cost vs warm average.",
    )

    return cases


# -----------------------------------------------------------------------------
# Reporting
# -----------------------------------------------------------------------------


def format_row(row: dict[str, Any]) -> str:
    if row.get("status") == "error":
        return f"ERROR: {str(row.get('error', 'unknown'))[:140]}"

    if "ops_per_s" in row and "avg_us" in row:
        return f"{row['ops_per_s']:,.0f} ops/s | {row['avg_us']:.3f} us/op"

    # For custom rows, show a few interesting numeric fields.
    preferred = (
        "ops_per_s",
        "avg_us",
        "total_s",
        "tracemalloc_peak_kb",
        "allocated_blocks_per_call",
        "gc_collect_s",
        "p99_us",
        "first_call_us",
        "failed_count",
    )

    parts = []
    for key in preferred:
        if key in row:
            value = row[key]
            if isinstance(value, float):
                parts.append(f"{key}={value:,.3f}")
            else:
                parts.append(f"{key}={value}")

    if not parts:
        return "custom metrics"

    return " | ".join(parts[:4])


def make_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [r for r in rows if r.get("status") == "ok"]
    errors = [r for r in rows if r.get("status") == "error"]
    timed = [r for r in ok if "avg_us" in r]

    categories: dict[str, dict[str, Any]] = {}
    for row in timed:
        cat = row["category"]
        bucket = categories.setdefault(
            cat,
            {
                "count": 0,
                "total_ops_per_s": 0.0,
                "total_avg_us": 0.0,
            },
        )
        bucket["count"] += 1
        bucket["total_ops_per_s"] += float(row.get("ops_per_s", 0.0))
        bucket["total_avg_us"] += float(row.get("avg_us", 0.0))

    for cat, bucket in categories.items():
        if bucket["count"]:
            bucket["avg_ops_per_s"] = bucket["total_ops_per_s"] / bucket["count"]
            bucket["avg_avg_us"] = bucket["total_avg_us"] / bucket["count"]

    slowest = sorted(timed, key=lambda r: r.get("avg_us", 0.0), reverse=True)[:20]
    fastest = sorted(timed, key=lambda r: r.get("avg_us", float("inf")))[:20]

    return {
        "total_cases": len(rows),
        "ok": len(ok),
        "errors": len(errors),
        "timed_cases": len(timed),
        "categories": categories,
        "slowest": [
            {
                "name": r["name"],
                "category": r["category"],
                "avg_us": r.get("avg_us"),
                "ops_per_s": r.get("ops_per_s"),
            }
            for r in slowest
        ],
        "fastest": [
            {
                "name": r["name"],
                "category": r["category"],
                "avg_us": r.get("avg_us"),
                "ops_per_s": r.get("ops_per_s"),
            }
            for r in fastest
        ],
        "error_cases": [
            {
                "name": r["name"],
                "category": r["category"],
                "error": r.get("error"),
            }
            for r in errors
        ],
    }


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark highrise_fast.")

    parser.add_argument(
        "--quick", action="store_true", help="Very fast smoke benchmark."
    )
    parser.add_argument("--full", action="store_true", help="Higher iteration counts.")
    parser.add_argument(
        "--iterations", type=int, default=150, help="Base sync iterations."
    )
    parser.add_argument(
        "--async-iterations", type=int, default=10, help="Async repetitions."
    )
    parser.add_argument(
        "--memory-iterations", type=int, default=1000, help="Memory test iterations."
    )
    parser.add_argument(
        "--gc-iterations", type=int, default=10_000, help="GC stress iterations."
    )
    parser.add_argument(
        "--extra-keys", type=int, default=250, help="Unknown keys per hot payload."
    )
    parser.add_argument(
        "--bulk-size", type=int, default=500, help="Large inventory item count."
    )
    parser.add_argument(
        "--deque-size", type=int, default=5000, help="History buffer size."
    )
    parser.add_argument(
        "--category", type=str, default=None, help="Only run one category."
    )
    parser.add_argument(
        "--filter", type=str, default=None, help="Only run cases containing substring."
    )
    parser.add_argument(
        "--json", type=str, default="benchmark_results.json", help="Output JSON path."
    )
    parser.add_argument("--quiet", action="store_true", help="Print less output.")

    args = parser.parse_args()

    if args.quick:
        args.iterations = min(args.iterations, 30)
        args.async_iterations = min(args.async_iterations, 3)
        args.memory_iterations = min(args.memory_iterations, 200)
        args.gc_iterations = min(args.gc_iterations, 1000)
        args.extra_keys = min(args.extra_keys, 50)
        args.bulk_size = min(args.bulk_size, 100)
        args.deque_size = min(args.deque_size, 500)

    if args.full:
        args.iterations = max(args.iterations, 2000)
        args.async_iterations = max(args.async_iterations, 50)
        args.memory_iterations = max(args.memory_iterations, 5000)
        args.gc_iterations = max(args.gc_iterations, 50_000)

    return args


def main() -> None:
    args = parse_args()

    cases = build_cases(args)

    if args.category:
        cases = [c for c in cases if c["category"] == args.category]

    if args.filter:
        needle = args.filter.lower()
        cases = [c for c in cases if needle in c["name"].lower()]

    print(f"Registered {len(cases)} benchmark cases.")

    rows: list[dict[str, Any]] = []

    for i, case in enumerate(cases, 1):
        row: dict[str, Any] = {
            "name": case["name"],
            "category": case["category"],
            "kind": case["kind"],
            "description": case.get("description", ""),
        }

        metrics = run_case(case, args)
        row.update(metrics)
        rows.append(row)

        if not args.quiet:
            print(
                f"{i:03d}/{len(cases)} [{row['status']:5s}] {case['category']} :: {case['name']}"
            )
            print(f"      {format_row(row)}")

    summary = make_summary(rows)

    output = {
        "args": vars(args),
        "summary": summary,
        "results": rows,
    }

    try:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, default=str)
        print(f"\nSaved results to: {os.path.abspath(args.json)}")
    except Exception as exc:
        print(f"\nCould not write JSON output: {exc}")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total cases : {summary['total_cases']}")
    print(f"OK          : {summary['ok']}")
    print(f"Errors      : {summary['errors']}")
    print(f"Timed cases : {summary['timed_cases']}")

    print("\nCategory averages:")
    for cat in sorted(summary["categories"].keys()):
        bucket = summary["categories"][cat]
        if bucket.get("count"):
            print(
                f"  {cat}: "
                f"count={bucket['count']}, "
                f"avg_ops={bucket.get('avg_ops_per_s', 0):,.0f}, "
                f"avg_us={bucket.get('avg_avg_us', 0):.3f}"
            )

    print("\nTop 10 slowest by avg_us:")
    for row in summary["slowest"][:10]:
        print(f"  {row['avg_us']:12.3f} us | {row['category']} :: {row['name']}")

    print("\nTop 10 fastest by avg_us:")
    for row in summary["fastest"][:10]:
        print(f"  {row['avg_us']:12.3f} us | {row['category']} :: {row['name']}")

    if summary["errors"]:
        print("\nError cases:")
        for row in summary["error_cases"][:20]:
            print(f"  {row['category']} :: {row['name']} -> {row['error']}")


if __name__ == "__main__":
    main()

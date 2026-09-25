#!/usr/bin/env python3
"""
benchmark_v3.py — MAXIMUM-SCALE TYPE VALIDATION & PERFORMANCE BENCHMARK
======================================================================

A unified, adversarial, high-scale benchmark for highrise_fast
against the official highrise SDK.

The official SDK is the ORACLE. Its accept/reject decision defines
"correct". The official SDK is never scored.

Phases
------
  1. GENERATE : exhaustive + pairwise + triplewise + fuzz +
                cross-event + adversarial + boundary
  2. OFFICIAL : classify all cases with the official SDK (the oracle)
  3. LENIENT  : classify all cases with highrise_fast lenient mode
  4. STRICT   : classify all cases with highrise_fast strict mode
  5. PERF     : encode/decode/round-trip/sustained-load + percentiles
  6. MEMORY   : GC pressure, tracemalloc peak, leaks, object growth
  7. REPORT   : JSON report + regression vs previous run

Presets
-------
  --quick      :     5,000 cases      (fast smoke test)
  --standard   :   100,000 cases      (CI-friendly)
  --max        : 1,000,000 cases      (default)
  --extreme    :10,000,000 cases      (stress)

Usage
-----
  python benchmark_v3.py
  python benchmark_v3.py --quick
  python benchmark_v3.py --preset standard --workers 8
  python benchmark_v3.py --target 500000 --no-adversarial
  python benchmark_v3.py --save-official gold_1m.json
  python benchmark_v3.py --reuse-official gold_1m.json
  python benchmark_v3.py --json-report report_v3.json
  python benchmark_v3.py --regression report_v2.json
  python benchmark_v3.py --show all
"""

from __future__ import annotations

import argparse
import copy
import gc
import hashlib
import inspect
import itertools
import json
import os
import platform
import random
import re
import statistics
import sys
import time
import tracemalloc
from collections import Counter
from collections.abc import Iterable, Iterator
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from multiprocessing import get_context
from typing import Any

# ═══════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════
VERSION = "3.0.0"
OFFICIAL = "highrise"
CUSTOM = "highrise_fast"

PRESETS = {
    "quick": {
        "target": 5_000,
        "pairwise": 500,
        "triplewise": 0,
        "fuzz": 1_000,
        "cross": 0,
        "endurance": 3.0,
    },
    "standard": {
        "target": 100_000,
        "pairwise": 10_000,
        "triplewise": 0,
        "fuzz": 20_000,
        "cross": 5_000,
        "endurance": 5.0,
    },
    "max": {
        "target": 1_000_000,
        "pairwise": 100_000,
        "triplewise": 50_000,
        "fuzz": 200_000,
        "cross": 50_000,
        "endurance": 10.0,
    },
    "extreme": {
        "target": 10_000_000,
        "pairwise": 500_000,
        "triplewise": 500_000,
        "fuzz": 2_000_000,
        "cross": 500_000,
        "endurance": 20.0,
    },
}

# ═══════════════════════════════════════════════════════════════
# OUTPUT
# ═══════════════════════════════════════════════════════════════


def p(*args, **kwargs):
    print(*args, **kwargs, flush=True)


def header(title: str):
    p()
    p("═" * 100)
    p(f"  {title}")
    p("═" * 100)


def sub(title: str):
    p()
    p(f"  ── {title} " + "─" * max(0, 90 - len(title)))


def short(text: str, limit: int = 80) -> str:
    text = str(text)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def fmt_ns(v: float | None) -> str:
    if v is None:
        return "n/a"
    if v < 1_000:
        return f"{v:.0f} ns"
    if v < 1_000_000:
        return f"{v / 1_000:.2f} µs"
    if v < 1_000_000_000:
        return f"{v / 1_000_000:.2f} ms"
    return f"{v / 1_000_000_000:.2f} s"


def fmt_bytes(v: float | None) -> str:
    if v is None:
        return "n/a"
    v = float(v)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if abs(v) < 1024:
            return f"{v:.1f} {u}"
        v /= 1024
    return f"{v:.1f} PB"


class Progress:
    def __init__(self, total: int, label: str = "working", enabled: bool = True):
        self.total = max(1, total)
        self.label = label
        self.enabled = enabled
        self.start = time.perf_counter()
        self.done = 0
        self._last = 0.0

    def update(self, n: int = 1):
        if not self.enabled:
            return
        self.done += n
        now = time.perf_counter()
        if now - self._last > 0.5 or self.done >= self.total:
            self._last = now
            elapsed = now - self.start
            rate = self.done / elapsed if elapsed > 0 else 0
            eta = (self.total - self.done) / rate if rate > 0 else 0
            pct = 100 * self.done / self.total
            sys.stdout.write(
                f"\r  {self.label}: {self.done:>12,}/{self.total:,} "
                f"({pct:5.1f}%) | {rate:>10,.0f}/s | ETA {eta:>7.1f}s   "
            )
            sys.stdout.flush()
            if self.done >= self.total:
                sys.stdout.write("\n")

    def close(self):
        if self.enabled and self.done < self.total:
            sys.stdout.write("\n")


# ═══════════════════════════════════════════════════════════════
# BASE PAYLOADS (12 event types)
# ═══════════════════════════════════════════════════════════════
BASE_PAYLOADS: dict[str, dict] = {
    "ChatEvent": {
        "_type": "ChatEvent",
        "user": {"id": "u1", "username": "alice"},
        "message": "hello",
        "whisper": False,
    },
    "UserJoinedEvent": {
        "_type": "UserJoinedEvent",
        "user": {"id": "u2", "username": "bob"},
        "position": {"x": 5.5, "y": 0.0, "z": 12.3, "facing": "FrontRight"},
    },
    "UserLeftEvent": {
        "_type": "UserLeftEvent",
        "user": {"id": "u3", "username": "charlie"},
    },
    "UserMovedEvent": {
        "_type": "UserMovedEvent",
        "user": {"id": "u1", "username": "alice"},
        "position": {"x": 10.5, "y": 0.0, "z": 20.3, "facing": "BackLeft"},
    },
    "EmoteEvent": {
        "_type": "EmoteEvent",
        "user": {"id": "u1", "username": "alice"},
        "emote_id": "wave",
        "receiver": None,
    },
    "ReactionEvent": {
        "_type": "ReactionEvent",
        "user": {"id": "u1", "username": "alice"},
        "receiver": {"id": "u2", "username": "bob"},
        "reaction": "heart",
    },
    "TipReactionEvent": {
        "_type": "TipReactionEvent",
        "sender": {"id": "u1", "username": "alice"},
        "receiver": {"id": "u2", "username": "bob"},
        "item": {"type": "gold", "amount": 5},
    },
    "VoiceEvent": {
        "_type": "VoiceEvent",
        "users": [
            [{"id": "u1", "username": "alice"}, "voice"],
            [{"id": "u2", "username": "bob"}, "muted"],
        ],
        "seconds_left": 300,
    },
    "ChannelEvent": {
        "_type": "ChannelEvent",
        "sender_id": "u1",
        "msg": "hello channel",
    },
    "RoomModeratedEvent": {
        "_type": "RoomModeratedEvent",
        "moderatorId": "mod1",
        "targetUserId": "u5",
        "moderationType": "ban",
        "duration": 3600,
    },
    "Error": {
        "_type": "Error",
        "message": "timeout",
        "do_not_reconnect": False,
        "rid": "r99",
    },
    "GetWalletResponse": {
        "_type": "GetWalletResponse",
        "rid": "w1",
        "content": [
            {"type": "gold", "amount": 500},
            {"type": "earned_gold", "amount": 200},
        ],
    },
    "GetRoomUsersResponse": {
        "_type": "GetRoomUsersResponse",
        "content": [
            [
                {"id": "u1", "username": "alice"},
                {"x": 5.5, "y": 0.0, "z": 12.3, "facing": "FrontRight"},
            ],
            [{"id": "u2", "username": "bob"}, None],
        ],
    },
}

# ── Auto-expand with all official event types (from discover_events.py) ──
try:
    with open("expanded_base_payloads.json", encoding="utf-8") as _f:
        _EXTRA = json.load(_f)
    for _k, _v in _EXTRA.items():
        if _k not in BASE_PAYLOADS and isinstance(_v, dict) and "_type" in _v:
            BASE_PAYLOADS[_k] = _v
    print(
        f"  [BASE_PAYLOADS] loaded {len(BASE_PAYLOADS)} event types "
        f"({len(_EXTRA)} from expanded_base_payloads.json)"
    )
except FileNotFoundError:
    print(
        "  [BASE_PAYLOADS] expanded_base_payloads.json not found — "
        "run discover_events.py to test all 28 event types"
    )
except Exception as _e:  # noqa: BLE001 — best-effort expansion probe
    print(f"  [BASE_PAYLOADS] expansion failed: {_e}")


# ═══════════════════════════════════════════════════════════════
# CASE MODEL
# ═══════════════════════════════════════════════════════════════
@dataclass
class Case:
    id: str
    base: str
    family: str  # exhaustive | pairwise | triplewise | fuzz | cross | adversarial | boundary | top-level | baseline
    mutation: str
    payload: Any

    official_accept: bool | None = None
    official_error: str = ""
    lenient_accept: bool | None = None
    lenient_error: str = ""
    strict_accept: bool | None = None
    strict_error: str = ""


# ═══════════════════════════════════════════════════════════════
# PATH HELPERS
# ═══════════════════════════════════════════════════════════════
def parse_path(path: str) -> list[str | int]:
    tokens: list[str | int] = []
    i = 0
    if path.startswith("$"):
        i = 1
    while i < len(path):
        if path[i] == ".":
            j = i + 1
            while j < len(path) and path[j] not in ".[":
                j += 1
            tokens.append(path[i + 1 : j])
            i = j
        elif path[i] == "[":
            j = path.index("]", i)
            tokens.append(int(path[i + 1 : j]))
            i = j + 1
        else:
            i += 1
    return tokens


def set_path(payload: Any, path: str, value: Any) -> Any:
    data = copy.deepcopy(payload)
    tokens = parse_path(path)
    if not tokens:
        return data
    try:
        cur = data
        for t in tokens[:-1]:
            cur = cur[t]
        cur[tokens[-1]] = value
    except (KeyError, IndexError, TypeError):
        pass
    return data


def delete_path(payload: Any, path: str) -> Any:
    data = copy.deepcopy(payload)
    tokens = parse_path(path)
    if not tokens:
        return data
    try:
        cur = data
        for t in tokens[:-1]:
            cur = cur[t]
        last = tokens[-1]
        if isinstance(cur, dict) and isinstance(last, str):
            cur.pop(last, None)
        elif isinstance(cur, list) and isinstance(last, int) and 0 <= last < len(cur):
            cur[last] = None
    except (KeyError, IndexError, TypeError):
        pass
    return data


def iter_paths(value: Any, path: str = "$") -> Iterator[tuple[str, Any]]:
    if isinstance(value, dict):
        for k, child in value.items():
            cp = f"{path}.{k}"
            yield cp, child
            yield from iter_paths(child, cp)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            cp = f"{path}[{i}]"
            yield cp, child
            yield from iter_paths(child, cp)


def set_key(payload: dict, key: str, value: Any) -> dict:
    d = copy.deepcopy(payload)
    d[key] = value
    return d


def delete_key(payload: dict, key: str) -> dict:
    d = copy.deepcopy(payload)
    d.pop(key, None)
    return d


# ═══════════════════════════════════════════════════════════════
# WRONG-VALUE POOL (boundary-aware)
# ═══════════════════════════════════════════════════════════════
WRONG_VALUES: list[tuple[str, Any]] = [
    ("null", None),
    ("true", True),
    ("false", False),
    ("int-0", 0),
    ("int-1", 1),
    ("int-neg", -1),
    ("int-large", 2**62),
    ("int-max", 2**63 - 1),
    ("float", 1.5),
    ("float-neg", -1.5),
    ("float-large", 1e308),
    ("float-small", 1e-308),
    ("string-empty", ""),
    ("string-space", " "),
    ("string-wrong", "wrong"),
    ("string-unicode", "é😀"),
    ("string-long", "A" * 300),
    ("list-empty", []),
    ("list-one", [1]),
    ("dict-empty", {}),
    ("dict-wrong", {"wrong": True}),
]


# ═══════════════════════════════════════════════════════════════
# CASE GENERATORS
# ═══════════════════════════════════════════════════════════════
def _hash_payload(payload: Any) -> bytes:
    try:
        src = json.dumps(payload, sort_keys=True, default=str)
    except (TypeError, ValueError, RecursionError):
        src = repr(payload)
    return hashlib.blake2b(src.encode("utf-8", "replace"), digest_size=8).digest()


def generate_exhaustive(seen: set[bytes]) -> Iterator[Case]:
    """All top-level, baseline, global and single-path mutations."""
    # Top-level non-objects
    top = [
        ("top-level-list", []),
        ("top-level-string", "not_a_dict"),
        ("top-level-int", 123),
        ("top-level-float", 123.45),
        ("top-level-true", True),
        ("top-level-false", False),
        ("top-level-null", None),
        ("top-level-empty-dict", {}),
    ]
    for mut, payload in top:
        yield Case("", "TopLevel", "top-level", mut, payload)

    # Baselines
    for base, payload in BASE_PAYLOADS.items():
        yield Case("", base, "baseline", "valid baseline", copy.deepcopy(payload))

    # Global mutations
    for base, payload in BASE_PAYLOADS.items():
        yield Case(
            "", base, "exhaustive", "missing _type", delete_key(payload, "_type")
        )
        for label, val in [
            ("null", None),
            ("true", True),
            ("int", 123),
            ("float", 1.5),
            ("empty-string", ""),
            ("space", " "),
            ("unknown", "UnknownEventXYZ"),
            ("lowercase", base.lower()),
            ("trailing-space", base + " "),
            ("list", []),
            ("dict", {}),
        ]:
            yield Case(
                "",
                base,
                "exhaustive",
                f"_type = {label}",
                set_key(payload, "_type", val),
            )

        if "rid" in payload:
            yield Case(
                "", base, "exhaustive", "missing rid", delete_key(payload, "rid")
            )
            for label, val in [
                ("null", None),
                ("int", 123),
                ("float", 1.5),
                ("empty-string", ""),
                ("unicode", "rid_é😀"),
                ("long", "r" * 300),
                ("list", []),
                ("dict", {}),
            ]:
                yield Case(
                    "",
                    base,
                    "exhaustive",
                    f"rid = {label}",
                    set_key(payload, "rid", val),
                )

        yield Case(
            "",
            base,
            "exhaustive",
            "extra unknown root field",
            set_key(payload, "extra_unknown", True),
        )

        # Single-path mutations
        for path, value in iter_paths(payload):
            if path == "$._type":
                continue
            tokens = parse_path(path)
            if tokens and isinstance(tokens[-1], str):
                yield Case(
                    "", base, "exhaustive", f"delete {path}", delete_path(payload, path)
                )
            for label, wrong in WRONG_VALUES:
                yield Case(
                    "",
                    base,
                    "exhaustive",
                    f"{path} = {label}",
                    set_path(payload, path, wrong),
                )
            if isinstance(value, dict):
                yield Case(
                    "",
                    base,
                    "exhaustive",
                    f"{path}.unknown_extra = true",
                    set_path(payload, f"{path}.unknown_extra", True),
                )


def generate_pairwise(max_cases: int, rng: random.Random) -> Iterator[Case]:
    """Two simultaneous mutations on distinct paths."""
    emitted = 0
    bases = list(BASE_PAYLOADS.items())
    rng.shuffle(bases)
    for base, payload in bases:
        paths = [p for p, _ in iter_paths(payload) if p != "$._type"]
        if len(paths) < 2:
            continue
        combos = list(itertools.combinations(paths, 2))
        rng.shuffle(combos)
        for p1, p2 in combos:
            if emitted >= max_cases:
                return
            l1, v1 = rng.choice(WRONG_VALUES)
            l2, v2 = rng.choice(WRONG_VALUES)
            mutated = set_path(set_path(payload, p1, v1), p2, v2)
            yield Case("", base, "pairwise", f"{p1}={l1} + {p2}={l2}", mutated)
            emitted += 1


def generate_triplewise(max_cases: int, rng: random.Random) -> Iterator[Case]:
    emitted = 0
    bases = list(BASE_PAYLOADS.items())
    rng.shuffle(bases)
    for base, payload in bases:
        paths = [p for p, _ in iter_paths(payload) if p != "$._type"]
        if len(paths) < 3:
            continue
        while emitted < max_cases:
            p1, p2, p3 = rng.sample(paths, 3)
            l1, v1 = rng.choice(WRONG_VALUES)
            l2, v2 = rng.choice(WRONG_VALUES)
            l3, v3 = rng.choice(WRONG_VALUES)
            mutated = set_path(set_path(set_path(payload, p1, v1), p2, v2), p3, v3)
            yield Case(
                "", base, "triplewise", f"{p1}={l1} + {p2}={l2} + {p3}={l3}", mutated
            )
            emitted += 1
        if emitted >= max_cases:
            return


def generate_fuzz(max_cases: int, rng: random.Random) -> Iterator[Case]:
    emitted = 0
    bases = list(BASE_PAYLOADS.items())
    while emitted < max_cases:
        base, payload = rng.choice(bases)
        paths = [p for p, _ in iter_paths(payload) if p != "$._type"]
        if not paths:
            continue
        mutated = copy.deepcopy(payload)
        n = rng.randint(1, 4)
        labels = []
        for _ in range(n):
            path = rng.choice(paths)
            label, val = rng.choice(WRONG_VALUES)
            mutated = set_path(mutated, path, val)
            labels.append(f"{path}={label}")
        yield Case("", base, "fuzz", f"fuzz[{emitted}]: " + " + ".join(labels), mutated)
        emitted += 1


def generate_cross_event(max_cases: int, rng: random.Random) -> Iterator[Case]:
    """Inject fields from one event type into another."""
    emitted = 0
    bases = list(BASE_PAYLOADS.items())
    while emitted < max_cases:
        src_name, src = rng.choice(bases)
        dst_name, dst = rng.choice(bases)
        if src_name == dst_name:
            continue
        src_keys = [k for k in src if k != "_type"]
        if not src_keys:
            continue
        key = rng.choice(src_keys)
        mutated = set_key(dst, key, copy.deepcopy(src[key]))
        yield Case(
            "", dst_name, "cross", f"inject {src_name}.{key} into {dst_name}", mutated
        )
        emitted += 1


def generate_adversarial() -> Iterator[Case]:
    """Hand-crafted nasty payloads."""
    # Deeply nested
    deep: dict = {"_type": "ChatEvent", "level": 0}
    cur = deep
    for i in range(1, 100):
        cur["child"] = {"level": i}
        cur = cur["child"]
    yield Case("", "Adversarial", "adversarial", "100-level nesting", deep)

    # Huge array
    yield Case(
        "",
        "GetRoomUsersResponse",
        "adversarial",
        "10k-user list",
        {
            "_type": "GetRoomUsersResponse",
            "content": [
                [{"id": f"u{i}", "username": f"u{i}"}, None] for i in range(10_000)
            ],
        },
    )

    # Duplicate keys via malformed JSON — represented as string, parsed by loads
    yield Case(
        "",
        "Raw",
        "adversarial",
        "duplicate keys (raw)",
        '{"_type":"ChatEvent","_type":"Error","message":"x"}',
    )

    # Prototype-pollution-style keys
    for key in ("__class__", "__dict__", "__proto__", "constructor", "prototype"):
        yield Case(
            "",
            "ChatEvent",
            "adversarial",
            f"proto-pollution {key}",
            set_key(BASE_PAYLOADS["ChatEvent"], key, {"polluted": True}),
        )

    # Unicode attacks
    for label, s in [
        ("rtl-override", "\u202e reversed \u202c"),
        ("null-byte", "a\x00b"),
        ("bom", "\ufeffhello"),
        ("zero-width", "\u200b\u200c\u200d"),
        ("surrogate", "a\ud800b"),
        ("emoji-zwj", "👨‍👩‍👧‍👦"),
    ]:
        yield Case(
            "",
            "ChatEvent",
            "adversarial",
            f"unicode {label}",
            set_key(BASE_PAYLOADS["ChatEvent"], "message", s),
        )

    # NaN/Infinity
    yield Case(
        "",
        "Position",
        "adversarial",
        "NaN x",
        {
            "_type": "UserMovedEvent",
            "user": {"id": "u1", "username": "a"},
            "position": {"x": float("nan"), "y": 0.0, "z": 0.0, "facing": "Front"},
        },
    )
    yield Case(
        "",
        "Position",
        "adversarial",
        "+Inf z",
        {
            "_type": "UserMovedEvent",
            "user": {"id": "u1", "username": "a"},
            "position": {"x": 0.0, "y": 0.0, "z": float("inf"), "facing": "Front"},
        },
    )

    # Enormous ints
    yield Case(
        "",
        "RoomModeratedEvent",
        "adversarial",
        "duration 2**128",
        {
            "_type": "RoomModeratedEvent",
            "moderatorId": "m",
            "targetUserId": "u",
            "moderationType": "ban",
            "duration": 2**128,
        },
    )

    # Wrong-type user in every event
    for base, payload in BASE_PAYLOADS.items():
        if isinstance(payload.get("user"), dict):
            yield Case(
                "", base, "adversarial", "user = int", set_key(payload, "user", 123)
            )
            yield Case(
                "", base, "adversarial", "user = list", set_key(payload, "user", [])
            )


def generate_boundary() -> Iterator[Case]:
    """Boundary-value cases near typical limits."""
    yield Case(
        "",
        "ChatEvent",
        "boundary",
        "message 2000 chars",
        set_key(BASE_PAYLOADS["ChatEvent"], "message", "A" * 2000),
    )
    yield Case(
        "",
        "ChatEvent",
        "boundary",
        "message 2001 chars",
        set_key(BASE_PAYLOADS["ChatEvent"], "message", "A" * 2001),
    )
    yield Case(
        "",
        "ChatEvent",
        "boundary",
        "username 255 chars",
        set_path(BASE_PAYLOADS["ChatEvent"], "$.user.username", "u" * 255),
    )
    yield Case(
        "",
        "ChatEvent",
        "boundary",
        "username 256 chars",
        set_path(BASE_PAYLOADS["ChatEvent"], "$.user.username", "u" * 256),
    )
    yield Case(
        "",
        "ChatEvent",
        "boundary",
        "user id empty",
        set_path(BASE_PAYLOADS["ChatEvent"], "$.user.id", ""),
    )
    yield Case(
        "",
        "ChatEvent",
        "boundary",
        "user id unicode",
        set_path(BASE_PAYLOADS["ChatEvent"], "$.user.id", "üser_😀"),
    )
    for v in (0, 1, -1, 2**31 - 1, -(2**31), 2**63 - 1, -(2**63)):
        yield Case(
            "",
            "RoomModeratedEvent",
            "boundary",
            f"duration = {v}",
            set_key(BASE_PAYLOADS["RoomModeratedEvent"], "duration", v),
        )


# ═══════════════════════════════════════════════════════════════
# CASE PIPELINE
# ═══════════════════════════════════════════════════════════════
def generate_all_cases(cfg: dict, seed: int) -> list[Case]:
    rng = random.Random(seed)
    seen: set[bytes] = set()
    cases: list[Case] = []

    def emit(it: Iterable[Case]) -> None:
        for case in it:
            if len(cases) >= cfg["target"]:
                return
            try:
                h = _hash_payload(case.payload)
            except (TypeError, ValueError, RecursionError):
                h = None
            if h is not None:
                if h in seen:
                    continue
                seen.add(h)
            cases.append(case)

    sub("PHASE 1 · CASE GENERATION")

    emit(generate_exhaustive(seen))
    p(f"    exhaustive     : {len(cases):>10,}")

    if cfg.get("pairwise"):
        emit(generate_pairwise(cfg["pairwise"], rng))
        p(f"    pairwise       : {len(cases):>10,} (cumulative)")

    if cfg.get("triplewise"):
        emit(generate_triplewise(cfg["triplewise"], rng))
        p(f"    triplewise     : {len(cases):>10,} (cumulative)")

    if cfg.get("fuzz"):
        emit(generate_fuzz(cfg["fuzz"], rng))
        p(f"    fuzz           : {len(cases):>10,} (cumulative)")

    if cfg.get("cross"):
        emit(generate_cross_event(cfg["cross"], rng))
        p(f"    cross-event    : {len(cases):>10,} (cumulative)")

    if not cfg.get("no_adversarial"):
        emit(generate_adversarial())
        p(f"    adversarial    : {len(cases):>10,} (cumulative)")

    if not cfg.get("no_boundary"):
        emit(generate_boundary())
        p(f"    boundary       : {len(cases):>10,} (cumulative)")

    for i, case in enumerate(cases, start=1):
        case.id = f"V3-{i:07d}"

    p(f"    TOTAL          : {len(cases):>10,} unique cases")
    return cases


# ═══════════════════════════════════════════════════════════════
# WORKERS
# ═══════════════════════════════════════════════════════════════
_GLOBAL_PARSER: Any = None
_GLOBAL_MODE: str = ""


def _build_parser(mode: str):
    if mode == "official":
        from highrise import Incoming, converter

        def parse(payload):
            return converter.loads(json.dumps(payload, default=str), Incoming)

        return parse

    if mode == "lenient":
        from highrise_fast import parse_server_message

        return parse_server_message

    if mode == "strict":
        import highrise_fast

        parse = getattr(highrise_fast, "parse_server_message", None)
        try:
            sig = inspect.signature(parse)
            if "strict" in sig.parameters:
                return lambda p: parse(p, strict=True)
        except (TypeError, ValueError):
            pass
        validate = getattr(highrise_fast, "validate_server_message", None)
        if callable(validate) and parse is not None:

            def strict_parse(p):
                validate(p)
                return parse(p)

            return strict_parse
        strict = getattr(highrise_fast, "strict_parse_server_message", None)
        if callable(strict):
            return strict
        return None

    raise ValueError(f"Unknown mode: {mode}")


def _init_worker(mode: str) -> None:
    global _GLOBAL_PARSER, _GLOBAL_MODE
    _GLOBAL_MODE = mode
    try:
        _GLOBAL_PARSER = _build_parser(mode)
    except Exception:  # noqa: BLE001 — any failure => mode-unavailable sentinel
        _GLOBAL_PARSER = None


def _classify_batch(payloads: list[Any]) -> list[tuple[bool, str]]:
    out: list[tuple[bool, str]] = []
    parser = _GLOBAL_PARSER
    if parser is None:
        for _ in payloads:
            out.append((False, f"{_GLOBAL_MODE}-mode-unavailable"))
        return out
    for payload in payloads:
        try:
            parser(payload)
            out.append((True, ""))
        except Exception as exc:  # noqa: BLE001 — oracle: any raise == REJECT
            out.append((False, f"{type(exc).__name__}: {exc}"[:500]))
    return out


# ═══════════════════════════════════════════════════════════════
# PARALLEL DRIVER
# ═══════════════════════════════════════════════════════════════
def _batched(items: list[Any], size: int) -> Iterator[list[Any]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def classify_parallel(
    payloads: list[Any],
    mode: str,
    workers: int,
    chunk_size: int,
    label: str,
) -> list[tuple[bool, str]]:
    if workers <= 1 or len(payloads) < 200:
        _init_worker(mode)
        progress = Progress(len(payloads), label)
        results: list[tuple[bool, str]] = []
        for batch in _batched(payloads, chunk_size):
            results.extend(_classify_batch(batch))
            progress.update(len(batch))
        progress.close()
        return results

    ctx = get_context("spawn")
    results = [None] * len(payloads)
    progress = Progress(len(payloads), label)

    with ProcessPoolExecutor(
        max_workers=workers,
        mp_context=ctx,
        initializer=_init_worker,
        initargs=(mode,),
    ) as ex:
        future_to_range: dict[Any, tuple[int, int]] = {}
        for start, batch in zip(
            range(0, len(payloads), chunk_size),
            _batched(payloads, chunk_size),
        ):
            end = start + len(batch)
            future = ex.submit(_classify_batch, batch)
            future_to_range[future] = (start, end)

        for future in as_completed(future_to_range):
            start, end = future_to_range[future]
            try:
                batch_results = future.result()
            except Exception as exc:  # noqa: BLE001 — worker crashes become data
                batch_results = [(False, f"worker-crash: {exc}")] * (end - start)
            results[start:end] = batch_results
            progress.update(end - start)

    progress.close()
    return results  # type: ignore[return-value]


# ═══════════════════════════════════════════════════════════════
# GOLDEN MATRIX I/O
# ═══════════════════════════════════════════════════════════════
def save_golden(cases: list[Case], path: str) -> None:
    payload = {
        "version": VERSION,
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "total": len(cases),
        "cases": [
            {
                "id": c.id,
                "base": c.base,
                "family": c.family,
                "mutation": c.mutation,
                "payload": c.payload,
                "official_accept": c.official_accept,
                "official_error": c.official_error[:400],
            }
            for c in cases
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, default=str)
    p(f"    ✅ golden matrix saved: {path}")


def load_golden(cases: list[Case], path: str) -> int:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    entries = data.get("cases", [])
    by_id = {c.id: c for c in cases}
    loaded = 0
    for entry in entries:
        cid = entry.get("id")
        target = by_id.get(cid)
        if target is None:
            continue
        target.official_accept = entry.get("official_accept")
        target.official_error = entry.get("official_error", "")
        loaded += 1
    return loaded


# ═══════════════════════════════════════════════════════════════
# FEEDBACK SCORE
# ═══════════════════════════════════════════════════════════════
_EXPECTED_WORDS = (
    "expected",
    "must be",
    "type",
    "str",
    "string",
    "dict",
    "bool",
    "boolean",
    "float",
    "int",
    "number",
    "list",
    "required",
    "missing",
)
_GOT_WORDS = ("got", "received", "actual", "but got", "instance", "found")


def feedback_score(mutation: str, error_text: str) -> int:
    if not error_text:
        return 0
    text = error_text.lower()
    score = 0
    tokens = {
        t
        for t in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", mutation.lower())
        if len(t) >= 3
    }
    if tokens and any(t in text for t in tokens):
        score += 35
    if any(w in text for w in _EXPECTED_WORDS):
        score += 25
    if any(w in text for w in _GOT_WORDS):
        score += 20
    if any(m in text for m in ("$", ".", "path", "field", "->")):
        score += 10
    if len(error_text) >= 20:
        score += 5
    if "\n" in error_text:
        score += 5
    return min(100, score)


# ═══════════════════════════════════════════════════════════════
# PERF BENCHMARK
# ═══════════════════════════════════════════════════════════════
def _stats(samples: list[float]) -> dict[str, float]:
    samples = sorted(samples)
    n = len(samples)
    if n == 0:
        return {}

    def q(f: float) -> float:
        idx = min(int(n * f), n - 1)
        return samples[idx]

    total = sum(samples)
    return {
        "n": n,
        "total_ns": total,
        "avg_ns": total / n,
        "p50_ns": q(0.50),
        "p90_ns": q(0.90),
        "p95_ns": q(0.95),
        "p99_ns": q(0.99),
        "p999_ns": q(0.999),
        "p9999_ns": q(0.9999),
        "min_ns": samples[0],
        "max_ns": samples[-1],
        "stdev_ns": statistics.stdev(samples) if n > 1 else 0.0,
    }


def _micro(fn, iters: int, warmup: int = 50) -> dict[str, float]:
    for _ in range(warmup):
        fn()
    samples: list[float] = []
    for _ in range(iters):
        t0 = time.perf_counter_ns()
        fn()
        samples.append(time.perf_counter_ns() - t0)
    return _stats(samples)


def run_perf_phase(cfg: dict) -> dict[str, Any]:
    sub("PHASE 5 · PERFORMANCE")
    try:
        from highrise_fast import (
            dumps_json,
            loads_json,
            parse_server_message,
        )
        from highrise_fast import (
            parse_server_message as _p,
        )
    except ImportError as e:
        p(f"    ⚠️  custom SDK unavailable: {e}")
        return {}

    iters = cfg.get("perf_iters", 20_000)
    out: dict[str, Any] = {}

    enc_payload = {
        "_type": "ChatRequest",
        "rid": "perf",
        "message": "hello world",
        "whisper_target_id": None,
    }
    out["encode"] = _micro(lambda: dumps_json(enc_payload), iters)

    raw = json.dumps(
        {
            "_type": "ChatEvent",
            "user": {"id": "u1", "username": "alice"},
            "message": "hello",
            "whisper": False,
        }
    ).encode()
    out["decode"] = _micro(lambda: loads_json(raw), iters)

    out["round_trip"] = _micro(lambda: loads_json(dumps_json(enc_payload)), iters)

    chat_dict = {
        "_type": "ChatEvent",
        "user": {"id": "u1", "username": "alice"},
        "message": "hello",
        "whisper": False,
    }
    out["parse_lenient"] = _micro(lambda: parse_server_message(chat_dict), iters)

    try:
        inspect.signature(_p).parameters.get("strict")
        if "strict" in inspect.signature(_p).parameters:
            out["parse_strict"] = _micro(lambda: _p(chat_dict, strict=True), iters)
    except (TypeError, ValueError):
        pass

    # Throughput
    t0 = time.perf_counter()
    total_bytes = 0
    ops = 0
    while time.perf_counter() - t0 < 1.0:
        total_bytes += len(dumps_json(enc_payload))
        ops += 1
    out["throughput_mbps"] = total_bytes / (time.perf_counter() - t0) / (1024 * 1024)

    for key, s in out.items():
        if isinstance(s, dict):
            p(
                f"    {key:16s}  avg={fmt_ns(s['avg_ns']):>10s}  "
                f"p50={fmt_ns(s['p50_ns']):>10s}  "
                f"p99={fmt_ns(s['p99_ns']):>10s}  "
                f"p99.9={fmt_ns(s['p999_ns']):>10s}  "
                f"stdev={fmt_ns(s['stdev_ns']):>10s}"
            )

    # Sustained load
    duration = cfg.get("endurance", 10.0)
    p(f"\n    Sustained lenient parse for {duration:.1f}s...")
    latencies: list[float] = []
    errors = 0
    ops = 0
    t_start = time.perf_counter()
    while time.perf_counter() - t_start < duration:
        t0 = time.perf_counter_ns()
        try:
            parse_server_message(chat_dict)
            ops += 1
        except Exception:  # noqa: BLE001 — count as error, keep loop alive
            errors += 1
        latencies.append(time.perf_counter_ns() - t0)
    elapsed = time.perf_counter() - t_start
    sustained = _stats(latencies)
    sustained["ops"] = ops
    sustained["errors"] = errors
    sustained["duration_s"] = elapsed
    sustained["ops_per_sec"] = ops / elapsed
    out["sustained"] = sustained

    p(
        f"    Sustained: {ops:,} ops in {elapsed:.2f}s ({ops / elapsed:,.0f} ops/s), {errors} errors"
    )
    p(
        f"    Latency  : p50={fmt_ns(sustained['p50_ns'])}  "
        f"p95={fmt_ns(sustained['p95_ns'])}  "
        f"p99={fmt_ns(sustained['p99_ns'])}  "
        f"p99.9={fmt_ns(sustained['p999_ns'])}  "
        f"p99.99={fmt_ns(sustained['p9999_ns'])}"
    )

    return out


# ═══════════════════════════════════════════════════════════════
# MEMORY / LEAK PHASE
# ═══════════════════════════════════════════════════════════════
def run_memory_phase(cfg: dict) -> dict[str, Any]:
    sub("PHASE 6 · MEMORY / LEAK AUDIT")
    out: dict[str, Any] = {}

    try:
        from highrise_fast import (
            Highrise,
            Position,
            User,
            dumps_json,
            loads_json,
            parse_server_message,
        )
    except ImportError as e:
        p(f"    ⚠️  custom SDK unavailable: {e}")
        return {}

    # GC pressure
    sample = {
        "_type": "ChatEvent",
        "user": {"id": "u1", "username": "alice"},
        "message": "gc",
        "whisper": False,
    }
    gc.collect()
    gc.collect()
    before = gc.get_stats()[0]["collections"] if gc.get_stats() else 0
    for _ in range(50_000):
        parse_server_message(sample)
    gc.collect()
    after = gc.get_stats()[0]["collections"] if gc.get_stats() else 0
    out["gc_collections_50k"] = after - before
    p(f"    GC collections during 50k parses : {out['gc_collections_50k']}")

    # Object growth
    gc.collect()
    objs_before = len(gc.get_objects())
    for _ in range(50_000):
        parse_server_message(sample)
    gc.collect()
    objs_after = len(gc.get_objects())
    out["object_growth_50k"] = objs_after - objs_before
    p(f"    Object count growth (50k parses) : {out['object_growth_50k']:+,}")

    # tracemalloc peak
    tracemalloc.start()
    for _ in range(20_000):
        loads_json(dumps_json(sample))
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    out["tracemalloc_peak_bytes"] = peak
    out["tracemalloc_per_op"] = peak / 20_000
    p(
        f"    tracemalloc peak (20k rt)        : {fmt_bytes(peak)} ({fmt_bytes(peak / 20_000)}/op)"
    )

    # Cancelled-request leak
    import asyncio

    class SilentWS:
        async def send_str(self, data):
            pass

        async def send_bytes(self, data):
            pass

    async def leak_test(n: int) -> int:
        hr = Highrise()
        hr.ws = SilentWS()
        hr.my_id = "bot"
        tasks = [asyncio.create_task(hr.get_wallet()) for _ in range(n)]
        await asyncio.sleep(0.3)
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        return len(hr._pending)

    try:
        leaked = asyncio.run(leak_test(cfg.get("leak_n", 200)))
        out["cancelled_leak"] = leaked
        p(
            f"    Cancelled-request leak ({cfg.get('leak_n', 200):>4d})    : "
            f"{leaked} {'✅ clean' if leaked == 0 else '*** LEAK ***'}"
        )
    except Exception as e:  # noqa: BLE001 — leak-test harness
        out["cancelled_leak_error"] = str(e)[:200]
        p(f"    ⚠️  cancelled-request leak test: {e}")

    # WeakRef GC
    u = User(id="u1", username="alice")
    pos = Position(x=1.0, y=0.0, z=2.0, facing="Front")
    import weakref

    wr_u = weakref.ref(u)
    wr_p = weakref.ref(pos)
    del u, pos
    gc.collect()
    gc.collect()
    out["weakref_user_collected"] = wr_u() is None
    out["weakref_pos_collected"] = wr_p() is None
    p(
        f"    WeakRef collected (User)         : "
        f"{'✅' if out['weakref_user_collected'] else '❌ (cycle)'}"
    )
    p(
        f"    WeakRef collected (Position)     : "
        f"{'✅' if out['weakref_pos_collected'] else '❌ (cycle)'}"
    )

    return out


# ═══════════════════════════════════════════════════════════════
# REPORT
# ═══════════════════════════════════════════════════════════════
def _match_stats(cases: list[Case], key: str) -> dict[str, Any]:
    total = len(cases)
    accepts = sum(1 for c in cases if getattr(c, f"{key}_accept") is True)
    matches = sum(
        1
        for c in cases
        if getattr(c, f"{key}_accept") is not None
        and c.official_accept is not None
        and getattr(c, f"{key}_accept") == c.official_accept
    )
    return {
        "accepts": accepts,
        "rejects": total - accepts,
        "matches": matches,
        "match_rate": matches / total if total else 0.0,
    }


def build_report(
    cases: list[Case],
    cfg: dict,
    official_s: float,
    lenient_s: float,
    strict_s: float,
    strict_available: bool,
    strict_note: str,
    perf: dict[str, Any],
    mem: dict[str, Any],
) -> dict[str, Any]:
    family_counter = Counter(c.family for c in cases)
    base_counter = Counter(c.base for c in cases)

    official_fb: list[float] = []
    strict_fb: list[float] = []
    mismatches: list[dict[str, Any]] = []

    for c in cases:
        if c.official_accept is False:
            official_fb.append(feedback_score(c.mutation, c.official_error))
            if strict_available:
                if c.strict_accept is False:
                    strict_fb.append(feedback_score(c.mutation, c.strict_error))
                elif c.strict_accept is True:
                    strict_fb.append(0.0)
                    mismatches.append(
                        {
                            "id": c.id,
                            "base": c.base,
                            "family": c.family,
                            "mutation": c.mutation,
                            "official": "REJECT",
                            "strict": "ACCEPT",
                            "official_error": c.official_error[:300],
                        }
                    )

    avg = lambda xs: sum(xs) / len(xs) if xs else 0.0

    report = {
        "version": VERSION,
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "platform": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
        },
        "config": {
            k: v
            for k, v in cfg.items()
            if isinstance(v, (int, float, str, bool, type(None)))
        },
        "generation": {
            "total_cases": len(cases),
            "unique_payloads": len(cases),
            "by_family": dict(family_counter),
            "by_base": dict(base_counter),
        },
        "official": {
            "accepts": sum(1 for c in cases if c.official_accept is True),
            "rejects": sum(1 for c in cases if c.official_accept is False),
            "duration_s": official_s,
            "cases_per_sec": len(cases) / official_s if official_s > 0 else 0,
        },
        "lenient": {
            **_match_stats(cases, "lenient"),
            "duration_s": lenient_s,
            "cases_per_sec": len(cases) / lenient_s if lenient_s > 0 else 0,
        },
        "strict": {
            **_match_stats(cases, "strict"),
            "available": strict_available,
            "note": strict_note,
            "duration_s": strict_s,
            "cases_per_sec": len(cases) / strict_s if strict_s > 0 else 0,
        },
        "feedback": {
            "official_avg": avg(official_fb),
            "strict_avg": avg(strict_fb),
            "strict_ratio": (
                (avg(strict_fb) / avg(official_fb)) if avg(official_fb) else 0.0
            ),
        },
        "performance": perf,
        "memory": mem,
        "mismatches": mismatches[:200],
        "mismatch_count": len(mismatches),
    }
    return report


def print_report(report: dict[str, Any], show: str, cases: list[Case]) -> None:
    header("RESULTS")
    gen = report["generation"]
    p(f"  Total cases              : {gen['total_cases']:>14,}")
    p(f"  Unique payloads          : {gen['unique_payloads']:>14,}")
    p("  By family                :")
    for fam, n in sorted(gen["by_family"].items(), key=lambda kv: -kv[1]):
        p(f"      {fam:14s} {n:>14,}")

    off = report["official"]
    p(f"\n  Official ACCEPT          : {off['accepts']:>14,}")
    p(f"  Official REJECT          : {off['rejects']:>14,}")
    p(
        f"  Official duration        : {off['duration_s']:>14.2f} s "
        f"({off['cases_per_sec']:>12,.0f} cases/s)"
    )

    lenient = report["lenient"]
    p(
        f"\n  Custom lenient match     : {lenient['matches']:>14,}/{lenient['accepts'] + lenient['rejects']:,} "
        f"({lenient['match_rate'] * 100:.4f}%)"
    )
    p(
        f"  Custom lenient duration  : {lenient['duration_s']:>14.2f} s "
        f"({lenient['cases_per_sec']:>12,.0f} cases/s)"
    )

    strict = report["strict"]
    if strict["available"]:
        p(
            f"\n  Custom strict match      : {strict['matches']:>14,}/{strict['accepts'] + strict['rejects']:,} "
            f"({strict['match_rate'] * 100:.4f}%)"
        )
        p(
            f"  Custom strict duration   : {strict['duration_s']:>14.2f} s "
            f"({strict['cases_per_sec']:>12,.0f} cases/s)"
        )
    else:
        p(f"\n  Custom strict            : ⚠️  unavailable ({strict['note']})")

    fb = report["feedback"]
    p(f"\n  Official feedback avg    : {fb['official_avg']:>6.2f}/100")
    p(
        f"  Custom strict feedback   : {fb['strict_avg']:>6.2f}/100 "
        f"(×{fb['strict_ratio']:.2f} vs official)"
    )

    # Mismatch table
    if show == "all":
        header("CASES")
        p(
            f"{'ID':10s} {'Family':12s} {'Base':22s} {'Oracle':7s} {'Len':7s} {'Strict':7s} Mutation"
        )
        p("─" * 110)
        limit = cases if len(cases) <= 500 else cases[:500]
        for c in limit:
            p(
                f"{c.id:10s} {c.family:12s} {short(c.base, 22):22s} "
                f"{'ACC' if c.official_accept else 'REJ':7s} "
                f"{'ACC' if c.lenient_accept else 'REJ':7s} "
                f"{'ACC' if c.strict_accept else 'REJ':7s} "
                f"{short(c.mutation, 50)}"
            )
        if len(cases) > 500:
            p(f"... {len(cases) - 500:,} more cases omitted")

    if show in ("mismatches", "all"):
        header("MISMATCHES")
        if not report["mismatches"]:
            p("  ✅ No strict-mode mismatches.")
        else:
            p(f"  ❌ {report['mismatch_count']:,} mismatches (showing first 50)")
            for m in report["mismatches"][:50]:
                p(f"  [{m['id']}] {m['base']} — {short(m['mutation'], 60)}")
                p(f"      Official: {m['official']} | Strict: {m['strict']}")
                if m.get("official_error"):
                    p(f"      Off err : {short(m['official_error'], 180)}")


def print_verdict(report: dict[str, Any]) -> int:
    header("FINAL VERDICT")
    strict = report["strict"]
    total = report["generation"]["total_cases"]

    if not strict["available"]:
        p("  ❌ STRICT MODE MISSING")
        p(
            "     Add parse_server_message(data, strict=True) or validate_server_message(data)."
        )
        return 2

    if strict["matches"] == total:
        p(f"  🏆 SUCCESS: strict mode matches official on all {total:,} cases.")
        p(
            f"     Feedback quality: {report['feedback']['strict_avg']:.2f}/100 "
            f"vs official {report['feedback']['official_avg']:.2f}/100"
        )
        return 0

    p(f"  ❌ {total - strict['matches']:,} mismatch(es) out of {total:,}.")
    return 1


# ═══════════════════════════════════════════════════════════════
# REGRESSION
# ═══════════════════════════════════════════════════════════════
def diff_regression(current: dict[str, Any], prev_path: str) -> None:
    sub("REGRESSION vs PREVIOUS REPORT")
    try:
        with open(prev_path, encoding="utf-8") as f:
            prev = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        p(f"    ⚠️  could not load previous report: {e}")
        return

    def show(label, cur_val, prev_val, lower_is_better=False):
        if prev_val in (None, 0) or cur_val is None:
            return
        delta = cur_val - prev_val
        pct = (delta / prev_val) * 100
        improved = (delta < 0) if lower_is_better else (delta > 0)
        arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
        mark = "✅" if improved or delta == 0 else "⚠️"
        p(
            f"    {label:38s} {prev_val:>14,.2f} → {cur_val:>14,.2f} ({arrow}{abs(pct):.2f}%) {mark}"
        )

    cur_off = current.get("official", {})
    prev_off = prev.get("official", {})
    show("official accepts", cur_off.get("accepts"), prev_off.get("accepts"))

    cur_len = current.get("lenient", {})
    prev_len = prev.get("lenient", {})
    show(
        "lenient match rate",
        cur_len.get("match_rate", 0) * 100,
        prev_len.get("match_rate", 0) * 100,
    )

    cur_str = current.get("strict", {})
    prev_str = prev.get("strict", {})
    show(
        "strict match rate",
        cur_str.get("match_rate", 0) * 100,
        prev_str.get("match_rate", 0) * 100,
    )
    show("strict cases/s", cur_str.get("cases_per_sec"), prev_str.get("cases_per_sec"))
    show(
        "strict feedback avg",
        current.get("feedback", {}).get("strict_avg"),
        prev.get("feedback", {}).get("strict_avg"),
    )


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
def main() -> int:
    ap = argparse.ArgumentParser(
        description=f"benchmark_v3 — MAXIMUM-SCALE type validation & perf — v{VERSION}"
    )
    ap.add_argument("--preset", choices=list(PRESETS.keys()), default=None)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--standard", action="store_true")
    ap.add_argument("--max", action="store_true")
    ap.add_argument("--extreme", action="store_true")
    ap.add_argument(
        "--target", type=int, default=None, help="Override target case count"
    )
    ap.add_argument("--pairwise", type=int, default=None)
    ap.add_argument("--triplewise", type=int, default=None)
    ap.add_argument("--fuzz", type=int, default=None)
    ap.add_argument("--cross", type=int, default=None)
    ap.add_argument("--endurance", type=float, default=None)
    ap.add_argument("--perf-iters", type=int, default=20_000)
    ap.add_argument("--leak-n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--chunk-size", type=int, default=256)
    ap.add_argument("--no-adversarial", action="store_true")
    ap.add_argument("--no-boundary", action="store_true")
    ap.add_argument("--no-perf", action="store_true")
    ap.add_argument("--no-memory", action="store_true")
    ap.add_argument(
        "--no-official",
        action="store_true",
        help="Skip official classification (needs --reuse-official)",
    )
    ap.add_argument(
        "--save-official",
        type=str,
        default="",
        help="Save the official golden matrix to this path",
    )
    ap.add_argument(
        "--reuse-official",
        type=str,
        default="",
        help="Load a previously saved official golden matrix",
    )
    ap.add_argument(
        "--json-report",
        type=str,
        default="",
        help="Write the full JSON report to this path",
    )
    ap.add_argument(
        "--regression",
        type=str,
        default="",
        help="Compare against a previous JSON report",
    )
    ap.add_argument(
        "--show", choices=["none", "mismatches", "all"], default="mismatches"
    )
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    # Resolve preset
    if args.quick:
        args.preset = "quick"
    elif args.standard:
        args.preset = "standard"
    elif args.extreme:
        args.preset = "extreme"
    elif args.max or args.preset is None:
        args.preset = "max"

    cfg = dict(PRESETS[args.preset])
    if args.target is not None:
        cfg["target"] = args.target
    if args.pairwise is not None:
        cfg["pairwise"] = args.pairwise
    if args.triplewise is not None:
        cfg["triplewise"] = args.triplewise
    if args.fuzz is not None:
        cfg["fuzz"] = args.fuzz
    if args.cross is not None:
        cfg["cross"] = args.cross
    if args.endurance is not None:
        cfg["endurance"] = args.endurance
    cfg["perf_iters"] = args.perf_iters
    cfg["leak_n"] = args.leak_n
    cfg["no_adversarial"] = args.no_adversarial
    cfg["no_boundary"] = args.no_boundary
    cfg["seed"] = args.seed

    # Header
    p("═" * 100)
    p(f"  BENCHMARK V3 · MAXIMUM-SCALE TYPE VALIDATION · v{VERSION}")
    p(
        f"  {datetime.now(tz=UTC).strftime('%Y-%m-%d %H:%M:%S')}  |  "
        f"Python {sys.version.split()[0]}  |  {platform.platform()}"
    )
    p(
        f"  Preset={args.preset}  target={cfg['target']:,}  workers={args.workers}  seed={args.seed}"
    )
    p("═" * 100)

    # ── Phase 1: generate ──
    cases = generate_all_cases(cfg, args.seed)

    # ── Phase 2: official ──
    sub("PHASE 2 · OFFICIAL ORACLE CLASSIFICATION")
    official_s = 0.0
    if args.reuse_official:
        n = load_golden(cases, args.reuse_official)
        p(
            f"    ✅ loaded {n:,}/{len(cases):,} official verdicts from {args.reuse_official}"
        )
    elif args.no_official:
        p("    ⚠️  --no-official set without --reuse-official; cannot proceed.")
        return 2
    else:
        t0 = time.perf_counter()
        results = classify_parallel(
            [c.payload for c in cases],
            mode="official",
            workers=args.workers,
            chunk_size=args.chunk_size,
            label="official",
        )
        official_s = time.perf_counter() - t0
        for c, (acc, err) in zip(cases, results):
            c.official_accept, c.official_error = acc, err
        if args.save_official:
            save_golden(cases, args.save_official)

    # ── Phase 3: lenient ──
    sub("PHASE 3 · CUSTOM LENIENT CLASSIFICATION")
    t0 = time.perf_counter()
    results = classify_parallel(
        [c.payload for c in cases],
        mode="lenient",
        workers=args.workers,
        chunk_size=args.chunk_size,
        label="lenient",
    )
    lenient_s = time.perf_counter() - t0
    for c, (acc, err) in zip(cases, results):
        c.lenient_accept, c.lenient_error = acc, err

    # ── Phase 4: strict ──
    sub("PHASE 4 · CUSTOM STRICT CLASSIFICATION")
    _init_worker("strict")
    strict_available = _GLOBAL_PARSER is not None
    strict_note = (
        "parse_server_message(..., strict=True)"
        if strict_available
        else "strict mode not detected"
    )
    strict_s = 0.0
    if strict_available:
        p(f"    ✅ strict mode detected: {strict_note}")
        t0 = time.perf_counter()
        results = classify_parallel(
            [c.payload for c in cases],
            mode="strict",
            workers=args.workers,
            chunk_size=args.chunk_size,
            label="strict",
        )
        strict_s = time.perf_counter() - t0
        for c, (acc, err) in zip(cases, results):
            c.strict_accept, c.strict_error = acc, err
    else:
        p(f"    ❌ strict mode not detected ({strict_note})")

    # ── Phase 5: performance ──
    perf = {} if args.no_perf else run_perf_phase(cfg)

    # ── Phase 6: memory ──
    mem = {} if args.no_memory else run_memory_phase(cfg)

    # ── Report ──
    report = build_report(
        cases,
        cfg,
        official_s,
        lenient_s,
        strict_s,
        strict_available,
        strict_note,
        perf,
        mem,
    )
    print_report(report, args.show, cases)

    if args.regression:
        diff_regression(report, args.regression)

    if args.json_report:
        sub("WRITING JSON REPORT")
        with open(args.json_report, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        p(f"    ✅ {args.json_report}")

    return print_verdict(report)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        p("\n  ⚠️  interrupted")
        sys.exit(130)

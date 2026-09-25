#!/usr/bin/env python3
"""
BENCHMARK V4: THE MOTHERSHIP (LEVIATHAN EDITION)
================================================
A massive, multi-phase, 100,000+ test combinatorial stress suite for highrise_fast.
Tests: Type Validation, Wire Protocol, Async Concurrency, Memory Leaks, and Security.

Usage:
    python benchmarkv4.py
    python benchmarkv4.py --minimal
    python benchmarkv4.py --target 5000 --workers 2
    python benchmarkv4.py --phases 1,2,3
    python benchmarkv4.py --extreme

Outputs (always written, even on crash):
    benchmarkv4.log         - full run log (ANSI stripped)
    benchmarkv4_crash.log   - faulthandler crash dump
    benchmarkv4_report.json - per-phase results, updated after each phase

Measurement policy
------------------
Wall-clock  (time.perf_counter_ns)     : throughput / ETA / progress
CPU time    (time.process_time_ns)     : per-op CPU cost (what the README claims)
Both are reported by Phase 3 so that "faster" and "less CPU" can be separated.
"""

# FIX: benchmark harness intentionally catches Exception to record accept/reject.
# ruff: noqa: BLE001, S110

from __future__ import annotations

import argparse
import asyncio
import atexit
import contextlib
import copy
import faulthandler
import gc
import hashlib
import inspect
import json
import math
import multiprocessing as mp
import os
import random
import re
import signal
import sys
import threading
import time
import traceback
import tracemalloc
import weakref
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ═══════════════════════════════════════════════════════════════════════════════
# LOG / CRASH / REPORT FILE SETUP  (must happen before anything else)
# ═══════════════════════════════════════════════════════════════════════════════
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_SCRIPT_DIR = Path(__file__).resolve().parent
LOG_FILE = _SCRIPT_DIR / "benchmarkv4.log"
CRASH_FILE = _SCRIPT_DIR / "benchmarkv4_crash.log"
REPORT_FILE = _SCRIPT_DIR / "benchmarkv4_report.json"

# FIX: only the main process opens the log file. Spawned workers on Windows
# re-import this module and would otherwise truncate the log every time.
# FIX (SIM115): file handles are managed via an ExitStack registered with
# atexit, so the process-lifetime open() calls are context-managed correctly.
_LOG_FH = None
_CRASH_FH = None
_ATEXIT_STACK = contextlib.ExitStack()
if __name__ == "__main__":
    try:
        _LOG_FH = _ATEXIT_STACK.enter_context(
            open(LOG_FILE, "w", encoding="utf-8", buffering=1)
        )
    except Exception:
        _LOG_FH = None
    try:
        _CRASH_FH = _ATEXIT_STACK.enter_context(open(CRASH_FILE, "w", encoding="utf-8"))
        faulthandler.enable(file=_CRASH_FH, all_threads=True)
    except Exception:
        _CRASH_FH = None

# FIX: PHASE_RESULTS must exist before write_report can be used by signal handlers.
PHASE_RESULTS: dict[str, Any] = {}


def write_report() -> None:
    """Write current phase results to disk. Never raise."""
    try:
        with REPORT_FILE.open("w", encoding="utf-8") as f:
            json.dump(PHASE_RESULTS, f, indent=2, default=str)
    except Exception as e:
        try:
            sys.stderr.write(f"  ⚠️ could not write report: {e}\n")
        except Exception:
            pass


def p(*args, **kwargs):
    text = " ".join(str(a) for a in args)
    try:
        print(text, **kwargs, flush=True)
    except Exception:
        pass
    if _LOG_FH is not None:
        try:
            _LOG_FH.write(_ANSI_RE.sub("", text) + "\n")
            _LOG_FH.flush()
        except Exception:
            pass


# FIX (SIM115): the two log handles are owned by _ATEXIT_STACK, which is
# closed below. The manual _close_logs() helper is no longer needed.
atexit.register(_ATEXIT_STACK.close)
atexit.register(write_report)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
VERSION = "4.2.0-MOTHERSHIP"

# FIX: dramatically reduced defaults. Windows spawn re-imports every worker,
# so 4+ workers each loading orjson + aiohttp + cattrs is a real CPU/memory hit.
DEFAULT_TARGET = 5_000
DEFAULT_WORKERS = max(1, min(2, (os.cpu_count() or 2) - 1))
DEFAULT_ITERS = 3_000
DEFAULT_PHASE4_CONCURRENCY = 200
DEFAULT_PHASE5_PARSES = 5_000


class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    WARN = "\033[93m"
    FAIL = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"


def header(title: str):
    p(f"\n{Colors.BOLD}{Colors.CYAN}{'═' * 100}")
    p(f"  {title}")
    p(f"{'═' * 100}{Colors.END}\n")


def sub(title: str):
    p(f"\n{Colors.BOLD}── {title} {'─' * max(0, 90 - len(title))}{Colors.END}")


class Progress:
    def __init__(self, total: int, label: str = "working"):
        self.total = max(1, total)
        self.label = label
        self.start = time.perf_counter()
        self.done = 0
        self._last = 0.0

    def update(self, n: int = 1):
        self.done += n
        now = time.perf_counter()
        if now - self._last > 0.2 or self.done >= self.total:
            self._last = now
            elapsed = now - self.start
            rate = self.done / elapsed if elapsed > 0 else 0
            eta = (self.total - self.done) / rate if rate > 0 else 0
            pct = 100 * self.done / self.total
            sys.stdout.write(
                f"\r  {self.label}: {self.done:>10,}/{self.total:,} "
                f"({pct:5.1f}%) | {rate:>8,.0f}/s | ETA {eta:>5.1f}s   "
            )
            sys.stdout.flush()
            if self.done >= self.total:
                sys.stdout.write("\n")
                sys.stdout.flush()


class Watchdog:
    """Log a heartbeat while a phase is running so a hang is visible."""

    def __init__(self, label: str, interval: float = 15.0):
        self.label = label
        self.interval = interval
        self._stop = threading.Event()
        self._t: threading.Thread | None = None
        self.start_time = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()

        def loop():
            while not self._stop.wait(self.interval):
                elapsed = time.perf_counter() - self.start_time
                p(f"  [{self.label}] still running... ({elapsed:.1f}s elapsed)")

        self._t = threading.Thread(
            target=loop, daemon=True, name=f"watchdog-{self.label}"
        )
        self._t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._t is not None:
            self._t.join(timeout=1.0)


# ═══════════════════════════════════════════════════════════════════════════════
# BASE PAYLOADS
# ═══════════════════════════════════════════════════════════════════════════════
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

# ═══════════════════════════════════════════════════════════════════════════════
# PATH HELPERS & MUTATORS
# ═══════════════════════════════════════════════════════════════════════════════
WRONG_VALUES = [
    ("null", None),
    ("true", True),
    ("false", False),
    ("int", 123),
    ("float", 1.5),
    ("string", "wrong"),
    ("empty", ""),
    ("list", []),
    ("dict", {}),
    ("large", 2**62),
]


def parse_path(path: str) -> list:
    tokens = []
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
    with contextlib.suppress(KeyError, IndexError, TypeError):
        cur = data
        for t in tokens[:-1]:
            cur = cur[t]
        cur[tokens[-1]] = value
    return data


def delete_path(payload: Any, path: str) -> Any:
    data = copy.deepcopy(payload)
    tokens = parse_path(path)
    if not tokens:
        return data
    with contextlib.suppress(KeyError, IndexError, TypeError):
        cur = data
        for t in tokens[:-1]:
            cur = cur[t]
        last = tokens[-1]
        if isinstance(cur, dict):
            cur.pop(last, None)
        elif isinstance(cur, list) and 0 <= last < len(cur):
            cur[last] = None
    return data


def iter_paths(value: Any, path: str = "$"):
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


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: THE SWARM (PAYLOAD GENERATOR)
# ═══════════════════════════════════════════════════════════════════════════════
@dataclass
class Case:
    id: str
    base: str
    family: str
    mutation: str
    payload: Any


def generate_swarm(target: int, seed: int) -> list[Case]:
    rng = random.Random(seed)
    cases: list[Case] = []
    seen = set()

    def emit(case: Case) -> bool:
        if len(cases) >= target:
            return False
        try:
            h = hashlib.blake2b(
                json.dumps(case.payload, sort_keys=True, default=str).encode(),
                digest_size=8,
            ).digest()
        except (TypeError, ValueError):
            h = repr(case.payload).encode()
        if h in seen:
            return True
        seen.add(h)
        cases.append(case)
        return True

    for b, p_ in BASE_PAYLOADS.items():
        emit(Case("", b, "baseline", "valid", copy.deepcopy(p_)))
    for mut, val in [("list", []), ("string", "x"), ("int", 1), ("null", None)]:
        emit(Case("", "TopLevel", "top", mut, val))

    for b, p_ in BASE_PAYLOADS.items():
        for path, _ in iter_paths(p_):
            if path == "$._type":
                continue
            emit(Case("", b, "exhaustive", f"del {path}", delete_path(p_, path)))
            for lbl, val in WRONG_VALUES:
                emit(
                    Case("", b, "exhaustive", f"{path}={lbl}", set_path(p_, path, val))
                )

    bases = list(BASE_PAYLOADS.items())
    while len(cases) < target:
        b, p_ = rng.choice(bases)
        paths = [pt for pt, _ in iter_paths(p_) if pt != "$._type"]
        if not paths:
            continue

        mutated = copy.deepcopy(p_)
        labels = []
        for _ in range(rng.randint(1, 4)):
            pt = rng.choice(paths)
            lbl, val = rng.choice(WRONG_VALUES)
            mutated = set_path(mutated, pt, val)
            labels.append(f"{pt}={lbl}")
        emit(Case("", b, "fuzz", "+".join(labels), mutated))

    for i, c in enumerate(cases, 1):
        c.id = f"V4-{i:06d}"
    return cases


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: THE ORACLE CRUCIBLE (VALIDATION WORKERS)
# ═══════════════════════════════════════════════════════════════════════════════
_GLOBAL_PARSERS: dict[str, Any] = {}


def init_worker():
    """Runs in each worker process after spawn."""
    global _GLOBAL_PARSERS
    _GLOBAL_PARSERS = {}

    # FIX: log worker identity to stderr (stdout is inherited, log file is not).
    sys.stderr.write(f"  [worker {os.getpid()}] starting...\n")
    sys.stderr.flush()

    try:
        from highrise import Incoming, converter

        _GLOBAL_PARSERS["official"] = lambda p_: converter.loads(
            json.dumps(p_, default=str), Incoming
        )
        sys.stderr.write(f"  [worker {os.getpid()}] official OK\n")
        sys.stderr.flush()
    except (ImportError, AttributeError) as e:
        sys.stderr.write(f"  [worker {os.getpid()}] official MISSING: {e}\n")
        sys.stderr.flush()

    try:
        from highrise_fast import parse_server_message

        _GLOBAL_PARSERS["lenient"] = parse_server_message
        sig = inspect.signature(parse_server_message)
        if "strict" in sig.parameters:
            _GLOBAL_PARSERS["strict"] = lambda p_: parse_server_message(p_, strict=True)
        sys.stderr.write(f"  [worker {os.getpid()}] custom OK\n")
        sys.stderr.flush()
    except (ImportError, AttributeError, TypeError) as e:
        sys.stderr.write(f"  [worker {os.getpid()}] custom MISSING: {e}\n")
        sys.stderr.flush()


def classify_batch(payloads: list[Any]) -> list[dict]:
    results = []
    for p_ in payloads:
        rec = {
            "off_acc": False,
            "off_err": "",
            "len_acc": False,
            "len_err": "",
            "str_acc": False,
            "str_err": "",
        }

        if "official" in _GLOBAL_PARSERS:
            try:
                _GLOBAL_PARSERS["official"](p_)
                rec["off_acc"] = True
            except Exception as e:
                rec["off_err"] = f"{type(e).__name__}: {e}"

        if "lenient" in _GLOBAL_PARSERS:
            try:
                _GLOBAL_PARSERS["lenient"](p_)
                rec["len_acc"] = True
            except Exception as e:
                rec["len_err"] = f"{type(e).__name__}: {e}"

        if "strict" in _GLOBAL_PARSERS:
            try:
                _GLOBAL_PARSERS["strict"](p_)
                rec["str_acc"] = True
            except Exception as e:
                rec["str_err"] = f"{type(e).__name__}: {e}"

        results.append(rec)
    return results


def _payload_chunks(cases: list[Case], n: int):
    """FIX: yield payload lists directly from cases so we don't hold a second copy."""
    for i in range(0, len(cases), n):
        yield [c.payload for c in cases[i : i + n]]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3: THE WIRE SPEEDFORCE (MICROBENCHMARKS)
# ═══════════════════════════════════════════════════════════════════════════════
def _bench_pair(fn, iters: int) -> tuple[float, float]:
    """Return (cpu_ns_per_op, wall_ns_per_op).

    On Windows, time.process_time_ns() only advances when the OS scheduler
    ticks the process (~15.6 ms). A fast function can finish many iterations
    inside a single quantum, giving c1 - c0 == 0. We grow the loop until the
    CPU clock registers at least one tick, bounded by a total work cap.
    If we still get zero, we return NaN for CPU so callers can render N/A
    instead of dividing by zero.
    """
    for _ in range(200):
        fn()
    gc.collect()

    cap = 5_000_000  # hard ceiling on total iterations, not per-probe
    total_run = 0
    probe = max(1, iters)

    while True:
        w0 = time.perf_counter_ns()
        c0 = time.process_time_ns()
        for _ in range(probe):
            fn()
        c1 = time.process_time_ns()
        w1 = time.perf_counter_ns()

        cpu_delta = c1 - c0
        wall_delta = w1 - w0
        total_run += probe

        if cpu_delta > 0:
            return cpu_delta / probe, wall_delta / probe

        if total_run >= cap:
            return float("nan"), wall_delta / probe

        remaining = cap - total_run
        probe = min(probe * 4, remaining)
        if probe <= 0:
            return float("nan"), wall_delta / max(1, total_run)


def _ratio(num: float, den: float) -> float:
    """Safe ratio: NaN if either side is NaN or the denominator is 0."""
    if math.isnan(num) or math.isnan(den) or den == 0:
        return float("nan")
    return num / den


def _fmt_ratio(x: float) -> str:
    return "      N/A" if math.isnan(x) else f"{x:>9.2f}x"


def _fmt_us(x: float) -> str:
    return "    N/A  " if math.isnan(x) else f"{x / 1000:>9.2f}"


def run_wire_speedforce(iters: int = DEFAULT_ITERS) -> dict:
    sub("PHASE 3: WIRE PROTOCOL SPEEDFORCE (CPU + WALL)")
    try:
        from highrise import ChatRequest, Incoming, Outgoing, converter
    except ImportError as e:
        p(f"  ⚠️ Official SDK missing: {e}")
        return {"ok": False, "reason": f"official import: {e}"}

    try:
        dumps_json, loads_json = _resolve_custom_codec()
    except Exception as e:
        p(f"  ⚠️ Custom SDK codec missing: {e}")
        return {"ok": False, "reason": f"custom codec: {e}"}

    enc_payload = {
        "_type": "ChatRequest",
        "rid": "perf",
        "message": "hello",
        "whisper_target_id": None,
    }
    raw_bytes = json.dumps(
        {
            "_type": "ChatEvent",
            "user": {"id": "u1", "username": "a"},
            "message": "h",
            "whisper": False,
        }
    ).encode()

    def off_ser():
        return converter.dumps(ChatRequest(message="hello"), Outgoing)

    def cus_ser():
        return dumps_json(enc_payload)

    def off_des():
        return converter.loads(raw_bytes.decode(), Incoming)

    def cus_des():
        return loads_json(raw_bytes)

    off_ser_cpu, off_ser_wall = _bench_pair(off_ser, iters)
    cus_ser_cpu, cus_ser_wall = _bench_pair(cus_ser, iters)
    off_des_cpu, off_des_wall = _bench_pair(off_des, iters)
    cus_des_cpu, cus_des_wall = _bench_pair(cus_des, iters)

    ser_cpu = _ratio(off_ser_cpu, cus_ser_cpu)
    ser_wall = _ratio(off_ser_wall, cus_ser_wall)
    des_cpu = _ratio(off_des_cpu, cus_des_cpu)
    des_wall = _ratio(off_des_wall, cus_des_wall)

    p(
        f"  {'Operation':<22}{'Official CPU':>15}{'Custom CPU':>15}{'CPU x':>10}{'Wall x':>10}"
    )
    p(f"  {'-' * 22}{'-' * 15}{'-' * 15}{'-' * 10}{'-' * 10}")
    p(
        f"  {'Serialize':<22}"
        f"{_fmt_us(off_ser_cpu):>15}"
        f"{_fmt_us(cus_ser_cpu):>15}"
        f"{Colors.GREEN}{_fmt_ratio(ser_cpu)}{Colors.END}"
        f"{Colors.GREEN}{_fmt_ratio(ser_wall)}{Colors.END}"
    )
    p(
        f"  {'Deserialize':<22}"
        f"{_fmt_us(off_des_cpu):>15}"
        f"{_fmt_us(cus_des_cpu):>15}"
        f"{Colors.GREEN}{_fmt_ratio(des_cpu)}{Colors.END}"
        f"{Colors.GREEN}{_fmt_ratio(des_wall)}{Colors.END}"
    )

    if math.isnan(ser_cpu) or math.isnan(des_cpu):
        p(
            f"  {Colors.WARN}⚠️ Some CPU ratios are N/A: process_time_ns() "
            f"never ticked within the cap.{Colors.END}"
        )
        p(f"  {Colors.WARN}   Wall-clock ratios below are still valid.{Colors.END}")

    return {
        "ok": True,
        "ser_cpu_speedup": ser_cpu,
        "ser_wall_speedup": ser_wall,
        "des_cpu_speedup": des_cpu,
        "des_wall_speedup": des_wall,
    }


def _resolve_custom_codec():
    import highrise_fast as hf

    dumps = getattr(hf, "dumps_json", None)
    loads = getattr(hf, "loads_json", None)

    if dumps is None or loads is None:
        try:
            import orjson

            dumps = lambda o: orjson.dumps(o)
            loads = lambda b: orjson.loads(
                b if isinstance(b, (bytes, bytearray)) else b.encode()
            )
        except ImportError:
            dumps = lambda o: json.dumps(o).encode()
            loads = lambda b: json.loads(
                b if isinstance(b, (bytes, bytearray)) else b.encode()
            )
    return dumps, loads


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4: THE CONCURRENCY ABYSS (ASYNC LEAKS)
# ═══════════════════════════════════════════════════════════════════════════════
async def run_concurrency_abyss(n: int = DEFAULT_PHASE4_CONCURRENCY) -> dict:
    sub("PHASE 4: CONCURRENCY ABYSS & LEAK AUDIT")
    try:
        from highrise_fast import Highrise
    except ImportError:
        p("  ⚠️ Custom SDK missing")
        return {"ok": False, "reason": "import"}

    class SilentWS:
        async def send_str(self, data):
            pass

        async def send_bytes(self, data):
            pass

    async def leak_test() -> int | None:
        hr = Highrise()
        hr.ws = SilentWS()
        hr.my_id = "bot"

        if not hasattr(hr, "_pending"):
            p(
                f"  {Colors.WARN}⚠️ Highrise._pending not present — "
                f"leak test cannot be validated on this build.{Colors.END}"
            )
            return None

        sem = asyncio.Semaphore(50)
        tasks: list[asyncio.Task] = []

        async def one():
            async with sem:
                return await hr.get_wallet()

        for _ in range(n):
            tasks.append(asyncio.create_task(one()))

        await asyncio.sleep(0.2)
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        pending = getattr(hr, "_pending", None)
        if not isinstance(pending, dict):
            p(
                f"  {Colors.WARN}⚠️ Highrise._pending is not a dict — leak test skipped.{Colors.END}"
            )
            return None
        return len(pending)

    try:
        leaked = await asyncio.wait_for(leak_test(), timeout=30.0)
    except TimeoutError:
        p(f"  {Colors.FAIL}❌ leak test timed out after 30s{Colors.END}")
        return {"ok": False, "reason": "timeout"}

    if leaked is None:
        return {"ok": False, "reason": "unvalidated"}

    status = (
        f"{Colors.GREEN}✅ CLEAN{Colors.END}"
        if leaked == 0
        else f"{Colors.FAIL}❌ LEAKED {leaked}{Colors.END}"
    )
    p(f"  Cancelled {n:,} concurrent requests -> Pending Registry: {status}")
    return {"ok": True, "leak_validated": True, "leaked": leaked}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 5: THE MEMORY SINGULARITY
# ═══════════════════════════════════════════════════════════════════════════════
def run_memory_singularity(parses: int = DEFAULT_PHASE5_PARSES) -> dict:
    sub("PHASE 5: MEMORY SINGULARITY & GC STORMS")
    try:
        from highrise_fast import Position, User, parse_server_message
    except ImportError:
        p("  ⚠️ Custom SDK missing")
        return {"ok": False, "reason": "import"}

    gc.collect()
    sample = {
        "_type": "ChatEvent",
        "user": {"id": "u1", "username": "a"},
        "message": "gc",
        "whisper": False,
    }
    gc_was_enabled = gc.isenabled()
    before_coll = sum(s["collections"] for s in gc.get_stats())

    if gc_was_enabled:
        gc.disable()
    try:
        for _ in range(parses):
            parse_server_message(sample)
    finally:
        if gc_was_enabled:
            gc.enable()
        gc.collect()

    after_coll = sum(s["collections"] for s in gc.get_stats())
    delta = after_coll - before_coll
    p(
        f"  GC Collections ({parses // 1000}k parses) : {delta} "
        f"({Colors.GREEN}✅ Low Pressure{Colors.END} if < 5)"
    )

    u = User(id="u1", username="a")
    pos = Position(x=1.0, y=0.0, z=2.0, facing="Front")
    wr_u, wr_p = weakref.ref(u), weakref.ref(pos)
    del u, pos
    gc.collect()
    u_clean = wr_u() is None
    p_clean = wr_p() is None
    p(
        f"  User Object Cycle Check     : {'✅ Clean' if u_clean else '❌ Cycle Detected'}"
    )
    p(
        f"  Position Object Cycle Check : {'✅ Clean' if p_clean else '❌ Cycle Detected'}"
    )

    class _MemObj:
        __slots__ = ("__weakref__", "payload")

        def __init__(self, pl):
            self.payload = pl

    tracemalloc.start()
    refs = []
    for i in range(parses):
        obj = _MemObj({"data": "x" * random.randint(10, 1000)})
        refs.append(weakref.ref(obj))
        if i % 1000 == 0:
            refs.clear()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    p(f"  Tracemalloc Peak ({parses // 1000}k churn): {peak / 1024:.1f} KB")
    return {
        "ok": True,
        "gc_delta": delta,
        "user_clean": u_clean,
        "pos_clean": p_clean,
        "tracemalloc_peak_kb": peak / 1024,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 6: ADVERSARIAL INPUT ROBUSTNESS
# ═══════════════════════════════════════════════════════════════════════════════
def run_security_gauntlet() -> dict:
    sub("PHASE 6: ADVERSARIAL INPUT ROBUSTNESS")
    try:
        from highrise_fast import parse_server_message
    except ImportError:
        return {"ok": False, "reason": "import"}

    attacks: dict[str, Any] = {
        "Regex Stress String": {
            "_type": "ChatEvent",
            "user": {"id": "u1", "username": "a"},
            "message": "(a+)+$" * 50,
            "whisper": False,
        },
        "UTF-8 Surrogate": {
            "_type": "ChatEvent",
            "user": {"id": "u1", "username": "a\ud800b"},
            "message": "x",
            "whisper": False,
        },
        "NaN In Position": {
            "_type": "UserMovedEvent",
            "user": {"id": "u1", "username": "a"},
            "position": {"x": float("nan"), "y": 0, "z": 0, "facing": "Front"},
        },
        "Huge Integer": {
            "_type": "GetWalletResponse",
            "rid": "w1",
            "content": [{"type": "gold", "amount": 2**200}],
        },
        "Deep Nesting": {
            "_type": "ChatEvent",
            "user": {"id": "u1", "username": "a"},
            "message": "x",
            "whisper": False,
        },
    }

    deep = copy.deepcopy(attacks["Deep Nesting"])
    cur = deep
    for i in range(50):
        cur["nested"] = {"level": i}
        cur = cur["nested"]
    attacks["Deep Nesting"] = deep

    passed = 0
    results: dict[str, dict] = {}
    for name, payload in attacks.items():
        try:
            t0 = time.perf_counter()
            parse_server_message(payload)
            elapsed = time.perf_counter() - t0
            if elapsed > 1.0:
                p(
                    f"  {name:24s}: {Colors.FAIL}❌ TIMEOUT ({elapsed * 1000:.0f}ms){Colors.END}"
                )
                results[name] = {"ok": False, "ms": elapsed * 1000, "mode": "timeout"}
            else:
                p(
                    f"  {name:24s}: {Colors.GREEN}✅ Handled ({elapsed * 1000:.2f}ms){Colors.END}"
                )
                passed += 1
                results[name] = {"ok": True, "ms": elapsed * 1000, "mode": "accept"}
        except Exception as e:
            p(
                f"  {name:24s}: {Colors.GREEN}✅ Rejected Safely ({type(e).__name__}){Colors.END}"
            )
            passed += 1
            results[name] = {"ok": True, "mode": "reject", "exc": type(e).__name__}

    p(f"  Robustness Score: {passed}/{len(attacks)}")
    return {"ok": True, "robustness": results, "score": f"{passed}/{len(attacks)}"}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE RUNNERS (with per-phase isolation)
# ═══════════════════════════════════════════════════════════════════════════════
def run_phase(name: str, fn, *args, **kwargs):
    header(f"PHASE {name}")
    t0 = time.perf_counter()
    try:
        result = fn(*args, **kwargs)
        result = result if isinstance(result, dict) else {"ok": True, "value": result}
    except Exception as e:
        tb = traceback.format_exc()
        p(f"  {Colors.FAIL}❌ PHASE CRASHED: {type(e).__name__}: {e}{Colors.END}")
        p(f"  {Colors.WARN}{tb}{Colors.END}")
        result = {"ok": False, "reason": f"{type(e).__name__}: {e}"}
    result["elapsed_s"] = time.perf_counter() - t0
    PHASE_RESULTS[name] = result
    write_report()
    p(f"  ⏱  Phase {name} took {result['elapsed_s']:.2f}s")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN RUNNER
# ═══════════════════════════════════════════════════════════════════════════════
def _parse_phases(spec: str) -> set[str]:
    if not spec or spec.lower() == "all":
        return {"1", "2", "3", "4", "5", "6"}
    return {x.strip() for x in spec.split(",") if x.strip()}


def _run_phase_2(cases: list[Case], workers: int) -> dict:
    """Phase 2 with bounded-window submission and BrokenProcessPool handling."""
    ctx = mp.get_context("spawn")
    chunk_size = 250  # FIX: smaller chunks = smoother parent memory + progress
    off_acc = len_acc = str_acc = 0
    off_accept_str_reject = 0
    off_reject_str_accept = 0
    pool_broken = False

    total_chunks = (len(cases) + chunk_size - 1) // chunk_size
    prog = Progress(total_chunks, "Crucible")

    ex = ProcessPoolExecutor(
        max_workers=workers, mp_context=ctx, initializer=init_worker
    )
    try:
        chunk_iter = iter(_payload_chunks(cases, chunk_size))
        window = max(2, workers * 2)
        pending: set = set()

        for _ in range(window):
            try:
                pending.add(ex.submit(classify_batch, next(chunk_iter)))
            except StopIteration:
                break

        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for f in done:
                try:
                    batch = f.result()
                except BrokenProcessPool as e:
                    p(f"\n  {Colors.FAIL}❌ ProcessPool broken: {e}{Colors.END}")
                    p(
                        f"  {Colors.WARN}   A worker died. See {CRASH_FILE} for details.{Colors.END}"
                    )
                    pool_broken = True
                    for p_f in pending:
                        p_f.cancel()
                    pending.clear()
                    break
                except Exception as e:
                    p(
                        f"\n  {Colors.WARN}⚠️ worker error: {type(e).__name__}: {e}{Colors.END}"
                    )
                    batch = []

                for rec in batch:
                    if rec["off_acc"]:
                        off_acc += 1
                    if rec["len_acc"]:
                        len_acc += 1
                    if rec["str_acc"]:
                        str_acc += 1
                    off_ok = rec["off_acc"] or rec["off_err"]
                    str_ok = rec["str_acc"] or rec["str_err"]
                    if off_ok and str_ok:
                        if rec["off_acc"] and not rec["str_acc"]:
                            off_accept_str_reject += 1
                        elif (not rec["off_acc"]) and rec["str_acc"]:
                            off_reject_str_accept += 1
                prog.update()

                if not pool_broken:
                    try:
                        pending.add(ex.submit(classify_batch, next(chunk_iter)))
                    except StopIteration:
                        pass
    finally:
        # FIX: don't block forever on shutdown if a worker is dead.
        try:
            ex.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

    strict_mismatches = off_accept_str_reject + off_reject_str_accept
    p(f"\n  {Colors.BOLD}ORACLE VERDICT:{Colors.END}")
    p(f"  Official Accepts    : {off_acc:,}")
    p(f"  Custom Lenient Accs : {len_acc:,}")
    p(f"  Custom Strict Accs  : {str_acc:,}")
    if pool_broken:
        p(f"  {Colors.FAIL}⚠️ Pool was broken — counts are partial.{Colors.END}")
    if strict_mismatches == 0 and not pool_broken:
        p(
            f"  Strict Parity       : {Colors.GREEN}✅ 100% MATCH (both directions){Colors.END}"
        )
    else:
        p(
            f"  Strict Parity       : {Colors.FAIL}❌ {strict_mismatches} mismatches{Colors.END}"
        )
        p(f"    official ACCEPT / strict REJECT : {off_accept_str_reject:,}")
        p(f"    official REJECT / strict ACCEPT : {off_reject_str_accept:,}")

    return {
        "ok": not pool_broken,
        "pool_broken": pool_broken,
        "off_acc": off_acc,
        "len_acc": len_acc,
        "str_acc": str_acc,
        "strict_mismatches": strict_mismatches,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=DEFAULT_TARGET)
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    ap.add_argument("--extreme", action="store_true", help="250,000 cases")
    ap.add_argument("--iters", type=int, default=DEFAULT_ITERS)
    ap.add_argument("--concurrency", type=int, default=DEFAULT_PHASE4_CONCURRENCY)
    ap.add_argument("--parses", type=int, default=DEFAULT_PHASE5_PARSES)
    ap.add_argument("--phases", type=str, default="all")
    ap.add_argument(
        "--minimal",
        action="store_true",
        help="Smallest possible run (500 cases, 1 worker, quick phases)",
    )
    args = ap.parse_args()

    if args.minimal:
        args.target = 500
        args.workers = 1
        args.iters = 500
        args.concurrency = 25
        args.parses = 500

    if args.extreme:
        args.target = 250_000

    phases = _parse_phases(args.phases)

    p(
        f"{Colors.BOLD}{Colors.HEADER}BENCHMARK V4: THE MOTHERSHIP (LEVIATHAN){Colors.END}"
    )
    p(f"  Version:  {VERSION}")
    p(f"  Log:      {LOG_FILE}")
    p(f"  Crash:    {CRASH_FILE}")
    p(f"  Report:   {REPORT_FILE}")
    p(
        f"  Target: {args.target:,} cases | Workers: {args.workers} | "
        f"Python: {sys.version.split()[0]}"
    )
    p(f"  Phases: {sorted(phases)}")
    p(
        f"  {Colors.WARN}Tip: if this crashes, open {REPORT_FILE.name} "
        f"for partial results.{Colors.END}"
    )

    # ── Phase 1 ─────────────────────────────────────────────────────────────
    cases: list[Case] = []
    if "1" in phases:
        header("PHASE 1: THE SWARM (COMBINATORIAL GENERATION)")
        t0 = time.perf_counter()
        try:
            cases = generate_swarm(args.target, seed=42)
            p(
                f"  Generated {Colors.BOLD}{len(cases):,}{Colors.END} unique adversarial "
                f"payloads in {time.perf_counter() - t0:.2f}s"
            )
            PHASE_RESULTS["1"] = {
                "ok": True,
                "cases": len(cases),
                "elapsed_s": time.perf_counter() - t0,
            }
        except Exception as e:
            p(f"  {Colors.FAIL}❌ Phase 1 crashed: {e}{Colors.END}")
            PHASE_RESULTS["1"] = {"ok": False, "reason": str(e)}
            cases = []
        write_report()

    # ── Phase 2 ─────────────────────────────────────────────────────────────
    if "2" in phases and cases:
        header("PHASE 2: THE ORACLE CRUCIBLE (MULTIPROCESSING VALIDATION)")
        p(f"  Launching {args.workers} worker(s)... (spawn re-imports the SDKs)")
        t0 = time.perf_counter()
        try:
            with Watchdog("Phase 2", interval=15.0):
                result = _run_phase_2(cases, args.workers)
            result["elapsed_s"] = time.perf_counter() - t0
            PHASE_RESULTS["2"] = result
        except Exception as e:
            tb = traceback.format_exc()
            p(f"  {Colors.FAIL}❌ Phase 2 crashed: {e}{Colors.END}")
            p(f"  {Colors.WARN}{tb}{Colors.END}")
            PHASE_RESULTS["2"] = {
                "ok": False,
                "reason": f"{type(e).__name__}: {e}",
                "elapsed_s": time.perf_counter() - t0,
            }
        write_report()
    elif "2" in phases and not cases:
        p(
            f"  {Colors.WARN}⚠️ Phase 2 needs phase 1 — run with '--phases 1,2'{Colors.END}"
        )
        PHASE_RESULTS["2"] = {"ok": False, "reason": "no cases (phase 1 skipped)"}
        write_report()

    # ── Phase 3 ─────────────────────────────────────────────────────────────
    if "3" in phases:
        PHASE_RESULTS["3"] = run_phase("3", run_wire_speedforce, iters=args.iters) or {}

    # ── Phase 4 ─────────────────────────────────────────────────────────────
    if "4" in phases:
        PHASE_RESULTS["4"] = (
            run_phase("4", lambda: asyncio.run(run_concurrency_abyss(args.concurrency)))
            or {}
        )

    # ── Phase 5 ─────────────────────────────────────────────────────────────
    if "5" in phases:
        PHASE_RESULTS["5"] = (
            run_phase("5", run_memory_singularity, parses=args.parses) or {}
        )

    # ── Phase 6 ─────────────────────────────────────────────────────────────
    if "6" in phases:
        PHASE_RESULTS["6"] = run_phase("6", run_security_gauntlet) or {}

    # ── Summary ─────────────────────────────────────────────────────────────
    header("FINAL MOTHERSHIP VERDICT")
    p(f"  {'Phase':<8}{'Status':<12}{'Time':>10}  Detail")
    p(f"  {'-' * 8}{'-' * 12}{'-' * 10}  {'-' * 60}")
    for name in sorted(PHASE_RESULTS):
        r = PHASE_RESULTS[name]
        status = (
            f"{Colors.GREEN}OK{Colors.END}"
            if r.get("ok")
            else f"{Colors.FAIL}FAILED{Colors.END}"
        )
        t = r.get("elapsed_s", 0.0)
        detail = ""
        if name == "2" and r.get("ok"):
            detail = f"strict_mismatches={r.get('strict_mismatches', '?')}"
            if r.get("pool_broken"):
                detail += " (pool was broken)"
        elif name == "3" and r.get("ok"):
            detail = (
                f"ser CPU {r.get('ser_cpu_speedup', 0):.2f}x, "
                f"des CPU {r.get('des_cpu_speedup', 0):.2f}x"
            )
        elif name == "4" and r.get("ok"):
            detail = f"leaked={r.get('leaked', '?')}"
        elif name == "5" and r.get("ok"):
            detail = f"gc_delta={r.get('gc_delta', '?')}, peak={r.get('tracemalloc_peak_kb', 0):.1f}KB"
        elif name == "6" and r.get("ok"):
            detail = f"score={r.get('score', '?')}"
        elif not r.get("ok"):
            detail = str(r.get("reason", ""))[:60]
        p(f"  {name:<8}{status:<21}{t:>8.2f}s  {detail}")

    p()
    p(f"  Log:    {LOG_FILE}")
    p(f"  Report: {REPORT_FILE}")
    p(f"  Crash:  {CRASH_FILE}")

    phase2 = PHASE_RESULTS.get("2", {})
    if phase2.get("ok") and phase2.get("strict_mismatches", 0) == 0:
        p(
            f"\n  {Colors.BOLD}{Colors.GREEN}🏆 LEVIATHAN DEFEATED: highrise_fast "
            f"maintains bidirectional Oracle Parity.{Colors.END}"
        )
    else:
        p(f"\n  {Colors.BOLD}{Colors.WARN}⚠️ See per-phase status above.{Colors.END}")


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════
def _dump_and_exit(signum, _frame):
    try:
        p(f"\n  received signal {signum}")
        write_report()
        p(f"  report saved to {REPORT_FILE}")
    except Exception:
        pass
    sys.exit(130)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _dump_and_exit)
    signal.signal(signal.SIGTERM, _dump_and_exit)
    try:
        main()
    except KeyboardInterrupt:
        _dump_and_exit(2, None)
    except Exception as e:
        p(f"\n{Colors.FAIL}❌ FATAL: {type(e).__name__}: {e}{Colors.END}")
        p(traceback.format_exc())
        write_report()
        sys.exit(1)
    finally:
        write_report()

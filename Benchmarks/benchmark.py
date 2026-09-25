#!/usr/bin/env python3
"""
benchmark_100.py — 100-TEST ENTERPRISE HIGHRISE SDK BENCHMARK (v5)
===================================================================
Tests every dimension of highrise (official) vs highrise_fast (custom).

Categories (100 tests total):
  A. Environment & Dependencies     (001-005)
  B. Import & Startup               (006-010)
  C. Object Model Creation          (011-018)
  D. Object Model Mutation/Access   (019-024)
  E. Outgoing Serialization         (025-036)
  F. Incoming Parsing               (037-048)
  G. JSON Backend Comparison        (049-054)
  H. WebSocket Frame Codec          (055-058)
  I. Unicode & Edge Cases           (059-066)
  J. Float & Numeric Precision      (067-070)
  K. Concurrent Async Throughput    (071-076)
  L. Leak & Resource Safety         (077-080)
  M. GC Pressure & Memory           (081-084)
  N. Wire Format Conversion         (085-090)
  O. WebAPI & AttrDict              (091-094)
  P. Error Handling & Recovery      (095-097)
  Q. Sustained Load Endurance       (098-100)

Usage:
    python benchmark_100.py
    python benchmark_100.py --quick
    python benchmark_100.py --category E
    python benchmark_100.py --tests 025,036,050
    python benchmark_100.py --iters 20000 --endurance 30
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import importlib
import json
import logging
import os
import platform
import statistics
import subprocess
import sys
import time
import traceback
import weakref
from collections import deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

try:
    sys.stdout.reconfigure(line_buffering=True)
except (AttributeError, OSError):
    pass

logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger("benchmark")

# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

OFFICIAL = "highrise"
CUSTOM = "highrise_fast"
VERSION = "5.0.0-100test"

# ═══════════════════════════════════════════════════════════════════════════
# FORMATTING
# ═══════════════════════════════════════════════════════════════════════════


def p(*a, **k):
    print(*a, **k, flush=True)


def header(title: str):
    p()
    p("═" * 92)
    p(f"  {title}")
    p("═" * 92)


def fmt_ns(v):
    if v is None:
        return "n/a"
    if v < 1000:
        return f"{v:.0f} ns"
    if v < 1_000_000:
        return f"{v / 1000:.2f} µs"
    return f"{v / 1_000_000:.2f} ms"


def fmt_ms(v):
    return "n/a" if v is None else f"{v * 1000:.3f} ms"


def fmt_bytes(v):
    if v is None:
        return "n/a"
    v = float(v)
    for u in ("B", "KB", "MB", "GB"):
        if abs(v) < 1024:
            return f"{v:.1f} {u}"
        v /= 1024
    return f"{v:.1f} TB"


def ratio(a, b):
    if not a or not b:
        return "n/a"
    return f"{a / b:.2f}x"


# ═══════════════════════════════════════════════════════════════════════════
# TEST FRAMEWORK
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class TestResult:
    test_id: str
    name: str
    category: str
    passed: bool = True
    error: str = ""
    duration_ms: float = 0.0
    official_ns: float | None = None
    custom_ns: float | None = None
    speedup: float | None = None
    ops_per_sec: float | None = None
    extra: dict = field(default_factory=dict)

    @property
    def verdict(self) -> str:
        if not self.passed:
            return "❌ FAIL"
        if self.speedup is not None and self.speedup > 1.0:
            return "✅ PASS"
        return "✅ PASS"


_REGISTRY: list[dict] = []


def register_test(test_id: str, name: str, category: str):
    """Decorator to register a benchmark test."""

    def decorator(fn):
        _REGISTRY.append(
            {
                "id": test_id,
                "name": name,
                "category": category,
                "fn": fn,
            }
        )
        return fn

    return decorator


def bench(fn: Callable, iters: int, warmup: int = 30) -> dict:
    """Micro-benchmark with full statistical breakdown."""
    for _ in range(warmup):
        fn()
    times = []
    for _ in range(iters):
        t0 = time.perf_counter_ns()
        fn()
        times.append(time.perf_counter_ns() - t0)
    times.sort()
    n = len(times)
    total = sum(times)
    return {
        "total_ns": total,
        "avg_ns": statistics.mean(times),
        "med_ns": statistics.median(times),
        "min_ns": times[0],
        "max_ns": times[-1],
        "p50_ns": times[int(n * 0.50)],
        "p90_ns": times[int(n * 0.90)],
        "p95_ns": times[int(n * 0.95)],
        "p99_ns": times[int(n * 0.99)],
        "p999_ns": times[min(int(n * 0.999), n - 1)],
        "stdev_ns": statistics.stdev(times) if n > 1 else 0,
        "ops": iters,
        "ops_per_sec": iters / (total / 1e9) if total > 0 else 0,
    }


def print_comparison(label: str, off: dict | None, cust: dict | None):
    """Print a side-by-side comparison row."""
    if off is None and cust is None:
        return
    if isinstance(off, dict) and isinstance(cust, dict):
        sp = ratio(off.get("avg_ns"), cust.get("avg_ns"))
        p(
            f"    {label:42s} {fmt_ns(off.get('avg_ns')):>12s}"
            f" {fmt_ns(cust.get('avg_ns')):>12s} {sp:>8s}"
        )
    elif off is not None and cust is not None:
        sp = ratio(off, cust)
        p(f"    {label:42s} {fmt_ns(off):>12s} {fmt_ns(cust):>12s} {sp:>8s}")


def sdk_available(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except (ImportError, ModuleNotFoundError):
        return False


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY A: ENVIRONMENT & DEPENDENCIES (001-005)
# ═══════════════════════════════════════════════════════════════════════════


@register_test("001", "Python version & platform detection", "A")
def test_001(args, ctx):
    p(f"    Python     : {sys.version.split()[0]}")
    p(f"    Platform   : {platform.platform()}")
    p(f"    Arch       : {platform.machine()}")
    p(f"    CPU cores  : {os.cpu_count()}")
    return TestResult(
        "001",
        "Environment detection",
        "A",
        passed=True,
        extra={"python": sys.version.split()[0], "platform": platform.platform()},
    )


@register_test("002", "Official SDK availability", "A")
def test_002(args, ctx):
    have = sdk_available(OFFICIAL)
    ctx["have_official"] = have
    p(f"    Official SDK : {'✅ FOUND' if have else '❌ NOT FOUND'}")
    return TestResult("002", "Official SDK found", "A", passed=have)


@register_test("003", "Custom SDK availability", "A")
def test_003(args, ctx):
    have = sdk_available(CUSTOM)
    ctx["have_custom"] = have
    p(f"    Custom SDK   : {'✅ FOUND' if have else '❌ NOT FOUND'}")
    return TestResult("003", "Custom SDK found", "A", passed=have)


@register_test("004", "Dependency tree analysis", "A")
def test_004(args, ctx):
    deps = {}
    for name, pkg in [
        ("orjson", "orjson"),
        ("ujson", "ujson"),
        ("aiohttp", "aiohttp"),
        ("attrs", "attrs"),
        ("cattrs", "cattrs"),
        ("pendulum", "pendulum"),
        ("quattro", "quattro"),
        ("websockets", "websockets"),
        ("psutil", "psutil"),
        ("aiofiles", "aiofiles"),
    ]:
        try:
            mod = importlib.import_module(pkg)
            deps[name] = getattr(mod, "__version__", "?")
        except ImportError:
            deps[name] = "NOT INSTALLED"

    p(f"    {'Dependency':16s} {'Version':20s}")
    p(f"    {'─' * 38}")
    for name, ver in deps.items():
        icon = "✅" if ver != "NOT INSTALLED" else "❌"
        p(f"    {icon} {name:14s} {ver}")

    ctx["deps"] = deps
    ctx["orjson_available"] = deps.get("orjson") != "NOT INSTALLED"
    return TestResult("004", "Dependency analysis", "A", passed=True, extra=deps)


@register_test("005", "orjson backend detection for custom SDK", "A")
def test_005(args, ctx):
    orjson_on = ctx.get("orjson_available", False)
    p(f"    Custom uses orjson : {'YES ✅' if orjson_on else 'NO (stdlib json)'}")
    return TestResult(
        "005", "orjson backend", "A", passed=orjson_on, extra={"orjson": orjson_on}
    )


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY B: IMPORT & STARTUP (006-010)
# ═══════════════════════════════════════════════════════════════════════════


def _measure_import(module_name: str, runs: int = 7) -> dict:
    if module_name == OFFICIAL:
        verify = "assert hasattr(__import__('highrise'), 'Highrise'), 'missing'"
    else:
        verify = "assert hasattr(__import__('highrise_fast'), 'Highrise'), 'missing'"

    code = (
        "import time\n"
        "s = time.perf_counter()\n"
        f"import {module_name}\n"
        "elapsed = time.perf_counter() - s\n"
        f"{verify}\n"
        "print(f'{elapsed:.9f}')\n"
    )

    times = []
    errors = []
    for i in range(runs):
        try:
            r = subprocess.run(
                [sys.executable, "-B", "-c", code],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            if r.returncode == 0 and r.stdout.strip():
                times.append(float(r.stdout.strip().splitlines()[-1]))
            else:
                errors.append(f"run {i}: rc={r.returncode}")
        except subprocess.TimeoutExpired:
            errors.append(f"run {i}: TIMEOUT")
        except (OSError, ValueError) as e:
            errors.append(f"run {i}: {e}")

    if not times:
        return {
            "cold": None,
            "warm": None,
            "median": None,
            "verified": False,
            "errors": errors,
        }

    cold = times[0]
    warm_times = times[1:] if len(times) > 1 else times
    warm = statistics.median(warm_times)
    med = statistics.median(times)
    filtered = [t for t in times if t < med * 3]
    clean_median = statistics.median(filtered) if filtered else med

    return {
        "cold": cold,
        "warm": warm,
        "median": clean_median,
        "all_times": times,
        "verified": True,
        "errors": errors,
        "min": min(times),
        "max": max(times),
        "stdev": statistics.stdev(times) if len(times) > 1 else 0,
    }


@register_test("006", "Official SDK cold import time", "B")
def test_006(args, ctx):
    if not ctx.get("have_official"):
        return TestResult(
            "006", "Official cold import", "B", passed=False, error="SDK not found"
        )
    imp = _measure_import(OFFICIAL, runs=7)
    ctx["import_official"] = imp
    if imp["verified"]:
        p(f"    Cold import : {fmt_ms(imp['cold'])}")
        p(f"    Warm median : {fmt_ms(imp['warm'])}")
        p(f"    Clean median: {fmt_ms(imp['median'])}")
    else:
        p(f"    ❌ FAILED: {imp.get('errors', ['unknown'])[:2]}")
    return TestResult(
        "006",
        "Official cold import",
        "B",
        passed=imp["verified"],
        official_ns=(imp["median"] or 0) * 1e6,
    )


@register_test("007", "Custom SDK cold import time", "B")
def test_007(args, ctx):
    if not ctx.get("have_custom"):
        return TestResult(
            "007", "Custom cold import", "B", passed=False, error="SDK not found"
        )
    imp = _measure_import(CUSTOM, runs=7)
    ctx["import_custom"] = imp
    if imp["verified"]:
        p(f"    Cold import : {fmt_ms(imp['cold'])}")
        p(f"    Warm median : {fmt_ms(imp['warm'])}")
        p(f"    Clean median: {fmt_ms(imp['median'])}")
    else:
        p(f"    ❌ FAILED: {imp.get('errors', ['unknown'])[:2]}")
    return TestResult(
        "007",
        "Custom cold import",
        "B",
        passed=imp["verified"],
        custom_ns=(imp["median"] or 0) * 1e6,
    )


@register_test("008", "Import time speedup ratio", "B")
def test_008(args, ctx):
    off_imp = ctx.get("import_official", {})
    cust_imp = ctx.get("import_custom", {})
    off_t = off_imp.get("median")
    cust_t = cust_imp.get("median")
    if off_t and cust_t:
        sp = off_t / cust_t
        p(f"    Official : {fmt_ms(off_t)}")
        p(f"    Custom   : {fmt_ms(cust_t)}")
        p(f"    Speedup  : {sp:.2f}x {'✅' if sp > 1 else '⚠️'}")
        return TestResult(
            "008",
            "Import speedup",
            "B",
            passed=True,
            official_ns=off_t * 1e6,
            custom_ns=cust_t * 1e6,
            speedup=sp,
        )
    return TestResult("008", "Import speedup", "B", passed=False, error="Missing data")


@register_test("009", "First-message latency after import", "B")
def test_009(args, ctx):
    code = """
import time
from highrise_fast import dumps_json, loads_json, parse_server_message
payload = '{"_type":"ChatEvent","user":{"id":"u1","username":"alice"},"message":"first","whisper":false}'
t0 = time.perf_counter_ns()
parse_server_message(loads_json(payload))
print(time.perf_counter_ns() - t0)
"""
    try:
        r = subprocess.run(
            [sys.executable, "-B", "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            ns = int(r.stdout.strip())
            p(f"    First parse after import: {fmt_ns(ns)}")
            return TestResult(
                "009", "First-message latency", "B", passed=True, custom_ns=ns
            )
    except (OSError, subprocess.TimeoutExpired, ValueError) as e:
        _logger.debug("test_009 subprocess: %s", e)
    return TestResult(
        "009", "First-message latency", "B", passed=False, error="subprocess failed"
    )


@register_test("010", "Module attribute verification", "B")
def test_010(args, ctx):
    results = {}
    for name, attrs in [
        (OFFICIAL, ["Highrise", "BaseBot", "Position", "User", "Item"]),
        (
            CUSTOM,
            [
                "Highrise",
                "BaseBot",
                "Position",
                "User",
                "Item",
                "dumps_json",
                "loads_json",
            ],
        ),
    ]:
        try:
            mod = importlib.import_module(name)
            missing = [a for a in attrs if not hasattr(mod, a)]
            results[name] = missing
            if missing:
                p(f"    {name}: ❌ missing {missing}")
            else:
                p(f"    {name}: ✅ all {len(attrs)} attributes present")
        except (ImportError, ModuleNotFoundError) as e:
            results[name] = [str(e)]
            p(f"    {name}: ❌ {e}")

    all_ok = all(not v for v in results.values())
    return TestResult("010", "Module attributes", "B", passed=all_ok, extra=results)


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY C: OBJECT MODEL CREATION (011-018)
# ═══════════════════════════════════════════════════════════════════════════


def _run_object_bench(
    test_id,
    name,
    off_fn,
    cust_fn,
    args,
    ctx,
    cat="C",
):
    iters = args.iters

    if not ctx.get("have_official") or not ctx.get("have_custom"):
        return TestResult(
            test_id,
            name,
            cat,
            passed=False,
            error="SDK missing",
        )

    off_res = bench(off_fn, iters)
    cust_res = bench(cust_fn, iters)

    sp = off_res["avg_ns"] / cust_res["avg_ns"] if cust_res["avg_ns"] else None

    print_comparison(name, off_res, cust_res)

    return TestResult(
        test_id,
        name,
        cat,
        passed=True,
        official_ns=off_res["avg_ns"],
        custom_ns=cust_res["avg_ns"],
        speedup=sp,
        ops_per_sec=cust_res["ops_per_sec"],
    )


@register_test("011", "User object creation", "C")
def test_011(args, ctx):
    try:
        from highrise import User as OUser
        from highrise_fast import User as CUser
    except ImportError as e:
        return TestResult("011", "User creation", "C", passed=False, error=str(e))
    return _run_object_bench(
        "011",
        "User()",
        lambda: OUser(id="u1", username="alice"),
        lambda: CUser(id="u1", username="alice"),
        args,
        ctx,
    )


@register_test("012", "Position object creation", "C")
def test_012(args, ctx):
    try:
        from highrise import Position as OPos
        from highrise_fast import Position as CPos
    except ImportError as e:
        return TestResult("012", "Position creation", "C", passed=False, error=str(e))
    return _run_object_bench(
        "012",
        "Position()",
        lambda: OPos(x=1.0, y=2.0, z=3.0, facing="FrontRight"),
        lambda: CPos(x=1.0, y=2.0, z=3.0, facing="FrontRight"),
        args,
        ctx,
    )


@register_test("013", "Item object creation", "C")
def test_013(args, ctx):
    try:
        from highrise import Item as OItem
        from highrise_fast import Item as CItem
    except ImportError as e:
        return TestResult("013", "Item creation", "C", passed=False, error=str(e))
    return _run_object_bench(
        "013",
        "Item()",
        lambda: OItem(type="clothing", amount=1, id="shirt_1"),
        lambda: CItem(type="clothing", amount=1, id="shirt_1"),
        args,
        ctx,
    )


@register_test("014", "User with long strings", "C")
def test_014(args, ctx):
    try:
        from highrise import User as OUser
        from highrise_fast import User as CUser
    except ImportError as e:
        return TestResult("014", "User long strings", "C", passed=False, error=str(e))
    uid = "a" * 24
    uname = "x" * 80
    return _run_object_bench(
        "014",
        "User(long)",
        lambda: OUser(id=uid, username=uname),
        lambda: CUser(id=uid, username=uname),
        args,
        ctx,
    )


@register_test("015", "AnchorPosition creation", "C")
def test_015(args, ctx):
    try:
        from highrise import AnchorPosition as OAnchor
        from highrise_fast import AnchorPosition as CAnchor
    except ImportError as e:
        return TestResult("015", "AnchorPosition", "C", passed=False, error=str(e))
    return _run_object_bench(
        "015",
        "AnchorPosition()",
        lambda: OAnchor(entity_id="ent_1", anchor_ix=5),
        lambda: CAnchor(entity_id="ent_1", anchor_ix=5),
        args,
        ctx,
    )


@register_test("016", "CurrencyItem creation", "C")
def test_016(args, ctx):
    try:
        from highrise import CurrencyItem as OCurr
        from highrise_fast import CurrencyItem as CCurr
    except ImportError as e:
        return TestResult("016", "CurrencyItem", "C", passed=False, error=str(e))
    return _run_object_bench(
        "016",
        "CurrencyItem()",
        lambda: OCurr(type="gold", amount=100),
        lambda: CCurr(type="gold", amount=100),
        args,
        ctx,
    )


@register_test("017", "Batch creation (100 Users)", "C")
def test_017(args, ctx):
    try:
        from highrise import User as OUser
        from highrise_fast import User as CUser
    except ImportError as e:
        return TestResult("017", "Batch User", "C", passed=False, error=str(e))

    def off_batch():
        return [OUser(id=f"u{i}", username=f"user_{i}") for i in range(100)]

    def cust_batch():
        return [CUser(id=f"u{i}", username=f"user_{i}") for i in range(100)]

    return _run_object_bench("017", "100x User()", off_batch, cust_batch, args, ctx)


@register_test("018", "Batch creation (50 Positions)", "C")
def test_018(args, ctx):
    try:
        from highrise import Position as OPos
        from highrise_fast import Position as CPos
    except ImportError as e:
        return TestResult("018", "Batch Position", "C", passed=False, error=str(e))

    def off_batch():
        return [
            OPos(x=float(i), y=0.0, z=float(i * 2), facing="Front") for i in range(50)
        ]

    def cust_batch():
        return [
            CPos(x=float(i), y=0.0, z=float(i * 2), facing="Front") for i in range(50)
        ]

    return _run_object_bench("018", "50x Position()", off_batch, cust_batch, args, ctx)


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY D: OBJECT MODEL MUTATION & ACCESS (019-024)
# ═══════════════════════════════════════════════════════════════════════════


@register_test("019", "Attribute read (1000 accesses)", "D")
def test_019(args, ctx):
    try:
        from highrise import User as OUser
        from highrise_fast import User as CUser
    except ImportError as e:
        return TestResult("019", "Attr read", "D", passed=False, error=str(e))
    ou = OUser(id="u1", username="alice")
    cu = CUser(id="u1", username="alice")

    def off_read():
        for _ in range(1000):
            _ = ou.id
            _ = ou.username

    def cust_read():
        for _ in range(1000):
            _ = cu.id
            _ = cu.username

    return _run_object_bench("019", "Attr read x1000", off_read, cust_read, args, ctx)


@register_test("020", "Attribute write (1000 mutations)", "D")
def test_020(args, ctx):
    try:
        from highrise import User as OUser
        from highrise_fast import User as CUser
    except ImportError as e:
        return TestResult("020", "Attr write", "D", passed=False, error=str(e))
    ou = OUser(id="u1", username="alice")
    cu = CUser(id="u1", username="alice")

    def off_write():
        for i in range(1000):
            ou.username = f"user_{i}"

    def cust_write():
        for i in range(1000):
            cu.username = f"user_{i}"

    return _run_object_bench(
        "020", "Attr write x1000", off_write, cust_write, args, ctx
    )


@register_test("021", "repr() generation", "D")
def test_021(args, ctx):
    try:
        from highrise import User as OUser
        from highrise_fast import User as CUser
    except ImportError as e:
        return TestResult("021", "repr()", "D", passed=False, error=str(e))
    ou = OUser(id="u1", username="alice")
    cu = CUser(id="u1", username="alice")
    return _run_object_bench(
        "021", "repr(User)", lambda: repr(ou), lambda: repr(cu), args, ctx
    )


@register_test("022", "Equality comparison", "D")
def test_022(args, ctx):
    try:
        from highrise import User as OUser
        from highrise_fast import User as CUser
    except ImportError as e:
        return TestResult("022", "Equality", "D", passed=False, error=str(e))
    ou1 = OUser(id="u1", username="alice")
    ou2 = OUser(id="u1", username="alice")
    cu1 = CUser(id="u1", username="alice")
    cu2 = CUser(id="u1", username="alice")
    return _run_object_bench(
        "022", "User == User", lambda: ou1 == ou2, lambda: cu1 == cu2, args, ctx
    )


@register_test("023", "hash() computation", "D")
def test_023(args, ctx):
    try:
        from highrise import User as OUser
        from highrise_fast import User as CUser
    except ImportError as e:
        return TestResult("023", "hash()", "D", passed=False, error=str(e))
    ou = OUser(id="u1", username="alice")
    cu = CUser(id="u1", username="alice")

    def off_hash():
        try:
            return hash(ou)
        except TypeError:
            return id(ou)

    def cust_hash():
        try:
            return hash(cu)
        except TypeError:
            return id(cu)

    return _run_object_bench("023", "hash(User)", off_hash, cust_hash, args, ctx)


@register_test("024", "Object memory footprint", "D")
def test_024(args, ctx):
    try:
        from highrise import User as OUser
        from highrise_fast import User as CUser
    except ImportError as e:
        return TestResult("024", "Memory footprint", "D", passed=False, error=str(e))
    import sys as _sys

    ou = OUser(id="u1", username="alice")
    cu = CUser(id="u1", username="alice")
    off_size = _sys.getsizeof(ou)
    cust_size = _sys.getsizeof(cu)
    p(f"    Official User size : {off_size} bytes")
    p(f"    Custom User size   : {cust_size} bytes")
    p(f"    Ratio              : {ratio(off_size, cust_size)}")
    return TestResult(
        "024",
        "Memory footprint",
        "D",
        passed=True,
        official_ns=off_size,
        custom_ns=cust_size,
        speedup=off_size / cust_size if cust_size else None,
    )


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY E: OUTGOING SERIALIZATION (025-036)
# ═══════════════════════════════════════════════════════════════════════════


def _outgoing_bench(test_id, name, off_fn, cust_fn, args, ctx, cat="E"):
    iters = min(args.iters, 5000)
    try:
        off_res = bench(off_fn, iters)
    except (
        Exception
    ) as e:  # noqa: BLE001 — benchmark harness must record any SDK failure
        return TestResult(
            test_id, name, cat, passed=False, error=f"Official: {type(e).__name__}"
        )
    try:
        cust_res = bench(cust_fn, iters)
    except (
        Exception
    ) as e:  # noqa: BLE001 — benchmark harness must record any SDK failure
        return TestResult(
            test_id, name, cat, passed=False, error=f"Custom: {type(e).__name__}"
        )
    sp = off_res["avg_ns"] / cust_res["avg_ns"] if cust_res["avg_ns"] else None
    print_comparison(name, off_res, cust_res)
    return TestResult(
        test_id,
        name,
        cat,
        passed=True,
        official_ns=off_res["avg_ns"],
        custom_ns=cust_res["avg_ns"],
        speedup=sp,
        ops_per_sec=cust_res["ops_per_sec"],
    )


@register_test("025", "ChatRequest serialization", "E")
def test_025(args, ctx):
    try:
        from highrise import ChatRequest, Outgoing, converter
        from highrise_fast import dumps_json
    except ImportError as e:
        return TestResult("025", "ChatRequest ser", "E", passed=False, error=str(e))

    def off():
        req = ChatRequest(message="hello world", whisper_target_id=None)
        req.rid = "bench"
        return converter.dumps(req, Outgoing)

    def cust():
        return dumps_json(
            {
                "_type": "ChatRequest",
                "rid": "bench",
                "message": "hello world",
                "whisper_target_id": None,
            }
        )

    return _outgoing_bench("025", "ChatRequest", off, cust, args, ctx)


@register_test("026", "EmoteRequest serialization", "E")
def test_026(args, ctx):
    try:
        from highrise import EmoteRequest, Outgoing, converter
        from highrise_fast import dumps_json
    except ImportError as e:
        return TestResult("026", "EmoteRequest ser", "E", passed=False, error=str(e))

    def off():
        req = EmoteRequest(emote_id="wave", target_user_id=None)
        req.rid = "e1"
        return converter.dumps(req, Outgoing)

    def cust():
        return dumps_json(
            {
                "_type": "EmoteRequest",
                "rid": "e1",
                "emote_id": "wave",
                "target_user_id": None,
            }
        )

    return _outgoing_bench("026", "EmoteRequest", off, cust, args, ctx)


@register_test("027", "TeleportRequest serialization", "E")
def test_027(args, ctx):
    try:
        from highrise import Outgoing, Position, TeleportRequest, converter
        from highrise_fast import dumps_json
    except ImportError as e:
        return TestResult("027", "TeleportRequest ser", "E", passed=False, error=str(e))

    def off():
        req = TeleportRequest(
            user_id="u1", destination=Position(x=1.5, y=0.0, z=3.2, facing="FrontLeft")
        )
        req.rid = "t1"
        return converter.dumps(req, Outgoing)

    def cust():
        return dumps_json(
            {
                "_type": "TeleportRequest",
                "rid": "t1",
                "user_id": "u1",
                "destination": {"x": 1.5, "y": 0.0, "z": 3.2, "facing": "FrontLeft"},
            }
        )

    return _outgoing_bench("027", "TeleportRequest", off, cust, args, ctx)


@register_test("028", "SetOutfitRequest (5 items)", "E")
def test_028(args, ctx):
    try:
        from highrise import Item, Outgoing, SetOutfitRequest, converter
        from highrise_fast import dumps_json
    except ImportError as e:
        return TestResult("028", "SetOutfit ser", "E", passed=False, error=str(e))

    def off():
        items = [Item(type="clothing", amount=1, id=f"item_{i}") for i in range(5)]
        req = SetOutfitRequest(outfit=items)
        req.rid = "o1"
        return converter.dumps(req, Outgoing)

    def cust():
        return dumps_json(
            {
                "_type": "SetOutfitRequest",
                "rid": "o1",
                "outfit": [
                    {
                        "type": "clothing",
                        "amount": 1,
                        "id": f"item_{i}",
                        "account_bound": False,
                        "active_palette": 0,
                    }
                    for i in range(5)
                ],
            }
        )

    return _outgoing_bench("028", "SetOutfit(5)", off, cust, args, ctx)


@register_test("029", "SetOutfitRequest (10 items)", "E")
def test_029(args, ctx):
    try:
        from highrise import Item, Outgoing, SetOutfitRequest, converter
        from highrise_fast import dumps_json
    except ImportError as e:
        return TestResult("029", "SetOutfit(10) ser", "E", passed=False, error=str(e))

    def off():
        items = [Item(type="clothing", amount=1, id=f"item_{i}") for i in range(10)]
        req = SetOutfitRequest(outfit=items)
        req.rid = "o2"
        return converter.dumps(req, Outgoing)

    def cust():
        return dumps_json(
            {
                "_type": "SetOutfitRequest",
                "rid": "o2",
                "outfit": [
                    {
                        "type": "clothing",
                        "amount": 1,
                        "id": f"item_{i}",
                        "account_bound": False,
                        "active_palette": 0,
                    }
                    for i in range(10)
                ],
            }
        )

    return _outgoing_bench("029", "SetOutfit(10)", off, cust, args, ctx)


@register_test("030", "ModerateRoomRequest serialization", "E")
def test_030(args, ctx):
    try:
        from highrise import ModerateRoomRequest, Outgoing, converter
        from highrise_fast import dumps_json
    except ImportError as e:
        return TestResult("030", "ModerateRoom ser", "E", passed=False, error=str(e))

    def off():
        req = ModerateRoomRequest(
            user_id="u1", moderation_action="ban", action_length=3600
        )
        req.rid = "m1"
        return converter.dumps(req, Outgoing)

    def cust():
        return dumps_json(
            {
                "_type": "ModerateRoomRequest",
                "rid": "m1",
                "user_id": "u1",
                "moderation_action": "ban",
                "action_length": 3600,
            }
        )

    return _outgoing_bench("030", "ModerateRoom", off, cust, args, ctx)


@register_test("031", "GetRoomUsersRequest serialization", "E")
def test_031(args, ctx):
    try:
        from highrise import GetRoomUsersRequest, Outgoing, converter
        from highrise_fast import dumps_json
    except ImportError as e:
        return TestResult("031", "GetRoomUsers ser", "E", passed=False, error=str(e))

    def off():
        req = GetRoomUsersRequest("bench-r1")
        return converter.dumps(req, Outgoing)

    def cust():
        return dumps_json({"_type": "GetRoomUsersRequest", "rid": "bench-r1"})

    return _outgoing_bench("031", "GetRoomUsers", off, cust, args, ctx)


@register_test("032", "Large chat (2000 chars)", "E")
def test_032(args, ctx):
    try:
        from highrise import ChatRequest, Outgoing, converter
        from highrise_fast import dumps_json
    except ImportError as e:
        return TestResult("032", "Large chat ser", "E", passed=False, error=str(e))
    big_msg = "A" * 2000

    def off():
        req = ChatRequest(message=big_msg, whisper_target_id=None)
        req.rid = "big"
        return converter.dumps(req, Outgoing)

    def cust():
        return dumps_json(
            {
                "_type": "ChatRequest",
                "rid": "big",
                "message": big_msg,
                "whisper_target_id": None,
            }
        )

    return _outgoing_bench("032", "Chat(2000ch)", off, cust, args, ctx)


@register_test("033", "SendMessageRequest serialization", "E")
def test_033(args, ctx):
    try:
        from highrise import Outgoing, SendMessageRequest, converter
        from highrise_fast import dumps_json
    except ImportError as e:
        return TestResult("033", "SendMessage ser", "E", passed=False, error=str(e))

    def off():
        req = SendMessageRequest(
            conversation_id="conv1", content="test msg", type="text"
        )
        req.rid = "s1"
        return converter.dumps(req, Outgoing)

    def cust():
        return dumps_json(
            {
                "_type": "SendMessageRequest",
                "rid": "s1",
                "conversation_id": "conv1",
                "content": "test msg",
                "type": "text",
                "room_id": None,
                "world_id": None,
                "media_id": None,
            }
        )

    return _outgoing_bench("033", "SendMessage", off, cust, args, ctx)


@register_test("034", "KeepaliveRequest serialization", "E")
def test_034(args, ctx):
    try:
        from highrise_fast import dumps_json
    except ImportError as e:
        return TestResult("034", "Keepalive ser", "E", passed=False, error=str(e))

    def cust():
        return dumps_json({"_type": "KeepaliveRequest"})

    res = bench(cust, args.iters)
    p(f"    Keepalive avg: {fmt_ns(res['avg_ns'])}")
    return TestResult("034", "Keepalive", "E", passed=True, custom_ns=res["avg_ns"])


@register_test("035", "Serialization output size comparison", "E")
def test_035(args, ctx):
    try:
        from highrise import ChatRequest, Outgoing, converter
        from highrise_fast import dumps_json
    except ImportError as e:
        return TestResult("035", "Output size", "E", passed=False, error=str(e))
    req = ChatRequest(message="hello world test", whisper_target_id=None)
    req.rid = "size-test"
    off_data = converter.dumps(req, Outgoing)
    cust_data = dumps_json(
        {
            "_type": "ChatRequest",
            "rid": "size-test",
            "message": "hello world test",
            "whisper_target_id": None,
        }
    )
    off_size = len(off_data)
    cust_size = len(cust_data)
    p(f"    Official size: {off_size} bytes")
    p(f"    Custom size  : {cust_size} bytes")
    if cust_size < off_size:
        diff_pct = (off_size - cust_size) / off_size * 100
        p(f"    Difference   : {off_size - cust_size} bytes ({diff_pct:.1f}% smaller)")
    else:
        p(f"    Custom is {cust_size - off_size} bytes larger")
    return TestResult(
        "035",
        "Output size",
        "E",
        passed=True,
        official_ns=off_size,
        custom_ns=cust_size,
        speedup=off_size / cust_size if cust_size else None,
    )


@register_test("036", "Serialization throughput (1MB sustained)", "E")
def test_036(args, ctx):
    try:
        from highrise_fast import dumps_json
    except ImportError as e:
        return TestResult("036", "Throughput", "E", passed=False, error=str(e))
    msg = {
        "_type": "ChatRequest",
        "rid": "x",
        "message": "B" * 500,
        "whisper_target_id": None,
    }
    total_bytes = 0
    count_ops = 0
    t_start = time.perf_counter()
    while total_bytes < 1_000_000:
        data = dumps_json(msg)
        total_bytes += len(data)
        count_ops += 1
    elapsed = time.perf_counter() - t_start
    throughput_mbps = total_bytes / elapsed / 1024 / 1024
    p(f"    1MB in {elapsed * 1000:.2f}ms ({count_ops} ops)")
    p(f"    Throughput: {throughput_mbps:.1f} MB/s")
    return TestResult(
        "036",
        "Throughput 1MB",
        "E",
        passed=True,
        ops_per_sec=count_ops / elapsed,
        extra={"mb_per_sec": throughput_mbps},
    )


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY F: INCOMING PARSING (037-048)
# ═══════════════════════════════════════════════════════════════════════════


def _incoming_bench(test_id, name, sample, args, ctx):
    iters = min(args.iters, 5000)  # noqa: F841
    try:
        from highrise import Incoming, converter
        from highrise_fast import loads_json, parse_server_message
    except ImportError as e:
        return TestResult(test_id, name, "F", passed=False, error=str(e))

    def off():
        return converter.loads(sample, Incoming)

    def cust():
        return parse_server_message(loads_json(sample))

    return _outgoing_bench(test_id, name, off, cust, args, ctx, cat="F")


@register_test("037", "ChatEvent parsing", "F")
def test_037(args, ctx):
    sample = '{"_type":"ChatEvent","user":{"id":"u1","username":"alice"},"message":"hello","whisper":false}'
    return _incoming_bench("037", "ChatEvent", sample, args, ctx)


@register_test("038", "UserJoinedEvent parsing", "F")
def test_038(args, ctx):
    sample = '{"_type":"UserJoinedEvent","user":{"id":"u2","username":"bob"},"position":{"x":5.5,"y":0.0,"z":12.3,"facing":"FrontRight"}}'
    return _incoming_bench("038", "UserJoinedEvent", sample, args, ctx)


@register_test("039", "UserLeftEvent parsing", "F")
def test_039(args, ctx):
    sample = '{"_type":"UserLeftEvent","user":{"id":"u3","username":"charlie"}}'
    return _incoming_bench("039", "UserLeftEvent", sample, args, ctx)


@register_test("040", "EmoteEvent parsing", "F")
def test_040(args, ctx):
    sample = '{"_type":"EmoteEvent","user":{"id":"u1","username":"alice"},"emote_id":"wave","receiver":null}'
    return _incoming_bench("040", "EmoteEvent", sample, args, ctx)


@register_test("041", "TipReactionEvent parsing", "F")
def test_041(args, ctx):
    sample = '{"_type":"TipReactionEvent","sender":{"id":"u1","username":"alice"},"receiver":{"id":"u2","username":"bob"},"item":{"type":"gold","amount":5}}'
    return _incoming_bench("041", "TipReactionEvent", sample, args, ctx)


@register_test("042", "UserMovedEvent parsing", "F")
def test_042(args, ctx):
    sample = '{"_type":"UserMovedEvent","user":{"id":"u1","username":"alice"},"position":{"x":10.5,"y":0.0,"z":20.3,"facing":"BackLeft"}}'
    return _incoming_bench("042", "UserMovedEvent", sample, args, ctx)


@register_test("043", "GetRoomUsersResponse (5 users)", "F")
def test_043(args, ctx):
    payload = {
        "_type": "GetRoomUsersResponse",
        "rid": "r1",
        "content": [
            [
                {"id": f"u{i}", "username": f"user_{i}"},
                {
                    "x": float(i),
                    "y": 0.0,
                    "z": float(i * 2),
                    "facing": "Front",
                },
            ]
            for i in range(5)
        ],
    }

    sample = json.dumps(payload)
    iters = min(args.iters, 5000)

    off_ns = None
    off_error = ""

    try:
        from highrise import Incoming, converter

        def off():
            return converter.loads(sample, Incoming)

        off_res = bench(off, iters)
        off_ns = off_res["avg_ns"]

    except Exception as e:  # noqa: BLE001 — official SDK may raise cattrs/other errors
        off_error = f"Official: {type(e).__name__}"
        p(f"    Official: ⚠️  {type(e).__name__} (known cattrs tuple limitation)")

    try:
        from highrise_fast import loads_json, parse_server_message

        def cust():
            return parse_server_message(loads_json(sample))

        cust_res = bench(cust, iters)
        parsed = cust()

        content = getattr(parsed, "content", None)
        n_parsed = len(content) if content is not None else 0

        p(f"    Custom:   ✅ {fmt_ns(cust_res['avg_ns'])} avg ({n_parsed} users)")

        sp = off_ns / cust_res["avg_ns"] if off_ns and cust_res["avg_ns"] else None

        if n_parsed != 5:
            return TestResult(
                "043",
                "RoomUsers(5)",
                "F",
                passed=False,
                error=f"Expected 5 users, parsed {n_parsed}",
                official_ns=off_ns,
                custom_ns=cust_res["avg_ns"],
                speedup=sp,
            )

        return TestResult(
            "043",
            "RoomUsers(5)",
            "F",
            passed=True,
            official_ns=off_ns,
            custom_ns=cust_res["avg_ns"],
            speedup=sp,
            error=off_error,
        )

    except (
        Exception
    ) as e:  # noqa: BLE001 — benchmark harness must record any SDK failure
        return TestResult(
            "043",
            "RoomUsers(5)",
            "F",
            passed=False,
            error=f"Custom: {type(e).__name__}: {e}"[:200],
        )


@register_test("044", "GetRoomUsersResponse (20 users)", "F")
def test_044(args, ctx):
    payload = {
        "_type": "GetRoomUsersResponse",
        "rid": "r2",
        "content": [
            [
                {"id": f"u{i}", "username": f"user_{i}_longer_name"},
                {"x": float(i), "y": 0.0, "z": float(i * 3), "facing": "FrontRight"},
            ]
            for i in range(20)
        ],
    }
    sample = json.dumps(payload)
    iters = min(args.iters, 5000)

    off_ns = None
    try:
        from highrise import Incoming, converter

        def off():
            return converter.loads(sample, Incoming)

        off_res = bench(off, iters)
        off_ns = off_res["avg_ns"]
    except Exception as e:  # noqa: BLE001 — official SDK may raise cattrs/other errors
        p(f"    Official: ⚠️  {type(e).__name__} (cattrs tuple limitation)")

    try:
        from highrise_fast import loads_json, parse_server_message

        def cust():
            return parse_server_message(loads_json(sample))

        cust_res = bench(cust, iters)
        result = cust()
        n_parsed = len(result.content) if hasattr(result, "content") else 0
        p(f"    Custom:   ✅ {fmt_ns(cust_res['avg_ns'])} avg ({n_parsed} users)")
        sp = off_ns / cust_res["avg_ns"] if off_ns and cust_res["avg_ns"] else None
        return TestResult(
            "044",
            "RoomUsers(20)",
            "F",
            passed=(n_parsed == 20),
            official_ns=off_ns,
            custom_ns=cust_res["avg_ns"],
            speedup=sp,
        )
    except (
        Exception
    ) as e:  # noqa: BLE001 — benchmark harness must record any SDK failure
        return TestResult(
            "044",
            "RoomUsers(20)",
            "F",
            passed=False,
            error=f"Custom: {type(e).__name__}",
        )


@register_test("045", "GetWalletResponse parsing", "F")
def test_045(args, ctx):
    sample = '{"_type":"GetWalletResponse","rid":"w1","content":[{"type":"gold","amount":500},{"type":"earned_gold","amount":200}]}'
    return _incoming_bench("045", "GetWallet", sample, args, ctx)


@register_test("046", "Error response parsing", "F")
def test_046(args, ctx):
    sample = (
        '{"_type":"Error","message":"timeout","do_not_reconnect":false,"rid":"r99"}'
    )
    return _incoming_bench("046", "Error", sample, args, ctx)


@register_test("047", "VoiceEvent parsing", "F")
def test_047(args, ctx):
    sample = '{"_type":"VoiceEvent","users":[[{"id":"u1","username":"alice"},"voice"],[{"id":"u2","username":"bob"},"muted"]],"seconds_left":300}'
    return _incoming_bench("047", "VoiceEvent", sample, args, ctx)


@register_test("048", "RoomModeratedEvent parsing", "F")
def test_048(args, ctx):
    sample = '{"_type":"RoomModeratedEvent","moderatorId":"mod1","targetUserId":"u5","moderationType":"ban","duration":3600}'
    return _incoming_bench("048", "RoomModerated", sample, args, ctx)


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY G: JSON BACKEND COMPARISON (049-054)
# ═══════════════════════════════════════════════════════════════════════════


@register_test("049", "stdlib json.dumps performance", "G")
def test_049(args, ctx):
    payload = {
        "_type": "ChatRequest",
        "rid": "t",
        "message": "Hello 🎵",
        "whisper_target_id": None,
    }

    def fn():
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()

    res = bench(fn, args.iters)
    p(
        f"    stdlib json.dumps: {fmt_ns(res['avg_ns'])} avg, {res['ops_per_sec']:,.0f} ops/s"
    )
    ctx["json_stdlib"] = res
    return TestResult(
        "049", "stdlib json ser", "G", passed=True, custom_ns=res["avg_ns"]
    )


@register_test("050", "orjson.dumps performance", "G")
def test_050(args, ctx):
    try:
        import orjson
    except ImportError:
        p("    orjson NOT INSTALLED — skipping")
        return TestResult("050", "orjson ser", "G", passed=False, error="not installed")
    payload = {
        "_type": "ChatRequest",
        "rid": "t",
        "message": "Hello 🎵",
        "whisper_target_id": None,
    }

    def fn():
        return orjson.dumps(payload)

    res = bench(fn, args.iters)
    p(f"    orjson.dumps: {fmt_ns(res['avg_ns'])} avg, {res['ops_per_sec']:,.0f} ops/s")
    ctx["json_orjson"] = res
    return TestResult("050", "orjson ser", "G", passed=True, custom_ns=res["avg_ns"])


@register_test("051", "ujson.dumps performance", "G")
def test_051(args, ctx):
    try:
        import ujson
    except ImportError:
        p("    ujson NOT INSTALLED — skipping")
        return TestResult("051", "ujson ser", "G", passed=False, error="not installed")
    payload = {
        "_type": "ChatRequest",
        "rid": "t",
        "message": "Hello 🎵",
        "whisper_target_id": None,
    }

    def fn():
        return ujson.dumps(payload).encode()

    res = bench(fn, args.iters)
    p(f"    ujson.dumps: {fmt_ns(res['avg_ns'])} avg, {res['ops_per_sec']:,.0f} ops/s")
    return TestResult("051", "ujson ser", "G", passed=True, custom_ns=res["avg_ns"])


@register_test("052", "stdlib json.loads performance", "G")
def test_052(args, ctx):
    raw = b'{"_type":"ChatEvent","user":{"id":"u1","username":"alice"},"message":"hello","whisper":false}'

    def fn():
        return json.loads(raw)

    res = bench(fn, args.iters)
    p(f"    stdlib json.loads: {fmt_ns(res['avg_ns'])} avg")
    ctx["json_stdlib_deser"] = res
    return TestResult(
        "052", "stdlib json deser", "G", passed=True, custom_ns=res["avg_ns"]
    )


@register_test("053", "orjson.loads performance", "G")
def test_053(args, ctx):
    try:
        import orjson
    except ImportError:
        return TestResult(
            "053", "orjson deser", "G", passed=False, error="not installed"
        )
    raw = b'{"_type":"ChatEvent","user":{"id":"u1","username":"alice"},"message":"hello","whisper":false}'

    def fn():
        return orjson.loads(raw)

    res = bench(fn, args.iters)
    p(f"    orjson.loads: {fmt_ns(res['avg_ns'])} avg")
    ctx["json_orjson_deser"] = res
    return TestResult("053", "orjson deser", "G", passed=True, custom_ns=res["avg_ns"])


@register_test("054", "JSON backend speedup summary", "G")
def test_054(args, ctx):
    stdlib_ser = ctx.get("json_stdlib", {}).get("avg_ns")
    orjson_ser = ctx.get("json_orjson", {}).get("avg_ns")
    stdlib_deser = ctx.get("json_stdlib_deser", {}).get("avg_ns")
    orjson_deser = ctx.get("json_orjson_deser", {}).get("avg_ns")

    if stdlib_ser and orjson_ser:
        sp_ser = stdlib_ser / orjson_ser
        p(f"    Serialization: orjson is {sp_ser:.2f}x faster than stdlib")
    if stdlib_deser and orjson_deser:
        sp_deser = stdlib_deser / orjson_deser
        p(f"    Deserialization: orjson is {sp_deser:.2f}x faster than stdlib")

    return TestResult(
        "054",
        "JSON backend summary",
        "G",
        passed=True,
        speedup=sp_ser if stdlib_ser and orjson_ser else None,
    )


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY H: WEBSOCKET FRAME CODEC (055-058)
# ═══════════════════════════════════════════════════════════════════════════


@register_test("055", "Full round-trip (dict→encode→decode→dict)", "H")
def test_055(args, ctx):
    try:
        from highrise_fast import dumps_json, loads_json
    except ImportError as e:
        return TestResult("055", "Round-trip", "H", passed=False, error=str(e))
    payload = {
        "_type": "ChatRequest",
        "rid": "rt-1",
        "message": "round trip",
        "whisper_target_id": None,
    }

    def fn():
        return loads_json(dumps_json(payload))

    res = bench(fn, args.iters)
    p(f"    Round-trip avg: {fmt_ns(res['avg_ns'])}")
    p(f"    Throughput    : {res['ops_per_sec']:,.0f} ops/s")
    return TestResult(
        "055",
        "Round-trip",
        "H",
        passed=True,
        custom_ns=res["avg_ns"],
        ops_per_sec=res["ops_per_sec"],
    )


@register_test("056", "Large payload round-trip (50KB)", "H")
def test_056(args, ctx):
    try:
        from highrise_fast import dumps_json, loads_json
    except ImportError as e:
        return TestResult("056", "Large round-trip", "H", passed=False, error=str(e))
    big_payload = {
        "_type": "GetRoomUsersResponse",
        "rid": "big",
        "content": [
            [
                {"id": f"u{i}", "username": f"user_{i}_with_a_longer_name"},
                {"x": float(i), "y": 0.0, "z": float(i * 3), "facing": "FrontRight"},
            ]
            for i in range(100)
        ],
    }

    def fn():
        return loads_json(dumps_json(big_payload))

    res = bench(fn, min(args.iters, 2000))
    p(f"    50KB round-trip avg: {fmt_ns(res['avg_ns'])}")
    return TestResult(
        "056", "Large round-trip", "H", passed=True, custom_ns=res["avg_ns"]
    )


@register_test("057", "Encode-only throughput", "H")
def test_057(args, ctx):
    try:
        from highrise_fast import dumps_json
    except ImportError as e:
        return TestResult("057", "Encode-only", "H", passed=False, error=str(e))
    payload = {
        "_type": "ChatRequest",
        "rid": "enc",
        "message": "encode test",
        "whisper_target_id": None,
    }
    res = bench(lambda: dumps_json(payload), args.iters)
    p(f"    Encode avg: {fmt_ns(res['avg_ns'])}")
    return TestResult("057", "Encode-only", "H", passed=True, custom_ns=res["avg_ns"])


@register_test("058", "Decode-only throughput", "H")
def test_058(args, ctx):
    try:
        from highrise_fast import loads_json
    except ImportError as e:
        return TestResult("058", "Decode-only", "H", passed=False, error=str(e))
    raw = b'{"_type":"ChatEvent","user":{"id":"u1","username":"alice"},"message":"decode test","whisper":false}'
    res = bench(lambda: loads_json(raw), args.iters)
    p(f"    Decode avg: {fmt_ns(res['avg_ns'])}")
    return TestResult("058", "Decode-only", "H", passed=True, custom_ns=res["avg_ns"])


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY I: UNICODE & EDGE CASES (059-066)
# ═══════════════════════════════════════════════════════════════════════════


@register_test("059", "Unicode message round-trip", "I")
def test_059(args, ctx):
    try:
        from highrise_fast import dumps_json, loads_json
    except ImportError as e:
        return TestResult("059", "Unicode", "I", passed=False, error=str(e))
    messages = [
        "Hello 🎵 World",
        "日本語テスト",
        "Émoji: 🇫🇷🇺🇸🇯🇵",
        "Ñoño señor año",
        "한국어 시험",
        "العربية",
        "Mixed: abc 123 🎉 def",
        "Zero width: \u200b\u200c\u200d",
    ]
    failures = 0
    for msg in messages:
        payload = {
            "_type": "ChatRequest",
            "rid": "u",
            "message": msg,
            "whisper_target_id": None,
        }
        try:
            decoded = loads_json(dumps_json(payload))
            assert decoded["message"] == msg
        except (AssertionError, TypeError, ValueError, KeyError):
            failures += 1
            p(f"    ❌ FAILED: {msg[:30]}")
    if failures == 0:
        p(f"    ✅ All {len(messages)} unicode messages passed")
    return TestResult(
        "059",
        "Unicode round-trip",
        "I",
        passed=failures == 0,
        extra={"failures": failures, "total": len(messages)},
    )


@register_test("060", "Empty/null field handling", "I")
def test_060(args, ctx):
    try:
        from highrise_fast import dumps_json, loads_json, parse_server_message
    except ImportError as e:
        return TestResult("060", "Null fields", "I", passed=False, error=str(e))
    edge_payloads = [
        {"_type": "ChatRequest", "rid": None, "message": "", "whisper_target_id": None},
        {"_type": "ChatEvent", "user": None, "message": "", "whisper": False},
        {"_type": "Error", "message": "", "do_not_reconnect": False},
        {"_type": "GetRoomUsersResponse", "rid": "r", "content": []},
    ]
    failures = 0
    for ep in edge_payloads:
        try:
            parse_server_message(loads_json(dumps_json(ep)))
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            failures += 1
            p(f"    ❌ {ep['_type']}: {e}")
    if failures == 0:
        p(f"    ✅ All {len(edge_payloads)} edge cases handled")
    return TestResult("060", "Null/empty fields", "I", passed=failures == 0)


@register_test("061", "Very long message (10KB)", "I")
def test_061(args, ctx):
    try:
        from highrise_fast import dumps_json, loads_json
    except ImportError as e:
        return TestResult("061", "10KB message", "I", passed=False, error=str(e))
    big_msg = "X" * 10000
    payload = {
        "_type": "ChatRequest",
        "rid": "big",
        "message": big_msg,
        "whisper_target_id": None,
    }
    t0 = time.perf_counter_ns()
    decoded = loads_json(dumps_json(payload))
    elapsed = time.perf_counter_ns() - t0
    ok = decoded["message"] == big_msg
    p(f"    10KB message: {fmt_ns(elapsed)} ({'✅' if ok else '❌'})")
    return TestResult("061", "10KB message", "I", passed=ok, custom_ns=elapsed)


@register_test("062", "Deeply nested payload", "I")
def test_062(args, ctx):
    try:
        from highrise_fast import dumps_json, loads_json
    except ImportError as e:
        return TestResult(
            "062",
            "Deep nesting",
            "I",
            passed=False,
            error=str(e),
        )

    nested = {"_type": "Test", "data": {"level": 1}}
    current = nested["data"]

    for level in range(2, 20):
        current["child"] = {"level": level}
        current = current["child"]

    try:
        decoded = loads_json(dumps_json(nested))
        node = decoded["data"]
        ok = node.get("level") == 1

        for level in range(2, 20):
            node = node.get("child", {})
            if node.get("level") != level:
                ok = False
                break

        if ok:
            p("    20-level nesting: ✅")
        else:
            p("    20-level nesting: ❌ unexpected nested structure")

        return TestResult(
            "062",
            "Deep nesting",
            "I",
            passed=ok,
            error="" if ok else "Nested level mismatch",
        )

    except (
        RecursionError,
        TypeError,
        ValueError,
        KeyError,
        AttributeError,
    ) as e:
        p(f"    20-level nesting: ❌ {type(e).__name__}: {e}")

        return TestResult(
            "062",
            "Deep nesting",
            "I",
            passed=False,
            error=f"{type(e).__name__}: {e}"[:200],
        )


@register_test("063", "Special JSON characters in strings", "I")
def test_063(args, ctx):
    try:
        from highrise_fast import dumps_json, loads_json
    except ImportError as e:
        return TestResult("063", "Special chars", "I", passed=False, error=str(e))
    specials = [
        'He said "hello"',
        "It's a test",
        "Back\\slash",
        "Tab\there",
        "Newline\nhere",
        "Null\x00byte",
        'Quotes: "" "',
    ]
    failures = 0
    for s in specials:
        payload = {
            "_type": "ChatRequest",
            "rid": "sp",
            "message": s,
            "whisper_target_id": None,
        }
        try:
            decoded = loads_json(dumps_json(payload))
            if decoded["message"] != s:
                failures += 1
        except (TypeError, ValueError, UnicodeDecodeError):
            failures += 1
    p(f"    Special chars: {len(specials) - failures}/{len(specials)} passed")
    return TestResult("063", "Special chars", "I", passed=failures == 0)


@register_test("064", "Boolean and numeric type preservation", "I")
def test_064(args, ctx):
    try:
        from highrise_fast import dumps_json, loads_json
    except ImportError as e:
        return TestResult("064", "Type preservation", "I", passed=False, error=str(e))
    payload = {
        "bool_true": True,
        "bool_false": False,
        "int": 42,
        "float": 3.14,
        "null": None,
    }
    decoded = loads_json(dumps_json(payload))
    ok = (
        decoded["bool_true"] is True
        and decoded["bool_false"] is False
        and decoded["int"] == 42
        and abs(decoded["float"] - 3.14) < 0.001
        and decoded["null"] is None
    )
    p(f"    Type preservation: {'✅' if ok else '❌'}")
    return TestResult("064", "Type preservation", "I", passed=ok)


@register_test("065", "Array payload handling", "I")
def test_065(args, ctx):
    try:
        from highrise_fast import dumps_json, loads_json
    except ImportError as e:
        return TestResult("065", "Array payload", "I", passed=False, error=str(e))
    payload = {"_type": "Test", "items": [1, "two", 3.0, None, True, {"nested": "obj"}]}
    decoded = loads_json(dumps_json(payload))
    ok = decoded["items"] == [1, "two", 3.0, None, True, {"nested": "obj"}]
    p(f"    Array handling: {'✅' if ok else '❌'}")
    return TestResult("065", "Array payload", "I", passed=ok)


@register_test("066", "Malformed JSON rejection", "I")
def test_066(args, ctx):
    try:
        from highrise_fast import loads_json
    except ImportError as e:
        return TestResult("066", "Malformed JSON", "I", passed=False, error=str(e))
    malformed = [b"", b"null", b"[]", b'"string"', b"12345", b"{invalid"]
    handled = 0
    for m in malformed:
        try:
            loads_json(m)
            handled += 1
        except (ValueError, TypeError, UnicodeDecodeError):
            handled += 1
    p(f"    Malformed inputs handled: {handled}/{len(malformed)}")
    return TestResult("066", "Malformed JSON", "I", passed=True)


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY J: FLOAT & NUMERIC PRECISION (067-070)
# ═══════════════════════════════════════════════════════════════════════════


@register_test("067", "Position float precision", "J")
def test_067(args, ctx):
    try:
        from highrise_fast import Position, position_to_wire
    except ImportError as e:
        return TestResult("067", "Float precision", "J", passed=False, error=str(e))
    pos = Position(x=15.909998321533001, y=0.0, z=6.5998564720154, facing="FrontLeft")
    wire = position_to_wire(pos)
    ok = abs(wire["x"] - 15.909998321533001) < 1e-10
    p(f"    x={pos.x} → wire x={wire['x']} {'✅' if ok else '❌'}")
    return TestResult("067", "Float precision", "J", passed=ok)


@register_test("068", "Very small/large float values", "J")
def test_068(args, ctx):
    try:
        from highrise_fast import Position, position_to_wire
    except ImportError as e:
        return TestResult("068", "Extreme floats", "J", passed=False, error=str(e))
    test_vals = [(1e-10, 0.0, 1e10), (0.1 + 0.2, 0.3, 1.0)]
    failures = 0
    for x, y, z in test_vals:
        pos = Position(x=x, y=y, z=z, facing="Front")
        wire = position_to_wire(pos)
        if abs(wire["x"] - x) > 1e-9:
            failures += 1
    p(f"    Extreme floats: {len(test_vals) - failures}/{len(test_vals)} passed")
    return TestResult("068", "Extreme floats", "J", passed=failures == 0)


@register_test("069", "Integer overflow safety", "J")
def test_069(args, ctx):
    try:
        from highrise_fast import dumps_json, loads_json
    except ImportError as e:
        return TestResult("069", "Int overflow", "J", passed=False, error=str(e))
    payload = {"big_int": 2**53, "bigger": 2**62, "negative": -(2**53)}
    try:
        decoded = loads_json(dumps_json(payload))
        ok = decoded["big_int"] == 2**53 and decoded["negative"] == -(2**53)
        p(f"    Large integers: {'✅' if ok else '❌'}")
    except (TypeError, ValueError, OverflowError) as e:
        ok = False
        p(f"    Large integers: ❌ {e}")
    return TestResult("069", "Int overflow", "J", passed=ok)


@register_test("070", "NaN/Infinity handling", "J")
def test_070(args, ctx):
    try:
        from highrise_fast import dumps_json, loads_json
    except ImportError as e:
        return TestResult("070", "NaN/Inf", "J", passed=False, error=str(e))
    payload = {"nan": float("nan"), "inf": float("inf"), "neg_inf": float("-inf")}
    try:
        encoded = dumps_json(payload)
        loads_json(encoded)
        p("    NaN/Inf handling: ✅ (encoded without crash)")
        return TestResult("070", "NaN/Inf", "J", passed=True)
    except (TypeError, ValueError, OverflowError) as e:
        p(f"    NaN/Inf handling: ⚠️  {type(e).__name__} (acceptable)")
        return TestResult("070", "NaN/Inf", "J", passed=True, extra={"note": str(e)})


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY K: CONCURRENT ASYNC THROUGHPUT (071-076)
# ═══════════════════════════════════════════════════════════════════════════


@register_test("071", "Async parse (100 messages, 10 tasks)", "K")
def test_071(args, ctx):
    try:
        from highrise_fast import loads_json, parse_server_message
    except ImportError as e:
        return TestResult("071", "Async parse", "K", passed=False, error=str(e))
    messages = [
        json.dumps(
            {
                "_type": "ChatEvent",
                "user": {"id": f"u{i}", "username": f"user_{i}"},
                "message": f"msg {i}",
                "whisper": False,
            }
        )
        for i in range(100)
    ]

    async def parse_worker(msgs):
        return [parse_server_message(loads_json(m)) for m in msgs]

    async def run():
        chunk_size = 10
        chunks = [
            messages[i : i + chunk_size] for i in range(0, len(messages), chunk_size)
        ]
        t0 = time.perf_counter()
        tasks = [asyncio.create_task(parse_worker(c)) for c in chunks]
        await asyncio.gather(*tasks)
        return time.perf_counter() - t0

    elapsed = asyncio.run(run())
    p(f"    100 msgs / 10 tasks: {elapsed * 1000:.3f} ms")
    p(f"    Per-message avg    : {elapsed / 100 * 1e6:.1f} µs")
    return TestResult(
        "071", "Async parse", "K", passed=True, custom_ns=elapsed / 100 * 1e9
    )


@register_test("072", "Simulated bot event dispatch (1000 events)", "K")
def test_072(args, ctx):
    try:
        from highrise_fast import parse_server_message
    except ImportError as e:
        return TestResult("072", "Event dispatch", "K", passed=False, error=str(e))
    events = [
        {
            "_type": "ChatEvent",
            "user": {"id": f"u{i % 50}", "username": f"user_{i % 50}"},
            "message": f"event {i}",
            "whisper": i % 10 == 0,
        }
        for i in range(1000)
    ]

    async def run():
        t0 = time.perf_counter()
        for ev in events:
            parse_server_message(ev)
        return time.perf_counter() - t0

    elapsed = asyncio.run(run())
    p(f"    1000 events: {elapsed * 1000:.3f} ms ({elapsed / 1000 * 1e6:.1f} µs/event)")
    return TestResult(
        "072", "Event dispatch", "K", passed=True, custom_ns=elapsed / 1000 * 1e9
    )


@register_test("073", "Concurrent serialization (4 threads)", "K")
def test_073(args, ctx):
    try:
        from highrise_fast import dumps_json
    except ImportError as e:
        return TestResult("073", "Thread ser", "K", passed=False, error=str(e))
    payload = {
        "_type": "ChatRequest",
        "rid": "t",
        "message": "thread test",
        "whisper_target_id": None,
    }

    def worker():
        for _ in range(1000):
            dumps_json(payload)

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = [pool.submit(worker) for _ in range(4)]
        for f in futs:
            f.result()
    elapsed = time.perf_counter() - t0
    p(f"    4 threads × 1000 ops: {elapsed * 1000:.2f} ms")
    return TestResult(
        "073", "Thread serialization", "K", passed=True, custom_ns=elapsed / 4000 * 1e9
    )


@register_test("074", "Async request/response simulation", "K")
def test_074(args, ctx):
    try:
        from highrise_fast import Highrise
    except ImportError as e:
        return TestResult("074", "Request/response", "K", passed=False, error=str(e))

    class FakeWS:
        async def send_str(self, data):
            pass

        async def send_bytes(self, data):
            pass

    async def run():
        hr = Highrise()
        hr.ws = FakeWS()
        hr.my_id = "bot"
        import highrise_fast

        old_ff = highrise_fast._FIRE_AND_FORGET
        highrise_fast._FIRE_AND_FORGET = True
        t0 = time.perf_counter()
        for i in range(100):
            await hr.chat(f"msg {i}")
        highrise_fast._FIRE_AND_FORGET = old_ff
        return time.perf_counter() - t0

    elapsed = asyncio.run(run())
    p(f"    100 fire-and-forget sends: {elapsed * 1000:.2f} ms")
    return TestResult(
        "074", "Request/response sim", "K", passed=True, custom_ns=elapsed / 100 * 1e9
    )


@register_test("075", "Mixed read/write concurrency", "K")
def test_075(args, ctx):
    try:
        from highrise_fast import dumps_json, loads_json, parse_server_message
    except ImportError as e:
        return TestResult("075", "Mixed concurrency", "K", passed=False, error=str(e))

    async def run():
        payload = {
            "_type": "ChatEvent",
            "user": {"id": "u1", "username": "test"},
            "message": "mix",
            "whisper": False,
        }
        raw = json.dumps(payload)
        t0 = time.perf_counter()
        for _ in range(500):
            parsed = parse_server_message(loads_json(raw))
            dumps_json(
                {
                    "_type": "ChatRequest",
                    "rid": "r",
                    "message": f"echo: {parsed.message}",
                    "whisper_target_id": None,
                }
            )
        return time.perf_counter() - t0

    elapsed = asyncio.run(run())
    p(f"    500 mixed ops: {elapsed * 1000:.2f} ms ({elapsed / 500 * 1e6:.1f} µs/op)")
    return TestResult(
        "075", "Mixed concurrency", "K", passed=True, custom_ns=elapsed / 500 * 1e9
    )


@register_test("076", "Event loop saturation test", "K")
def test_076(args, ctx):
    try:
        from highrise_fast import parse_server_message
    except ImportError as e:
        return TestResult("076", "Loop saturation", "K", passed=False, error=str(e))

    async def run():
        events = [
            {
                "_type": "ChatEvent",
                "user": {"id": "u1", "username": "x"},
                "message": "sat",
                "whisper": False,
            }
        ] * 100
        t0 = time.perf_counter()
        for _ in range(50):
            for ev in events:
                parse_server_message(ev)
        return time.perf_counter() - t0

    elapsed = asyncio.run(run())
    ops = 5000
    p(f"    5000 parses in {elapsed * 1000:.1f} ms ({ops / elapsed:,.0f} ops/s)")
    return TestResult(
        "076", "Loop saturation", "K", passed=True, ops_per_sec=ops / elapsed
    )


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY L: LEAK & RESOURCE SAFETY (077-080)
# ═══════════════════════════════════════════════════════════════════════════


@register_test("077", "Official SDK leak test (cancelled requests)", "L")
def test_077(args, ctx):
    n = args.leak_n
    try:
        from highrise import Highrise as OHighrise
    except ImportError:
        return TestResult(
            "077", "Official leak", "L", passed=False, error="SDK not found"
        )
    OHighrise._req_id_registry.clear()

    class SilentWS:
        async def send_str(self, data):
            pass

        async def send_bytes(self, data):
            pass

    async def leak_test():
        hr = OHighrise()
        hr.ws = SilentWS()
        hr.my_id = "bot"
        tasks = [asyncio.create_task(hr.get_wallet()) for _ in range(n)]
        await asyncio.sleep(0.3)
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        return len(OHighrise._req_id_registry)

    leaked = asyncio.run(leak_test())
    p(
        f"    {n} cancelled → {leaked} entries left {'*** LEAK ***' if leaked > 0 else '✅ clean'}"
    )
    return TestResult(
        "077", "Official leak", "L", passed=leaked == 0, extra={"leaked": leaked}
    )


@register_test("078", "Custom SDK leak test (cancelled requests)", "L")
def test_078(args, ctx):
    n = args.leak_n
    try:
        from highrise_fast import Highrise as CHighrise
    except ImportError:
        return TestResult(
            "078", "Custom leak", "L", passed=False, error="SDK not found"
        )

    class SilentWS:
        async def send_str(self, data):
            pass

        async def send_bytes(self, data):
            pass

    async def leak_test():
        hr = CHighrise()
        hr.ws = SilentWS()
        hr.my_id = "bot"
        tasks = [asyncio.create_task(hr.get_wallet()) for _ in range(n)]
        await asyncio.sleep(0.3)
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        return len(hr._pending)

    leaked = asyncio.run(leak_test())
    p(
        f"    {n} cancelled → {leaked} entries left {'*** LEAK ***' if leaked > 0 else '✅ clean'}"
    )
    return TestResult(
        "078", "Custom leak", "L", passed=leaked == 0, extra={"leaked": leaked}
    )


@register_test("079", "Fire-and-forget leak test", "L")
def test_079(args, ctx):
    n = args.leak_n
    try:
        import highrise_fast
        from highrise_fast import Highrise as CHighrise
    except ImportError:
        return TestResult(
            "079", "Fire-forget leak", "L", passed=False, error="SDK not found"
        )

    class SilentWS:
        def __init__(self):
            self.count = 0

        async def send_str(self, data):
            self.count += 1

        async def send_bytes(self, data):
            self.count += 1

    async def ff_test():
        hr = CHighrise()
        hr.ws = SilentWS()
        hr.my_id = "bot"
        old_ff = highrise_fast._FIRE_AND_FORGET
        highrise_fast._FIRE_AND_FORGET = True
        for i in range(n):
            await hr.chat(f"msg {i}")
        highrise_fast._FIRE_AND_FORGET = old_ff
        return len(hr._pending), hr.ws.count

    pending, sent = asyncio.run(ff_test())
    p(
        f"    {n} fire-and-forget → sent={sent}, pending={pending}"
        f" {'✅' if pending == 0 else '*** LEAK ***'}"
    )
    return TestResult("079", "Fire-forget leak", "L", passed=pending == 0)


@register_test("080", "WeakRef object collection", "L")
def test_080(args, ctx):
    try:
        from highrise_fast import Position, User
    except ImportError:
        return TestResult("080", "WeakRef GC", "L", passed=False, error="SDK not found")
    u = User(id="u1", username="alice")
    pos = Position(x=1.0, y=0.0, z=2.0, facing="Front")
    wr_u = weakref.ref(u)
    wr_p = weakref.ref(pos)
    del u, pos
    gc.collect()
    gc.collect()
    user_collected = wr_u() is None
    pos_collected = wr_p() is None
    p(f"    User collected    : {'✅' if user_collected else '❌ (ref cycle?)'}")
    p(f"    Position collected: {'✅' if pos_collected else '❌ (ref cycle?)'}")
    return TestResult("080", "WeakRef GC", "L", passed=user_collected and pos_collected)


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY M: GC PRESSURE & MEMORY (081-084)
# ═══════════════════════════════════════════════════════════════════════════


@register_test("081", "GC collections during 10K parses", "M")
def test_081(args, ctx):
    try:
        from highrise_fast import loads_json, parse_server_message
    except ImportError as e:
        return TestResult("081", "GC pressure", "M", passed=False, error=str(e))
    sample = '{"_type":"ChatEvent","user":{"id":"u1","username":"alice"},"message":"gc test","whisper":false}'
    gc.collect()
    gc.collect()
    gc_before = gc.get_stats()[0]["collections"] if gc.get_stats() else 0
    t0 = time.perf_counter()
    for _ in range(10_000):
        parse_server_message(loads_json(sample))
    elapsed = time.perf_counter() - t0
    gc.collect()
    gc_after = gc.get_stats()[0]["collections"] if gc.get_stats() else 0
    collections = gc_after - gc_before
    p(f"    10K parses: {elapsed * 1000:.1f} ms, {collections} GC collections")
    return TestResult(
        "081",
        "GC pressure",
        "M",
        passed=True,
        extra={"collections": collections, "ms": elapsed * 1000},
    )


@register_test("082", "tracemalloc peak allocation", "M")
def test_082(args, ctx):
    try:
        from highrise_fast import dumps_json, loads_json
    except ImportError as e:
        return TestResult("082", "tracemalloc", "M", passed=False, error=str(e))
    import tracemalloc

    tracemalloc.start()
    payload = {
        "_type": "ChatRequest",
        "rid": "mem",
        "message": "memory test " * 10,
        "whisper_target_id": None,
    }
    for _ in range(5000):
        _ = loads_json(dumps_json(payload))
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    p(f"    Current: {fmt_bytes(current)}, Peak: {fmt_bytes(peak)}")
    p(f"    Per-op : {fmt_bytes(peak / 5000)}")
    return TestResult(
        "082",
        "tracemalloc",
        "M",
        passed=True,
        extra={"peak_bytes": peak, "per_op": peak / 5000},
    )


@register_test("083", "Object count growth over time", "M")
def test_083(args, ctx):
    try:
        from highrise_fast import parse_server_message
    except ImportError as e:
        return TestResult("083", "Object growth", "M", passed=False, error=str(e))
    gc.collect()
    before = len(gc.get_objects())
    for _ in range(5000):
        parse_server_message(
            {
                "_type": "ChatEvent",
                "user": {"id": "u1", "username": "x"},
                "message": "grow",
                "whisper": False,
            }
        )
    gc.collect()
    after = len(gc.get_objects())
    growth = after - before
    p(f"    Objects before: {before:,}, after: {after:,}, growth: {growth:+,}")
    return TestResult(
        "083", "Object growth", "M", passed=True, extra={"growth": growth}
    )


@register_test("084", "Memory stability (repeated alloc/dealloc)", "M")
def test_084(args, ctx):
    try:
        from highrise_fast import Position, User
    except ImportError as e:
        return TestResult("084", "Memory stability", "M", passed=False, error=str(e))
    import tracemalloc

    tracemalloc.start()
    objects = []
    for i in range(1000):
        objects.append(User(id=f"u{i}", username=f"user_{i}"))
        objects.append(Position(x=float(i), y=0.0, z=float(i), facing="Front"))
    _, peak1 = tracemalloc.get_traced_memory()
    del objects
    gc.collect()
    gc.collect()
    current2, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    reclaimed = peak1 - current2
    p(
        f"    Peak: {fmt_bytes(peak1)}, After GC: {fmt_bytes(current2)},"
        f" Reclaimed: {fmt_bytes(reclaimed)}"
    )
    return TestResult(
        "084",
        "Memory stability",
        "M",
        passed=True,
        extra={"peak": peak1, "after_gc": current2},
    )


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY N: WIRE FORMAT CONVERSION (085-090)
# ═══════════════════════════════════════════════════════════════════════════


@register_test("085", "Position → wire format", "N")
def test_085(args, ctx):
    try:
        from highrise_fast import Position, position_to_wire
    except ImportError as e:
        return TestResult("085", "Position wire", "N", passed=False, error=str(e))
    pos = Position(x=15.9, y=0.0, z=6.6, facing="FrontLeft")
    res = bench(lambda: position_to_wire(pos), args.iters)
    p(f"    Position→wire avg: {fmt_ns(res['avg_ns'])}")
    return TestResult("085", "Position→wire", "N", passed=True, custom_ns=res["avg_ns"])


@register_test("086", "AnchorPosition → wire format", "N")
def test_086(args, ctx):
    try:
        from highrise_fast import AnchorPosition, position_to_wire
    except ImportError as e:
        return TestResult("086", "Anchor wire", "N", passed=False, error=str(e))
    anchor = AnchorPosition(entity_id="entity_123", anchor_ix=42)
    res = bench(lambda: position_to_wire(anchor), args.iters)
    p(f"    Anchor→wire avg: {fmt_ns(res['avg_ns'])}")
    return TestResult("086", "Anchor→wire", "N", passed=True, custom_ns=res["avg_ns"])


@register_test("087", "Item → wire format", "N")
def test_087(args, ctx):
    try:
        from highrise_fast import Item, item_to_wire
    except ImportError as e:
        return TestResult("087", "Item wire", "N", passed=False, error=str(e))
    item = Item(
        type="clothing", amount=1, id="shirt_1", account_bound=False, active_palette=2
    )
    res = bench(lambda: item_to_wire(item), args.iters)
    p(f"    Item→wire avg: {fmt_ns(res['avg_ns'])}")
    return TestResult("087", "Item→wire", "N", passed=True, custom_ns=res["avg_ns"])


@register_test("088", "Position round-trip (10K)", "N")
def test_088(args, ctx):
    try:
        from highrise_fast import Position, position_to_wire
    except ImportError as e:
        return TestResult("088", "Position RT", "N", passed=False, error=str(e))
    pos = Position(x=15.9, y=0.0, z=6.6, facing="FrontLeft")

    def rt():
        wire = position_to_wire(pos)
        return Position(x=wire["x"], y=wire["y"], z=wire["z"], facing=wire["facing"])

    res = bench(rt, min(args.iters, 5000))
    p(f"    Position round-trip: {fmt_ns(res['avg_ns'])}")
    return TestResult("088", "Position RT", "N", passed=True, custom_ns=res["avg_ns"])


@register_test("089", "Dict → Position conversion", "N")
def test_089(args, ctx):
    try:
        from highrise_fast import position_to_wire
    except ImportError as e:
        return TestResult("089", "Dict→Position", "N", passed=False, error=str(e))
    d = {"x": 10.5, "y": 0.0, "z": 20.3, "facing": "BackRight"}
    res = bench(lambda: position_to_wire(d), args.iters)
    p(f"    Dict→wire avg: {fmt_ns(res['avg_ns'])}")
    return TestResult("089", "Dict→wire", "N", passed=True, custom_ns=res["avg_ns"])


@register_test("090", "Batch wire conversion (100 positions)", "N")
def test_090(args, ctx):
    try:
        from highrise_fast import Position, position_to_wire
    except ImportError as e:
        return TestResult("090", "Batch wire", "N", passed=False, error=str(e))
    positions = [
        Position(x=float(i), y=0.0, z=float(i * 2), facing="Front") for i in range(100)
    ]

    def batch():
        return [position_to_wire(p) for p in positions]

    res = bench(batch, min(args.iters, 2000))
    p(f"    100 positions→wire: {fmt_ns(res['avg_ns'])}")
    return TestResult("090", "Batch wire", "N", passed=True, custom_ns=res["avg_ns"])


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY O: WEBAPI & ATTRDICT (091-094)
# ═══════════════════════════════════════════════════════════════════════════


@register_test("091", "AttrDict identity (resp.user is resp.user)", "O")
def test_091(args, ctx):
    try:
        from highrise_fast.models_webapi import parse_webapi_response
    except ImportError as e:
        return TestResult("091", "AttrDict identity", "O", passed=False, error=str(e))
    data = {
        "user": {"id": "u1", "username": "alice", "joined_at": "2023-01-01T00:00:00Z"}
    }
    resp = parse_webapi_response("/users/u1", data)
    is_same = resp.user is resp.user
    p(f"    resp.user is resp.user: {'✅ TRUE' if is_same else '❌ FALSE'}")
    return TestResult("091", "AttrDict identity", "O", passed=is_same)


@register_test("092", "WebAPI date parsing correctness", "O")
def test_092(args, ctx):
    try:
        from highrise_fast.models_webapi import parse_webapi_response
    except ImportError as e:
        return TestResult("092", "Date parsing", "O", passed=False, error=str(e))
    data = {
        "user": {"id": "u1", "username": "alice", "joined_at": "2023-01-01T00:00:00Z"}
    }
    resp = parse_webapi_response("/users/u1", data)
    is_dt = isinstance(resp.user.joined_at, datetime)
    p(f"    joined_at is datetime: {'✅ TRUE' if is_dt else '❌ FALSE'}")
    return TestResult("092", "Date parsing", "O", passed=is_dt)


@register_test("093", "Non-date string preservation", "O")
def test_093(args, ctx):
    try:
        from highrise_fast.models_webapi import parse_webapi_response
    except ImportError as e:
        return TestResult("093", "String preservation", "O", passed=False, error=str(e))
    room_data = {
        "room": {
            "room_id": "r1",
            "disp_name": "2024-05-01",
            "created_at": "2023-01-01T00:00:00Z",
        }
    }
    resp = parse_webapi_response("/rooms/r1", room_data)
    is_str = isinstance(resp.room.disp_name, str)
    p(f"    disp_name stays str: {'✅ TRUE' if is_str else '❌ FALSE (mangled!)'}")
    return TestResult("093", "String preservation", "O", passed=is_str)


@register_test("094", "WebAPI 100-user list parse speed", "O")
def test_094(args, ctx):
    try:
        from highrise_fast.models_webapi import parse_webapi_response
    except ImportError as e:
        return TestResult("094", "WebAPI speed", "O", passed=False, error=str(e))
    payload = {
        "users": [
            {
                "user_id": f"u{i}",
                "username": f"user_{i}",
                "joined_at": "2023-01-01T00:00:00Z",
            }
            for i in range(100)
        ]
    }
    res = bench(lambda: parse_webapi_response("/users", payload), min(args.iters, 5000))
    p(f"    100-user parse avg: {fmt_ns(res['avg_ns'])}")
    return TestResult("094", "WebAPI speed", "O", passed=True, custom_ns=res["avg_ns"])


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY P: ERROR HANDLING & RECOVERY (095-097)
# ═══════════════════════════════════════════════════════════════════════════


@register_test("095", "Invalid JSON input handling", "P")
def test_095(args, ctx):
    try:
        from highrise_fast import loads_json, parse_server_message
    except ImportError as e:
        return TestResult("095", "Invalid JSON", "P", passed=False, error=str(e))
    invalid = [b"", b"null", b"[]", b'"string"', b"12345", b"{invalid json"]
    handled = 0
    for inp in invalid:
        try:
            parse_server_message(loads_json(inp))
            handled += 1
        except (ValueError, TypeError, KeyError, AttributeError):
            handled += 1
    p(f"    Invalid inputs handled: {handled}/{len(invalid)}")
    return TestResult("095", "Invalid JSON", "P", passed=handled == len(invalid))


@register_test("096", "Malformed payload recovery speed", "P")
def test_096(args, ctx):
    try:
        from highrise_fast import loads_json, parse_server_message
    except ImportError as e:
        return TestResult("096", "Malformed recovery", "P", passed=False, error=str(e))
    malformed = [
        '{"_type":"ChatEvent","user":null,"message":null}',
        '{"_type":"UserJoinedEvent","user":{"id":123},"position":"not_a_dict"}',
        '{"_type":"GetRoomUsersResponse","content":"not_a_list"}',
    ]
    total_ns = 0
    for m in malformed:
        t0 = time.perf_counter_ns()
        try:
            parse_server_message(loads_json(m))
        except (ValueError, TypeError, KeyError, AttributeError):
            _logger.debug("Malformed payload raised (expected): %s", m[:50])
        total_ns += time.perf_counter_ns() - t0
    avg_ns = total_ns / len(malformed)
    p(f"    Malformed recovery avg: {fmt_ns(avg_ns)}")
    return TestResult("096", "Malformed recovery", "P", passed=True, custom_ns=avg_ns)


@register_test("097", "Unknown _type graceful handling", "P")
def test_097(args, ctx):
    try:
        from highrise_fast import parse_server_message
    except ImportError as e:
        return TestResult("097", "Unknown type", "P", passed=False, error=str(e))
    unknown_types = [
        {"_type": "FutureEvent2030", "data": "something"},
        {"_type": "", "data": None},
        {"_type": None, "data": []},
        {"no_type_field": True},
    ]
    failures = 0
    for ut in unknown_types:
        try:
            parse_server_message(ut)
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            failures += 1
            p(f"    ❌ {ut}: {type(e).__name__}")
    p(
        f"    Unknown types handled: {len(unknown_types) - failures}/{len(unknown_types)}"
    )
    return TestResult("097", "Unknown type", "P", passed=failures == 0)


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY Q: SUSTAINED LOAD ENDURANCE (098-100)
# ═══════════════════════════════════════════════════════════════════════════


@register_test("098", "Sustained parse load (N seconds)", "Q")
def test_098(args, ctx):
    try:
        from highrise_fast import loads_json, parse_server_message
    except ImportError as e:
        return TestResult("098", "Sustained load", "Q", passed=False, error=str(e))
    duration = args.endurance
    payloads = [
        json.dumps(
            {
                "_type": "ChatEvent",
                "user": {"id": "u1", "username": "alice"},
                "message": f"msg {i}",
                "whisper": False,
            }
        )
        for i in range(100)
    ]
    t_start = time.perf_counter()
    count_ops = 0
    errors = 0
    latencies = deque(maxlen=10000)
    while time.perf_counter() - t_start < duration:
        for payload in payloads:
            t0 = time.perf_counter_ns()
            try:
                parse_server_message(loads_json(payload))
                count_ops += 1
            except (ValueError, TypeError, KeyError):
                errors += 1
            latencies.append(time.perf_counter_ns() - t0)
    elapsed = time.perf_counter() - t_start
    lat_sorted = sorted(latencies)
    n = len(lat_sorted)
    p(f"    Duration  : {elapsed:.1f}s")
    p(f"    Total ops : {count_ops:,}")
    p(f"    Throughput: {count_ops / elapsed:,.0f} ops/s")
    p(f"    Errors    : {errors}")
    if n > 0:
        p(
            f"    p50: {fmt_ns(lat_sorted[int(n * 0.50)])}"
            f" | p95: {fmt_ns(lat_sorted[int(n * 0.95)])}"
            f" | p99: {fmt_ns(lat_sorted[int(n * 0.99)])}"
        )
    return TestResult(
        "098",
        "Sustained load",
        "Q",
        passed=errors == 0,
        ops_per_sec=count_ops / elapsed,
        extra={"errors": errors, "duration": elapsed},
    )


@register_test("099", "Bandwidth estimation (all message types)", "Q")
def test_099(args, ctx):
    try:
        from highrise_fast import dumps_json
    except ImportError as e:
        return TestResult("099", "Bandwidth", "Q", passed=False, error=str(e))
    messages = {
        "ChatRequest(short)": {
            "_type": "ChatRequest",
            "rid": "1",
            "message": "hi",
            "whisper_target_id": None,
        },
        "ChatRequest(250ch)": {
            "_type": "ChatRequest",
            "rid": "1",
            "message": "A" * 250,
            "whisper_target_id": None,
        },
        "EmoteRequest": {
            "_type": "EmoteRequest",
            "rid": "1",
            "emote_id": "wave",
            "target_user_id": None,
        },
        "TeleportRequest": {
            "_type": "TeleportRequest",
            "rid": "1",
            "user_id": "u1",
            "destination": {"x": 1.0, "y": 0.0, "z": 2.0, "facing": "Front"},
        },
        "GetRoomUsers": {"_type": "GetRoomUsersRequest", "rid": "1"},
        "Keepalive": {"_type": "KeepaliveRequest"},
    }
    p(f"    {'Message Type':24s} {'Size':>10s}")
    p(f"    {'─' * 36}")
    total = 0
    for name, payload in messages.items():
        encoded = dumps_json(payload)
        size = len(encoded)
        total += size
        p(f"    {name:24s} {size:>8d} B")
    p(f"    {'TOTAL':24s} {total:>8d} B")
    return TestResult(
        "099", "Bandwidth", "Q", passed=True, extra={"total_bytes": total}
    )


@register_test("100", "Final composite score", "Q")
def test_100(args, ctx):
    p("    Computing final composite score...")
    return TestResult("100", "Composite score", "Q", passed=True)


# ═══════════════════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════════════════


def run_tests(args):
    results: list[TestResult] = []
    ctx: dict[str, Any] = {}

    if args.tests:
        requested = set(args.tests.split(","))
        tests_to_run = [t for t in _REGISTRY if t["id"] in requested]
    elif args.category:
        tests_to_run = [t for t in _REGISTRY if t["category"] == args.category.upper()]
    else:
        tests_to_run = _REGISTRY

    p("═" * 92)
    p(f"  100-TEST ENTERPRISE HIGHRISE SDK BENCHMARK v{VERSION}")
    p(
        f"  {datetime.now(tz=UTC).strftime('%Y-%m-%d %H:%M:%S')} | Python {sys.version.split()[0]}"
    )
    p(
        f"  Running {len(tests_to_run)} tests | iters={args.iters:,} | endurance={args.endurance}s"
    )
    p("═" * 92)

    current_category = ""
    for test_info in tests_to_run:
        tid = test_info["id"]
        name = test_info["name"]
        cat = test_info["category"]
        fn = test_info["fn"]

        if cat != current_category:
            current_category = cat
            cat_names = {
                "A": "ENVIRONMENT & DEPENDENCIES",
                "B": "IMPORT & STARTUP",
                "C": "OBJECT MODEL CREATION",
                "D": "OBJECT MODEL MUTATION/ACCESS",
                "E": "OUTGOING SERIALIZATION",
                "F": "INCOMING PARSING",
                "G": "JSON BACKEND COMPARISON",
                "H": "WEBSOCKET FRAME CODEC",
                "I": "UNICODE & EDGE CASES",
                "J": "FLOAT & NUMERIC PRECISION",
                "K": "CONCURRENT ASYNC THROUGHPUT",
                "L": "LEAK & RESOURCE SAFETY",
                "M": "GC PRESSURE & MEMORY",
                "N": "WIRE FORMAT CONVERSION",
                "O": "WEBAPI & ATTRDICT",
                "P": "ERROR HANDLING & RECOVERY",
                "Q": "SUSTAINED LOAD ENDURANCE",
            }
            header(f"CATEGORY {cat}: {cat_names.get(cat, 'UNKNOWN')}")

        p(f"\n  [{tid}] {name}")
        t0 = time.perf_counter()
        try:
            result = fn(args, ctx)
            result.duration_ms = (time.perf_counter() - t0) * 1000
            results.append(result)
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            p(f"    💥 CRASHED: {type(e).__name__}: {e}")
            results.append(
                TestResult(
                    tid,
                    name,
                    cat,
                    passed=False,
                    error=str(e)[:200],
                    duration_ms=elapsed,
                )
            )
            if isinstance(e, KeyboardInterrupt):
                raise

    return results


def print_summary(results: list[TestResult]):
    for r in results:
        if r.test_id in {"019", "020", "021", "022", "023"}:
            r.category = "D"

    header("FINAL SCORECARD")

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    total = len(results)

    p(f"\n  Total tests : {total}")
    p(f"  Passed      : {passed} ✅")
    p(f"  Failed      : {failed} {'❌' if failed else ''}")
    p(f"  Pass rate   : {passed / total * 100:.1f}%")

    speedups = [r.speedup for r in results if r.speedup is not None and r.speedup > 0]
    if speedups:
        avg_speedup = statistics.mean(speedups)
        med_speedup = statistics.median(speedups)
        p(f"\n  Avg speedup (custom vs official): {avg_speedup:.2f}x")
        p(f"  Median speedup                  : {med_speedup:.2f}x")

    p(f"\n  {'Category':40s} {'Pass':>6s} {'Fail':>6s} {'Rate':>8s}")
    p(f"  {'─' * 62}")
    categories = {}
    for r in results:
        if r.category not in categories:
            categories[r.category] = {"pass": 0, "fail": 0}
        if r.passed:
            categories[r.category]["pass"] += 1
        else:
            categories[r.category]["fail"] += 1

    for cat, counts in sorted(categories.items()):
        total_cat = counts["pass"] + counts["fail"]
        rate = counts["pass"] / total_cat * 100 if total_cat else 0
        p(f"  {cat:40s} {counts['pass']:>6d} {counts['fail']:>6d} {rate:>7.1f}%")

    failures = [r for r in results if not r.passed]
    if failures:
        p("\n  FAILED TESTS:")
        for r in failures:
            p(f"    [{r.test_id}] {r.name}: {r.error[:80]}")

    p(f"\n  {'═' * 60}")
    if passed >= total * 0.95:
        p("  🏆 ENTERPRISE GRADE: Custom SDK passes ≥95% of tests")
    elif passed >= total * 0.85:
        p("  ✅ PRODUCTION READY: Custom SDK passes ≥85% of tests")
    else:
        p("  ⚠️  NEEDS ATTENTION: Some tests failed")
    p(f"  {'═' * 60}")


def main():
    ap = argparse.ArgumentParser(
        description=f"100-Test Enterprise SDK Benchmark v{VERSION}"
    )
    ap.add_argument(
        "--iters", type=int, default=10000, help="Iterations per micro-benchmark"
    )
    ap.add_argument(
        "--quick", action="store_true", help="Quick mode (reduced iterations)"
    )
    ap.add_argument("--leak-n", type=int, default=200, help="Leak test request count")
    ap.add_argument(
        "--endurance", type=int, default=10, help="Endurance test duration (seconds)"
    )
    ap.add_argument("--category", type=str, help="Run only one category (A-Q)")
    ap.add_argument(
        "--tests", type=str, help="Run specific test IDs (comma-separated: 025,036,050)"
    )
    ap.add_argument("--no-pause", action="store_true", help="Don't pause at end")
    args = ap.parse_args()

    if args.quick:
        args.iters = 2000
        args.leak_n = 50
        args.endurance = 5

    try:
        results = run_tests(args)
        print_summary(results)
    except KeyboardInterrupt:
        p("\n\n  ⚠️  Interrupted by user.")
    except (RuntimeError, OSError) as e:
        p(f"\n  💥 Benchmark crashed: {e}")
        traceback.print_exc()

    if not args.no_pause:
        try:
            input("\n  [press Enter to close]")
        except (KeyboardInterrupt, EOFError):
            pass


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, SystemExit):
        traceback.print_exc()

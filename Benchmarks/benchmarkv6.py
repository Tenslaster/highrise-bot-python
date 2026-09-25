#!/usr/bin/env python3
"""
BENCHMARK V6 — DEBUG-FIRST & PROTOCOL-GAP SUITE
==============================================

Focus areas V1-V5 do not cover:
  01. debug_payload / explain_debug multi-error collection
  02. Reason-code and path accuracy assertions
  03. Type-coercion edge cases (strict must reject)
  04. Semantic bounds edge cases
  05. Protocol coverage for all 46 _DISPATCH handlers
  06. Nested structure edge cases
  07. List / tuple / array edge cases
  08. String / encoding edge cases
  09. Integer / float / number edge cases
  10. Boolean / None / null edge cases
  11. Model <-> validator consistency
  12. Web API model coverage (skips cleanly if models_webapi absent)
  13. Async / concurrency / state machine
  14. Encoding / serialization edge cases

Usage:
    python benchmarkv6.py --quick
    python benchmarkv6.py
    python benchmarkv6.py --category 01_debug
    python benchmarkv6.py --filter facing
    python benchmarkv6.py --list
    python benchmarkv6.py --json results.json
"""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import copy
import json
import sys
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Import block
# ---------------------------------------------------------------------------

try:
    import highrise_fast as hf  # noqa: F401  (import presence check)
    from highrise_fast.validation import (
        BASE_PAYLOADS,
        HighriseFastValidationError,
        ReasonCode,
        ValidationErrorDetail,  # noqa: F401
        _debug_default_for,
        _debug_get_value,
        _debug_set_value,
        _debug_tokens,
        debug_payload,
        explain_debug,
        validate_server_message,
    )

    _IMPORT_OK = True
    _IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover
    _IMPORT_OK = False
    _IMPORT_ERROR = exc


# ═══════════════════════════════════════════════════════════════════════════
# Result model
# ═══════════════════════════════════════════════════════════════════════════


class SkipTest(Exception):
    """Raised by a test case to indicate it should be skipped."""


@dataclass
class CaseResult:
    name: str
    category: str
    status: str = "ok"  # ok | fail | error | skip
    duration_s: float = 0.0
    detail: str = ""


@dataclass
class Suite:
    cases: list[tuple[str, str, Callable[[], None]]] = field(default_factory=list)
    results: list[CaseResult] = field(default_factory=list)

    def add(self, name: str, category: str, fn: Callable[[], None]) -> None:
        self.cases.append((name, category, fn))

    def run(self, filter_: str = "", category: str = "", quick: bool = False) -> None:
        # Filter first, then apply --quick against the filtered list.
        selected = [
            (name, cat, fn)
            for (name, cat, fn) in self.cases
            if (not filter_ or filter_ in name) and (not category or category == cat)
        ]

        for idx, (name, cat, fn) in enumerate(selected, 1):
            if quick and idx % 3 != 1:
                self.results.append(CaseResult(name, cat, "skip"))
                continue

            t0 = time.perf_counter()
            try:
                fn()
                self.results.append(
                    CaseResult(name, cat, "ok", time.perf_counter() - t0)
                )
                print(f"  [PASS] {name}")
            except SkipTest as exc:
                self.results.append(
                    CaseResult(name, cat, "skip", time.perf_counter() - t0, str(exc))
                )
                print(f"  [SKIP] {name}: {exc}")
            except AssertionError as exc:
                self.results.append(
                    CaseResult(name, cat, "fail", time.perf_counter() - t0, str(exc))
                )
                print(f"  [FAIL] {name}: {exc}")
            except Exception as exc:
                self.results.append(
                    CaseResult(name, cat, "error", time.perf_counter() - t0, repr(exc))
                )
                print(f"  [ERR ] {name}: {exc!r}")

    def summary(self) -> dict:
        by_cat: dict[str, dict[str, int]] = defaultdict(
            lambda: {"ok": 0, "fail": 0, "error": 0, "skip": 0}
        )
        for r in self.results:
            by_cat[r.category][r.status] += 1
        total_ok = sum(1 for r in self.results if r.status == "ok")
        total_fail = sum(1 for r in self.results if r.status == "fail")
        total_error = sum(1 for r in self.results if r.status == "error")
        total_skip = sum(1 for r in self.results if r.status == "skip")
        return {
            "total": len(self.results),
            "ok": total_ok,
            "fail": total_fail,
            "error": total_error,
            "skip": total_skip,
            "by_category": dict(by_cat),
        }


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def expect_validation_error(
    payload: Any,
    *,
    strict: bool = True,
    strict_semantic: bool = False,
) -> HighriseFastValidationError:
    """Assert that validate_server_message rejects the payload."""
    try:
        validate_server_message(payload, strict=strict, strict_semantic=strict_semantic)
    except HighriseFastValidationError as exc:
        return exc
    raise AssertionError(
        f"expected HighriseFastValidationError, got success for {payload!r}"
    )


def expect_ok(
    payload: Any,
    *,
    strict: bool = True,
    strict_semantic: bool = False,
) -> None:
    """Assert that validate_server_message accepts the payload."""
    try:
        validate_server_message(payload, strict=strict, strict_semantic=strict_semantic)
    except HighriseFastValidationError as exc:
        raise AssertionError(f"expected success, got: {exc.short()}") from exc


def clone(payload: dict) -> dict:
    return copy.deepcopy(payload)


def base(name: str) -> dict:
    if name not in BASE_PAYLOADS:
        raise KeyError(
            f"no BASE_PAYLOAD for {name!r}; available: {sorted(BASE_PAYLOADS)[:10]}..."
        )
    return clone(BASE_PAYLOADS[name])


def _run_async(coro):
    """Run a coroutine safely whether or not a loop is already running."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Already inside an event loop — run in a worker thread with its own loop.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


# ═══════════════════════════════════════════════════════════════════════════
# 01 — debug_payload / explain_debug
# ═══════════════════════════════════════════════════════════════════════════


def build_debug_cases(s: Suite) -> None:
    cat = "01_debug"

    def valid_chat_ok():
        report = debug_payload(base("ChatEvent"))
        assert report["ok"] is True, report
        assert report["issue_count"] == 0, report

    s.add("debug_valid_chat_ok", cat, valid_chat_ok)

    def multi_error_count():
        bad = {
            "_type": "ChatEvent",
            "user": {"id": 123, "username": True},
            "message": None,
            "whisper": "yes",
        }
        report = debug_payload(bad)
        assert report["issue_count"] == 4, report
        assert report["ok"] is False

    s.add("debug_multi_error_count", cat, multi_error_count)

    def stops_on_missing_type():
        report = debug_payload({"user": {}, "message": "x", "whisper": False})
        assert report["issue_count"] == 1, report
        assert report["issues"][0]["reason_code"] == ReasonCode.MISSING_FIELD

    s.add("debug_stops_on_missing_type", cat, stops_on_missing_type)

    def stops_on_unknown_type():
        report = debug_payload({"_type": "FakeEvent", "x": 1, "y": 2})
        assert report["issue_count"] == 1, report
        assert report["issues"][0]["reason_code"] == ReasonCode.UNKNOWN_TYPE

    s.add("debug_stops_on_unknown_type", cat, stops_on_unknown_type)

    def stops_on_non_dict():
        report = debug_payload(["not", "a", "dict"])
        assert report["issue_count"] == 1, report
        assert report["issues"][0]["path"] == "$"

    s.add("debug_stops_on_non_dict", cat, stops_on_non_dict)

    def type_non_str():
        report = debug_payload({"_type": 123, "x": 1})
        assert report["issue_count"] == 1, report
        assert report["issues"][0]["path"] == "$._type"

    s.add("debug_type_non_str", cat, type_non_str)

    def max_issues_cap():
        bad = base("ChatEvent")
        bad["user"] = {"id": 1, "username": 2}
        bad["message"] = 3
        bad["whisper"] = 4
        report = debug_payload(bad, max_issues=2)
        assert report["issue_count"] == 2, report

    s.add("debug_max_issues_cap", cat, max_issues_cap)

    def semantic_collected():
        bad = base("ChatEvent")
        bad["message"] = "A" * 2000
        report = debug_payload(bad, strict_semantic=True)
        assert report["ok"] is False
        assert any(
            i["reason_code"] == ReasonCode.INVALID_LENGTH for i in report["issues"]
        ), report

    s.add("debug_semantic_collected", cat, semantic_collected)

    def no_mutation():
        original = base("ChatEvent")
        snapshot = copy.deepcopy(original)
        debug_payload(original)
        assert original == snapshot, "debug_payload mutated its input"

    s.add("debug_no_mutation", cat, no_mutation)

    def payload_key_returns_original():
        original = base("ChatEvent")
        report = debug_payload(original)
        assert report["payload"] == original

    s.add("debug_payload_key_returns_original", cat, payload_key_returns_original)

    def explain_ok():
        text = explain_debug(base("ChatEvent"))
        assert text == "ChatEvent: OK", text

    s.add("debug_explain_ok", cat, explain_ok)

    def explain_reject():
        bad = {
            "_type": "ChatEvent",
            "user": {"id": 1, "username": "x"},
            "message": "m",
            "whisper": False,
        }
        text = explain_debug(bad)
        assert "REJECTED" in text, text
        assert "WRONG_TYPE" in text, text
        assert "$.user.id" in text, text

    s.add("debug_explain_reject", cat, explain_reject)

    def tokens_parse():
        assert _debug_tokens("$.user.id") == ["user", "id"]
        assert _debug_tokens("$.content[0].amount") == ["content", 0, "amount"]
        assert _debug_tokens("$.users[0][1]") == ["users", 0, 1]
        assert _debug_tokens("$") == []
        assert _debug_tokens("$._type") == ["_type"]

    s.add("debug_tokens_parse", cat, tokens_parse)

    def default_for_primitives():
        assert _debug_default_for("str", "$.x", "") == "debug"
        assert _debug_default_for("int", "$.x", "") == 0
        assert _debug_default_for("float", "$.x", "") == 0.0
        assert _debug_default_for("bool", "$.x", "") is False
        assert _debug_default_for("dict", "$.x", "") == {}
        assert _debug_default_for("list", "$.x", "") == []

    s.add("debug_default_for_primitives", cat, default_for_primitives)

    def default_for_literals():
        # Direct assertions. Fails loudly if any literal default changes.
        assert _debug_default_for("literal", "$.position.facing", "") == "FrontRight"
        assert _debug_default_for("literal", "$.reaction", "") == "heart"
        assert _debug_default_for("literal", "$.moderationType", "") == "mute"
        assert _debug_default_for("literal", "$.users[0][1]", "") == "voice"

    s.add("debug_default_for_literals", cat, default_for_literals)

    def default_for_semantic_uses_current_value():
        # The semantic-error fallback. Repairs float → 0.0, int → 0, str → "debug".
        assert (
            _debug_default_for("[-2000.0, 2000.0]", "$.position.x", "", 9999.0) == 0.0
        )
        assert _debug_default_for(">=0", "$.content[0].amount", "", -100) == 0
        assert _debug_default_for("<=1024", "$.message", "", "A" * 2000) == "debug"
        # bool must be checked before int in the fallback.
        assert _debug_default_for(">=0", "$.flag", "", True) is False

    s.add(
        "debug_default_for_semantic_uses_current",
        cat,
        default_for_semantic_uses_current_value,
    )

    def get_value_basic():
        p = {"user": {"id": "u1", "tags": ["a", "b"]}}
        assert _debug_get_value(p, "$.user.id") == "u1"
        assert _debug_get_value(p, "$.user.tags[1]") == "b"
        assert _debug_get_value(p, "$.user.tags[5]") is None
        assert _debug_get_value(p, "$.missing.path") is None
        assert _debug_get_value(p, "$") == p

    s.add("debug_get_value_basic", cat, get_value_basic)

    def set_value_nested():
        p: dict = {}
        assert _debug_set_value(p, "$.a.b.c", "x") is True
        assert p == {"a": {"b": {"c": "x"}}}

    s.add("debug_set_value_nested", cat, set_value_nested)

    def set_value_list():
        p: list = []
        assert _debug_set_value(p, "$[2]", "x") is True
        assert p[2] == "x"

    s.add("debug_set_value_list", cat, set_value_list)

    def set_value_refuses_type():
        p = {"_type": "ChatEvent"}
        assert _debug_set_value(p, "$._type", "X") is False
        assert p["_type"] == "ChatEvent"

    s.add("debug_set_value_refuses_type", cat, set_value_refuses_type)

    def dedup_same_error():
        bad = base("ChatEvent")
        bad["message"] = None
        report = debug_payload(bad)
        paths = [i["path"] for i in report["issues"]]
        assert paths.count("$.message") == 1, report

    s.add("debug_dedup_same_error", cat, dedup_same_error)

    def first_error_matches():
        bad = base("ChatEvent")
        bad["message"] = None
        bad["whisper"] = "yes"
        report = debug_payload(bad)
        assert report["issues"], "expected at least one issue"
        assert report["first_error"] is not None
        # first_error is the rendered string of issues[0].
        assert "[WRONG_TYPE]" in report["first_error"], report["first_error"]
        assert "$.message" in report["first_error"], report["first_error"]

    s.add("debug_first_error_matches", cat, first_error_matches)

    def no_phantom_after_repair_float():
        """Regression guard: a semantic float error must not spawn a phantom
        WRONG_TYPE issue from the repair step."""
        bad = base("UserMovedEvent")
        bad["position"]["x"] = 9999.0
        report = debug_payload(bad, strict_semantic=True)
        oob = [
            i for i in report["issues"] if i["reason_code"] == ReasonCode.OUT_OF_BOUNDS
        ]
        wrong = [
            i for i in report["issues"] if i["reason_code"] == ReasonCode.WRONG_TYPE
        ]
        assert len(oob) == 1, report
        assert len(wrong) == 0, f"phantom WRONG_TYPE from repair: {report}"

    s.add("debug_no_phantom_after_repair_float", cat, no_phantom_after_repair_float)

    def no_phantom_after_repair_int():
        """Same regression guard for the int/negative-amount case."""
        bad = base("GetWalletResponse")
        bad["content"][0]["amount"] = -100
        report = debug_payload(bad, strict_semantic=True)
        oob = [
            i for i in report["issues"] if i["reason_code"] == ReasonCode.OUT_OF_BOUNDS
        ]
        wrong = [
            i for i in report["issues"] if i["reason_code"] == ReasonCode.WRONG_TYPE
        ]
        assert len(oob) == 1, report
        assert len(wrong) == 0, f"phantom WRONG_TYPE from repair: {report}"

    s.add("debug_no_phantom_after_repair_int", cat, no_phantom_after_repair_int)

    def deeply_nested_invalid():
        bad = base("GetRoomUsersResponse")
        if bad.get("content") and len(bad["content"]) > 0:
            bad["content"][0][0]["id"] = 123
        report = debug_payload(bad)
        assert report["ok"] is False
        paths = [i["path"] for i in report["issues"]]
        assert any("id" in p for p in paths), report

    s.add("debug_deeply_nested_invalid", cat, deeply_nested_invalid)


# ═══════════════════════════════════════════════════════════════════════════
# 02 — reason codes + paths
# ═══════════════════════════════════════════════════════════════════════════


def build_reason_path_cases(s: Suite) -> None:
    cat = "02_reason_path"

    def missing_str():
        bad = base("ChatEvent")
        del bad["message"]
        exc = expect_validation_error(bad)
        assert exc.errors[0].reason_code == ReasonCode.MISSING_FIELD
        assert exc.errors[0].path == "$.message"

    s.add("reason_missing_str", cat, missing_str)

    def wrong_type_str():
        bad = base("ChatEvent")
        bad["message"] = 123
        exc = expect_validation_error(bad)
        assert exc.errors[0].reason_code == ReasonCode.WRONG_TYPE
        assert exc.errors[0].path == "$.message"

    s.add("reason_wrong_type_str", cat, wrong_type_str)

    def wrong_type_bool():
        bad = base("ChatEvent")
        bad["whisper"] = "yes"
        exc = expect_validation_error(bad)
        assert exc.errors[0].reason_code == ReasonCode.WRONG_TYPE
        assert exc.errors[0].path == "$.whisper"

    s.add("reason_wrong_type_bool", cat, wrong_type_bool)

    def unknown_type():
        exc = expect_validation_error({"_type": "FakeEvent"})
        assert exc.errors[0].reason_code == ReasonCode.UNKNOWN_TYPE
        assert exc.errors[0].path == "$._type"

    s.add("reason_unknown_type", cat, unknown_type)

    def missing_type():
        exc = expect_validation_error({"x": 1})
        assert exc.errors[0].reason_code == ReasonCode.MISSING_FIELD
        assert exc.errors[0].path == "$._type"

    s.add("reason_missing_type", cat, missing_type)

    def non_finite_float():
        bad = base("UserMovedEvent")
        bad["position"]["x"] = float("inf")
        exc = expect_validation_error(bad)
        assert exc.errors[0].reason_code == ReasonCode.OUT_OF_BOUNDS
        assert exc.errors[0].path == "$.position.x"

    s.add("reason_non_finite_float", cat, non_finite_float)

    def semantic_length():
        bad = base("ChatEvent")
        bad["message"] = "A" * 1025
        exc = expect_validation_error(bad, strict_semantic=True)
        assert exc.errors[0].reason_code == ReasonCode.INVALID_LENGTH

    s.add("reason_semantic_length", cat, semantic_length)

    def semantic_wallet_negative():
        bad = base("GetWalletResponse")
        bad["content"][0]["amount"] = -1
        exc = expect_validation_error(bad, strict_semantic=True)
        assert exc.errors[0].reason_code == ReasonCode.OUT_OF_BOUNDS
        assert exc.errors[0].path == "$.content[0].amount"

    s.add("reason_semantic_wallet_negative", cat, semantic_wallet_negative)

    def nested_path_user_id():
        bad = base("ChatEvent")
        bad["user"]["id"] = 123
        exc = expect_validation_error(bad)
        assert exc.errors[0].path == "$.user.id"

    s.add("path_nested_user_id", cat, nested_path_user_id)

    def tuple_path_voice():
        bad = base("VoiceEvent")
        bad["users"][0][1] = "invalid"
        exc = expect_validation_error(bad)
        assert exc.errors[0].path == "$.users[0][1]"

    s.add("path_tuple_voice", cat, tuple_path_voice)

    def list_index_path_wallet():
        bad = base("GetWalletResponse")
        bad["content"][0]["type"] = 123
        exc = expect_validation_error(bad)
        assert exc.errors[0].path == "$.content[0].type"

    s.add("path_list_index_wallet", cat, list_index_path_wallet)

    def path_for_type_field():
        exc = expect_validation_error({"_type": 123})
        assert exc.errors[0].path == "$._type"

    s.add("path_for_type_field", cat, path_for_type_field)

    def path_for_root_non_dict():
        exc = expect_validation_error("not a dict")
        assert exc.errors[0].path == "$"

    s.add("path_for_root_non_dict", cat, path_for_root_non_dict)

    def path_invalid_length_tuple():
        bad = base("VoiceEvent")
        bad["users"][0] = [{"id": "x"}, "voice", "extra"]
        exc = expect_validation_error(bad)
        assert exc.errors[0].reason_code == ReasonCode.INVALID_LENGTH

    s.add("path_invalid_length_tuple", cat, path_invalid_length_tuple)


# ═══════════════════════════════════════════════════════════════════════════
# 03 — type coercion (strict must reject)
# ═══════════════════════════════════════════════════════════════════════════


def build_type_cases(s: Suite) -> None:
    cat = "03_type_coercion"

    def str_rejects_int():
        bad = base("ChatEvent")
        bad["message"] = 123
        expect_validation_error(bad)

    s.add("type_str_rejects_int", cat, str_rejects_int)

    def str_rejects_bool():
        bad = base("ChatEvent")
        bad["message"] = True
        expect_validation_error(bad)

    s.add("type_str_rejects_bool", cat, str_rejects_bool)

    def str_rejects_none():
        bad = base("ChatEvent")
        bad["message"] = None
        expect_validation_error(bad)

    s.add("type_str_rejects_none", cat, str_rejects_none)

    def str_rejects_list():
        bad = base("ChatEvent")
        bad["message"] = []
        expect_validation_error(bad)

    s.add("type_str_rejects_list", cat, str_rejects_list)

    def str_rejects_dict():
        bad = base("ChatEvent")
        bad["message"] = {}
        expect_validation_error(bad)

    s.add("type_str_rejects_dict", cat, str_rejects_dict)

    def str_rejects_bytes():
        bad = base("ChatEvent")
        bad["message"] = b"bytes"
        expect_validation_error(bad)

    s.add("type_str_rejects_bytes", cat, str_rejects_bytes)

    def bool_rejects_int():
        bad = base("ChatEvent")
        bad["whisper"] = 1
        expect_validation_error(bad)

    s.add("type_bool_rejects_int", cat, bool_rejects_int)

    def bool_rejects_str():
        bad = base("ChatEvent")
        bad["whisper"] = "true"
        expect_validation_error(bad)

    s.add("type_bool_rejects_str", cat, bool_rejects_str)

    def bool_rejects_none():
        bad = base("ChatEvent")
        bad["whisper"] = None
        expect_validation_error(bad)

    s.add("type_bool_rejects_none", cat, bool_rejects_none)

    def int_accepts_numeric_str():
        # Documented behavior: _require_int coerces numeric strings.
        bad = base("RoomModeratedEvent")
        bad["duration"] = "60"
        expect_ok(bad)

    s.add("type_int_accepts_numeric_str", cat, int_accepts_numeric_str)

    def int_rejects_alpha_str():
        bad = base("RoomModeratedEvent")
        bad["duration"] = "abc"
        expect_validation_error(bad)

    s.add("type_int_rejects_alpha_str", cat, int_rejects_alpha_str)

    def float_rejects_nan():
        bad = base("UserMovedEvent")
        bad["position"]["x"] = float("nan")
        expect_validation_error(bad)

    s.add("type_float_rejects_nan", cat, float_rejects_nan)

    def float_rejects_inf():
        bad = base("UserMovedEvent")
        bad["position"]["y"] = float("inf")
        expect_validation_error(bad)

    s.add("type_float_rejects_inf", cat, float_rejects_inf)

    def float_rejects_neg_inf():
        bad = base("UserMovedEvent")
        bad["position"]["z"] = float("-inf")
        expect_validation_error(bad)

    s.add("type_float_rejects_neg_inf", cat, float_rejects_neg_inf)

    def literal_rejects_bad():
        bad = base("ReactionEvent")
        bad["reaction"] = "not_a_reaction"
        expect_validation_error(bad)

    s.add("type_literal_rejects_bad", cat, literal_rejects_bad)

    def literal_rejects_non_str():
        bad = base("ReactionEvent")
        bad["reaction"] = 123
        expect_validation_error(bad)

    s.add("type_literal_rejects_non_str", cat, literal_rejects_non_str)

    def list_rejects_str():
        bad = base("GetWalletResponse")
        bad["content"] = ""
        expect_validation_error(bad)

    s.add("type_list_rejects_str", cat, list_rejects_str)

    def list_rejects_dict():
        bad = base("GetWalletResponse")
        bad["content"] = {}
        expect_validation_error(bad)

    s.add("type_list_rejects_dict", cat, list_rejects_dict)

    def list_rejects_none():
        bad = base("GetWalletResponse")
        bad["content"] = None
        expect_validation_error(bad)

    s.add("type_list_rejects_none", cat, list_rejects_none)

    def dict_rejects_list():
        bad = base("ChatEvent")
        bad["user"] = []
        expect_validation_error(bad)

    s.add("type_dict_rejects_list", cat, dict_rejects_list)

    def dict_rejects_str():
        bad = base("ChatEvent")
        bad["user"] = "user_string"
        expect_validation_error(bad)

    s.add("type_dict_rejects_str", cat, dict_rejects_str)

    def dict_rejects_none():
        bad = base("ChatEvent")
        bad["user"] = None
        expect_validation_error(bad)

    s.add("type_dict_rejects_none", cat, dict_rejects_none)


# ═══════════════════════════════════════════════════════════════════════════
# 04 — semantic bounds
# ═══════════════════════════════════════════════════════════════════════════


def build_semantic_cases(s: Suite) -> None:
    cat = "04_semantic"

    def chat_len_1024_ok():
        good = base("ChatEvent")
        good["message"] = "A" * 1024
        expect_ok(good, strict_semantic=True)

    s.add("semantic_chat_len_1024_ok", cat, chat_len_1024_ok)

    def chat_len_1025_reject():
        bad = base("ChatEvent")
        bad["message"] = "A" * 1025
        expect_validation_error(bad, strict_semantic=True)

    s.add("semantic_chat_len_1025_reject", cat, chat_len_1025_reject)

    def chat_len_0_ok():
        good = base("ChatEvent")
        good["message"] = ""
        expect_ok(good, strict_semantic=True)

    s.add("semantic_chat_len_0_ok", cat, chat_len_0_ok)

    def pos_exact_bound_ok():
        good = base("UserMovedEvent")
        good["position"]["x"] = 2000.0
        expect_ok(good, strict_semantic=True)

    s.add("semantic_pos_exact_bound_ok", cat, pos_exact_bound_ok)

    def pos_neg_bound_ok():
        good = base("UserMovedEvent")
        good["position"]["x"] = -2000.0
        expect_ok(good, strict_semantic=True)

    s.add("semantic_pos_neg_bound_ok", cat, pos_neg_bound_ok)

    def pos_just_out_reject():
        bad = base("UserMovedEvent")
        bad["position"]["x"] = 2000.1
        expect_validation_error(bad, strict_semantic=True)

    s.add("semantic_pos_just_out_reject", cat, pos_just_out_reject)

    def pos_neg_just_out_reject():
        bad = base("UserMovedEvent")
        bad["position"]["x"] = -2000.1
        expect_validation_error(bad, strict_semantic=True)

    s.add("semantic_pos_neg_just_out_reject", cat, pos_neg_just_out_reject)

    def pos_all_three_out():
        bad = base("UserMovedEvent")
        bad["position"]["x"] = 9999.0
        bad["position"]["y"] = 9999.0
        bad["position"]["z"] = 9999.0
        report = debug_payload(bad, strict_semantic=True)

        oob = [
            i for i in report["issues"] if i["reason_code"] == ReasonCode.OUT_OF_BOUNDS
        ]
        assert len(oob) == 3, f"expected 3 OOB, got {len(oob)}: {report}"

        paths = sorted(i["path"] for i in oob)
        assert paths == ["$.position.x", "$.position.y", "$.position.z"], paths

        # Regression guard: no phantom WRONG_TYPE from the repair step.
        wrong = [
            i for i in report["issues"] if i["reason_code"] == ReasonCode.WRONG_TYPE
        ]
        assert len(wrong) == 0, f"phantom WRONG_TYPE: {report}"

    s.add("semantic_pos_all_three_out", cat, pos_all_three_out)

    def wallet_zero_ok():
        good = base("GetWalletResponse")
        good["content"][0]["amount"] = 0
        expect_ok(good, strict_semantic=True)

    s.add("semantic_wallet_zero_ok", cat, wallet_zero_ok)

    def wallet_negative_reject():
        bad = base("GetWalletResponse")
        bad["content"][0]["amount"] = -1
        expect_validation_error(bad, strict_semantic=True)

    s.add("semantic_wallet_negative_reject", cat, wallet_negative_reject)

    def wallet_both_negative():
        bad = base("GetWalletResponse")
        # Force two items so "both" is meaningful.
        bad["content"] = [
            {"type": "gold", "amount": -100},
            {"type": "bubbles", "amount": -50},
        ]
        report = debug_payload(bad, strict_semantic=True)

        neg = [
            i
            for i in report["issues"]
            if i["reason_code"] == ReasonCode.OUT_OF_BOUNDS and "amount" in i["path"]
        ]
        assert len(neg) == 2, f"expected 2, got {len(neg)}: {report}"

        paths = sorted(i["path"] for i in neg)
        assert paths == ["$.content[0].amount", "$.content[1].amount"], paths

        wrong = [
            i for i in report["issues"] if i["reason_code"] == ReasonCode.WRONG_TYPE
        ]
        assert len(wrong) == 0, f"phantom WRONG_TYPE: {report}"

    s.add("semantic_wallet_both_negative", cat, wallet_both_negative)

    def multi_semantic_collected():
        bad = base("ChatEvent")
        bad["message"] = "A" * 2000
        bad["user"]["id"] = 123
        report = debug_payload(bad, strict_semantic=True)
        assert report["ok"] is False
        assert report["issue_count"] >= 2, report

    s.add("semantic_multi_collected", cat, multi_semantic_collected)

    def chat_with_unicode_emoji():
        good = base("ChatEvent")
        good["message"] = "Hello! 🎉🎊 🚀" * 50
        expect_ok(good, strict_semantic=True)

    s.add("semantic_chat_unicode_emoji", cat, chat_with_unicode_emoji)


# ═══════════════════════════════════════════════════════════════════════════
# 05 — protocol coverage
# ═══════════════════════════════════════════════════════════════════════════


def build_protocol_cases(s: Suite) -> None:
    cat = "05_protocol"

    dispatch_keys = [
        "ChatEvent",
        "UserJoinedEvent",
        "UserLeftEvent",
        "UserMovedEvent",
        "EmoteEvent",
        "ReactionEvent",
        "TipReactionEvent",
        "VoiceEvent",
        "ChannelEvent",
        "RoomModeratedEvent",
        "MessageEvent",
        "Error",
        "GetWalletResponse",
        "GetRoomUsersResponse",
        "GetBackpackResponse",
        "ChangeBackpackResponse",
        "GetRoomPrivilegeResponse",
        "CheckVoiceChatResponse",
        "GetUserOutfitResponse",
        "GetConversationsResponse",
        "SendMessageResponse",
        "SendBulkMessageResponse",
        "GetMessagesResponse",
        "LeaveConversationResponse",
        "BuyVoiceTimeResponse",
        "BuyRoomBoostResponse",
        "TipUserResponse",
        "GetInventoryResponse",
        "SetOutfitResponse",
        "BuyItemResponse",
        "MessageMediaResponse",
        "ChatResponse",
        "EmoteResponse",
        "ReactionResponse",
        "IndicatorResponse",
        "ChannelResponse",
        "KeepaliveResponse",
        "TeleportResponse",
        "FloorHitResponse",
        "AnchorHitResponse",
        "ModerateRoomResponse",
        "ChangeRoomPrivilegeResponse",
        "MoveUserToRoomResponse",
        "InviteSpeakerResponse",
        "RemoveSpeakerResponse",
        "SessionMetadata",
    ]

    for name in dispatch_keys:

        def make_validator(payload_name: str = name):
            def _v():
                if payload_name in BASE_PAYLOADS:
                    expect_ok(BASE_PAYLOADS[payload_name])
                else:
                    try:
                        validate_server_message({"_type": payload_name})
                    except HighriseFastValidationError:
                        pass
                    except Exception as exc:
                        raise AssertionError(
                            f"unexpected crash for {payload_name}: {exc!r}"
                        ) from exc

            return _v

        s.add(f"protocol_{name}_base", cat, make_validator())

    probes = [
        ("ChatEvent", "user"),
        ("ChatEvent", "message"),
        ("ChatEvent", "whisper"),
        ("UserJoinedEvent", "user"),
        ("UserJoinedEvent", "position"),
        ("UserLeftEvent", "user"),
        ("UserMovedEvent", "user"),
        ("UserMovedEvent", "position"),
        ("EmoteEvent", "user"),
        ("EmoteEvent", "emote_id"),
        ("ReactionEvent", "user"),
        ("ReactionEvent", "reaction"),
        ("ReactionEvent", "receiver"),
        ("TipReactionEvent", "sender"),
        ("TipReactionEvent", "receiver"),
        ("TipReactionEvent", "item"),
        ("VoiceEvent", "users"),
        ("VoiceEvent", "seconds_left"),
        ("ChannelEvent", "sender_id"),
        ("ChannelEvent", "msg"),
        ("RoomModeratedEvent", "moderatorId"),
        ("RoomModeratedEvent", "targetUserId"),
        ("RoomModeratedEvent", "moderationType"),
        ("SessionMetadata", "user_id"),
        ("SessionMetadata", "room_info"),
        ("Error", "message"),
        ("GetWalletResponse", "content"),
        ("GetRoomUsersResponse", "content"),
        ("GetInventoryResponse", "items"),
        ("GetUserOutfitResponse", "outfit"),
    ]

    for payload_name, field_name in probes:

        def make_probe(pn: str = payload_name, fn: str = field_name):
            def _p():
                if pn not in BASE_PAYLOADS:
                    raise SkipTest(f"no BASE_PAYLOAD for {pn}")
                bad = base(pn)
                if fn not in bad:
                    raise SkipTest(f"{fn} not present in {pn}")
                del bad[fn]
                exc = expect_validation_error(bad)
                assert exc.errors[0].reason_code == ReasonCode.MISSING_FIELD
                assert exc.errors[0].path == f"$.{fn}"

            return _p

        s.add(f"protocol_missing_{payload_name}_{field_name}", cat, make_probe())

    def session_metadata_room_info_missing_owner():
        bad = base("SessionMetadata")
        del bad["room_info"]["owner_id"]
        exc = expect_validation_error(bad)
        assert exc.errors[0].path == "$.room_info.owner_id"

    s.add(
        "protocol_session_metadata_missing_owner",
        cat,
        session_metadata_room_info_missing_owner,
    )

    def voice_event_bad_row_length():
        bad = base("VoiceEvent")
        bad["users"][0] = [{"id": "x"}]
        expect_validation_error(bad)

    s.add("protocol_voice_event_bad_row_length", cat, voice_event_bad_row_length)

    def voice_event_row_not_list():
        bad = base("VoiceEvent")
        bad["users"][0] = "not_a_list"
        expect_validation_error(bad)

    s.add("protocol_voice_event_row_not_list", cat, voice_event_row_not_list)


# ═══════════════════════════════════════════════════════════════════════════
# 06 — nested structure edge cases
# ═══════════════════════════════════════════════════════════════════════════


def build_nested_cases(s: Suite) -> None:
    cat = "06_nested"

    def user_as_list():
        bad = base("ChatEvent")
        bad["user"] = []
        expect_validation_error(bad)

    s.add("nested_user_as_list", cat, user_as_list)

    def user_as_string():
        bad = base("ChatEvent")
        bad["user"] = "username"
        expect_validation_error(bad)

    s.add("nested_user_as_string", cat, user_as_string)

    def user_as_null():
        bad = base("ChatEvent")
        bad["user"] = None
        expect_validation_error(bad)

    s.add("nested_user_as_null", cat, user_as_null)

    def user_id_as_int():
        bad = base("ChatEvent")
        bad["user"]["id"] = 123
        expect_validation_error(bad)

    s.add("nested_user_id_as_int", cat, user_id_as_int)

    def user_username_as_bool():
        bad = base("ChatEvent")
        bad["user"]["username"] = True
        expect_validation_error(bad)

    s.add("nested_user_username_as_bool", cat, user_username_as_bool)

    def user_with_extra_fields():
        good = base("ChatEvent")
        good["user"]["extra_field"] = "extra"
        expect_ok(good)

    s.add("nested_user_extra_fields", cat, user_with_extra_fields)

    def receiver_null():
        bad = base("ReactionEvent")
        bad["receiver"] = None
        expect_validation_error(bad)

    s.add("nested_receiver_null", cat, receiver_null)

    def emote_receiver_null_ok():
        good = base("EmoteEvent")
        good["receiver"] = None
        expect_ok(good)

    s.add("nested_emote_receiver_null", cat, emote_receiver_null_ok)

    def position_as_anchor():
        bad = base("UserMovedEvent")
        bad["position"] = {"entity_id": "anchor_1", "anchor_ix": 0}
        expect_ok(bad)

    s.add("nested_position_as_anchor", cat, position_as_anchor)

    def deep_nesting_no_crash():
        deep: dict = {"_type": "ChatEvent"}
        current = deep
        for i in range(50):
            current[f"level_{i}"] = {}
            current = current[f"level_{i}"]
        current["value"] = "leaf"
        try:
            validate_server_message(deep)
        except HighriseFastValidationError:
            pass
        except RecursionError:
            raise AssertionError("recursion limit hit at depth 50")

    s.add("nested_deep_50_no_crash", cat, deep_nesting_no_crash)

    def wallet_content_nested_bad():
        bad = base("GetWalletResponse")
        bad["content"][0]["type"] = None
        expect_validation_error(bad)

    s.add("nested_wallet_content_bad", cat, wallet_content_nested_bad)


# ═══════════════════════════════════════════════════════════════════════════
# 07 — list / tuple / array edge cases
# ═══════════════════════════════════════════════════════════════════════════


def build_list_cases(s: Suite) -> None:
    cat = "07_list"

    def content_empty_ok():
        good = base("GetWalletResponse")
        good["content"] = []
        expect_ok(good)

    s.add("list_content_empty_ok", cat, content_empty_ok)

    def users_empty_ok():
        good = base("VoiceEvent")
        good["users"] = []
        expect_ok(good)

    s.add("list_users_empty_ok", cat, users_empty_ok)

    def content_with_none_row():
        bad = base("GetWalletResponse")
        bad["content"] = [None]
        expect_validation_error(bad)

    s.add("list_content_none_row", cat, content_with_none_row)

    def content_row_too_short():
        bad = base("GetRoomUsersResponse")
        bad["content"][0] = [bad["content"][0][0]]
        expect_validation_error(bad)

    s.add("list_content_row_too_short", cat, content_row_too_short)

    def content_row_too_long():
        bad = base("GetRoomUsersResponse")
        bad["content"][0] = list(bad["content"][0]) + ["extra"]
        expect_validation_error(bad)

    s.add("list_content_row_too_long", cat, content_row_too_long)

    def users_invalid_row_at_500():
        bad = base("VoiceEvent")
        template = bad["users"][0]
        bad["users"] = [copy.deepcopy(template) for _ in range(1000)]
        bad["users"][500] = "invalid"
        exc = expect_validation_error(bad)
        assert "500" in exc.errors[0].path, exc.errors[0].path

    s.add("list_users_invalid_row_at_500", cat, users_invalid_row_at_500)

    def content_mixed_valid_invalid():
        bad = base("GetWalletResponse")
        valid_item = copy.deepcopy(bad["content"][0])
        bad["content"] = [valid_item, valid_item, {"bad": True}, valid_item]
        exc = expect_validation_error(bad)
        assert "[2]" in exc.errors[0].path, exc.errors[0].path

    s.add("list_content_mixed_valid_invalid", cat, content_mixed_valid_invalid)


# ═══════════════════════════════════════════════════════════════════════════
# 08 — string / encoding edge cases
# ═══════════════════════════════════════════════════════════════════════════


def build_string_cases(s: Suite) -> None:
    cat = "08_string"

    def str_empty_ok():
        good = base("ChatEvent")
        good["message"] = ""
        expect_ok(good)

    s.add("string_empty_ok", cat, str_empty_ok)

    def str_with_null_byte():
        good = base("ChatEvent")
        good["message"] = "hello\x00world"
        expect_ok(good)

    s.add("string_null_byte", cat, str_with_null_byte)

    def str_with_unicode():
        good = base("ChatEvent")
        good["message"] = "héllo wörld 日本語 🎉"
        expect_ok(good)

    s.add("string_unicode", cat, str_with_unicode)

    def str_with_control_chars():
        good = base("ChatEvent")
        good["message"] = "line1\nline2\ttabbed"
        expect_ok(good)

    s.add("string_control_chars", cat, str_with_control_chars)

    def str_with_rtl_override():
        good = base("ChatEvent")
        good["message"] = "text\u202eRTL_OVERRIDE"
        expect_ok(good)

    s.add("string_rtl_override", cat, str_with_rtl_override)

    def str_with_bom():
        good = base("ChatEvent")
        good["message"] = "\ufeffBOM prefix"
        expect_ok(good)

    s.add("string_bom", cat, str_with_bom)

    def string_field_rejects_bytearray():
        bad = base("ChatEvent")
        bad["message"] = bytearray(b"data")
        expect_validation_error(bad)

    s.add("string_field_rejects_bytearray", cat, string_field_rejects_bytearray)

    def string_field_rejects_memoryview():
        bad = base("ChatEvent")
        bad["message"] = memoryview(b"data")
        expect_validation_error(bad)

    s.add("string_field_rejects_memoryview", cat, string_field_rejects_memoryview)

    def string_field_accepts_subclass():
        class MyStr(str):
            pass

        good = base("ChatEvent")
        good["message"] = MyStr("subclass")
        expect_ok(good)

    s.add("string_field_accepts_subclass", cat, string_field_accepts_subclass)


# ═══════════════════════════════════════════════════════════════════════════
# 09 — integer / float / number edge cases
# ═══════════════════════════════════════════════════════════════════════════


def build_number_cases(s: Suite) -> None:
    cat = "09_number"

    def float_accepts_zero():
        good = base("UserMovedEvent")
        good["position"]["x"] = 0.0
        expect_ok(good)

    s.add("number_float_zero", cat, float_accepts_zero)

    def float_accepts_neg_zero():
        good = base("UserMovedEvent")
        good["position"]["x"] = -0.0
        expect_ok(good)

    s.add("number_float_neg_zero", cat, float_accepts_neg_zero)

    def float_rejects_overflow():
        bad = base("UserMovedEvent")
        bad["position"]["x"] = 1e309
        expect_validation_error(bad)

    s.add("number_float_overflow_reject", cat, float_rejects_overflow)

    def int_accepts_large():
        good = base("RoomModeratedEvent")
        good["duration"] = 2**63
        expect_ok(good)

    s.add("number_int_large", cat, int_accepts_large)

    def int_accepts_very_large():
        good = base("RoomModeratedEvent")
        good["duration"] = 2**128
        expect_ok(good)

    s.add("number_int_very_large", cat, int_accepts_very_large)

    def float_accepts_int():
        good = base("UserMovedEvent")
        good["position"]["x"] = 100
        expect_ok(good)

    s.add("number_float_accepts_int", cat, float_accepts_int)


# ═══════════════════════════════════════════════════════════════════════════
# 10 — boolean / None / null edge cases
# ═══════════════════════════════════════════════════════════════════════════


def build_bool_cases(s: Suite) -> None:
    cat = "10_bool"

    def bool_true_ok():
        good = base("ChatEvent")
        good["whisper"] = True
        expect_ok(good)

    s.add("bool_true_ok", cat, bool_true_ok)

    def bool_false_ok():
        good = base("ChatEvent")
        good["whisper"] = False
        expect_ok(good)

    s.add("bool_false_ok", cat, bool_false_ok)

    def bool_rejects_string_true():
        bad = base("ChatEvent")
        bad["whisper"] = "True"
        expect_validation_error(bad)

    s.add("bool_rejects_str_true", cat, bool_rejects_string_true)

    def bool_rejects_string_yes():
        bad = base("ChatEvent")
        bad["whisper"] = "yes"
        expect_validation_error(bad)

    s.add("bool_rejects_str_yes", cat, bool_rejects_string_yes)

    def optional_str_none_ok():
        good = base("Error")
        good["rid"] = None
        expect_ok(good)

    s.add("bool_optional_str_none", cat, optional_str_none_ok)

    def optional_dict_none_ok():
        good = base("SessionMetadata")
        good["rate_limits"] = None
        expect_ok(good)

    s.add("bool_optional_dict_none", cat, optional_dict_none_ok)


# ═══════════════════════════════════════════════════════════════════════════
# 11 — model ↔ validator consistency
# ═══════════════════════════════════════════════════════════════════════════


def build_consistency_cases(s: Suite) -> None:
    cat = "11_consistency"

    def position_facing_optional():
        good = base("UserMovedEvent")
        del good["position"]["facing"]
        expect_ok(good)

    s.add("consistency_position_facing_optional", cat, position_facing_optional)

    def anchor_position_int():
        payload = base("UserMovedEvent")
        payload["position"] = {"entity_id": "test", "anchor_ix": 5}
        expect_ok(payload)

    s.add("consistency_anchor_position_int", cat, anchor_position_int)

    def currency_item_required_fields():
        bad = base("GetWalletResponse")
        del bad["content"][0]["type"]
        expect_validation_error(bad)

    s.add("consistency_currency_item_type_required", cat, currency_item_required_fields)

    def duration_optional():
        good = base("RoomModeratedEvent")
        del good["duration"]
        expect_ok(good)

    s.add("consistency_duration_optional", cat, duration_optional)

    def is_new_conversation_optional():
        good = base("MessageEvent")
        del good["is_new_conversation"]
        expect_ok(good)

    s.add(
        "consistency_is_new_conversation_optional",
        cat,
        is_new_conversation_optional,
    )

    def wallet_rid_optional():
        good = base("GetWalletResponse")
        del good["rid"]
        expect_ok(good)

    s.add("consistency_wallet_rid_optional", cat, wallet_rid_optional)

    def error_do_not_reconnect_default():
        good = base("Error")
        good["do_not_reconnect"] = False
        expect_ok(good)

    s.add("consistency_error_do_not_reconnect", cat, error_do_not_reconnect_default)

    def session_metadata_optionals():
        good = base("SessionMetadata")
        for opt in ["rate_limits", "connection_id", "sdk_version"]:
            if opt in good:
                del good[opt]
        expect_ok(good)

    s.add("consistency_session_metadata_optionals", cat, session_metadata_optionals)


# ═══════════════════════════════════════════════════════════════════════════
# 12 — Web API models (skips cleanly if models_webapi absent)
# ═══════════════════════════════════════════════════════════════════════════


def build_webapi_cases(s: Suite) -> None:
    cat = "12_webapi"

    try:
        from highrise_fast.models_webapi import (  # noqa: F401
            WebApiError,
            WebApiRoom,
            WebApiUser,
            WebApiWallet,
        )

        _HAS_WEBAPI = True
    except ImportError:
        _HAS_WEBAPI = False

    def _require_webapi():
        if not _HAS_WEBAPI:
            raise SkipTest("highrise_fast.models_webapi not available")

    def webapi_user_valid():
        _require_webapi()
        user = WebApiUser(id="user123", username="testuser")
        assert user.id == "user123"
        assert user.username == "testuser"

    s.add("webapi_user_valid", cat, webapi_user_valid)

    def webapi_room_valid():
        _require_webapi()
        room = WebApiRoom(id="room1", name="Test Room")
        assert room.id == "room1"
        assert room.name == "Test Room"

    s.add("webapi_room_valid", cat, webapi_room_valid)

    def webapi_wallet_valid():
        _require_webapi()
        wallet = WebApiWallet(gold=100, bubbles=50)
        assert wallet.gold == 100
        assert wallet.bubbles == 50

    s.add("webapi_wallet_valid", cat, webapi_wallet_valid)

    def webapi_error_valid():
        _require_webapi()
        err = WebApiError(message="oops")
        assert err.message == "oops"

    s.add("webapi_error_valid", cat, webapi_error_valid)


# ═══════════════════════════════════════════════════════════════════════════
# 13 — async / concurrency / state machine
# ═══════════════════════════════════════════════════════════════════════════


def build_async_cases(s: Suite) -> None:
    cat = "13_async"

    def concurrent_validation():
        results: list[str] = []

        async def validate_one():
            payload = base("ChatEvent")
            try:
                validate_server_message(payload)
                results.append("ok")
            except HighriseFastValidationError:
                results.append("invalid")
            except Exception as exc:
                results.append(f"error:{exc!r}")

        async def run_all():
            await asyncio.gather(*[validate_one() for _ in range(100)])

        _run_async(run_all())
        errors = [r for r in results if r.startswith("error:")]
        assert not errors, f"concurrent errors: {errors[:3]}"
        assert len(results) == 100
        assert all(r == "ok" for r in results)

    s.add("async_concurrent_100_tasks", cat, concurrent_validation)

    def concurrent_debug_payload():
        async def debug_one():
            return debug_payload(base("ChatEvent"))

        async def run_all():
            return await asyncio.gather(*[debug_one() for _ in range(50)])

        results = _run_async(run_all())
        for r in results:
            assert isinstance(r, dict), type(r)
            assert r["ok"] is True, r

    s.add("async_concurrent_debug", cat, concurrent_debug_payload)

    def same_dict_concurrent():
        shared = base("ChatEvent")
        snapshot = copy.deepcopy(shared)

        async def validate_shared():
            validate_server_message(shared)

        async def run_all():
            await asyncio.gather(*[validate_shared() for _ in range(20)])

        _run_async(run_all())
        assert shared == snapshot, "shared dict was mutated"

    s.add("async_same_dict_no_mutation", cat, same_dict_concurrent)


# ═══════════════════════════════════════════════════════════════════════════
# 14 — encoding / serialization edge cases
# ═══════════════════════════════════════════════════════════════════════════


def build_encoding_cases(s: Suite) -> None:
    cat = "14_encoding"

    def bytes_input_rejected():
        exc = expect_validation_error(b'{"_type": "ChatEvent"}')
        assert exc.errors[0].path == "$"

    s.add("encoding_bytes_rejected", cat, bytes_input_rejected)

    def json_string_rejected():
        exc = expect_validation_error('{"_type": "ChatEvent"}')
        assert exc.errors[0].path == "$"

    s.add("encoding_json_string_rejected", cat, json_string_rejected)

    def list_input_rejected():
        exc = expect_validation_error([1, 2, 3])
        assert exc.errors[0].path == "$"

    s.add("encoding_list_rejected", cat, list_input_rejected)

    def none_input_rejected():
        exc = expect_validation_error(None)
        assert exc.errors[0].path == "$"

    s.add("encoding_none_rejected", cat, none_input_rejected)

    def int_input_rejected():
        exc = expect_validation_error(42)
        assert exc.errors[0].path == "$"

    s.add("encoding_int_rejected", cat, int_input_rejected)

    def type_as_bytes():
        exc = expect_validation_error({"_type": b"ChatEvent"})
        assert exc.errors[0].reason_code == ReasonCode.WRONG_TYPE

    s.add("encoding_type_as_bytes", cat, type_as_bytes)

    def type_as_int():
        exc = expect_validation_error({"_type": 123})
        assert exc.errors[0].reason_code == ReasonCode.WRONG_TYPE

    s.add("encoding_type_as_int", cat, type_as_int)

    def type_as_none():
        exc = expect_validation_error({"_type": None})
        assert exc.errors[0].reason_code == ReasonCode.WRONG_TYPE

    s.add("encoding_type_as_none", cat, type_as_none)

    def type_trailing_space():
        exc = expect_validation_error({"_type": "ChatEvent "})
        assert exc.errors[0].reason_code == ReasonCode.UNKNOWN_TYPE

    s.add("encoding_type_trailing_space", cat, type_trailing_space)

    def type_leading_space():
        exc = expect_validation_error({"_type": " ChatEvent"})
        assert exc.errors[0].reason_code == ReasonCode.UNKNOWN_TYPE

    s.add("encoding_type_leading_space", cat, type_leading_space)

    def type_wrong_case():
        exc = expect_validation_error({"_type": "chatEvent"})
        assert exc.errors[0].reason_code == ReasonCode.UNKNOWN_TYPE

    s.add("encoding_type_wrong_case", cat, type_wrong_case)

    def type_uppercase():
        exc = expect_validation_error({"_type": "CHATEVENT"})
        assert exc.errors[0].reason_code == ReasonCode.UNKNOWN_TYPE

    s.add("encoding_type_uppercase", cat, type_uppercase)

    def type_empty_string():
        exc = expect_validation_error({"_type": ""})
        assert exc.errors[0].reason_code == ReasonCode.UNKNOWN_TYPE

    s.add("encoding_type_empty_string", cat, type_empty_string)


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════


def build_all_cases() -> Suite:
    s = Suite()
    build_debug_cases(s)
    build_reason_path_cases(s)
    build_type_cases(s)
    build_semantic_cases(s)
    build_protocol_cases(s)
    build_nested_cases(s)
    build_list_cases(s)
    build_string_cases(s)
    build_number_cases(s)
    build_bool_cases(s)
    build_consistency_cases(s)
    build_webapi_cases(s)
    build_async_cases(s)
    build_encoding_cases(s)
    return s


def print_report(suite: Suite) -> None:
    summary = suite.summary()
    print("\n" + "=" * 70)
    print("BENCHMARK V6 — RESULTS")
    print("=" * 70)
    print(f"Total:   {summary['total']}")
    print(f"Passed:  {summary['ok']}")
    print(f"Failed:  {summary['fail']}")
    print(f"Errors:  {summary['error']}")
    print(f"Skipped: {summary['skip']}")
    print("-" * 70)

    if summary["by_category"]:
        print(f"\n{'Category':<22} {'OK':>5} {'FAIL':>5} {'ERR':>5} {'SKIP':>5}")
        print("-" * 47)
        for cat in sorted(summary["by_category"]):
            counts = summary["by_category"][cat]
            print(
                f"{cat:<22} {counts['ok']:>5} {counts['fail']:>5} "
                f"{counts['error']:>5} {counts['skip']:>5}"
            )

    failures = [r for r in suite.results if r.status in ("fail", "error")]
    if failures:
        print(f"\n{'=' * 70}")
        print(f"FAILURES & ERRORS ({len(failures)})")
        print("=" * 70)
        for r in failures[:20]:
            print(f"\n  [{r.status.upper()}] {r.name} ({r.category})")
            if r.detail:
                print(f"    {r.detail}")
        if len(failures) > 20:
            print(f"\n  ... and {len(failures) - 20} more")

    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark V6 — Debug-first & protocol-gap suite"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run every 3rd test case of the filtered set (faster)",
    )
    parser.add_argument(
        "--category",
        type=str,
        default="",
        help="Run only this category (e.g., 01_debug, 05_protocol)",
    )
    parser.add_argument(
        "--filter",
        type=str,
        default="",
        help="Run only tests whose name contains this substring",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all test cases and exit",
    )
    parser.add_argument(
        "--json",
        type=str,
        default="",
        help="Write results to JSON file",
    )
    args = parser.parse_args()

    if not _IMPORT_OK:
        print(f"ERROR: Cannot import highrise_fast: {_IMPORT_ERROR}")
        print("\nMake sure you're running from the repo root, or install the package:")
        print("  pip install -e .")
        return 1

    suite = build_all_cases()

    if args.list:
        print(f"\n{'Category':<22} Test Name")
        print("-" * 62)
        for name, cat, _ in suite.cases:
            print(f"{cat:<22} {name}")
        print(f"\nTotal: {len(suite.cases)} test cases")
        return 0

    print("=" * 70)
    print("BENCHMARK V6 — DEBUG-FIRST & PROTOCOL-GAP SUITE")
    print("=" * 70)
    print(f"Mode:      {'quick' if args.quick else 'full'}")
    print(f"Category:  {args.category or 'all'}")
    print(f"Filter:    {args.filter or 'none'}")
    print(f"Cases:     {len(suite.cases)}")
    print("=" * 70)
    print()

    t0 = time.perf_counter()
    suite.run(filter_=args.filter, category=args.category, quick=args.quick)
    elapsed = time.perf_counter() - t0

    print(f"\nCompleted in {elapsed:.2f}s")
    print_report(suite)

    if args.json:
        summary = suite.summary()
        output = {
            "elapsed_s": elapsed,
            "summary": summary,
            "results": [
                {
                    "name": r.name,
                    "category": r.category,
                    "status": r.status,
                    "duration_s": r.duration_s,
                    "detail": r.detail,
                }
                for r in suite.results
            ],
        }
        with open(args.json, "w") as f:
            json.dump(output, f, indent=2, default=str)
        print(f"Results written to: {args.json}")

    summary = suite.summary()
    return 0 if (summary["fail"] == 0 and summary["error"] == 0) else 1


if __name__ == "__main__":
    sys.exit(main())

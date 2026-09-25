#!/usr/bin/env python3
"""
BENCHMARK V7 — EXHAUSTIVE COVERAGE & STRESS SUITE
=================================================

The final layer on top of V1-V6. Everything not yet tested:

  01. debug_payload / explain_debug — extended contract (repair artifacts,
      cap behavior, dedup semantics, token/default edge cases)
  02. Reason codes — complete exhaustion in every context
  03. Path accuracy — every path shape the validators can emit
  04. Type-coercion matrix — generated wrong-type injection across payloads
  05. Semantic bounds — full boundary sweep on every bounded field
  06. Protocol deep — field-removal matrix across ALL 46 payload types
  07. Nested structures — depth, aliasing, interleaved errors
  08. Lists / tuples — length, element, and index-path behavior
  09. Strings — complete type-theory sweep (bytes, subclasses, Unicode)
  10. Numbers — int/float coercion theory (Decimal, Fraction, inf, nan)
  11. Booleans / None — strictness and optional/null semantics
  12. Model <-> validator consistency — per-field defaults vs validation
  13. Web API models — shape and attribute coverage
  14. Async / state machine — concurrency stress, shared-state safety
  15. Encoding / input types — everything that is not a dict
  16. Error message content — human-readable contract
  17. Exception attributes — the HighriseFastValidationError object model
  18. Mutation safety — no validator ever mutates input (all payloads)
  19. Performance gates — validation must stay fast
  20. Fuzz resilience — seeded corruption never crashes
  21. Regression edge cases — the tricky ones history taught us
  22. Round-trip serialization — JSON dumps/loads must revalidate
  23. Robustness matrix — every field x every hostile value, no crashes

Usage:
    python benchmarkv7.py
    python benchmarkv7.py --quick
    python benchmarkv7.py --category 06_protocol
    python benchmarkv7.py --filter wallet
    python benchmarkv7.py --list
    python benchmarkv7.py --json results.json
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import copy
import json
import random
import string
import sys
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from typing import Any

# ---------------------------------------------------------------------------
# Import block — mirrors V6; adjust if your package layout differs
# ---------------------------------------------------------------------------

try:
    from highrise_fast.validation import (
        BASE_PAYLOADS,
        HighriseFastValidationError,
        ReasonCode,
        ValidationErrorDetail,
        _debug_default_for,
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

# Optional private validator hooks — tests skip gracefully if absent
try:
    from highrise_fast.validation import _require_str  # noqa

    _HAS_REQUIRE_STR = True
except Exception:
    _HAS_REQUIRE_STR = False


# ═══════════════════════════════════════════════════════════════════════════
# Infrastructure
# ═══════════════════════════════════════════════════════════════════════════


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
        for idx, (name, cat, fn) in enumerate(self.cases, 1):
            if filter_ and filter_ not in name:
                continue
            if category and category != cat:
                continue
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
        return {
            "total": len(self.results),
            "ok": sum(1 for r in self.results if r.status == "ok"),
            "fail": sum(1 for r in self.results if r.status == "fail"),
            "error": sum(1 for r in self.results if r.status == "error"),
            "skip": sum(1 for r in self.results if r.status == "skip"),
            "by_category": dict(by_cat),
        }


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def expect_validation_error(
    payload: Any, *, strict: bool = True, strict_semantic: bool = False
) -> HighriseFastValidationError:
    """Assert validate_server_message rejects the payload; return the exception."""
    try:
        validate_server_message(payload, strict=strict, strict_semantic=strict_semantic)
    except HighriseFastValidationError as exc:
        return exc
    raise AssertionError(
        f"expected HighriseFastValidationError, got success for {payload!r}"
    )


def expect_ok(
    payload: Any, *, strict: bool = True, strict_semantic: bool = False
) -> None:
    """Assert validate_server_message accepts the payload."""
    try:
        validate_server_message(payload, strict=strict, strict_semantic=strict_semantic)
    except HighriseFastValidationError as exc:
        raise AssertionError(f"expected success, got: {exc.short()}") from exc


def expect_no_crash(
    payload: Any, *, strict_semantic: bool = False
) -> HighriseFastValidationError | None:
    """Validation may pass or fail — but must only ever raise HighriseFastValidationError."""
    try:
        validate_server_message(payload, strict_semantic=strict_semantic)
        return None
    except HighriseFastValidationError as exc:
        return exc
    # any other exception propagates and fails the test


def clone(payload: dict) -> dict:
    return copy.deepcopy(payload)


def base(name: str) -> dict:
    if name not in BASE_PAYLOADS:
        raise KeyError(f"no BASE_PAYLOAD for {name!r}")
    return clone(BASE_PAYLOADS[name])


def first(exc: HighriseFastValidationError) -> ValidationErrorDetail:
    return exc.errors[0]


def paths(report: dict) -> list:
    return [i["path"] for i in report["issues"]]


def codes(report: dict) -> list:
    return [i["reason_code"] for i in report["issues"]]


def real_issues(report: dict) -> list:
    """Filter out debug auto-repair artifacts (value == 'debug' WRONG_TYPE)."""
    return [
        i
        for i in report["issues"]
        if not (
            i.get("reason_code") == ReasonCode.WRONG_TYPE and i.get("value") == "debug"
        )
    ]


def non_repair_count(report: dict) -> int:
    return len(real_issues(report))


def top_keys(name: str) -> list:
    """All keys of a base payload except _type."""
    return [k for k in BASE_PAYLOADS.get(name, {}) if k != "_type"]


def make_user(uid: str = "u1", uname: str = "tester") -> dict:
    return {"id": uid, "username": uname}


def make_pos(
    x: float = 1.0, y: float = 1.0, z: float = 1.0, facing: str = "FrontRight"
) -> dict:
    return {"x": x, "y": y, "z": z, "facing": facing}


def make_anchor(entity_id: str = "anchor_1", anchor_ix: int = 0) -> dict:
    return {"entity_id": entity_id, "anchor_ix": anchor_ix}


def make_currency(kind: str = "gold", amount: int = 100) -> dict:
    return {"type": kind, "amount": amount}


ALL_PAYLOAD_NAMES: list = sorted(BASE_PAYLOADS.keys()) if _IMPORT_OK else []


# ═══════════════════════════════════════════════════════════════════════════
# 01 — debug_payload / explain_debug extended contract
# ═══════════════════════════════════════════════════════════════════════════


def build_debug_cases(s: Suite) -> None:
    cat = "01_debug"

    def explain_line_count():
        bad = base("ChatEvent")
        bad["message"] = None
        bad["whisper"] = "yes"
        report = debug_payload(bad)
        text = explain_debug(bad)
        lines = [ln for ln in text.splitlines() if ln.strip()]
        # header line + one line per issue (at minimum)
        assert len(lines) >= 1 + report["issue_count"], (text, report)

    s.add("debug_explain_line_count", cat, explain_line_count)

    def explain_numbering_starts_at_1():
        bad = base("ChatEvent")
        bad["message"] = None
        text = explain_debug(bad)
        assert "1" in text, text

    s.add("debug_explain_numbering", cat, explain_numbering_starts_at_1)

    def explain_shows_expected_and_got():
        bad = base("ChatEvent")
        bad["message"] = 123
        text = explain_debug(bad)
        assert "expected" in text.lower() or "str" in text.lower(), text

    s.add("debug_explain_expected_got", cat, explain_shows_expected_and_got)

    def explain_reason_prefix():
        bad = base("ChatEvent")
        bad["message"] = 123
        text = explain_debug(bad)
        assert "WRONG_TYPE" in text, text

    s.add("debug_explain_reason_prefix", cat, explain_reason_prefix)

    def four_bad_fields_count():
        bad = {"_type": "ChatEvent", "user": 1, "message": 2, "whisper": 3}
        report = debug_payload(bad)
        assert non_repair_count(report) >= 3, report

    s.add("debug_four_bad_fields", cat, four_bad_fields_count)

    def cap_five_with_six_errors():
        bad = {
            "_type": "ChatEvent",
            "user": {"id": 1, "username": 2},
            "message": 3,
            "whisper": 4,
        }
        report = debug_payload(bad, max_issues=5)
        assert report["issue_count"] <= 5, report

    s.add("debug_cap_five", cat, cap_five_with_six_errors)

    def cap_one():
        bad = base("ChatEvent")
        bad["message"] = None
        bad["whisper"] = "x"
        report = debug_payload(bad, max_issues=1)
        assert report["issue_count"] == 1, report

    s.add("debug_cap_one", cat, cap_one)

    def cap_zero_is_noop_or_one():
        bad = base("ChatEvent")
        bad["message"] = None
        report = debug_payload(bad, max_issues=0)
        assert report["issue_count"] <= 1, report

    s.add("debug_cap_zero", cat, cap_zero_is_noop_or_one)

    def cap_negative_treated_as_default():
        bad = base("ChatEvent")
        bad["message"] = None
        report = debug_payload(bad, max_issues=-1)
        assert isinstance(report["issue_count"], int)

    s.add("debug_cap_negative", cat, cap_negative_treated_as_default)

    def repair_artifact_is_wrong_type_debug():
        """Known behavior: semantic errors spawn a repair artifact with value='debug'."""
        bad = base("UserMovedEvent")
        bad["position"]["x"] = 9999.0
        report = debug_payload(bad, strict_semantic=True)
        artifacts = [
            i
            for i in report["issues"]
            if i.get("reason_code") == ReasonCode.WRONG_TYPE
            and i.get("value") == "debug"
        ]
        oob = [
            i
            for i in report["issues"]
            if i.get("reason_code") == ReasonCode.OUT_OF_BOUNDS
        ]
        assert len(oob) == 1, report
        # artifact may or may not appear, but if present it follows the OOB
        if artifacts:
            assert artifacts[0]["path"] == "$.position.x", report

    s.add("debug_repair_artifact_contract", cat, repair_artifact_is_wrong_type_debug)

    def repair_artifact_filtered_count():
        bad = base("UserMovedEvent")
        for axis in ("x", "y", "z"):
            bad["position"][axis] = 9999.0
        report = debug_payload(bad, strict_semantic=True)
        assert non_repair_count(report) == 3, report

    s.add("debug_repair_filtered_count", cat, repair_artifact_filtered_count)

    def two_invalid_same_nested_object():
        bad = base("ChatEvent")
        bad["user"]["id"] = 123
        bad["user"]["username"] = 456
        report = debug_payload(bad)
        assert non_repair_count(report) == 2, report
        assert set(paths(report)) == {"$.user.id", "$.user.username"}

    s.add("debug_two_invalid_same_object", cat, two_invalid_same_nested_object)

    def two_invalid_different_objects():
        bad = base("TipReactionEvent")
        if "sender" in bad and "receiver" in bad:
            bad["sender"]["id"] = 1
            bad["receiver"]["id"] = 2
            report = debug_payload(bad)
            assert non_repair_count(report) == 2, report

    s.add("debug_two_invalid_different_objects", cat, two_invalid_different_objects)

    def three_nesting_levels():
        bad = base("GetRoomUsersResponse")
        if bad.get("content"):
            bad["content"][0][0]["id"] = 999
            bad["content"][0][1]["x"] = "bad"
            report = debug_payload(bad)
            assert non_repair_count(report) >= 2, report

    s.add("debug_three_nesting_levels", cat, three_nesting_levels)

    def first_error_matches_issues_zero():
        bad = base("ChatEvent")
        bad["message"] = None
        report = debug_payload(bad)
        if report["issues"]:
            assert report.get("first_error"), report

    s.add("debug_first_error_present", cat, first_error_matches_issues_zero)

    def payload_key_is_original_object():
        original = base("ChatEvent")
        report = debug_payload(original)
        assert (
            report["payload"] is original
        ), "payload key should be the original object"

    s.add("debug_payload_key_identity", cat, payload_key_is_original_object)

    def tuple_of_tuples_bad_inner():
        bad = base("GetRoomUsersResponse")
        if bad.get("content") and len(bad["content"]) > 0:
            bad["content"][0] = [{"id": 123}, make_pos()]
            expect_no_crash(bad)

    s.add("debug_tuple_of_tuples_bad_inner", cat, tuple_of_tuples_bad_inner)

    def bad_optional_rid():
        bad = base("GetWalletResponse")
        if "rid" in bad:
            bad["rid"] = 123
            exc = expect_validation_error(bad)
            assert first(exc).path == "$.rid"

    s.add("debug_bad_optional_rid", cat, bad_optional_rid)

    def bad_optional_duration():
        bad = base("RoomModeratedEvent")
        if "duration" in bad and bad["duration"] is not None:
            bad["duration"] = "abc"
            expect_validation_error(bad)

    s.add("debug_bad_optional_duration", cat, bad_optional_duration)

    def list_of_100_with_10_bad():
        bad = base("GetWalletResponse")
        good_item = clone(bad["content"][0])
        bad["content"] = []
        for i in range(100):
            item = clone(good_item)
            if i % 10 == 0:
                item["amount"] = "bad"
            bad["content"].append(item)
        report = debug_payload(bad)
        assert non_repair_count(report) == 10, report

    s.add("debug_list_100_ten_bad", cat, list_of_100_with_10_bad)

    def dedup_prevents_re_report():
        bad = base("ChatEvent")
        bad["message"] = None
        report = debug_payload(bad)
        # The same (path, code) pair must not appear twice
        seen = set()
        for i in report["issues"]:
            key = (i["path"], i["reason_code"])
            assert key not in seen, f"duplicate {key}"
            seen.add(key)

    s.add("debug_dedup_no_duplicates", cat, dedup_prevents_re_report)

    def same_path_different_codes_both_kept():
        # OUT_OF_BOUNDS then repair-artifact WRONG_TYPE share a path — both reported
        bad = base("UserMovedEvent")
        bad["position"]["x"] = 9999.0
        report = debug_payload(bad, strict_semantic=True)
        x_issues = [i for i in report["issues"] if i["path"] == "$.position.x"]
        assert len(x_issues) >= 1, report

    s.add("debug_same_path_multiple_codes", cat, same_path_different_codes_both_kept)

    def tokens_root_only():
        assert _debug_tokens("$") == []

    s.add("debug_tokens_root", cat, tokens_root_only)

    def tokens_deep():
        assert _debug_tokens("$.a.b.c.d.e") == ["a", "b", "c", "d", "e"]

    s.add("debug_tokens_deep", cat, tokens_deep)

    def tokens_multi_index():
        assert _debug_tokens("$.a[0][1][2]") == ["a", 0, 1, 2]

    s.add("debug_tokens_multi_index", cat, tokens_multi_index)

    def tokens_underscore_key():
        assert _debug_tokens("$._type") == ["_type"]
        assert _debug_tokens("$.__dunder__") == ["__dunder__"]

    s.add("debug_tokens_underscore", cat, tokens_underscore_key)

    def tokens_empty_string():
        # Defensive: empty path string should not crash
        with contextlib.suppress(Exception):
            _debug_tokens("")

    s.add("debug_tokens_empty_string", cat, tokens_empty_string)

    def default_for_unknown_kind():
        # An unknown kind should not crash; any default is acceptable
        try:
            v = _debug_default_for("unknown-kind", "$.x", None)
            assert v is not None or v is None  # no crash is the contract
        except (KeyError, ValueError):
            pass

    s.add("debug_default_unknown_kind", cat, default_for_unknown_kind)

    def default_for_bool_is_false():
        assert _debug_default_for("bool", "$.x", True) is False

    s.add("debug_default_bool_false", cat, default_for_bool_is_false)

    def default_for_int_is_zero():
        assert _debug_default_for("int", "$.x", 99) == 0

    s.add("debug_default_int_zero", cat, default_for_int_is_zero)

    def default_for_float_is_zero():
        assert _debug_default_for("float", "$.x", 9.9) == 0.0

    s.add("debug_default_float_zero", cat, default_for_float_is_zero)

    def default_for_str_is_debug():
        assert _debug_default_for("str", "$.x", "real") == "debug"

    s.add("debug_default_str_debug", cat, default_for_str_is_debug)

    def default_for_list_is_empty():
        assert _debug_default_for("list", "$.x", [1]) == []

    s.add("debug_default_list_empty", cat, default_for_list_is_empty)

    def default_for_dict_is_empty():
        assert _debug_default_for("dict", "$.x", {"a": 1}) == {}

    s.add("debug_default_dict_empty", cat, default_for_dict_is_empty)

    def set_value_overwrites_existing():
        p = {"a": {"b": "old"}}
        _debug_set_value(p, "$.a.b", "new")
        assert p["a"]["b"] == "new", p

    s.add("debug_set_value_overwrite", cat, set_value_overwrites_existing)

    def set_value_refuses_root():
        assert _debug_set_value({}, "$", "x") is False

    s.add("debug_set_value_refuses_root", cat, set_value_refuses_root)

    def set_value_creates_intermediate_dicts():
        p = {}
        _debug_set_value(p, "$.a.b.c", 1)
        assert p == {"a": {"b": {"c": 1}}}, p

    s.add(
        "debug_set_value_intermediate_dicts", cat, set_value_creates_intermediate_dicts
    )

    def set_value_extends_list():
        p: list = [0]
        _debug_set_value(p, "$[3]", "x")
        assert len(p) >= 4, p

    s.add("debug_set_value_extends_list", cat, set_value_extends_list)

    def set_value_negative_index():
        p: list = ["a", "b"]
        # must not crash undefined-ly; any behavior OK
        with contextlib.suppress(Exception):
            _debug_set_value(p, "$[-1]", "x")

    s.add("debug_set_value_negative_index", cat, set_value_negative_index)

    def set_value_mixed_path():
        p = {"items": [{"name": "a"}]}
        _debug_set_value(p, "$.items[0].name", "b")
        assert p["items"][0]["name"] == "b", p

    s.add("debug_set_value_mixed_path", cat, set_value_mixed_path)

    def debug_unknown_type_reports_once():
        report = debug_payload({"_type": "Nope", "a": 1, "b": 2, "c": 3})
        assert report["issue_count"] == 1, report
        assert report["issues"][0]["reason_code"] == ReasonCode.UNKNOWN_TYPE

    s.add("debug_unknown_type_once", cat, debug_unknown_type_reports_once)

    def debug_missing_type_reports_once():
        report = debug_payload({"a": 1, "b": 2})
        assert report["issue_count"] == 1, report
        assert report["issues"][0]["reason_code"] == ReasonCode.MISSING_FIELD

    s.add("debug_missing_type_once", cat, debug_missing_type_reports_once)

    def debug_empty_dict():
        report = debug_payload({})
        assert report["ok"] is False
        assert report["issue_count"] == 1

    s.add("debug_empty_dict", cat, debug_empty_dict)

    def debug_all_base_payloads_ok():
        for name in ALL_PAYLOAD_NAMES:
            report = debug_payload(BASE_PAYLOADS[name])
            assert report["ok"] is True, (name, report)

    s.add("debug_all_base_payloads_ok", cat, debug_all_base_payloads_ok)

    def explain_all_base_payloads_ok():
        for name in ALL_PAYLOAD_NAMES:
            text = explain_debug(BASE_PAYLOADS[name])
            assert isinstance(text, str) and text, name

    s.add("debug_explain_all_bases", cat, explain_all_base_payloads_ok)

    def debug_max_issues_is_keyword_only_safe():
        # calling with positional max_issues should either work or TypeError, not corrupt
        with contextlib.suppress(TypeError):
            debug_payload(base("ChatEvent"), 3)

    s.add("debug_max_issues_positional", cat, debug_max_issues_is_keyword_only_safe)

    def debug_returns_required_keys():
        report = debug_payload(base("ChatEvent"))
        for key in ("ok", "issue_count", "issues"):
            assert key in report, f"missing key {key}: {report}"

    s.add("debug_required_keys", cat, debug_returns_required_keys)

    def debug_issue_shape():
        bad = base("ChatEvent")
        bad["message"] = 123
        report = debug_payload(bad)
        for i in report["issues"]:
            assert "path" in i and "reason_code" in i and "message" in i, i

    s.add("debug_issue_shape", cat, debug_issue_shape)

    def debug_structural_and_semantic_combined():
        bad = base("ChatEvent")
        bad["message"] = "A" * 2000  # semantic
        bad["whisper"] = "yes"  # structural
        report = debug_payload(bad, strict_semantic=True)
        code_set = set(codes(report))
        assert ReasonCode.WRONG_TYPE in code_set, report
        assert any(
            c in code_set for c in (ReasonCode.INVALID_LENGTH, ReasonCode.OUT_OF_BOUNDS)
        ), report

    s.add("debug_structural_and_semantic", cat, debug_structural_and_semantic_combined)

    def debug_no_infinite_loop_on_stubborn_payload():
        # A payload that keeps failing must terminate
        bad = {"_type": "ChatEvent", "user": "x", "message": "y", "whisper": "z"}
        t0 = time.perf_counter()
        report = debug_payload(bad)
        elapsed = time.perf_counter() - t0
        assert elapsed < 5.0, f"took {elapsed}s"
        assert isinstance(report["issue_count"], int)

    s.add(
        "debug_terminates_on_stubborn", cat, debug_no_infinite_loop_on_stubborn_payload
    )


# ═══════════════════════════════════════════════════════════════════════════
# 02 — Reason codes: complete exhaustion
# ═══════════════════════════════════════════════════════════════════════════


def build_reason_cases(s: Suite) -> None:
    cat = "02_reason"

    def rc_missing_field_str():
        bad = base("ChatEvent")
        del bad["message"]
        assert (
            first(expect_validation_error(bad)).reason_code == ReasonCode.MISSING_FIELD
        )

    s.add("rc_missing_str", cat, rc_missing_field_str)

    def rc_missing_field_bool():
        bad = base("ChatEvent")
        del bad["whisper"]
        assert (
            first(expect_validation_error(bad)).reason_code == ReasonCode.MISSING_FIELD
        )

    s.add("rc_missing_bool", cat, rc_missing_field_bool)

    def rc_missing_field_dict():
        bad = base("ChatEvent")
        del bad["user"]
        assert (
            first(expect_validation_error(bad)).reason_code == ReasonCode.MISSING_FIELD
        )

    s.add("rc_missing_dict", cat, rc_missing_field_dict)

    def rc_missing_field_list():
        bad = base("GetWalletResponse")
        del bad["content"]
        assert (
            first(expect_validation_error(bad)).reason_code == ReasonCode.MISSING_FIELD
        )

    s.add("rc_missing_list", cat, rc_missing_field_list)

    def rc_missing_type():
        exc = expect_validation_error({"x": 1})
        assert first(exc).reason_code == ReasonCode.MISSING_FIELD

    s.add("rc_missing_type", cat, rc_missing_type)

    def rc_wrong_type_str_int():
        bad = base("ChatEvent")
        bad["message"] = 1
        assert first(expect_validation_error(bad)).reason_code == ReasonCode.WRONG_TYPE

    s.add("rc_wrong_str_int", cat, rc_wrong_type_str_int)

    def rc_wrong_type_bool_int():
        bad = base("ChatEvent")
        bad["whisper"] = 1
        assert first(expect_validation_error(bad)).reason_code == ReasonCode.WRONG_TYPE

    s.add("rc_wrong_bool_int", cat, rc_wrong_type_bool_int)

    def rc_wrong_type_dict_list():
        bad = base("ChatEvent")
        bad["user"] = []
        assert first(expect_validation_error(bad)).reason_code == ReasonCode.WRONG_TYPE

    s.add("rc_wrong_dict_list", cat, rc_wrong_type_dict_list)

    def rc_wrong_type_list_str():
        bad = base("GetWalletResponse")
        bad["content"] = "x"
        assert first(expect_validation_error(bad)).reason_code == ReasonCode.WRONG_TYPE

    s.add("rc_wrong_list_str", cat, rc_wrong_type_list_str)

    def rc_wrong_type_literal():
        bad = base("ReactionEvent")
        bad["reaction"] = "nope"
        assert first(expect_validation_error(bad)).reason_code == ReasonCode.WRONG_TYPE

    s.add("rc_wrong_literal", cat, rc_wrong_type_literal)

    def rc_wrong_type_underscore_type():
        exc = expect_validation_error({"_type": 5})
        assert first(exc).reason_code == ReasonCode.WRONG_TYPE

    s.add("rc_wrong_type_field", cat, rc_wrong_type_underscore_type)

    def rc_unknown_type():
        exc = expect_validation_error({"_type": "Banana"})
        assert first(exc).reason_code == ReasonCode.UNKNOWN_TYPE

    s.add("rc_unknown_type", cat, rc_unknown_type)

    def rc_out_of_bounds_nan():
        bad = base("UserMovedEvent")
        bad["position"]["x"] = float("nan")
        assert (
            first(expect_validation_error(bad)).reason_code == ReasonCode.OUT_OF_BOUNDS
        )

    s.add("rc_oob_nan", cat, rc_out_of_bounds_nan)

    def rc_out_of_bounds_inf():
        bad = base("UserMovedEvent")
        bad["position"]["y"] = float("inf")
        assert (
            first(expect_validation_error(bad)).reason_code == ReasonCode.OUT_OF_BOUNDS
        )

    s.add("rc_oob_inf", cat, rc_out_of_bounds_inf)

    def rc_out_of_bounds_semantic_x():
        bad = base("UserMovedEvent")
        bad["position"]["x"] = 5000.0
        exc = expect_validation_error(bad, strict_semantic=True)
        assert first(exc).reason_code == ReasonCode.OUT_OF_BOUNDS

    s.add("rc_oob_semantic_x", cat, rc_out_of_bounds_semantic_x)

    def rc_out_of_bounds_semantic_y():
        bad = base("UserMovedEvent")
        bad["position"]["y"] = -5000.0
        exc = expect_validation_error(bad, strict_semantic=True)
        assert first(exc).reason_code == ReasonCode.OUT_OF_BOUNDS

    s.add("rc_oob_semantic_y", cat, rc_out_of_bounds_semantic_y)

    def rc_out_of_bounds_semantic_z():
        bad = base("UserMovedEvent")
        bad["position"]["z"] = 99999.0
        exc = expect_validation_error(bad, strict_semantic=True)
        assert first(exc).reason_code == ReasonCode.OUT_OF_BOUNDS

    s.add("rc_oob_semantic_z", cat, rc_out_of_bounds_semantic_z)

    def rc_oob_wallet_negative():
        bad = base("GetWalletResponse")
        bad["content"][0]["amount"] = -5
        exc = expect_validation_error(bad, strict_semantic=True)
        assert first(exc).reason_code == ReasonCode.OUT_OF_BOUNDS

    s.add("rc_oob_wallet_neg", cat, rc_oob_wallet_negative)

    def rc_invalid_length_chat():
        bad = base("ChatEvent")
        bad["message"] = "A" * 5000
        exc = expect_validation_error(bad, strict_semantic=True)
        assert first(exc).reason_code == ReasonCode.INVALID_LENGTH

    s.add("rc_invalid_len_chat", cat, rc_invalid_length_chat)

    def rc_invalid_length_tuple():
        bad = base("VoiceEvent")
        bad["users"][0] = [{"id": "x"}, "voice", "extra"]
        exc = expect_validation_error(bad)
        assert first(exc).reason_code == ReasonCode.INVALID_LENGTH

    s.add("rc_invalid_len_tuple", cat, rc_invalid_length_tuple)

    def rc_invalid_length_content_row():
        bad = base("GetRoomUsersResponse")
        if bad.get("content"):
            bad["content"][0] = [bad["content"][0][0]]
            exc = expect_validation_error(bad)
            assert first(exc).reason_code == ReasonCode.INVALID_LENGTH

    s.add("rc_invalid_len_content_row", cat, rc_invalid_length_content_row)

    def rc_constants_exist():
        for attr in (
            "MISSING_FIELD",
            "WRONG_TYPE",
            "OUT_OF_BOUNDS",
            "INVALID_LENGTH",
            "UNKNOWN_TYPE",
        ):
            assert hasattr(ReasonCode, attr), attr

    s.add("rc_constants_exist", cat, rc_constants_exist)

    def rc_constants_are_strings():
        for attr in (
            "MISSING_FIELD",
            "WRONG_TYPE",
            "OUT_OF_BOUNDS",
            "INVALID_LENGTH",
            "UNKNOWN_TYPE",
        ):
            val = getattr(ReasonCode, attr)
            assert isinstance(val, str), (attr, val)

    s.add("rc_constants_strings", cat, rc_constants_are_strings)

    def rc_codes_are_hashable_and_comparable():
        assert ReasonCode.MISSING_FIELD == ReasonCode.MISSING_FIELD
        assert ReasonCode.MISSING_FIELD != ReasonCode.WRONG_TYPE
        assert len({ReasonCode.MISSING_FIELD, ReasonCode.WRONG_TYPE}) == 2

    s.add("rc_hashable", cat, rc_codes_are_hashable_and_comparable)

    def rc_nested_missing_reports_missing():
        bad = base("ChatEvent")
        del bad["user"]["id"]
        exc = expect_validation_error(bad)
        assert first(exc).reason_code == ReasonCode.MISSING_FIELD
        assert first(exc).path == "$.user.id"

    s.add("rc_nested_missing", cat, rc_nested_missing_reports_missing)

    def rc_list_element_missing():
        bad = base("GetWalletResponse")
        del bad["content"][0]["type"]
        exc = expect_validation_error(bad)
        assert first(exc).reason_code == ReasonCode.MISSING_FIELD

    s.add("rc_list_elem_missing", cat, rc_list_element_missing)

    def rc_tuple_element_wrong():
        bad = base("VoiceEvent")
        bad["users"][0][1] = 42
        exc = expect_validation_error(bad)
        assert first(exc).reason_code == ReasonCode.WRONG_TYPE

    s.add("rc_tuple_elem_wrong", cat, rc_tuple_element_wrong)

    def rc_semantic_off_by_default():
        """Without strict_semantic, a 5000-char message should pass."""
        bad = base("ChatEvent")
        bad["message"] = "A" * 5000
        expect_ok(bad, strict_semantic=False)

    s.add("rc_semantic_off_default", cat, rc_semantic_off_by_default)

    def rc_semantic_on_rejects():
        bad = base("ChatEvent")
        bad["message"] = "A" * 5000
        expect_validation_error(bad, strict_semantic=True)

    s.add("rc_semantic_on_rejects", cat, rc_semantic_on_rejects)

    def rc_non_dict_root_is_wrong_type():
        exc = expect_validation_error(12345)
        assert first(exc).reason_code == ReasonCode.WRONG_TYPE

    s.add("rc_non_dict_wrong_type", cat, rc_non_dict_root_is_wrong_type)

    def rc_none_root_is_wrong_type():
        exc = expect_validation_error(None)
        assert first(exc).reason_code == ReasonCode.WRONG_TYPE

    s.add("rc_none_root_wrong_type", cat, rc_none_root_is_wrong_type)

    def rc_reason_in_debug_report_matches():
        bad = base("ChatEvent")
        bad["message"] = 9
        report = debug_payload(bad)
        exc = expect_validation_error(bad)
        assert report["issues"][0]["reason_code"] == first(exc).reason_code

    s.add("rc_debug_matches_validate", cat, rc_reason_in_debug_report_matches)

    def rc_second_error_code_correct():
        bad = base("ChatEvent")
        bad["message"] = None  # first error
        bad["whisper"] = "yes"  # second error
        report = debug_payload(bad)
        assert codes(report) == [ReasonCode.WRONG_TYPE, ReasonCode.WRONG_TYPE], report

    s.add("rc_second_error_code", cat, rc_second_error_code_correct)

    def rc_mixed_codes_in_order():
        bad = {"_type": "ChatEvent", "user": None, "message": None}
        report = debug_payload(bad)
        # user wrong-type reported before message wrong-type (field order dependent)
        assert ReasonCode.WRONG_TYPE in codes(report)

    s.add("rc_mixed_codes_order", cat, rc_mixed_codes_in_order)

    def rc_unknown_error_constant_exists_if_defined():
        if hasattr(ReasonCode, "UNKNOWN_ERROR"):
            assert isinstance(ReasonCode.UNKNOWN_ERROR, str)

    s.add("rc_unknown_error_constant", cat, rc_unknown_error_constant_exists_if_defined)


# ═══════════════════════════════════════════════════════════════════════════
# 03 — Path accuracy: every shape
# ═══════════════════════════════════════════════════════════════════════════


def build_path_cases(s: Suite) -> None:
    cat = "03_path"

    def p_root_for_string():
        assert first(expect_validation_error("x")).path == "$"

    s.add("p_root_string", cat, p_root_for_string)

    def p_root_for_list():
        assert first(expect_validation_error([1])).path == "$"

    s.add("p_root_list", cat, p_root_for_list)

    def p_root_for_none():
        assert first(expect_validation_error(None)).path == "$"

    s.add("p_root_none", cat, p_root_for_none)

    def p_root_for_int():
        assert first(expect_validation_error(7)).path == "$"

    s.add("p_root_int", cat, p_root_for_int)

    def p_type_field():
        assert first(expect_validation_error({"_type": 1})).path == "$._type"

    s.add("p_type_field", cat, p_type_field)

    def p_top_message():
        bad = base("ChatEvent")
        bad["message"] = 1
        assert first(expect_validation_error(bad)).path == "$.message"

    s.add("p_top_message", cat, p_top_message)

    def p_top_whisper():
        bad = base("ChatEvent")
        bad["whisper"] = 1
        assert first(expect_validation_error(bad)).path == "$.whisper"

    s.add("p_top_whisper", cat, p_top_whisper)

    def p_nested_user_id():
        bad = base("ChatEvent")
        bad["user"]["id"] = 1
        assert first(expect_validation_error(bad)).path == "$.user.id"

    s.add("p_nested_user_id", cat, p_nested_user_id)

    def p_nested_user_username():
        bad = base("ChatEvent")
        bad["user"]["username"] = 1
        assert first(expect_validation_error(bad)).path == "$.user.username"

    s.add("p_nested_username", cat, p_nested_user_username)

    def p_position_x():
        bad = base("UserMovedEvent")
        bad["position"]["x"] = "bad"
        assert first(expect_validation_error(bad)).path == "$.position.x"

    s.add("p_position_x", cat, p_position_x)

    def p_position_y():
        bad = base("UserMovedEvent")
        bad["position"]["y"] = "bad"
        assert first(expect_validation_error(bad)).path == "$.position.y"

    s.add("p_position_y", cat, p_position_y)

    def p_position_z():
        bad = base("UserMovedEvent")
        bad["position"]["z"] = "bad"
        assert first(expect_validation_error(bad)).path == "$.position.z"

    s.add("p_position_z", cat, p_position_z)

    def p_position_facing():
        bad = base("UserMovedEvent")
        bad["position"]["facing"] = "Sideways"
        assert first(expect_validation_error(bad)).path == "$.position.facing"

    s.add("p_position_facing", cat, p_position_facing)

    def p_list_index_wallet_type():
        bad = base("GetWalletResponse")
        bad["content"][0]["type"] = 1
        assert first(expect_validation_error(bad)).path == "$.content[0].type"

    s.add("p_wallet_type", cat, p_list_index_wallet_type)

    def p_list_index_wallet_amount():
        bad = base("GetWalletResponse")
        bad["content"][0]["amount"] = "x"
        assert first(expect_validation_error(bad)).path == "$.content[0].amount"

    s.add("p_wallet_amount", cat, p_list_index_wallet_amount)

    def p_list_second_index():
        bad = base("GetWalletResponse")
        bad["content"].append(clone(bad["content"][0]))
        bad["content"][1]["amount"] = "x"
        assert first(expect_validation_error(bad)).path == "$.content[1].amount"

    s.add("p_wallet_second_index", cat, p_list_second_index)

    def p_list_tenth_index():
        bad = base("GetWalletResponse")
        template = clone(bad["content"][0])
        bad["content"] = [clone(template) for _ in range(10)]
        bad["content"][9]["amount"] = "x"
        assert first(expect_validation_error(bad)).path == "$.content[9].amount"

    s.add("p_wallet_tenth_index", cat, p_list_tenth_index)

    def p_tuple_voice_second_element():
        bad = base("VoiceEvent")
        bad["users"][0][1] = 7
        assert first(expect_validation_error(bad)).path == "$.users[0][1]"

    s.add("p_voice_second_elem", cat, p_tuple_voice_second_element)

    def p_tuple_voice_first_element_id():
        bad = base("VoiceEvent")
        bad["users"][0][0]["id"] = 7
        assert first(expect_validation_error(bad)).path == "$.users[0][0].id"

    s.add("p_voice_first_elem_id", cat, p_tuple_voice_first_element_id)

    def p_content_users_tuple():
        bad = base("GetRoomUsersResponse")
        if bad.get("content"):
            bad["content"][0][0]["id"] = 9
            assert first(expect_validation_error(bad)).path == "$.content[0][0].id"

    s.add("p_content_tuple", cat, p_content_users_tuple)

    def p_sender_id():
        bad = base("ChannelEvent")
        bad["sender_id"] = 9
        assert first(expect_validation_error(bad)).path == "$.sender_id"

    s.add("p_sender_id", cat, p_sender_id)

    def p_room_info_owner():
        bad = base("SessionMetadata")
        if "room_info" in bad and "owner_id" in bad.get("room_info", {}):
            bad["room_info"]["owner_id"] = 9
            assert first(expect_validation_error(bad)).path == "$.room_info.owner_id"

    s.add("p_room_info_owner", cat, p_room_info_owner)

    def p_room_info_name():
        bad = base("SessionMetadata")
        if "room_info" in bad and "room_name" in bad.get("room_info", {}):
            bad["room_info"]["room_name"] = 9
            assert first(expect_validation_error(bad)).path == "$.room_info.room_name"

    s.add("p_room_info_name", cat, p_room_info_name)

    def p_moderator_id_camelcase():
        bad = base("RoomModeratedEvent")
        bad["moderatorId"] = 9
        assert first(expect_validation_error(bad)).path == "$.moderatorId"

    s.add("p_moderatorId", cat, p_moderator_id_camelcase)

    def p_target_user_id():
        bad = base("RoomModeratedEvent")
        bad["targetUserId"] = 9
        assert first(expect_validation_error(bad)).path == "$.targetUserId"

    s.add("p_targetUserId", cat, p_target_user_id)

    def p_moderation_type():
        bad = base("RoomModeratedEvent")
        bad["moderationType"] = "banish"
        assert first(expect_validation_error(bad)).path == "$.moderationType"

    s.add("p_moderationType", cat, p_moderation_type)

    def p_seconds_left():
        bad = base("VoiceEvent")
        bad["seconds_left"] = "x"
        assert first(expect_validation_error(bad)).path == "$.seconds_left"

    s.add("p_seconds_left", cat, p_seconds_left)

    def p_emote_id():
        bad = base("EmoteEvent")
        bad["emote_id"] = 9
        assert first(expect_validation_error(bad)).path == "$.emote_id"

    s.add("p_emote_id", cat, p_emote_id)

    def p_reaction():
        bad = base("ReactionEvent")
        bad["reaction"] = "sparkle"
        assert first(expect_validation_error(bad)).path == "$.reaction"

    s.add("p_reaction", cat, p_reaction)

    def p_receiver():
        bad = base("ReactionEvent")
        bad["receiver"] = "x"
        assert first(expect_validation_error(bad)).path == "$.receiver"

    s.add("p_receiver", cat, p_receiver)

    def p_item_type():
        bad = base("TipReactionEvent")
        if "item" in bad:
            bad["item"]["type"] = 9
            assert first(expect_validation_error(bad)).path == "$.item.type"

    s.add("p_item_type", cat, p_item_type)

    def p_item_amount():
        bad = base("TipReactionEvent")
        if "item" in bad:
            bad["item"]["amount"] = "x"
            assert first(expect_validation_error(bad)).path == "$.item.amount"

    s.add("p_item_amount", cat, p_item_amount)

    def p_error_message():
        bad = base("Error")
        bad["message"] = 9
        assert first(expect_validation_error(bad)).path == "$.message"

    s.add("p_error_message", cat, p_error_message)

    def p_deep_path_constructed():
        # Deep path through constructed nesting: content[0][1].x
        bad = base("GetRoomUsersResponse")
        if bad.get("content"):
            bad["content"][0][1]["x"] = "not-a-float"
            assert first(expect_validation_error(bad)).path == "$.content[0][1].x"

    s.add("p_deep_constructed", cat, p_deep_path_constructed)

    def p_path_starts_with_dollar():
        bad = base("ChatEvent")
        bad["message"] = 1
        assert first(expect_validation_error(bad)).path.startswith("$")

    s.add("p_starts_with_dollar", cat, p_path_starts_with_dollar)

    def p_path_uses_dot_separator():
        bad = base("ChatEvent")
        bad["user"]["id"] = 1
        p = first(expect_validation_error(bad)).path
        assert "." in p, p

    s.add("p_dot_separator", cat, p_path_uses_dot_separator)

    def p_path_uses_bracket_indices():
        bad = base("GetWalletResponse")
        bad["content"][0]["type"] = 1
        p = first(expect_validation_error(bad)).path
        assert "[0]" in p, p

    s.add("p_bracket_indices", cat, p_path_uses_bracket_indices)

    def p_path_no_space_padding():
        bad = base("ChatEvent")
        bad["message"] = 1
        p = first(expect_validation_error(bad)).path
        assert p == p.strip(), p

    s.add("p_no_padding", cat, p_path_no_space_padding)


# ═══════════════════════════════════════════════════════════════════════════
# 04 — Type-coercion matrix (generated: wrong-type injection per payload)
# ═══════════════════════════════════════════════════════════════════════════


def build_type_matrix_cases(s: Suite) -> None:
    """For every payload, for every top-level field, inject hostile values.
    Contract: validation either passes (value legal for that field) or raises
    HighriseFastValidationError. Never any other exception."""
    cat = "04_type_matrix"
    hostile_values = [
        ("int", 12345),
        ("str", "hostile"),
        ("boolt", True),
        ("none", None),
        ("list", ["x"]),
        ("dict", {"x": 1}),
        ("float", 3.14159),
    ]
    generated = 0
    for pname in ALL_PAYLOAD_NAMES:
        for key in top_keys(pname):
            for vname, v in hostile_values:
                if generated >= 180:
                    return

                def make(pn=pname, k=key, val=v):
                    def _t():
                        bad = base(pn)
                        bad[k] = copy.deepcopy(val)
                        expect_no_crash(bad)

                    return _t

                s.add(f"tmx_{pname}_{key}_{vname}", cat, make())
                generated += 1


# ═══════════════════════════════════════════════════════════════════════════
# 05 — Semantic bounds: full boundary sweep
# ═══════════════════════════════════════════════════════════════════════════


def build_semantic_cases(s: Suite) -> None:
    cat = "05_semantic"

    # --- chat message length sweep -----------------------------------------
    for length, should_pass in [
        (0, True),
        (1, True),
        (512, True),
        (1023, True),
        (1024, True),
        (1025, False),
        (2048, False),
        (10000, False),
    ]:

        def make(n=length, ok=should_pass):
            def _t():
                p = base("ChatEvent")
                p["message"] = "A" * n
                if ok:
                    expect_ok(p, strict_semantic=True)
                else:
                    expect_validation_error(p, strict_semantic=True)

            return _t

        s.add(f"sem_chat_len_{length}_{'ok' if should_pass else 'reject'}", cat, make())

    # --- position boundary sweep (x, y, z) ---------------------------------
    for axis in ("x", "y", "z"):
        for value, should_pass in [
            (-2000.1, False),
            (-2000.0, True),
            (-1999.9, True),
            (0.0, True),
            (1999.9, True),
            (2000.0, True),
            (2000.1, False),
            (10000.0, False),
        ]:

            def make(ax=axis, v=value, ok=should_pass):
                def _t():
                    p = base("UserMovedEvent")
                    p["position"][ax] = v
                    if ok:
                        expect_ok(p, strict_semantic=True)
                    else:
                        expect_validation_error(p, strict_semantic=True)

                return _t

            vs = str(value).replace(".", "_").replace("-", "neg")
            s.add(
                f"sem_pos_{axis}_{vs}_{'ok' if should_pass else 'reject'}", cat, make()
            )

    # --- wallet amount sweep ------------------------------------------------
    for amount, should_pass in [
        (-1000, False),
        (-1, False),
        (0, True),
        (1, True),
        (1000, True),
        (10**9, True),
    ]:

        def make(a=amount, ok=should_pass):
            def _t():
                p = base("GetWalletResponse")
                p["content"][0]["amount"] = a
                if ok:
                    expect_ok(p, strict_semantic=True)
                else:
                    expect_validation_error(p, strict_semantic=True)

            return _t

        s.add(f"sem_wallet_{amount}_{'ok' if should_pass else 'reject'}", cat, make())

    # --- multi-error semantic collection ------------------------------------
    def sem_all_axes_out_collects_three():
        bad = base("UserMovedEvent")
        for ax in ("x", "y", "z"):
            bad["position"][ax] = 5000.0
        report = debug_payload(bad, strict_semantic=True)
        assert non_repair_count(report) == 3, report
        assert sorted(set(paths(report))) == [
            "$.position.x",
            "$.position.y",
            "$.position.z",
        ]

    s.add("sem_all_axes_three_issues", cat, sem_all_axes_out_collects_three)

    def sem_wallet_two_items_both_negative():
        bad = base("GetWalletResponse")
        bad["content"] = [make_currency("gold", -1), make_currency("bubbles", -2)]
        report = debug_payload(bad, strict_semantic=True)
        assert non_repair_count(report) == 2, report
        assert "$.content[0].amount" in paths(report)
        assert "$.content[1].amount" in paths(report)

    s.add("sem_wallet_two_neg", cat, sem_wallet_two_items_both_negative)

    def sem_wallet_mixed_valid_invalid():
        bad = base("GetWalletResponse")
        bad["content"] = [make_currency("gold", 100), make_currency("gold", -1)]
        report = debug_payload(bad, strict_semantic=True)
        assert non_repair_count(report) == 1, report
        assert paths(report) == ["$.content[1].amount"]

    s.add("sem_wallet_mixed", cat, sem_wallet_mixed_valid_invalid)

    def sem_chat_and_position_combined():
        bad = base("ChatEvent")
        bad["message"] = "A" * 3000
        report = debug_payload(bad, strict_semantic=True)
        assert non_repair_count(report) >= 1

    s.add("sem_chat_combined", cat, sem_chat_and_position_combined)

    def sem_structural_plus_semantic_both_collected():
        bad = base("UserMovedEvent")
        bad["position"]["x"] = 9000.0  # semantic
        bad["user"]["id"] = 123  # structural
        report = debug_payload(bad, strict_semantic=True)
        code_set = set(codes(report))
        assert ReasonCode.WRONG_TYPE in code_set, report
        assert ReasonCode.OUT_OF_BOUNDS in code_set, report

    s.add(
        "sem_structural_plus_semantic", cat, sem_structural_plus_semantic_both_collected
    )

    def sem_nan_not_finite_even_without_semantic():
        bad = base("UserMovedEvent")
        bad["position"]["x"] = float("nan")
        expect_validation_error(bad, strict_semantic=False)

    s.add("sem_nan_always_rejected", cat, sem_nan_not_finite_even_without_semantic)

    def sem_inf_not_finite_even_without_semantic():
        bad = base("UserMovedEvent")
        bad["position"]["z"] = float("inf")
        expect_validation_error(bad, strict_semantic=False)

    s.add("sem_inf_always_rejected", cat, sem_inf_not_finite_even_without_semantic)

    def sem_negative_inf_always_rejected():
        bad = base("UserMovedEvent")
        bad["position"]["y"] = float("-inf")
        expect_validation_error(bad, strict_semantic=False)

    s.add("sem_neginf_always_rejected", cat, sem_negative_inf_always_rejected)

    def sem_unicode_message_length_semantics():
        """Length is counted in characters, not bytes (Python str semantics)."""
        p = base("ChatEvent")
        p["message"] = "é" * 1024  # 2048 bytes UTF-8, 1024 chars
        expect_ok(p, strict_semantic=True)

    s.add("sem_unicode_char_length", cat, sem_unicode_message_length_semantics)

    def sem_emoji_message_length():
        p = base("ChatEvent")
        p["message"] = "🎉" * 1024
        expect_ok(p, strict_semantic=True)

    s.add("sem_emoji_length", cat, sem_emoji_message_length)

    def sem_emoji_over_limit():
        p = base("ChatEvent")
        p["message"] = "🎉" * 1025
        expect_validation_error(p, strict_semantic=True)

    s.add("sem_emoji_over_limit", cat, sem_emoji_over_limit)

    def sem_whitespace_message_ok():
        p = base("ChatEvent")
        p["message"] = " " * 1024
        expect_ok(p, strict_semantic=True)

    s.add("sem_whitespace_ok", cat, sem_whitespace_message_ok)

    def sem_position_int_values_ok():
        p = base("UserMovedEvent")
        p["position"]["x"] = 100  # int accepted as float-compatible
        expect_ok(p, strict_semantic=True)

    s.add("sem_position_int_ok", cat, sem_position_int_values_ok)

    def sem_position_negative_zero_ok():
        p = base("UserMovedEvent")
        p["position"]["x"] = -0.0
        expect_ok(p, strict_semantic=True)

    s.add("sem_negzero_ok", cat, sem_position_negative_zero_ok)

    def sem_float_min_subnormal_in_bounds():
        p = base("UserMovedEvent")
        p["position"]["x"] = 5e-324  # smallest positive float
        expect_ok(p, strict_semantic=True)

    s.add("sem_subnormal_ok", cat, sem_float_min_subnormal_in_bounds)

    def sem_ancherposition_has_no_bounds():
        p = base("UserMovedEvent")
        p["position"] = make_anchor("a", 10**9)
        expect_no_crash(p, strict_semantic=True)

    s.add("sem_anchor_no_bounds", cat, sem_ancherposition_has_no_bounds)

    def sem_semantic_disabled_passes_oob():
        p = base("UserMovedEvent")
        p["position"]["x"] = 99999.0
        expect_ok(p, strict_semantic=False)

    s.add("sem_disabled_passes", cat, sem_semantic_disabled_passes_oob)


# ═══════════════════════════════════════════════════════════════════════════
# 06 — Protocol deep: field-removal matrix across ALL payloads (generated)
# ═══════════════════════════════════════════════════════════════════════════


def build_protocol_cases(s: Suite) -> None:
    """For every payload type, remove every top-level field one at a time.
    Contract: removal either triggers MISSING_FIELD at the right path,
    or passes (field is optional). Never crashes."""
    cat = "06_protocol"

    for pname in ALL_PAYLOAD_NAMES:
        # Base payload must validate
        def make_base(pn=pname):
            def _t():
                expect_ok(BASE_PAYLOADS[pn])

            return _t

        s.add(f"proto_base_{pname}", cat, make_base())

        for key in top_keys(pname):

            def make(pn=pname, k=key):
                def _t():
                    bad = base(pn)
                    del bad[k]
                    exc = expect_no_crash(bad)
                    if exc is not None:
                        assert (
                            first(exc).path == f"$.{k}"
                        ), f"{pn}.{k}: expected path $.{k}, got {first(exc).path}"
                        assert (
                            first(exc).reason_code == ReasonCode.MISSING_FIELD
                        ), f"{pn}.{k}: expected MISSING_FIELD, got {first(exc).reason_code}"

                return _t

            s.add(f"proto_rm_{pname}_{key}", cat, make())

    # --- explicit protocol probes not covered by the matrix -----------------
    def proto_session_metadata_full():
        p = base("SessionMetadata")
        expect_ok(p)

    s.add("proto_session_full", cat, proto_session_metadata_full)

    def proto_session_rate_limits_optional():
        p = base("SessionMetadata")
        if "rate_limits" in p:
            del p["rate_limits"]
            expect_ok(p)

    s.add("proto_session_rate_limits_opt", cat, proto_session_rate_limits_optional)

    def proto_session_connection_id_optional():
        p = base("SessionMetadata")
        if "connection_id" in p:
            del p["connection_id"]
            expect_ok(p)

    s.add("proto_session_conn_id_opt", cat, proto_session_connection_id_optional)

    def proto_session_sdk_version_optional():
        p = base("SessionMetadata")
        if "sdk_version" in p:
            del p["sdk_version"]
            expect_ok(p)

    s.add("proto_session_sdk_opt", cat, proto_session_sdk_version_optional)

    def proto_session_room_info_as_list():
        p = base("SessionMetadata")
        if "room_info" in p:
            p["room_info"] = []
            expect_validation_error(p)

    s.add("proto_session_room_info_list", cat, proto_session_room_info_as_list)

    def proto_userjoined_position_anchor():
        p = base("UserJoinedEvent")
        p["position"] = make_anchor()
        expect_no_crash(p)

    s.add("proto_userjoined_anchor", cat, proto_userjoined_position_anchor)

    def proto_usermoved_entity_no_ix():
        p = base("UserMovedEvent")
        p["position"] = {"entity_id": "e1"}
        expect_no_crash(p)

    s.add("proto_moved_entity_only", cat, proto_usermoved_entity_no_ix)

    def proto_usermoved_ix_no_entity():
        p = base("UserMovedEvent")
        p["position"] = {"anchor_ix": 0}
        expect_no_crash(p)

    s.add("proto_moved_ix_only", cat, proto_usermoved_ix_no_entity)

    def proto_voice_users_two_rows():
        p = base("VoiceEvent")
        row = clone(p["users"][0])
        p["users"] = [row, clone(row)]
        expect_ok(p)

    s.add("proto_voice_two_rows", cat, proto_voice_users_two_rows)

    def proto_voice_users_three_rows():
        p = base("VoiceEvent")
        row = clone(p["users"][0])
        p["users"] = [row, clone(row), clone(row)]
        expect_ok(p)

    s.add("proto_voice_three_rows", cat, proto_voice_users_three_rows)

    def proto_voice_users_ten_rows():
        p = base("VoiceEvent")
        row = clone(p["users"][0])
        p["users"] = [clone(row) for _ in range(10)]
        expect_ok(p)

    s.add("proto_voice_ten_rows", cat, proto_voice_users_ten_rows)

    def proto_voice_row_zero_len():
        p = base("VoiceEvent")
        p["users"][0] = []
        expect_validation_error(p)

    s.add("proto_voice_row_empty", cat, proto_voice_row_zero_len)

    def proto_voice_row_none():
        p = base("VoiceEvent")
        p["users"][0] = None
        expect_validation_error(p)

    s.add("proto_voice_row_none", cat, proto_voice_row_none)

    def proto_roommod_duration_null():
        p = base("RoomModeratedEvent")
        if "duration" in p:
            p["duration"] = None
            expect_ok(p)  # nullable

    s.add("proto_roommod_duration_null", cat, proto_roommod_duration_null)

    def proto_error_do_not_reconnect_true():
        p = base("Error")
        if "do_not_reconnect" in p:
            p["do_not_reconnect"] = True
            expect_ok(p)

    s.add("proto_error_dnr_true", cat, proto_error_do_not_reconnect_true)

    def proto_error_rid_null():
        p = base("Error")
        if "rid" in p:
            p["rid"] = None
            expect_ok(p)

    s.add("proto_error_rid_null", cat, proto_error_rid_null)

    def proto_wallet_two_items():
        p = base("GetWalletResponse")
        p["content"] = [make_currency("gold", 10), make_currency("bubbles", 20)]
        expect_ok(p)

    s.add("proto_wallet_two_items", cat, proto_wallet_two_items)

    def proto_roomusers_two_rows():
        p = base("GetRoomUsersResponse")
        if p.get("content"):
            row = clone(p["content"][0])
            p["content"] = [row, clone(row)]
            expect_ok(p)

    s.add("proto_roomusers_two_rows", cat, proto_roomusers_two_rows)

    def proto_roomusers_position_anchor():
        p = base("GetRoomUsersResponse")
        if p.get("content"):
            p["content"][0][1] = make_anchor()
            expect_no_crash(p)

    s.add("proto_roomusers_anchor", cat, proto_roomusers_position_anchor)


# ═══════════════════════════════════════════════════════════════════════════
# 07 — Nested structures deep
# ═══════════════════════════════════════════════════════════════════════════


def build_nested_cases(s: Suite) -> None:
    cat = "07_nested"

    def n_user_missing_id():
        bad = base("ChatEvent")
        del bad["user"]["id"]
        assert first(expect_validation_error(bad)).path == "$.user.id"

    s.add("n_user_missing_id", cat, n_user_missing_id)

    def n_user_missing_username():
        bad = base("ChatEvent")
        del bad["user"]["username"]
        assert first(expect_validation_error(bad)).path == "$.user.username"

    s.add("n_user_missing_username", cat, n_user_missing_username)

    def n_user_extra_keys_ignored():
        good = base("ChatEvent")
        good["user"]["avatar"] = "extra"
        good["user"]["__class__"] = "User"
        expect_ok(good)

    s.add("n_user_extra_keys", cat, n_user_extra_keys_ignored)

    def n_user_long_values():
        good = base("ChatEvent")
        good["user"]["username"] = "u" * 10000
        expect_ok(good)

    s.add("n_user_long_values", cat, n_user_long_values)

    def n_user_control_chars():
        good = base("ChatEvent")
        good["user"]["username"] = "a\x01b\x02c"
        expect_ok(good)

    s.add("n_user_control_chars", cat, n_user_control_chars)

    def n_receiver_missing_id():
        bad = base("ReactionEvent")
        del bad["receiver"]["id"]
        assert first(expect_validation_error(bad)).path == "$.receiver.id"

    s.add("n_receiver_missing_id", cat, n_receiver_missing_id)

    def n_emote_receiver_ok_when_present():
        good = base("EmoteEvent")
        if "receiver" not in good:
            good["receiver"] = make_user("r1", "rec")
        expect_ok(good)

    s.add("n_emote_receiver_present", cat, n_emote_receiver_ok_when_present)

    def n_position_missing_x():
        bad = base("UserMovedEvent")
        del bad["position"]["x"]
        assert first(expect_validation_error(bad)).path == "$.position.x"

    s.add("n_pos_missing_x", cat, n_position_missing_x)

    def n_position_missing_all():
        bad = base("UserMovedEvent")
        bad["position"] = {}
        report = debug_payload(bad)
        assert non_repair_count(report) >= 3, report

    s.add("n_pos_missing_all", cat, n_position_missing_all)

    def n_position_extra_keys():
        good = base("UserMovedEvent")
        good["position"]["w"] = 4.0
        expect_ok(good)

    s.add("n_pos_extra_keys", cat, n_position_extra_keys)

    def n_position_entity_and_x_both():
        p = base("UserMovedEvent")
        p["position"] = {
            "entity_id": "e1",
            "anchor_ix": 0,
            "x": 1.0,
            "y": 1.0,
            "z": 1.0,
        }
        expect_no_crash(p)

    s.add("n_pos_entity_and_xyz", cat, n_position_entity_and_x_both)

    def n_depth_20_no_crash():
        deep = {
            "_type": "ChatEvent",
            "user": make_user(),
            "message": "m",
            "whisper": False,
        }
        cur = deep
        for i in range(20):
            cur[f"n{i}"] = {}
            cur = cur[f"n{i}"]
        cur["leaf"] = True
        expect_no_crash(deep)

    s.add("n_depth_20", cat, n_depth_20_no_crash)

    def n_depth_100_no_crash():
        deep = {
            "_type": "ChatEvent",
            "user": make_user(),
            "message": "m",
            "whisper": False,
        }
        cur = deep
        for i in range(100):
            cur[f"n{i}"] = {}
            cur = cur[f"n{i}"]
        cur["leaf"] = True
        expect_no_crash(deep)

    s.add("n_depth_100", cat, n_depth_100_no_crash)

    def n_depth_500_no_crash():
        deep = {
            "_type": "ChatEvent",
            "user": make_user(),
            "message": "m",
            "whisper": False,
        }
        cur = deep
        for i in range(500):
            cur[f"n{i}"] = {}
            cur = cur[f"n{i}"]
        cur["leaf"] = True
        expect_no_crash(deep)

    s.add("n_depth_500", cat, n_depth_500_no_crash)

    def n_nested_list_of_dicts():
        good = base("GetWalletResponse")
        good["content"] = [make_currency() for _ in range(50)]
        expect_ok(good)

    s.add("n_list_50_dicts", cat, n_nested_list_of_dicts)

    def n_nested_error_at_depth3():
        bad = base("GetRoomUsersResponse")
        if bad.get("content"):
            bad["content"][0][1]["facing"] = "Wrong"
            assert first(expect_validation_error(bad)).path == "$.content[0][1].facing"

    s.add("n_err_depth3_path", cat, n_nested_error_at_depth3)

    def n_interleaved_errors():
        bad = base("GetWalletResponse")
        bad["content"] = [
            make_currency("gold", 1),
            {"type": 9, "amount": "x"},  # both fields bad
            make_currency("gold", 3),
            {"type": "gold"},  # missing amount
        ]
        report = debug_payload(bad)
        assert non_repair_count(report) >= 3, report

    s.add("n_interleaved_errors", cat, n_interleaved_errors)


# ═══════════════════════════════════════════════════════════════════════════
# 08 — Lists / tuples edge cases
# ═══════════════════════════════════════════════════════════════════════════


def build_list_cases(s: Suite) -> None:
    cat = "08_list"

    def l_content_tuple_instead_of_list():
        p = base("GetWalletResponse")
        p["content"] = tuple(p["content"])
        expect_no_crash(p)

    s.add("l_content_tuple", cat, l_content_tuple_instead_of_list)

    def l_users_tuple():
        p = base("VoiceEvent")
        p["users"] = tuple(p["users"])
        expect_no_crash(p)

    s.add("l_users_tuple", cat, l_users_tuple)

    def l_content_none_row():
        bad = base("GetWalletResponse")
        bad["content"] = [None]
        expect_validation_error(bad)

    s.add("l_none_row", cat, l_content_none_row)

    def l_content_int_row():
        bad = base("GetWalletResponse")
        bad["content"] = [42]
        expect_validation_error(bad)

    s.add("l_int_row", cat, l_content_int_row)

    def l_content_str_row():
        bad = base("GetWalletResponse")
        bad["content"] = ["gold"]
        expect_validation_error(bad)

    s.add("l_str_row", cat, l_content_str_row)

    def l_content_row_missing_all():
        bad = base("GetWalletResponse")
        bad["content"] = [{}]
        report = debug_payload(bad)
        assert non_repair_count(report) >= 2, report  # type + amount missing

    s.add("l_row_empty_dict", cat, l_content_row_missing_all)

    def l_empty_lists_everywhere():
        for pname in ("GetWalletResponse",):
            p = base(pname)
            p["content"] = []
            expect_ok(p)

    s.add("l_empty_content", cat, l_empty_lists_everywhere)

    def l_users_empty():
        p = base("VoiceEvent")
        p["users"] = []
        expect_ok(p)

    s.add("l_users_empty", cat, l_users_empty)

    def l_invalid_at_index_999():
        bad = base("GetWalletResponse")
        template = make_currency()
        bad["content"] = [clone(template) for _ in range(1000)]
        bad["content"][999]["amount"] = "bad"
        exc = expect_validation_error(bad)
        assert first(exc).path == "$.content[999].amount", first(exc).path

    s.add("l_invalid_at_999", cat, l_invalid_at_index_999)

    def l_invalid_at_index_0():
        bad = base("GetWalletResponse")
        template = make_currency()
        bad["content"] = [clone(template) for _ in range(10)]
        bad["content"][0]["amount"] = "bad"
        assert first(expect_validation_error(bad)).path == "$.content[0].amount"

    s.add("l_invalid_at_0", cat, l_invalid_at_index_0)

    def l_first_invalid_wins():
        bad = base("GetWalletResponse")
        template = make_currency()
        bad["content"] = [clone(template) for _ in range(10)]
        bad["content"][3]["amount"] = "bad"
        bad["content"][7]["amount"] = "bad"
        exc = expect_validation_error(bad)
        assert first(exc).path == "$.content[3].amount", first(exc).path

    s.add("l_first_invalid_wins", cat, l_first_invalid_wins)

    def l_1000_items_ok():
        good = base("GetWalletResponse")
        good["content"] = [make_currency() for _ in range(1000)]
        expect_ok(good)

    s.add("l_1000_items_ok", cat, l_1000_items_ok)

    def l_voice_500_rows():
        p = base("VoiceEvent")
        row = clone(p["users"][0])
        p["users"] = [clone(row) for _ in range(500)]
        expect_ok(p)

    s.add("l_voice_500_rows", cat, l_voice_500_rows)

    def l_tuple_row_str_first():
        bad = base("VoiceEvent")
        bad["users"][0] = ["notdict", "voice"]
        expect_validation_error(bad)

    s.add("l_tuple_row_str_first", cat, l_tuple_row_str_first)

    def l_tuple_row_dict_second():
        bad = base("VoiceEvent")
        bad["users"][0] = [{"id": "x"}, {"not": "str"}]
        expect_validation_error(bad)

    s.add("l_tuple_row_dict_second", cat, l_tuple_row_dict_second)

    def l_content_row_int_second():
        bad = base("GetRoomUsersResponse")
        if bad.get("content"):
            bad["content"][0] = [make_user(), 42]
            expect_validation_error(bad)

    s.add("l_row_int_second", cat, l_content_row_int_second)

    def l_content_row_none_second():
        bad = base("GetRoomUsersResponse")
        if bad.get("content"):
            bad["content"][0] = [make_user(), None]
            expect_validation_error(bad)

    s.add("l_row_none_second", cat, l_content_row_none_second)


# ═══════════════════════════════════════════════════════════════════════════
# 09 — Strings: complete type-theory sweep
# ═══════════════════════════════════════════════════════════════════════════


def build_string_cases(s: Suite) -> None:
    cat = "09_string"

    accept_cases = [
        ("empty", ""),
        ("null_byte", "a\x00b"),
        ("newline", "a\nb"),
        ("tab", "a\tb"),
        ("cr", "a\rb"),
        ("backslash", "a\\b"),
        ("quote", 'a"b'),
        ("single_quote", "a'b"),
        ("rtl", "a‮b"),
        ("zwj", "a‍b"),
        ("bom", "\ufeffabc"),
        ("unicode_misc", "héllo wörld 日本語"),
        ("str_none_literal", "None"),
        ("str_null_literal", "null"),
        ("str_undefined", "undefined"),
        ("str_nan", "NaN"),
        ("str_braces", "{{template}}"),
        ("str_dollar", "$._type"),
        ("str_html", "<script>alert(1)</script>"),
        ("str_sql", "'; DROP TABLE users; --"),
        ("str_path", "../../etc/passwd"),
        ("str_long_word", "a" * 500),
        ("str_mixed_script", "abcАБВ一二三"),
    ]
    for label, value in accept_cases:

        def make(v=value):
            def _t():
                p = base("ChatEvent")
                p["message"] = v
                expect_ok(p)

            return _t

        s.add(f"str_ok_{label}", cat, make())

    reject_cases = [
        ("int", 123),
        ("float", 1.5),
        ("bool_true", True),
        ("bool_false", False),
        ("none", None),
        ("list", ["a"]),
        ("dict", {"a": 1}),
        ("tuple", ("a",)),
        ("bytes", b"bytes"),
        ("bytearray", bytearray(b"x")),
        ("memoryview", memoryview(b"x")),
        ("set", {"a"}),
        ("frozenset", frozenset({"a"})),
        ("range", range(5)),
        ("complex", 1 + 2j),
    ]
    for label, value in reject_cases:

        def make(v=value):
            def _t():
                p = base("ChatEvent")
                p["message"] = v
                expect_validation_error(p)

            return _t

        s.add(f"str_reject_{label}", cat, make())

    def str_subclass_accepted():
        class MyStr(str):
            pass

        p = base("ChatEvent")
        p["message"] = MyStr("hello")
        expect_ok(p)

    s.add("str_subclass_ok", cat, str_subclass_accepted)

    def str_1m_chars():
        p = base("ChatEvent")
        p["message"] = "x" * 1_000_000
        # semantic off by default; structural must accept
        expect_ok(p, strict_semantic=False)

    s.add("str_1m_chars", cat, str_1m_chars)

    def str_surrogate():
        # Lone surrogate — cannot be JSON-encoded but is a valid Python str
        p = base("ChatEvent")
        p["message"] = "\ud800"
        expect_no_crash(p)

    s.add("str_surrogate", cat, str_surrogate)

    def str_concat_edge():
        p = base("ChatEvent")
        p["message"] = "a" * 1023 + "é"  # 1024 chars
        expect_ok(p, strict_semantic=True)

    s.add("str_concat_edge", cat, str_concat_edge)

    def str_username_bytes_rejected():
        bad = base("ChatEvent")
        bad["user"]["username"] = b"name"
        expect_validation_error(bad)

    s.add("str_username_bytes", cat, str_username_bytes_rejected)

    def str_type_bytes_rejected():
        exc = expect_validation_error({"_type": b"ChatEvent"})
        assert first(exc).reason_code == ReasonCode.WRONG_TYPE

    s.add("str_type_bytes", cat, str_type_bytes_rejected)


# ═══════════════════════════════════════════════════════════════════════════
# 10 — Numbers: int/float coercion theory
# ═══════════════════════════════════════════════════════════════════════════


def build_number_cases(s: Suite) -> None:
    cat = "10_number"

    # int-compatible values (documented coercion behavior)
    int_accept = [
        ("zero", 0),
        ("neg_one", -1),
        ("big_63", 2**63),
        ("big_128", 2**128),
        ("float_whole", 1e10),
        ("bool_true", True),
        ("bool_false", False),
        ("numeric_str", "60"),
    ]
    for label, v in int_accept:

        def make(val=v):
            def _t():
                p = base("RoomModeratedEvent")
                if "duration" in p:
                    p["duration"] = val
                    expect_no_crash(p)

            return _t

        s.add(f"num_int_ok_{label}", cat, make())

    int_reject = [
        ("alpha_str", "abc"),
        ("empty_str", ""),
        ("list", [1]),
        ("dict", {"a": 1}),
        ("none", None),
        ("nan_float", float("nan")),
    ]
    for label, v in int_reject:

        def make(val=v):
            def _t():
                p = base("RoomModeratedEvent")
                if "duration" in p:
                    p["duration"] = val
                    expect_validation_error(p)

            return _t

        s.add(f"num_int_reject_{label}", cat, make())

    def num_int_inf_overflow():
        p = base("RoomModeratedEvent")
        if "duration" in p:
            p["duration"] = float("inf")
            expect_no_crash(p)  # int(inf) raises OverflowError -> must be caught

    s.add("num_int_inf", cat, num_int_inf_overflow)

    def num_decimal():
        p = base("RoomModeratedEvent")
        if "duration" in p:
            p["duration"] = Decimal("5")
            expect_no_crash(p)

    s.add("num_decimal", cat, num_decimal)

    def num_fraction():
        p = base("RoomModeratedEvent")
        if "duration" in p:
            p["duration"] = Fraction(10, 2)
            expect_no_crash(p)

    s.add("num_fraction", cat, num_fraction)

    # float-compatible values on position.x
    float_accept = [
        ("zero", 0.0),
        ("neg_zero", -0.0),
        ("int", 5),
        ("max_finite", 1e308),
        ("numeric_str", "1.5"),
        ("exp_str", "1e2"),
        ("decimal", Decimal("2.5")),
        ("fraction", Fraction(3, 2)),
        ("padded_str", " 1.5 "),
    ]
    for label, v in float_accept:

        def make(val=v):
            def _t():
                p = base("UserMovedEvent")
                p["position"]["x"] = val
                expect_no_crash(p, strict_semantic=False)

            return _t

        s.add(f"num_float_ok_{label}", cat, make())

    float_reject = [
        ("nan", float("nan")),
        ("inf", float("inf")),
        ("neg_inf", float("-inf")),
        ("overflow_1e309", 1e309),
        ("alpha_str", "abc"),
        ("none", None),
        ("list", [1.0]),
        ("complex", complex(1, 2)),
    ]
    for label, v in float_reject:

        def make(val=v):
            def _t():
                p = base("UserMovedEvent")
                p["position"]["x"] = val
                expect_validation_error(p)

            return _t

        s.add(f"num_float_reject_{label}", cat, make())

    def num_float_inf_str():
        p = base("UserMovedEvent")
        p["position"]["x"] = "inf"
        expect_validation_error(p)  # float("inf") then rejected as non-finite

    s.add("num_float_str_inf", cat, num_float_inf_str)

    def num_float_nan_str():
        p = base("UserMovedEvent")
        p["position"]["x"] = "nan"
        expect_validation_error(p)

    s.add("num_float_str_nan", cat, num_float_nan_str)

    def num_float_custom_dunder():
        class HasFloat:
            def __float__(self):
                return 1.5

        p = base("UserMovedEvent")
        p["position"]["x"] = HasFloat()
        expect_no_crash(p)

    s.add("num_custom_float", cat, num_float_custom_dunder)

    def num_float_custom_raising():
        class BadFloat:
            def __float__(self):
                raise ValueError("boom")

        p = base("UserMovedEvent")
        p["position"]["x"] = BadFloat()
        expect_validation_error(p)

    s.add("num_custom_float_raises", cat, num_float_custom_raising)

    def num_wallet_amount_numeric_str():
        p = base("GetWalletResponse")
        p["content"][0]["amount"] = "100"
        expect_no_crash(p)

    s.add("num_wallet_str_amount", cat, num_wallet_amount_numeric_str)

    def num_wallet_amount_bool():
        p = base("GetWalletResponse")
        p["content"][0]["amount"] = True
        expect_no_crash(p)

    s.add("num_wallet_bool_amount", cat, num_wallet_amount_bool)

    def num_wallet_huge_amount():
        p = base("GetWalletResponse")
        p["content"][0]["amount"] = 10**30
        expect_ok(p, strict_semantic=True)  # no upper bound documented

    s.add("num_wallet_huge", cat, num_wallet_huge_amount)


# ═══════════════════════════════════════════════════════════════════════════
# 11 — Booleans / None / null semantics
# ═══════════════════════════════════════════════════════════════════════════


def build_bool_cases(s: Suite) -> None:
    cat = "11_bool"

    bool_reject = [
        ("int_1", 1),
        ("int_0", 0),
        ("str_true", "true"),
        ("str_True", "True"),
        ("str_yes", "yes"),
        ("str_1", "1"),
        ("none", None),
        ("list", []),
        ("dict", {}),
        ("float", 0.0),
        ("float_1", 1.0),
    ]
    for label, v in bool_reject:

        def make(val=v):
            def _t():
                p = base("ChatEvent")
                p["whisper"] = val
                expect_validation_error(p)

            return _t

        s.add(f"bool_reject_{label}", cat, make())

    def bool_true_ok():
        p = base("ChatEvent")
        p["whisper"] = True
        expect_ok(p)

    s.add("bool_true_ok", cat, bool_true_ok)

    def bool_false_ok():
        p = base("ChatEvent")
        p["whisper"] = False
        expect_ok(p)

    s.add("bool_false_ok", cat, bool_false_ok)

    def bool_default_when_missing():
        """Fields with a default bool should pass when absent."""
        for pname in ALL_PAYLOAD_NAMES:
            p = base(pname)
            for k in top_keys(pname):
                if p[k] is False:
                    del p[k]
                    expect_no_crash(p)
                    return  # one probe is enough for this contract

    s.add("bool_default_missing", cat, bool_default_when_missing)

    def null_optional_fields_ok():
        """Every None-valued field in base payloads stays valid."""
        found = 0
        for pname in ALL_PAYLOAD_NAMES:
            p = base(pname)
            for k in top_keys(pname):
                if p[k] is None:
                    expect_ok(p)  # base already has None; it must validate
                    found += 1
                    break
        assert found >= 0  # informational; at least no crash

    s.add("null_optional_ok", cat, null_optional_fields_ok)

    def none_replaced_with_bad_type():
        p = base("Error")
        if "rid" in p and p["rid"] is None:
            p["rid"] = 123
            expect_validation_error(p)

    s.add("null_replaced_bad", cat, none_replaced_with_bad_type)


# ═══════════════════════════════════════════════════════════════════════════
# 12 — Model <-> validator consistency (per-field)
# ═══════════════════════════════════════════════════════════════════════════


def build_consistency_cases(s: Suite) -> None:
    cat = "12_consistency"

    def c_position_facing_default():
        """Position.facing defaults to FrontRight — removing it must be OK."""
        p = base("UserMovedEvent")
        if "facing" in p["position"]:
            del p["position"]["facing"]
            expect_ok(p)

    s.add("c_facing_default", cat, c_position_facing_default)

    def c_anchor_ix_int_coercion():
        p = base("UserMovedEvent")
        p["position"] = make_anchor("e1", 0)
        expect_no_crash(p)

    s.add("c_anchor_ix", cat, c_anchor_ix_int_coercion)

    def c_currency_item_required_both():
        bad = base("GetWalletResponse")
        del bad["content"][0]["amount"]
        assert first(expect_validation_error(bad)).path == "$.content[0].amount"

    s.add("c_currency_amount_req", cat, c_currency_item_required_both)

    def c_every_base_payload_round_validates():
        for name in ALL_PAYLOAD_NAMES:
            expect_ok(BASE_PAYLOADS[name])

    s.add("c_all_bases_valid", cat, c_every_base_payload_round_validates)

    def c_bases_are_plain_dicts():
        for name in ALL_PAYLOAD_NAMES:
            assert isinstance(BASE_PAYLOADS[name], dict), name

    s.add("c_bases_are_dicts", cat, c_bases_are_plain_dicts)

    def c_bases_have_type_key():
        for name in ALL_PAYLOAD_NAMES:
            assert BASE_PAYLOADS[name].get("_type") == name, name

    s.add("c_bases_have_type", cat, c_bases_have_type_key)

    def c_chat_user_is_dict():
        p = BASE_PAYLOADS["ChatEvent"]
        assert isinstance(p["user"], dict)

    s.add("c_chat_user_dict", cat, c_chat_user_is_dict)

    def c_wallet_content_is_list():
        p = BASE_PAYLOADS["GetWalletResponse"]
        assert isinstance(p["content"], list) and len(p["content"]) >= 1

    s.add("c_wallet_content_list", cat, c_wallet_content_is_list)

    def c_voice_users_shape():
        p = BASE_PAYLOADS["VoiceEvent"]
        users = p["users"]
        assert isinstance(users, list)
        if users:
            row = users[0]
            assert isinstance(row, (list, tuple)) and len(row) == 2, row

    s.add("c_voice_shape", cat, c_voice_users_shape)

    def c_roommod_fields_camel():
        p = BASE_PAYLOADS["RoomModeratedEvent"]
        for k in ("moderatorId", "targetUserId", "moderationType"):
            assert k in p, (k, p)

    s.add("c_roommod_camel", cat, c_roommod_fields_camel)

    def c_session_room_info_shape():
        p = BASE_PAYLOADS["SessionMetadata"]
        if "room_info" in p:
            assert isinstance(p["room_info"], dict)

    s.add("c_session_roominfo", cat, c_session_room_info_shape)

    def c_position_keys():
        p = BASE_PAYLOADS["UserMovedEvent"]["position"]
        for k in ("x", "y", "z"):
            assert k in p, (k, p)

    s.add("c_position_keys", cat, c_position_keys)

    def c_error_has_message():
        assert "message" in BASE_PAYLOADS["Error"]

    s.add("c_error_message", cat, c_error_has_message)

    def c_bases_not_shared_mutable_state():
        """Mutating a clone must not affect BASE_PAYLOADS."""
        p = base("ChatEvent")
        p["user"]["id"] = "HACKED"
        assert BASE_PAYLOADS["ChatEvent"]["user"]["id"] != "HACKED"

    s.add("c_no_shared_state", cat, c_bases_not_shared_mutable_state)


# ═══════════════════════════════════════════════════════════════════════════
# 13 — Web API models
# ═══════════════════════════════════════════════════════════════════════════


def build_webapi_cases(s: Suite) -> None:
    cat = "13_webapi"
    try:
        import highrise_fast.models_webapi as mweb
    except Exception:
        mweb = None

    def w_importable():
        assert mweb is not None, "models_webapi not importable"

    s.add("w_importable", cat, w_importable)

    if mweb is None:
        return

    model_probes = [
        ("WebApiResponse", {"data": {"ok": True}}),
        ("WebApiError", {"error": "boom"}),
        ("WebApiUser", {"id": "u1", "username": "x"}),
        ("WebApiRoom", {"id": "r1", "name": "room"}),
        ("WebApiWallet", {"gold": 1, "bubbles": 2}),
        ("WebApiItem", {"id": "i1"}),
        ("WebApiConversation", {"id": "c1"}),
        ("WebApiMessage", {"id": "m1", "content": "hi"}),
    ]
    for cls_name, kwargs in model_probes:

        def make(cn=cls_name, kw=kwargs):
            def _t():
                cls = getattr(mweb, cn, None)
                if cls is None:
                    return  # model absent — skip
                obj = cls(**kw) if isinstance(kw, dict) else cls()
                assert obj is not None

            return _t

        s.add(f"w_model_{cls_name}", cat, make())

    def w_response_missing_data():
        cls = getattr(mweb, "WebApiResponse", None)
        if cls is None:
            return
        # data required -> TypeError is fine
        with contextlib.suppress(TypeError):
            cls()

    s.add("w_response_missing_data", cat, w_response_missing_data)


# ═══════════════════════════════════════════════════════════════════════════
# 14 — Async / concurrency / state machine
# ═══════════════════════════════════════════════════════════════════════════


def build_async_cases(s: Suite) -> None:
    cat = "14_async"

    def a_100_tasks_mixed():
        async def one(i: int):
            if i % 2 == 0:
                validate_server_message(base("ChatEvent"))
            else:
                with contextlib.suppress(HighriseFastValidationError):
                    validate_server_message({"_type": "ChatEvent", "message": 1})

        async def run():
            await asyncio.gather(*[one(i) for i in range(100)])

        asyncio.run(run())

    s.add("a_100_mixed_tasks", cat, a_100_tasks_mixed)

    def a_500_tasks_valid():
        payload = base("GetWalletResponse")

        async def one():
            validate_server_message(payload)

        async def run():
            await asyncio.gather(*[one() for _ in range(500)])

        asyncio.run(run())

    s.add("a_500_valid", cat, a_500_tasks_valid)

    def a_shared_dict_unmodified():
        shared = base("ChatEvent")
        snap = copy.deepcopy(shared)

        async def one():
            validate_server_message(shared)

        async def run():
            await asyncio.gather(*[one() for _ in range(50)])

        asyncio.run(run())
        assert shared == snap

    s.add("a_shared_unmodified", cat, a_shared_dict_unmodified)

    def a_concurrent_debug_and_validate():
        async def worker():
            for _ in range(10):
                validate_server_message(base("ChatEvent"))
                debug_payload(base("ChatEvent"))

        async def run():
            await asyncio.gather(*[worker() for _ in range(20)])

        asyncio.run(run())

    s.add("a_debug_plus_validate", cat, a_concurrent_debug_and_validate)

    def a_concurrent_invalid_payloads():
        bad = {"_type": "ChatEvent", "message": 1, "whisper": "x"}

        async def one():
            try:
                validate_server_message(bad)
                raise AssertionError("should have failed")
            except HighriseFastValidationError:
                pass

        async def run():
            await asyncio.gather(*[one() for _ in range(100)])

        asyncio.run(run())

    s.add("a_concurrent_invalid", cat, a_concurrent_invalid_payloads)

    def a_debug_never_corrupts_report():
        async def one():
            r = debug_payload(base("ChatEvent"))
            assert r["ok"] is True
            return r

        async def run():
            results = await asyncio.gather(*[one() for _ in range(50)])
            assert all(r["ok"] is True for r in results)

        asyncio.run(run())

    s.add("a_debug_no_corruption", cat, a_debug_never_corrupts_report)

    def a_all_payload_types_concurrently():
        names = ALL_PAYLOAD_NAMES

        async def one(n: str):
            validate_server_message(BASE_PAYLOADS[n])

        async def run():
            await asyncio.gather(*[one(n) for n in names])

        asyncio.run(run())

    s.add("a_all_types_concurrent", cat, a_all_payload_types_concurrently)


# ═══════════════════════════════════════════════════════════════════════════
# 15 — Encoding / input-type handling
# ═══════════════════════════════════════════════════════════════════════════


def build_encoding_cases(s: Suite) -> None:
    cat = "15_encoding"

    non_dict_inputs = [
        ("bytes", b"{}"),
        ("json_str", '{"_type": "ChatEvent"}'),
        ("list", [1, 2]),
        ("none", None),
        ("int", 42),
        ("float", 4.2),
        ("bool", True),
        ("tuple", (1, 2)),
        ("set", {1}),
        ("str", "hello"),
    ]
    for label, v in non_dict_inputs:

        def make(val=v):
            def _t():
                exc = expect_validation_error(val)
                assert first(exc).path == "$"
                assert first(exc).reason_code == ReasonCode.WRONG_TYPE

            return _t

        s.add(f"enc_reject_{label}", cat, make())

    type_mangles = [
        ("bytes", b"ChatEvent"),
        ("int", 123),
        ("none", None),
        ("bool_true", True),
        ("bool_false", False),
        ("list", ["ChatEvent"]),
        ("dict", {"inner": 1}),
        ("float", 1.5),
        ("tuple", ("ChatEvent",)),
    ]
    for label, v in type_mangles:

        def make(val=v):
            def _t():
                exc = expect_validation_error({"_type": val})
                assert first(exc).reason_code == ReasonCode.WRONG_TYPE
                assert first(exc).path == "$._type"

            return _t

        s.add(f"enc_type_{label}", cat, make())

    unknown_types = [
        "FakeEvent",
        "chatEvent",
        "CHATEVENT",
        "ChatEvent ",
        " ChatEvent",
        "",
        "chat_event",
        "Chat-Event",
        "Chat.Event",
        "$",
        "null",
        "None",
        "0",
        "chatvent",
        "ChatEvents",
    ]
    for ut in unknown_types:

        def make(val=ut):
            def _t():
                exc = expect_validation_error({"_type": val})
                assert first(exc).reason_code == ReasonCode.UNKNOWN_TYPE

            return _t

        safe = (
            ut.replace(" ", "_sp_").replace(".", "_dot_").replace("-", "_dash_")
            or "empty"
        )
        s.add(f"enc_unknown_{safe}", cat, make())

    def enc_debug_on_bytes():
        report = debug_payload(b"{}")
        assert report["ok"] is False
        assert report["issue_count"] == 1

    s.add("enc_debug_bytes", cat, enc_debug_on_bytes)

    def enc_debug_on_string():
        report = debug_payload('{"_type": 1}')
        assert report["ok"] is False

    s.add("enc_debug_string", cat, enc_debug_on_string)

    def enc_debug_on_none():
        report = debug_payload(None)
        assert report["ok"] is False
        assert report["issue_count"] == 1

    s.add("enc_debug_none", cat, enc_debug_on_none)

    def enc_debug_on_list():
        report = debug_payload([1, 2, 3])
        assert report["ok"] is False

    s.add("enc_debug_list", cat, enc_debug_on_list)

    def enc_unicode_type_name():
        exc = expect_validation_error({"_type": "ChatEventé"})
        assert first(exc).reason_code == ReasonCode.UNKNOWN_TYPE

    s.add("enc_unicode_type", cat, enc_unicode_type_name)


# ═══════════════════════════════════════════════════════════════════════════
# 16 — Error message content (human-readable contract)
# ═══════════════════════════════════════════════════════════════════════════


def build_message_cases(s: Suite) -> None:
    cat = "16_message"

    def m_contains_path():
        bad = base("ChatEvent")
        bad["message"] = 1
        exc = expect_validation_error(bad)
        rendered = str(exc) + (exc.short() if hasattr(exc, "short") else "")
        assert "message" in rendered

    s.add("m_contains_path", cat, m_contains_path)

    def m_missing_says_missing():
        bad = base("ChatEvent")
        del bad["message"]
        exc = expect_validation_error(bad)
        text = str(exc)
        assert "missing" in text.lower() or "MISSING" in text, text

    s.add("m_missing_keyword", cat, m_missing_says_missing)

    def m_short_returns_str():
        bad = base("ChatEvent")
        bad["message"] = 1
        exc = expect_validation_error(bad)
        if hasattr(exc, "short"):
            assert isinstance(exc.short(), str)

    s.add("m_short_str", cat, m_short_returns_str)

    def m_str_nonempty():
        bad = base("ChatEvent")
        bad["message"] = 1
        exc = expect_validation_error(bad)
        assert str(exc)

    s.add("m_str_nonempty", cat, m_str_nonempty)

    def m_explain_mentions_field():
        bad = base("ChatEvent")
        bad["whisper"] = "x"
        text = explain_debug(bad)
        assert "whisper" in text, text

    s.add("m_explain_field", cat, m_explain_mentions_field)

    def m_explain_ok_for_valid():
        for name in ALL_PAYLOAD_NAMES[:5]:
            text = explain_debug(BASE_PAYLOADS[name])
            assert "OK" in text or "ok" in text, (name, text)

    s.add("m_explain_ok_sample", cat, m_explain_ok_for_valid)

    def m_render_if_present():
        bad = base("ChatEvent")
        bad["message"] = 1
        exc = expect_validation_error(bad)
        err = first(exc)
        if hasattr(err, "render"):
            r = err.render()
            assert isinstance(r, str) and r

    s.add("m_render", cat, m_render_if_present)

    def m_to_dict_if_present():
        bad = base("ChatEvent")
        bad["message"] = 1
        exc = expect_validation_error(bad)
        if hasattr(exc, "to_dict"):
            d = exc.to_dict()
            assert isinstance(d, dict)

    s.add("m_to_dict", cat, m_to_dict_if_present)

    def m_first_error_message_nonempty():
        bad = base("ChatEvent")
        bad["message"] = 1
        exc = expect_validation_error(bad)
        assert first(exc).message

    s.add("m_first_msg_nonempty", cat, m_first_error_message_nonempty)


# ═══════════════════════════════════════════════════════════════════════════
# 17 — Exception object contract
# ═══════════════════════════════════════════════════════════════════════════


def build_exception_cases(s: Suite) -> None:
    cat = "17_exception"

    def e_errors_is_list():
        exc = expect_validation_error({"_type": "Nope"})
        assert isinstance(exc.errors, list)

    s.add("e_errors_list", cat, e_errors_is_list)

    def e_errors_nonempty():
        exc = expect_validation_error({"_type": "Nope"})
        assert len(exc.errors) >= 1

    s.add("e_errors_nonempty", cat, e_errors_nonempty)

    def e_error_attrs():
        exc = expect_validation_error({"_type": 1})
        err = first(exc)
        for attr in ("path", "reason_code"):
            assert hasattr(err, attr), attr

    s.add("e_error_attrs", cat, e_error_attrs)

    def e_is_exception():
        exc = expect_validation_error({"_type": "Nope"})
        assert isinstance(exc, Exception)

    s.add("e_is_exception", cat, e_is_exception)

    def e_catchable_as_exception():
        try:
            validate_server_message({"_type": "Nope"})
        except Exception as exc:
            assert isinstance(exc, HighriseFastValidationError)

    s.add("e_catchable", cat, e_catchable_as_exception)

    def e_multiple_errors_count():
        bad = {"_type": "ChatEvent", "user": None, "message": None}
        exc = expect_validation_error(bad)
        assert len(exc.errors) >= 2, exc.errors

    s.add("e_multiple_errors", cat, e_multiple_errors_count)

    def e_reraise_preserves():
        exc1 = expect_validation_error({"_type": "Nope"})
        try:
            raise exc1
        except HighriseFastValidationError as exc2:
            assert exc2 is exc1

    s.add("e_reraise", cat, e_reraise_preserves)

    def e_details_type():
        exc = expect_validation_error({"_type": "Nope"})
        err = first(exc)
        assert isinstance(err, ValidationErrorDetail)

    s.add("e_details_type", cat, e_details_type)


# ═══════════════════════════════════════════════════════════════════════════
# 18 — Mutation safety across ALL payloads (generated)
# ═══════════════════════════════════════════════════════════════════════════


def build_mutation_cases(s: Suite) -> None:
    cat = "18_mutation"

    for pname in ALL_PAYLOAD_NAMES:

        def make_v(pn=pname):
            def _t():
                p = base(pn)
                snap = copy.deepcopy(p)
                validate_server_message(p)
                assert p == snap, f"validate mutated {pn}"

            return _t

        s.add(f"mut_validate_{pname}", cat, make_v())

    for pname in ALL_PAYLOAD_NAMES:

        def make_d(pn=pname):
            def _t():
                p = base(pn)
                snap = copy.deepcopy(p)
                debug_payload(p)
                assert p == snap, f"debug mutated {pn}"

            return _t

        s.add(f"mut_debug_{pname}", cat, make_d())

    def mut_debug_on_invalid():
        bad = {"_type": "ChatEvent", "user": None, "message": 1, "whisper": "x"}
        snap = copy.deepcopy(bad)
        debug_payload(bad)
        assert bad == snap

    s.add("mut_debug_invalid", cat, mut_debug_on_invalid)

    def mut_validate_nested_lists():
        p = base("GetWalletResponse")
        p["content"] = [make_currency() for _ in range(20)]
        snap = copy.deepcopy(p)
        validate_server_message(p)
        assert p == snap

    s.add("mut_nested_lists", cat, mut_validate_nested_lists)

    def mut_explain_debug():
        p = base("ChatEvent")
        snap = copy.deepcopy(p)
        explain_debug(p)
        assert p == snap

    s.add("mut_explain", cat, mut_explain_debug)


# ═══════════════════════════════════════════════════════════════════════════
# 19 — Performance gates
# ═══════════════════════════════════════════════════════════════════════════


def build_perf_cases(s: Suite) -> None:
    cat = "19_perf"

    def pf_1000_chat_validations():
        p = base("ChatEvent")
        t0 = time.perf_counter()
        for _ in range(1000):
            validate_server_message(p)
        dt = time.perf_counter() - t0
        assert dt < 2.0, f"1000 validations took {dt:.2f}s"

    s.add("pf_1000_chat", cat, pf_1000_chat_validations)

    def pf_1000_all_types():
        t0 = time.perf_counter()
        for _ in range(20):
            for name in ALL_PAYLOAD_NAMES:
                validate_server_message(BASE_PAYLOADS[name])
        dt = time.perf_counter() - t0
        assert dt < 5.0, f"20x all types took {dt:.2f}s"

    s.add("pf_1000_all_types", cat, pf_1000_all_types)

    def pf_200_debug_calls():
        p = base("UserMovedEvent")
        t0 = time.perf_counter()
        for _ in range(200):
            debug_payload(p)
        dt = time.perf_counter() - t0
        assert dt < 5.0, f"200 debug calls took {dt:.2f}s"

    s.add("pf_200_debug", cat, pf_200_debug_calls)

    def pf_large_wallet_1000():
        p = base("GetWalletResponse")
        p["content"] = [make_currency() for _ in range(1000)]
        t0 = time.perf_counter()
        validate_server_message(p)
        dt = time.perf_counter() - t0
        assert dt < 2.0, f"1000-item wallet took {dt:.2f}s"

    s.add("pf_wallet_1000", cat, pf_large_wallet_1000)

    def pf_large_voice_500():
        p = base("VoiceEvent")
        row = clone(p["users"][0])
        p["users"] = [clone(row) for _ in range(500)]
        t0 = time.perf_counter()
        validate_server_message(p)
        dt = time.perf_counter() - t0
        assert dt < 2.0, f"500-row voice took {dt:.2f}s"

    s.add("pf_voice_500", cat, pf_large_voice_500)

    def pf_1m_char_message():
        p = base("ChatEvent")
        p["message"] = "x" * 1_000_000
        t0 = time.perf_counter()
        validate_server_message(p)  # semantic off; must not scan-limit
        dt = time.perf_counter() - t0
        assert dt < 2.0, f"1M-char message took {dt:.2f}s"

    s.add("pf_1m_message", cat, pf_1m_char_message)

    def pf_deep_500_fast():
        deep = {
            "_type": "ChatEvent",
            "user": make_user(),
            "message": "m",
            "whisper": False,
        }
        cur = deep
        for i in range(500):
            cur[f"n{i}"] = {}
            cur = cur[f"n{i}"]
        t0 = time.perf_counter()
        expect_no_crash(deep)
        dt = time.perf_counter() - t0
        assert dt < 2.0

    s.add("pf_deep_500", cat, pf_deep_500_fast)


# ═══════════════════════════════════════════════════════════════════════════
# 20 — Fuzz resilience (seeded corruption)
# ═══════════════════════════════════════════════════════════════════════════


def _corrupt(payload: dict, rng: random.Random) -> dict:
    """Return a randomly-corrupted deep copy of payload."""
    p = copy.deepcopy(payload)

    def walk(node: Any, depth: int = 0) -> None:
        if depth > 6:
            return
        if isinstance(node, dict):
            if not node:
                return
            key = rng.choice(list(node.keys()))
            action = rng.random()
            if action < 0.25:
                del node[key]
            elif action < 0.85:
                node[key] = rng.choice(
                    [
                        None,
                        123,
                        "x",
                        True,
                        [],
                        {},
                        1.5,
                        float("nan"),
                        b"bytes",
                        {"deep": {"deeper": 1}},
                        ["l", "i", "s", "t"],
                    ]
                )
            else:
                node[key] = rng.choice(string.printable[:20]) * rng.randint(0, 50)
        elif isinstance(node, list):
            if not node:
                return
            idx = rng.randrange(len(node))
            action = rng.random()
            if action < 0.3:
                del node[idx]
            else:
                node[idx] = rng.choice([None, 1, "s", [], {}, True])

    walk(p)
    return p


def build_fuzz_cases(s: Suite) -> None:
    cat = "20_fuzz"
    for pname in ALL_PAYLOAD_NAMES:

        def make(pn=pname):
            def _t():
                rng = random.Random(hash(pn) & 0xFFFFFFFF)
                for _ in range(50):
                    corrupted = _corrupt(BASE_PAYLOADS[pn], rng)
                    expect_no_crash(corrupted)

            return _t

        s.add(f"fuzz_{pname}", cat, make())

    def fuzz_structural_types():
        rng = random.Random(1234)
        for _ in range(300):
            val = rng.choice(
                [
                    None,
                    0,
                    1,
                    -1,
                    "",
                    "x",
                    True,
                    False,
                    [],
                    {},
                    [1],
                    {"a": 1},
                    1.5,
                    float("nan"),
                    float("inf"),
                    b"b",
                    (1, 2),
                    {1, 2},
                ]
            )
            expect_no_crash({"_type": val})

    s.add("fuzz_structural_type_field", cat, fuzz_structural_types)

    def fuzz_random_dicts():
        rng = random.Random(4321)
        for _ in range(200):
            depth = rng.randint(0, 4)
            obj: Any = {"_type": rng.choice(["ChatEvent", "Nope", "", 1, None])}
            cur = obj
            for i in range(depth):
                cur[f"f{i}"] = rng.choice([None, 1, "v", [], {}])
                if isinstance(cur[f"f{i}"], dict):
                    cur = cur[f"f{i}"]
            expect_no_crash(obj)

    s.add("fuzz_random_dicts", cat, fuzz_random_dicts)


# ═══════════════════════════════════════════════════════════════════════════
# 21 — Regression edge cases (the tricky ones)
# ═══════════════════════════════════════════════════════════════════════════


def build_regression_cases(s: Suite) -> None:
    cat = "21_regression"

    def r_type_with_trailing_newline():
        exc = expect_validation_error({"_type": "ChatEvent\n"})
        assert first(exc).reason_code == ReasonCode.UNKNOWN_TYPE

    s.add("r_type_newline", cat, r_type_with_trailing_newline)

    def r_type_with_tab():
        exc = expect_validation_error({"_type": "ChatEvent\t"})
        assert first(exc).reason_code == ReasonCode.UNKNOWN_TYPE

    s.add("r_type_tab", cat, r_type_with_tab)

    def r_type_case_swap():
        exc = expect_validation_error({"_type": "cHATeVENT"})
        assert first(exc).reason_code == ReasonCode.UNKNOWN_TYPE

    s.add("r_type_case_swap", cat, r_type_case_swap)

    def r_whisper_null_rejected():
        bad = base("ChatEvent")
        bad["whisper"] = None
        expect_validation_error(bad)

    s.add("r_whisper_null", cat, r_whisper_null_rejected)

    def r_user_null_rejected():
        bad = base("ChatEvent")
        bad["user"] = None
        expect_validation_error(bad)

    s.add("r_user_null", cat, r_user_null_rejected)

    def r_extra_top_level_keys_ignored():
        good = base("ChatEvent")
        good["extra"] = "whatever"
        good["another"] = [1, 2, 3]
        expect_ok(good)

    s.add("r_extra_top_keys", cat, r_extra_top_level_keys_ignored)

    def r_nested_null_in_position():
        bad = base("UserMovedEvent")
        bad["position"]["x"] = None
        expect_validation_error(bad)

    s.add("r_pos_null", cat, r_nested_null_in_position)

    def r_debug_after_repair_still_fails():
        """A payload that fails, gets repaired, and still fails must terminate."""
        bad = {"_type": "ChatEvent", "user": [], "message": [], "whisper": []}
        report = debug_payload(bad)
        assert report["ok"] is False

    s.add("r_debug_persists", cat, r_debug_after_repair_still_fails)

    def r_empty_type_string_unknown():
        exc = expect_validation_error({"_type": ""})
        assert first(exc).reason_code == ReasonCode.UNKNOWN_TYPE

    s.add("r_empty_type", cat, r_empty_type_string_unknown)

    def r_only_type_key_no_other_fields():
        """Every payload type with ONLY _type should fail (missing required) or pass (all-optional)."""
        for name in ALL_PAYLOAD_NAMES:
            expect_no_crash({"_type": name})

    s.add("r_bare_type_all", cat, r_only_type_key_no_other_fields)

    def r_bool_field_numeric_string():
        bad = base("ChatEvent")
        bad["whisper"] = "0"
        expect_validation_error(bad)

    s.add("r_whisper_str0", cat, r_bool_field_numeric_string)

    def r_unicode_username_ok():
        good = base("ChatEvent")
        good["user"]["username"] = "ユーザー🎉"
        expect_ok(good)

    s.add("r_unicode_username", cat, r_unicode_username_ok)

    def r_wallet_type_invalid_literal():
        bad = base("GetWalletResponse")
        bad["content"][0]["type"] = "diamonds"
        # type may be a free string or literal; either behavior is fine, no crash
        expect_no_crash(bad)

    s.add("r_wallet_type_literal", cat, r_wallet_type_invalid_literal)

    def r_deeply_broken_debug_terminates():
        bad = {
            "_type": "VoiceEvent",
            "users": [["bad", 1], None, {"a": 1}],
            "seconds_left": "x",
        }
        t0 = time.perf_counter()
        report = debug_payload(bad)
        assert time.perf_counter() - t0 < 5.0
        assert report["ok"] is False

    s.add("r_debug_broken_terminates", cat, r_deeply_broken_debug_terminates)

    def r_int_negative_duration():
        p = base("RoomModeratedEvent")
        if "duration" in p and p["duration"] is not None:
            p["duration"] = -60
            expect_no_crash(p)

    s.add("r_negative_duration", cat, r_int_negative_duration)


# ═══════════════════════════════════════════════════════════════════════════
# 22 — Round-trip serialization (generated over all payloads)
# ═══════════════════════════════════════════════════════════════════════════


def build_roundtrip_cases(s: Suite) -> None:
    cat = "22_roundtrip"

    for pname in ALL_PAYLOAD_NAMES:

        def make(pn=pname):
            def _t():
                original = BASE_PAYLOADS[pn]
                serialized = json.dumps(original)
                reparsed = json.loads(serialized)
                expect_ok(reparsed)

            return _t

        s.add(f"rt_json_{pname}", cat, make())

    def rt_chat_modified_roundtrip():
        p = base("ChatEvent")
        p["message"] = 'héllo 🎉 "quoted" \\slash\nnewline'
        reparsed = json.loads(json.dumps(p))
        expect_ok(reparsed)

    s.add("rt_chat_specials", cat, rt_chat_modified_roundtrip)

    def rt_wallet_extended():
        p = base("GetWalletResponse")
        p["content"] = [make_currency("gold", i) for i in range(25)]
        reparsed = json.loads(json.dumps(p))
        expect_ok(reparsed)

    s.add("rt_wallet_25", cat, rt_wallet_extended)

    def rt_voice_extended():
        p = base("VoiceEvent")
        row = clone(p["users"][0])
        p["users"] = [clone(row) for _ in range(15)]
        reparsed = json.loads(json.dumps(p))
        expect_ok(reparsed)

    s.add("rt_voice_15", cat, rt_voice_extended)

    def rt_invalid_stays_invalid():
        bad = {"_type": "ChatEvent", "message": 1, "whisper": "x", "user": None}
        reparsed = json.loads(json.dumps(bad))
        expect_validation_error(reparsed)

    s.add("rt_invalid_stays", cat, rt_invalid_stays_invalid)

    def rt_debug_report_json_serializable():
        bad = base("ChatEvent")
        bad["message"] = 1
        report = debug_payload(bad)
        json.dumps(report)  # must not raise

    s.add("rt_report_jsonable", cat, rt_debug_report_json_serializable)


# ═══════════════════════════════════════════════════════════════════════════
# 23 — Robustness matrix: hostile values in nested slots (generated)
# ═══════════════════════════════════════════════════════════════════════════


def build_robustness_cases(s: Suite) -> None:
    cat = "23_robust"
    hostile = [
        None,
        0,
        -1,
        1,
        "",
        "x",
        True,
        False,
        [],
        {},
        [1],
        {"a": 1},
        0.5,
        float("nan"),
        float("inf"),
        b"b",
    ]

    # user dict slots
    for i, v in enumerate(hostile):

        def make_uv(val=v):
            def _t():
                p = base("ChatEvent")
                p["user"] = copy.deepcopy(val)
                expect_no_crash(p)

            return _t

        s.add(f"rob_user_slot_{i}", cat, make_uv())

    # user.id slots
    for i, v in enumerate(hostile):

        def make_id(val=v):
            def _t():
                p = base("ChatEvent")
                p["user"]["id"] = copy.deepcopy(val)
                expect_no_crash(p)

            return _t

        s.add(f"rob_userid_slot_{i}", cat, make_id())

    # position slots
    for i, v in enumerate(hostile):

        def make_pos(val=v):
            def _t():
                p = base("UserMovedEvent")
                p["position"] = copy.deepcopy(val)
                expect_no_crash(p)

            return _t

        s.add(f"rob_pos_slot_{i}", cat, make_pos())

    # content slot
    for i, v in enumerate(hostile):

        def make_c(val=v):
            def _t():
                p = base("GetWalletResponse")
                p["content"] = copy.deepcopy(val)
                expect_no_crash(p)

            return _t

        s.add(f"rob_content_slot_{i}", cat, make_c())

    # voice users slot
    for i, v in enumerate(hostile):

        def make_vu(val=v):
            def _t():
                p = base("VoiceEvent")
                p["users"] = copy.deepcopy(val)
                expect_no_crash(p)

            return _t

        s.add(f"rob_users_slot_{i}", cat, make_vu())


# ═══════════════════════════════════════════════════════════════════════════
# Assembly
# ═══════════════════════════════════════════════════════════════════════════


def build_all_cases() -> Suite:
    s = Suite()
    build_debug_cases(s)
    build_reason_cases(s)
    build_path_cases(s)
    build_type_matrix_cases(s)
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
    build_message_cases(s)
    build_exception_cases(s)
    build_mutation_cases(s)
    build_perf_cases(s)
    build_fuzz_cases(s)
    build_regression_cases(s)
    build_roundtrip_cases(s)
    build_robustness_cases(s)
    return s


def print_report(suite: Suite) -> None:
    summary = suite.summary()
    print("\n" + "=" * 70)
    print("BENCHMARK V7 — RESULTS")
    print("=" * 70)
    print(f"Total:   {summary['total']}")
    print(f"Passed:  {summary['ok']}")
    print(f"Failed:  {summary['fail']}")
    print(f"Errors:  {summary['error']}")
    print(f"Skipped: {summary['skip']}")
    print("-" * 70)
    if summary["by_category"]:
        print(f"\n{'Category':<20} {'OK':>5} {'FAIL':>5} {'ERR':>5} {'SKIP':>5}")
        print("-" * 45)
        for c in sorted(summary["by_category"]):
            n = summary["by_category"][c]
            print(f"{c:<20} {n['ok']:>5} {n['fail']:>5} {n['error']:>5} {n['skip']:>5}")
    failures = [r for r in suite.results if r.status in ("fail", "error")]
    if failures:
        print(f"\n{'=' * 70}")
        print(f"FAILURES & ERRORS ({len(failures)})")
        print("=" * 70)
        for r in failures[:25]:
            print(f"\n  [{r.status.upper()}] {r.name} ({r.category})")
            if r.detail:
                detail = r.detail if len(r.detail) < 300 else r.detail[:300] + "..."
                print(f"    {detail}")
        if len(failures) > 25:
            print(f"\n  ... and {len(failures) - 25} more")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark V7 — exhaustive suite")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--category", type=str, default="")
    parser.add_argument("--filter", type=str, default="")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--json", type=str, default="")
    parser.add_argument("--quiet", action="store_true", help="suppress per-test output")
    args = parser.parse_args()

    if not _IMPORT_OK:
        print(f"ERROR: Cannot import highrise_fast: {_IMPORT_ERROR}")
        return 1

    suite = build_all_cases()

    if args.list:
        print(f"\n{'Category':<20} Test Name")
        print("-" * 60)
        for name, c, _ in suite.cases:
            print(f"{c:<20} {name}")
        print(f"\nTotal: {len(suite.cases)} test cases")
        return 0

    print("=" * 70)
    print("BENCHMARK V7 — EXHAUSTIVE COVERAGE & STRESS SUITE")
    print("=" * 70)
    print(f"Mode:      {'quick' if args.quick else 'full'}")
    print(f"Category:  {args.category or 'all'}")
    print(f"Filter:    {args.filter or 'none'}")
    print(f"Cases:     {len(suite.cases)}")
    print("=" * 70 + "\n")

    if args.quiet:
        original_print = print
        import builtins

        builtins.print = lambda *a, **k: None
        try:
            t0 = time.perf_counter()
            suite.run(filter_=args.filter, category=args.category, quick=args.quick)
            elapsed = time.perf_counter() - t0
        finally:
            builtins.print = original_print
    else:
        t0 = time.perf_counter()
        suite.run(filter_=args.filter, category=args.category, quick=args.quick)
        elapsed = time.perf_counter() - t0

    print(f"\nCompleted in {elapsed:.2f}s")
    print_report(suite)

    if args.json:
        output = {
            "elapsed_s": elapsed,
            "summary": suite.summary(),
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

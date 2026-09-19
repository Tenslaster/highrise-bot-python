#!/usr/bin/env python3
"""
benchmark_type_validation_250.py

Official-oracle type validation benchmark for highrise_fast.

This benchmark does NOT score the official SDK.
The official SDK is used as the reference/oracle.

For every generated payload:

    official ACCEPT/REJECT = expected behavior

Then highrise_fast is tested:

    - lenient mode
    - strict mode, if available

Strict mode is detected automatically if highrise_fast exposes either:

    parse_server_message(data, strict=True)

or:

    validate_server_message(data)

Usage:

    python benchmark_type_validation_250.py
    python benchmark_type_validation_250.py --target 250
    python benchmark_type_validation_250.py --show mismatches
    python benchmark_type_validation_250.py --show all
    python benchmark_type_validation_250.py --json-report report.json
"""

from __future__ import annotations

import argparse
import copy
import inspect
import json
import re
from dataclasses import dataclass
from typing import Any


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


def short(text: str, limit: int = 80) -> str:
    text = str(text)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


# ═══════════════════════════════════════════════════════════════
# BASE PAYLOADS
#
# These are known-valid incoming payloads based on the main benchmark.
# GetRoomUsersResponse is intentionally excluded by default because
# official cattrs has a known tuple limitation for that payload.
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
        "position": {
            "x": 5.5,
            "y": 0.0,
            "z": 12.3,
            "facing": "FrontRight",
        },
    },
    "UserLeftEvent": {
        "_type": "UserLeftEvent",
        "user": {"id": "u3", "username": "charlie"},
    },
    "UserMovedEvent": {
        "_type": "UserMovedEvent",
        "user": {"id": "u1", "username": "alice"},
        "position": {
            "x": 10.5,
            "y": 0.0,
            "z": 20.3,
            "facing": "BackLeft",
        },
    },
    "EmoteEvent": {
        "_type": "EmoteEvent",
        "user": {"id": "u1", "username": "alice"},
        "emote_id": "wave",
        "receiver": None,
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
            [
                {"id": "u1", "username": "alice"},
                "voice",
            ],
            [
                {"id": "u2", "username": "bob"},
                "muted",
            ],
        ],
        "seconds_left": 300,
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
}


# ═══════════════════════════════════════════════════════════════
# CASE MODEL
# ═══════════════════════════════════════════════════════════════
@dataclass
class Case:
    id: str
    base: str
    mutation: str
    payload: Any

    official_accept: bool | None = None
    official_error: str = ""

    lenient_accept: bool | None = None
    lenient_error: str = ""

    strict_accept: bool | None = None
    strict_error: str = ""

    @property
    def lenient_match(self) -> bool | None:
        if self.lenient_accept is None or self.official_accept is None:
            return None
        return self.lenient_accept == self.official_accept

    @property
    def strict_match(self) -> bool | None:
        if self.strict_accept is None or self.official_accept is None:
            return None
        return self.strict_accept == self.official_accept


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
        current = data
        for token in tokens[:-1]:
            current = current[token]
        current[tokens[-1]] = value
    except (KeyError, IndexError, TypeError):
        pass

    return data


def delete_path(payload: Any, path: str) -> Any:
    data = copy.deepcopy(payload)
    tokens = parse_path(path)

    if not tokens:
        return data

    try:
        current = data
        for token in tokens[:-1]:
            current = current[token]

        last = tokens[-1]

        if isinstance(current, dict) and isinstance(last, str):
            if last in current:
                del current[last]
        elif isinstance(current, list) and isinstance(last, int):
            if 0 <= last < len(current):
                current[last] = None
    except (KeyError, IndexError, TypeError):
        pass

    return data


def iter_paths(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield child_path, child
            yield from iter_paths(child, child_path)

    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{path}[{index}]"
            yield child_path, child
            yield from iter_paths(child, child_path)


def set_key(payload: dict, key: str, value: Any) -> dict:
    data = copy.deepcopy(payload)
    data[key] = value
    return data


def delete_key(payload: dict, key: str) -> dict:
    data = copy.deepcopy(payload)
    if key in data:
        del data[key]
    return data


# ═══════════════════════════════════════════════════════════════
# CASE GENERATOR
# ═══════════════════════════════════════════════════════════════
WRONG_VALUES: list[tuple[str, Any]] = [
    ("null", None),
    ("true", True),
    ("false", False),
    ("int", 123),
    ("float", 123.45),
    ("string", "wrong"),
    ("empty-string", ""),
    ("list", []),
    ("dict", {}),
    ("large-int", 2**62),
]


def generate_cases(target: int = 250) -> list[Case]:
    cases: list[Case] = []
    seen: set[str] = set()

    def add(base: str, mutation: str, payload: Any) -> None:
        if len(cases) >= target:
            return

        try:
            key = json.dumps(payload, sort_keys=True, default=str)
        except Exception:
            key = repr(payload)

        if key in seen:
            return

        seen.add(key)
        cases.append(
            Case(
                id="",
                base=base,
                mutation=mutation,
                payload=payload,
            )
        )

    # ── Top-level non-object cases ──
    top_level_cases: list[tuple[str, Any]] = [
        ("top-level-list", []),
        ("top-level-string", "not_a_dict"),
        ("top-level-int", 123),
        ("top-level-float", 123.45),
        ("top-level-true", True),
        ("top-level-null", None),
    ]

    for name, payload in top_level_cases:
        add("TopLevel", name, payload)

    # ── Valid baselines ──
    for base, payload in BASE_PAYLOADS.items():
        add(base, "valid baseline", copy.deepcopy(payload))

    # ── Global message-level mutations ──
    for base, payload in BASE_PAYLOADS.items():
        global_mutations: list[tuple[str, Any]] = [
            ("missing _type", delete_key(payload, "_type")),
            ("_type = null", set_key(payload, "_type", None)),
            ("_type = int", set_key(payload, "_type", 123)),
            ("_type = empty-string", set_key(payload, "_type", "")),
            ("_type = unknown", set_key(payload, "_type", "UnknownEventXYZ")),
            ("_type = lowercase", set_key(payload, "_type", base.lower())),
            ("rid = null", set_key(payload, "rid", None)),
            ("rid = int", set_key(payload, "rid", 123)),
            ("rid = list", set_key(payload, "rid", [])),
            ("rid = dict", set_key(payload, "rid", {})),
            ("extra unknown field", set_key(payload, "extra_benchmark_field", True)),
        ]

        if "rid" in payload:
            global_mutations.insert(
                6,
                ("missing rid", delete_key(payload, "rid")),
            )

        for mutation, mutated in global_mutations:
            add(base, mutation, mutated)

    # ── Leaf/path mutations, distributed across bases ──
    leaf_queues: dict[str, list[tuple[str, Any]]] = {}

    for base, payload in BASE_PAYLOADS.items():
        queue: list[tuple[str, Any]] = []

        for path, _ in iter_paths(payload):
            if path == "$._type" or path.endswith("._type"):
                continue

            queue.append((f"delete {path}", delete_path(payload, path)))

            for label, wrong_value in WRONG_VALUES:
                queue.append(
                    (
                        f"{path} = {label}",
                        set_path(payload, path, wrong_value),
                    )
                )

        leaf_queues[base] = queue

    while len(cases) < target and any(leaf_queues.values()):
        progressed = False

        for base in list(BASE_PAYLOADS.keys()):
            if len(cases) >= target:
                break

            queue = leaf_queues[base]
            if queue:
                mutation, mutated = queue.pop(0)
                add(base, mutation, mutated)
                progressed = True

        if not progressed:
            break

    # ── Fallback fillers if needed ──
    filler_counter = 0

    while len(cases) < target:
        base_name = list(BASE_PAYLOADS.keys())[filler_counter % len(BASE_PAYLOADS)]
        base_payload = BASE_PAYLOADS[base_name]

        mutated = set_key(
            base_payload,
            f"filler_field_{filler_counter}",
            filler_counter,
        )

        add(
            base_name,
            f"filler field {filler_counter}",
            mutated,
        )

        filler_counter += 1

    # Assign final IDs
    for i, case in enumerate(cases, start=1):
        case.id = f"TV-{i:03d}"

    return cases


# ═══════════════════════════════════════════════════════════════
# PARSERS
# ═══════════════════════════════════════════════════════════════
def get_official_parser():
    from highrise import Incoming, converter

    def parse(payload: Any):
        return converter.loads(json.dumps(payload), Incoming)

    return parse


def get_custom_lenient_parser():
    from highrise_fast import parse_server_message

    return parse_server_message


def get_custom_strict_parser():
    """
    Detect strict mode in highrise_fast.

    Supported patterns:

        1. parse_server_message(data, strict=True)
        2. validate_server_message(data)
        3. strict_parse_server_message(data)
    """
    import highrise_fast

    parse = getattr(highrise_fast, "parse_server_message", None)

    if parse is not None:
        try:
            sig = inspect.signature(parse)
            if "strict" in sig.parameters:
                return (
                    lambda data: parse(data, strict=True),
                    "parse_server_message(..., strict=True)",
                )
        except (TypeError, ValueError):
            pass

    validate = getattr(highrise_fast, "validate_server_message", None)
    if callable(validate) and parse is not None:

        def strict_parse(data: Any):
            validate(data)
            return parse(data)

        return (
            strict_parse,
            "validate_server_message(...) + parse_server_message(...)",
        )

    strict_parse = getattr(highrise_fast, "strict_parse_server_message", None)
    if callable(strict_parse):
        return (
            strict_parse,
            "strict_parse_server_message(...)",
        )

    return (
        None,
        "strict mode not found: add parse_server_message(..., strict=True) "
        "or validate_server_message(...)",
    )


def classify(fn, payload: Any) -> tuple[bool, str]:
    try:
        fn(payload)
        return True, ""
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


# ═══════════════════════════════════════════════════════════════
# FEEDBACK SCORE
# ═══════════════════════════════════════════════════════════════
EXPECTED_WORDS = (
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

GOT_WORDS = (
    "got",
    "received",
    "actual",
    "but got",
    "instance",
    "found",
)


def feedback_score(mutation: str, error_text: str) -> int:
    if not error_text:
        return 0

    text = error_text.lower()
    score = 0

    tokens = {
        token
        for token in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", mutation.lower())
        if len(token) >= 3
    }

    if tokens and any(token in text for token in tokens):
        score += 35

    if any(word in text for word in EXPECTED_WORDS):
        score += 25

    if any(word in text for word in GOT_WORDS):
        score += 20

    if any(marker in text for marker in ("$", ".", "path", "field", "->")):
        score += 10

    if len(error_text) >= 20:
        score += 5

    if "\n" in error_text:
        score += 5

    return min(100, score)


def avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


# ═══════════════════════════════════════════════════════════════
# PRINTING
# ═══════════════════════════════════════════════════════════════
def accept_label(value: bool | None) -> str:
    if value is None:
        return "?"
    return "ACCEPT" if value else "REJECT"


def print_case(case: Case, strict_available: bool):
    expected = accept_label(case.official_accept)
    lenient = accept_label(case.lenient_accept)
    strict = accept_label(case.strict_accept)

    if not strict_available or case.strict_accept is None:
        match = "?"
    elif case.strict_accept == case.official_accept:
        match = "OK"
    else:
        match = "BAD"

    p(
        f"{case.id:7s} "
        f"{case.base:22s} "
        f"{expected:7s} "
        f"{lenient:8s} "
        f"{strict:8s} "
        f"{match:4s} "
        f"{short(case.mutation, 70)}"
    )


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser(
        description=("Official-oracle type validation benchmark for highrise_fast")
    )
    ap.add_argument(
        "--target",
        type=int,
        default=250,
        help="Number of validation cases to generate",
    )
    ap.add_argument(
        "--show",
        choices=["none", "mismatches", "all"],
        default="mismatches",
        help="What to print after the run",
    )
    ap.add_argument(
        "--json-report",
        type=str,
        default="",
        help="Optional path to write a JSON report",
    )
    args = ap.parse_args()

    header("HIGHRISE TYPE VALIDATION BENCHMARK — OFFICIAL ORACLE")
    p("Official SDK is used as the reference/oracle.")
    p("Official SDK is NOT scored. Official behavior defines expected behavior.")
    p()

    # Official parser
    try:
        official_parser = get_official_parser()
    except Exception as exc:
        p(f"❌ Official SDK unavailable: {exc}")
        raise SystemExit(1)

    # Custom lenient parser
    try:
        lenient_parser = get_custom_lenient_parser()
    except Exception as exc:
        p(f"❌ Custom SDK unavailable: {exc}")
        raise SystemExit(1)

    # Custom strict parser
    strict_parser, strict_note = get_custom_strict_parser()
    strict_available = strict_parser is not None

    if strict_available:
        p(f"✅ Custom strict mode detected: {strict_note}")
    else:
        p(f"❌ Custom strict mode unavailable: {strict_note}")
        p()
        p("To pass this benchmark, highrise_fast needs strict validation.")
        p("For example:")
        p("    parse_server_message(payload, strict=True)")
        p("or:")
        p("    validate_server_message(payload)")
        p("    parse_server_message(payload)")

    p()
    p(f"Generating {args.target} type-validation cases...")
    cases = generate_cases(args.target)
    p(f"Generated {len(cases)} cases.")

    # ── Official classification ──
    header("OFFICIAL ORACLE CLASSIFICATION")

    for i, case in enumerate(cases, start=1):
        case.official_accept, case.official_error = classify(
            official_parser,
            case.payload,
        )

        if i % 25 == 0 or i == len(cases):
            p(f"  official classified {i}/{len(cases)}")

    # ── Custom lenient classification ──
    header("CUSTOM LENIENT CLASSIFICATION")

    for i, case in enumerate(cases, start=1):
        case.lenient_accept, case.lenient_error = classify(
            lenient_parser,
            case.payload,
        )

        if i % 25 == 0 or i == len(cases):
            p(f"  lenient classified {i}/{len(cases)}")

    # ── Custom strict classification ──
    if strict_available:
        header("CUSTOM STRICT CLASSIFICATION")

        for i, case in enumerate(cases, start=1):
            case.strict_accept, case.strict_error = classify(
                strict_parser,
                case.payload,
            )

            if i % 25 == 0 or i == len(cases):
                p(f"  strict classified {i}/{len(cases)}")
    else:
        header("CUSTOM STRICT CLASSIFICATION")
        p("Skipped: strict mode unavailable.")

    # ── Statistics ──
    header("RESULTS")

    total = len(cases)

    official_accepts = sum(1 for c in cases if c.official_accept)
    official_rejects = total - official_accepts

    lenient_matches = sum(
        1
        for c in cases
        if c.lenient_accept is not None
        and c.official_accept is not None
        and c.lenient_accept == c.official_accept
    )

    strict_matches = None
    if strict_available:
        strict_matches = sum(
            1
            for c in cases
            if c.strict_accept is not None
            and c.official_accept is not None
            and c.strict_accept == c.official_accept
        )

    p(f"Total cases              : {total}")
    p(f"Official ACCEPT cases    : {official_accepts}")
    p(f"Official REJECT cases    : {official_rejects}")
    p()
    p(
        f"Custom lenient match     : "
        f"{lenient_matches}/{total} "
        f"({lenient_matches / total * 100:.1f}%)"
    )

    if strict_available and strict_matches is not None:
        p(
            f"Custom strict match      : "
            f"{strict_matches}/{total} "
            f"({strict_matches / total * 100:.1f}%)"
        )
    else:
        p("Custom strict match      : unavailable")

    # ── Feedback quality ──
    header("ERROR FEEDBACK QUALITY")

    official_feedback: list[float] = []
    strict_feedback: list[float] = []

    for case in cases:
        if case.official_accept is False:
            official_feedback.append(feedback_score(case.mutation, case.official_error))

        if strict_available:
            if case.official_accept is False:
                if case.strict_accept is False:
                    strict_feedback.append(
                        feedback_score(case.mutation, case.strict_error)
                    )
                elif case.strict_accept is True:
                    strict_feedback.append(0.0)

    p(f"Official feedback average : {avg(official_feedback):.1f}/100")

    if strict_available:
        p(f"Custom strict feedback    : {avg(strict_feedback):.1f}/100")
    else:
        p("Custom strict feedback    : unavailable")

    p()
    p("Feedback score rewards errors that include:")
    p("  - field/path")
    p("  - expected type")
    p("  - actual/got type")
    p("  - enough detail to debug")
    p("  - multiple error lines")

    # ── Print case rows ──
    header("CASES")

    p(
        f"{'ID':7s} "
        f"{'Base':22s} "
        f"{'Oracle':7s} "
        f"{'Lenient':8s} "
        f"{'Strict':8s} "
        f"{'Match':4s} "
        f"Mutation"
    )
    p("─" * 110)

    if args.show == "all":
        for case in cases:
            print_case(case, strict_available)

    elif args.show == "mismatches":
        mismatches = [
            case
            for case in cases
            if strict_available
            and case.strict_accept is not None
            and case.official_accept is not None
            and case.strict_accept != case.official_accept
        ]

        if not mismatches:
            p("No strict-mode mismatches found.")
        else:
            for case in mismatches:
                print_case(case, strict_available)

    else:
        p("Case printing disabled.")

    # ── Mismatch details ──
    if strict_available:
        header("MISMATCH DETAILS")

        mismatches = [
            case
            for case in cases
            if case.strict_accept is not None
            and case.official_accept is not None
            and case.strict_accept != case.official_accept
        ]

        if not mismatches:
            p("✅ Custom strict mode matches the official SDK on all cases.")
        else:
            p(f"❌ {len(mismatches)} mismatch(es) found.")
            p()

            for case in mismatches[:50]:
                p(f"[{case.id}] {case.base} — {short(case.mutation, 80)}")
                p(f"    Official : {accept_label(case.official_accept)}")
                p(f"    Strict   : {accept_label(case.strict_accept)}")

                if case.official_error:
                    p(f"    Official error: {short(case.official_error, 220)}")

                if case.strict_error:
                    p(f"    Strict error  : {short(case.strict_error, 220)}")

                p()

            if len(mismatches) > 50:
                p(f"... and {len(mismatches) - 50} more mismatch(es)")

    # ── JSON report ──
    if args.json_report:
        report = {
            "target": args.target,
            "total_cases": total,
            "official_accepts": official_accepts,
            "official_rejects": official_rejects,
            "lenient_matches": lenient_matches,
            "strict_available": strict_available,
            "strict_note": strict_note,
            "strict_matches": strict_matches,
            "official_feedback_average": avg(official_feedback),
            "strict_feedback_average": avg(strict_feedback),
            "cases": [
                {
                    "id": case.id,
                    "base": case.base,
                    "mutation": case.mutation,
                    "payload": case.payload,
                    "official_accept": case.official_accept,
                    "official_error": case.official_error[:1000],
                    "lenient_accept": case.lenient_accept,
                    "lenient_error": case.lenient_error[:1000],
                    "strict_accept": case.strict_accept,
                    "strict_error": case.strict_error[:1000],
                    "lenient_match": case.lenient_match,
                    "strict_match": case.strict_match,
                }
                for case in cases
            ],
        }

        with open(args.json_report, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        p()
        p(f"✅ JSON report written: {args.json_report}")

    # ── Final verdict ──
    header("FINAL VERDICT")

    if not strict_available:
        p("❌ STRICT MODE MISSING")
        p()
        p("highrise_fast must expose strict validation, for example:")
        p()
        p("    parse_server_message(payload, strict=True)")
        p()
        p("or:")
        p()
        p("    validate_server_message(payload)")
        p("    parse_server_message(payload)")
        raise SystemExit(2)

    if strict_matches == total:
        p("🏆 SUCCESS: Custom strict validation matches official SDK behavior.")
        raise SystemExit(0)

    p("❌ Custom strict validation does not fully match the official SDK.")
    p()
    p("Target:")
    p("    Custom strict match: 250/250")
    raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        p()
        p("Interrupted.")
        raise SystemExit(130)

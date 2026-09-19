#!/usr/bin/env python3
"""
generate_official_gold_matrix.py

Generates a large official-oracle golden validation matrix.

This script uses the official SDK only to classify payloads as ACCEPT/REJECT.
The output JSON can later be used to test highrise_fast native validation
without importing the official SDK.

Usage:

    python generate_official_gold_matrix.py --target 5000
    python generate_official_gold_matrix.py --target 20000 --combos 5000 --fuzz 5000
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
from typing import Any


# ═══════════════════════════════════════════════════════════════
# BASE PAYLOADS
# ═══════════════════════════════════════════════════════════════
BASE_PAYLOADS: dict[str, dict[str, Any]] = {
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


TOP_LEVEL_CASES: list[tuple[str, Any]] = [
    ("top-level-list", []),
    ("top-level-empty-list", []),
    ("top-level-string", "not_a_dict"),
    ("top-level-empty-string", ""),
    ("top-level-int", 123),
    ("top-level-negative-int", -1),
    ("top-level-large-int", 2**62),
    ("top-level-float", 123.45),
    ("top-level-true", True),
    ("top-level-false", False),
    ("top-level-null", None),
    ("top-level-empty-dict", {}),
]


WRONG_VALUES: list[tuple[str, Any]] = [
    ("null", None),
    ("true", True),
    ("false", False),
    ("int-0", 0),
    ("int-1", 1),
    ("int-neg", -1),
    ("int-large", 2**62),
    ("float", 1.5),
    ("float-neg", -1.5),
    ("float-large", 1e308),
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
    data.pop(key, None)
    return data


# ═══════════════════════════════════════════════════════════════
# MUTATION GENERATORS
# ═══════════════════════════════════════════════════════════════
def global_mutations(base: str, payload: dict) -> list[tuple[str, Any]]:
    queue: list[tuple[str, Any]] = []

    # _type mutations
    queue.append(("missing _type", delete_key(payload, "_type")))

    type_mutations = [
        ("_type = null", None),
        ("_type = true", True),
        ("_type = false", False),
        ("_type = int", 123),
        ("_type = float", 123.45),
        ("_type = empty-string", ""),
        ("_type = space", " "),
        ("_type = unknown", "UnknownEventXYZ"),
        ("_type = lowercase", base.lower()),
        ("_type = trailing-space", base + " "),
        ("_type = leading-space", " " + base),
        ("_type = list", []),
        ("_type = dict", {}),
    ]

    for mutation, value in type_mutations:
        queue.append((mutation, set_key(payload, "_type", value)))

    # rid mutations
    if "rid" in payload:
        queue.append(("missing rid", delete_key(payload, "rid")))

    rid_mutations = [
        ("rid = null", None),
        ("rid = true", True),
        ("rid = false", False),
        ("rid = int", 123),
        ("rid = float", 123.45),
        ("rid = empty-string", ""),
        ("rid = string", "wrong_rid"),
        ("rid = unicode", "rid_é😀"),
        ("rid = long-string", "r" * 300),
        ("rid = list", []),
        ("rid = dict", {}),
    ]

    for mutation, value in rid_mutations:
        queue.append((mutation, set_key(payload, "rid", value)))

    # unknown fields
    queue.append(
        ("extra unknown root field", set_key(payload, "extra_unknown", True))
    )
    queue.append(
        ("extra unknown root dict", set_key(payload, "extra_meta", {"x": 1}))
    )

    return queue


def single_path_mutations(
    base: str,
    payload: dict,
) -> list[tuple[str, Any]]:
    queue: list[tuple[str, Any]] = []

    for path, value in iter_paths(payload):
        if path == "$._type":
            continue

        tokens = parse_path(path)

        # Delete only dict keys, not list indexes.
        if tokens and isinstance(tokens[-1], str):
            queue.append((f"delete {path}", delete_path(payload, path)))

        # Wrong scalar/container values.
        for label, wrong_value in WRONG_VALUES:
            queue.append(
                (
                    f"{path} = {label}",
                    set_path(payload, path, wrong_value),
                )
            )

        # Unknown field inside dicts.
        if isinstance(value, dict):
            queue.append(
                (
                    f"{path}.unknown_extra = true",
                    set_path(payload, f"{path}.unknown_extra", True),
                )
            )

        # List container mutations.
        if isinstance(value, list):
            queue.append((f"{path} = empty-list", set_path(payload, path, [])))
            queue.append((f"{path} = [None]", set_path(payload, path, [None])))

            if value:
                queue.append(
                    (
                        f"{path} = duplicated",
                        set_path(payload, path, value * 2),
                    )
                )
                queue.append(
                    (
                        f"{path} = truncated",
                        set_path(payload, path, value[:-1]),
                    )
                )

        # Tuple/list row mutations.
        if isinstance(value, (list, tuple)) and len(value) > 0:
            row = list(value)

            queue.append(
                (
                    f"{path} = row truncated",
                    set_path(payload, path, row[:-1]),
                )
            )
            queue.append(
                (
                    f"{path} = row extra item",
                    set_path(payload, path, row + [None]),
                )
            )

    return queue


def generate_cases(
    target: int,
    combos: int,
    fuzz: int,
    seed: int,
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(base: str, mutation: str, payload: Any) -> None:
        if target and len(cases) >= target:
            return

        try:
            key_source = json.dumps(payload, sort_keys=True, default=str)
        except Exception:
            key_source = repr(payload)

        key = hashlib.sha256(key_source.encode("utf-8")).hexdigest()

        if key in seen:
            return

        seen.add(key)
        cases.append(
            {
                "base": base,
                "mutation": mutation,
                "payload": payload,
            }
        )

    # Top-level cases.
    for mutation, payload in TOP_LEVEL_CASES:
        add("TopLevel", mutation, payload)

    # Valid baselines.
    for base, payload in BASE_PAYLOADS.items():
        add(base, "valid baseline", copy.deepcopy(payload))

    # Global message-level mutations.
    for base, payload in BASE_PAYLOADS.items():
        for mutation, mutated in global_mutations(base, payload):
            add(base, mutation, mutated)

    # Exhaustive single-path mutations.
    queues: dict[str, list[tuple[str, Any]]] = {}

    for base, payload in BASE_PAYLOADS.items():
        queues[base] = single_path_mutations(base, payload)

    while len(cases) < target and any(queues.values()):
        progressed = False

        for base in list(BASE_PAYLOADS.keys()):
            if target and len(cases) >= target:
                break

            queue = queues[base]
            if queue:
                mutation, mutated = queue.pop(0)
                add(base, mutation, mutated)
                progressed = True

        if not progressed:
            break

    # Pairwise/random combination mutations.
    rng = random.Random(seed)

    base_names = list(BASE_PAYLOADS.keys())

    for i in range(combos):
        if target and len(cases) >= target:
            break

        base = rng.choice(base_names)
        payload = BASE_PAYLOADS[base]

        paths = [
            path
            for path, _ in iter_paths(payload)
            if path != "$._type"
        ]

        if not paths:
            continue

        mutated = copy.deepcopy(payload)
        mutation_count = rng.randint(1, 3)

        mutation_labels = []

        for _ in range(mutation_count):
            path = rng.choice(paths)
            label, value = rng.choice(WRONG_VALUES)
            mutated = set_path(mutated, path, value)
            mutation_labels.append(f"{path}={label}")

        add(
            base,
            "combo: " + " + ".join(mutation_labels),
            mutated,
        )

    # Seeded fuzz mutations.
    for i in range(fuzz):
        if target and len(cases) >= target:
            break

        base = rng.choice(base_names)
        payload = BASE_PAYLOADS[base]

        paths = [
            path
            for path, _ in iter_paths(payload)
            if path != "$._type"
        ]

        if not paths:
            continue

        mutated = copy.deepcopy(payload)
        mutation_count = rng.randint(1, 4)

        for _ in range(mutation_count):
            path = rng.choice(paths)
            label, value = rng.choice(WRONG_VALUES)
            mutated = set_path(mutated, path, value)

        add(base, f"fuzz {i}", mutated)

    return cases


# ═══════════════════════════════════════════════════════════════
# OFFICIAL CLASSIFICATION
# ═══════════════════════════════════════════════════════════════
def classify_with_official(cases: list[dict[str, Any]]) -> None:
    from highrise import Incoming, converter

    cache: dict[str, tuple[bool, str]] = {}

    for i, case in enumerate(cases, start=1):
        payload = case["payload"]

        try:
            sample = json.dumps(payload, sort_keys=True, default=str)
        except Exception as exc:
            case["official_accept"] = False
            case["official_error"] = f"JSONEncodeError: {exc}"
            continue

        key = hashlib.sha256(sample.encode("utf-8")).hexdigest()

        cached = cache.get(key)
        if cached is not None:
            case["official_accept"] = cached[0]
            case["official_error"] = cached[1]
        else:
            try:
                converter.loads(sample, Incoming)
                result = (True, "")
            except Exception as exc:
                result = (False, f"{type(exc).__name__}: {exc}")

            cache[key] = result
            case["official_accept"] = result[0]
            case["official_error"] = result[1]

        if i % 100 == 0 or i == len(cases):
            print(f"  official classified {i}/{len(cases)}", flush=True)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate a large official golden validation matrix"
    )
    ap.add_argument(
        "--target",
        type=int,
        default=5000,
        help="Maximum number of cases to generate. Use 0 for no limit.",
    )
    ap.add_argument(
        "--combos",
        type=int,
        default=1000,
        help="Number of pairwise/random combination mutations",
    )
    ap.add_argument(
        "--fuzz",
        type=int,
        default=1000,
        help="Number of seeded fuzz mutations",
    )
    ap.add_argument(
        "--seed",
        type=int,
        default=12345,
        help="Random seed",
    )
    ap.add_argument(
        "--out",
        type=str,
        default="official_gold_large.json",
        help="Output JSON golden report",
    )
    args = ap.parse_args()

    print("═" * 100)
    print("  OFFICIAL GOLDEN VALIDATION MATRIX GENERATOR")
    print("═" * 100)

    cases = generate_cases(
        target=args.target,
        combos=args.combos,
        fuzz=args.fuzz,
        seed=args.seed,
    )

    print(f"Generated {len(cases)} unique cases.")
    print("Classifying with official SDK...")

    classify_with_official(cases)

    for i, case in enumerate(cases, start=1):
        case["id"] = f"GM-{i:05d}"

    accepts = sum(1 for case in cases if case.get("official_accept"))
    rejects = len(cases) - accepts

    report = {
        "total_cases": len(cases),
        "official_accepts": accepts,
        "official_rejects": rejects,
        "cases": cases,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    print()
    print(f"Total cases        : {len(cases)}")
    print(f"Official ACCEPT    : {accepts}")
    print(f"Official REJECT    : {rejects}")
    print(f"Golden report      : {args.out}")
    print()
    print("Next:")
    print(f"  python benchmark_native_gold.py {args.out}")


if __name__ == "__main__":
    main()
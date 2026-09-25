"""
benchmark_adversarial.py
Generates 10,000 malformed and semantically invalid payloads to benchmark
the strict validator and ensure it never crashes (only raises HighriseFastValidationError).
"""

import json
import random
import time

from highrise_fast.validation import (
    HighriseFastValidationError,
    validate_server_message,
)


def generate_adversarial_payload():
    """Generates a random invalid payload."""
    base = {
        "_type": "ChatEvent",
        "user": {"id": "u1", "username": "test"},
        "message": "hello",
        "whisper": False,
    }

    # Randomly corrupt the payload
    corruption = random.choice(
        [
            "missing_type",
            "unknown_type",
            "wrong_type_user_id",
            "missing_user",
            "semantic_message_too_long",
            "wrong_type_whisper",
            "null_user",
            "list_instead_of_dict",
        ]
    )

    if corruption == "missing_type":
        del base["_type"]
    elif corruption == "unknown_type":
        base["_type"] = "FakeEvent"
    elif corruption == "wrong_type_user_id":
        base["user"]["id"] = 12345  # Must be string
    elif corruption == "missing_user":
        del base["user"]
    elif corruption == "semantic_message_too_long":
        base["message"] = "A" * 2000  # Limit is 1024
    elif corruption == "wrong_type_whisper":
        base["whisper"] = "yes"  # Must be bool
    elif corruption == "null_user":
        base["user"] = None
    elif corruption == "list_instead_of_dict":
        return ["not", "a", "dict"]

    return base


def run_benchmark(n=10000):
    print(f"🚀 Starting Adversarial Benchmark ({n} iterations)...")

    errors_caught = 0
    unexpected_crashes = 0

    start_time = time.perf_counter()

    for i in range(n):
        payload = generate_adversarial_payload()
        try:
            # strict=True and strict_semantic=True to test all bounds
            validate_server_message(payload, strict=True, strict_semantic=True)
        except HighriseFastValidationError:
            errors_caught += 1
        except Exception as e:
            unexpected_crashes += 1
            print(f"❌ CRASH on iteration {i}: {type(e).__name__} - {e}")
            print(f"Payload: {json.dumps(payload, default=str)}")
            break

    elapsed = time.perf_counter() - start_time
    ops_per_sec = n / elapsed if elapsed > 0 else 0

    print("\n" + "=" * 40)
    print("📊 BENCHMARK RESULTS")
    print("=" * 40)
    print(f"Total Iterations : {n}")
    print(f"Errors Caught    : {errors_caught} (Expected)")
    print(f"Unexpected Crashes: {unexpected_crashes} (Should be 0)")
    print(f"Time Elapsed     : {elapsed:.3f} seconds")
    print(f"Throughput       : {ops_per_sec:,.0f} validations/sec")
    print("=" * 40)

    if unexpected_crashes == 0:
        print("✅ SUCCESS: Validator survived all adversarial inputs without crashing.")
    else:
        print("❌ FAILURE: Validator crashed on malformed input.")


if __name__ == "__main__":
    run_benchmark(10000)

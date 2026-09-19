"""
kkk.py — compare highrise_fast/validation.py against official_gold_5000.json

Run:
    python kkk.py                 # summary + first 20 mismatches per direction
    python kkk.py --all           # show every mismatch
"""

import json
import sys
import traceback
from collections import Counter


def load_validator():
    """Import validation.py and return its validate_server_message callable."""
    import importlib
    mod = importlib.import_module("validation")
    fn = getattr(mod, "validate_server_message", None)
    if fn is None:
        raise SystemExit(
            "validation.py has no 'validate_server_message' entrypoint"
        )
    return fn


def run_one(fn, payload):
    """Return (accepted: bool, note: str)."""
    try:
        fn(payload)
        return True, ""
    except Exception:
        tb = traceback.format_exc(limit=1).strip().splitlines()[-1]
        return False, tb


def compare(cases_path="official_gold_5000.json", show_all=False, max_examples=20):
    with open(cases_path, encoding="utf-8") as f:
        data = json.load(f)

    cases = data["cases"]
    validate = load_validator()

    total = agree = 0
    too_permissive = []   # we accept, official rejects
    too_strict = []       # we reject, official accepts
    fp_by_base = Counter()
    fn_by_base = Counter()
    fp_by_mut = Counter()
    fn_by_mut = Counter()

    for case in cases:
        total += 1
        expected = bool(case["official_accept"])
        got, note = run_one(validate, case["payload"])

        if got == expected:
            agree += 1
            continue

        rec = {
            "id": case["id"],
            "base": case["base"],
            "mutation": case["mutation"],
            "official_error": case.get("official_error", ""),
            "ours_note": note,
            "payload": case["payload"],
        }
        if expected is False and got is True:
            too_permissive.append(rec)
            fp_by_base[case["base"]] += 1
            fp_by_mut[case["mutation"]] += 1
        else:
            too_strict.append(rec)
            fn_by_base[case["base"]] += 1
            fn_by_mut[case["mutation"]] += 1

    print("=" * 72)
    print(f"Cases file: {cases_path}")
    print(f"Total: {total}")
    print(f"Agree: {agree}  ({agree / total:.2%})")
    print(f"Disagree: {len(too_permissive) + len(too_strict)}")
    print(f"  Too PERMISSIVE (we accept, official rejects): {len(too_permissive)}")
    print(f"  Too STRICT     (we reject, official accepts): {len(too_strict)}")
    print("=" * 72)

    def bucket(title, records, by_base, by_mut):
        print()
        print(title)
        print("-" * len(title))
        if not records:
            print("  (none)")
            return
        print("  by base:")
        for b, n in by_base.most_common():
            print(f"    {n:5d}  {b}")
        print("  by mutation (top 15):")
        for m, n in by_mut.most_common(15):
            print(f"    {n:5d}  {m}")
        print()
        show = records if show_all else records[:max_examples]
        for r in show:
            print(f"  [{r['id']}] {r['base']} / {r['mutation']}")
            if r["official_error"]:
                print(f"        official says: {r['official_error']}")
            if r["ours_note"]:
                print(f"        ours says:     {r['ours_note']}")
            print(f"        payload:       {json.dumps(r['payload'])[:160]}")
        if not show_all and len(records) > max_examples:
            print(f"  ... {len(records) - max_examples} more "
                  f"(re-run with --all to see them)")

    bucket("TOO PERMISSIVE — you accept, official rejects",
           too_permissive, fp_by_base, fp_by_mut)
    bucket("TOO STRICT — you reject, official accepts",
           too_strict, fn_by_base, fn_by_mut)

    return len(too_permissive) + len(too_strict)


def main(argv):
    flags = {a for a in argv[1:] if a.startswith("--")}
    positional = [a for a in argv[1:] if not a.startswith("--")]
    cases_path = positional[0] if positional else "official_gold_5000.json"
    sys.path.insert(0, ".")
    compare(cases_path, show_all="--all" in flags)


if __name__ == "__main__":
    main(sys.argv)
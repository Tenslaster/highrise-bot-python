#!/usr/bin/env python3
"""lint_fix.py — apply Python lint/format fixes in one shot.

Two backends:

  ruff    ``ruff check --fix`` + ``ruff format``         (preferred, fast)
  legacy  ``autoflake`` + ``isort`` + ``black``/``autopep8``

The ruff backend lets ruff own file discovery and exclusion, so it honors
``.gitignore``, ``.ruffignore``, ``.ruff.toml``, and per-directory
``pyproject.toml`` for free.  The legacy backend falls back to a small
built-in walker because the old tools have no comparable exclusion engine.

Exit codes
----------
0   clean, or all issues were auto-fixed
1   issues remain (typical for ``--check`` / ``--diff``)
2   usage error, missing dependency, or tool crash
130 interrupted
"""

from __future__ import annotations

import argparse
import fnmatch
import importlib.util
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Only used by the legacy backend.  The ruff backend delegates exclusion to
# ruff itself, which already knows about these and more.
LEGACY_EXCLUDE_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        ".venv",
        "venv",
        "env",
    }
)

LEGACY_EXCLUDE_GLOBS: tuple[str, ...] = ("*/migrations/*",)

EXIT_OK = 0
EXIT_ISSUES = 1
EXIT_ERROR = 2
EXIT_INTERRUPT = 130


# ---------------------------------------------------------------------------
# Process helpers
# ---------------------------------------------------------------------------


def _python() -> str:
    return sys.executable or "python"


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _run(cmd: Sequence[str], *, verbose: bool) -> int:
    """Run *cmd*, letting its stdout/stderr go straight to our terminal.

    We deliberately do NOT capture output.  ruff writes UTF-8, the Windows
    console is often cp1252, and any decode() we did here would be wrong for
    one of the two.  By not touching the bytes we sidestep the whole question
    -- and we get live output as a bonus.
    """
    if verbose:
        print("+", " ".join(cmd), flush=True)
    try:
        rc = subprocess.run(cmd, check=False).returncode
    except FileNotFoundError as exc:
        print(f"error: could not launch {cmd[0]!r}: {exc}", file=sys.stderr)
        return EXIT_ERROR
    # Negative rc on POSIX means "killed by signal"; normalize to an error.
    return rc if rc >= 0 else EXIT_ERROR


def _worse(a: int, b: int) -> int:
    """Combine two exit codes, keeping the more severe."""
    return max(a, b)


# ---------------------------------------------------------------------------
# Legacy backend -- file walker + tool runners
# ---------------------------------------------------------------------------


def _is_excluded(
    path: Path,
    exclude_dirs: frozenset[str],
    exclude_globs: Sequence[str],
) -> bool:
    parts = {part.lower() for part in path.parts}
    if parts & exclude_dirs:
        return True
    posix = path.as_posix()
    return any(fnmatch.fnmatch(posix, pat) for pat in exclude_globs)


def _gather_py_files(
    root: Path,
    *,
    recursive: bool,
    exclude_dirs: frozenset[str],
    exclude_globs: Sequence[str],
) -> list[Path]:
    if root.is_file():
        if root.suffix == ".py" and not _is_excluded(root, exclude_dirs, exclude_globs):
            return [root]
        return []
    if not root.exists():
        raise FileNotFoundError(root)
    it = root.rglob("*.py") if recursive else root.glob("*.py")
    files = [
        p
        for p in it
        if p.is_file() and not _is_excluded(p, exclude_dirs, exclude_globs)
    ]
    files.sort(key=lambda p: p.as_posix().lower())
    return files


def _run_legacy(
    files: Sequence[Path],
    *,
    check: bool,
    diff: bool,
    line_length: int | None,
    aggressive: int,
    verbose: bool,
) -> int:
    if not files:
        return EXIT_OK
    file_args = [str(p) for p in files]
    rc = EXIT_OK

    # 1. autoflake -- drop unused imports / variables
    cmd = [
        _python(),
        "-m",
        "autoflake",
        "--remove-all-unused-imports",
        "--remove-unused-variables",
    ]
    cmd += ["--check"] if check else (["--diff"] if diff else ["--in-place"])
    cmd += file_args
    rc = _worse(rc, _run(cmd, verbose=verbose))

    # 2. isort -- import order
    cmd = [_python(), "-m", "isort"]
    if line_length is not None:
        cmd += ["--line-length", str(line_length)]
    cmd += ["--check-only"] if check else (["--diff"] if diff else [])
    cmd += file_args
    rc = _worse(rc, _run(cmd, verbose=verbose))

    # 3. formatter -- black, falling back to autopep8
    if _module_available("black"):
        cmd = [_python(), "-m", "black"]
        if line_length is not None:
            cmd += ["--line-length", str(line_length)]
        cmd += ["--check"] if check else (["--diff"] if diff else [])
    else:
        cmd = [_python(), "-m", "autopep8"]
        if line_length is not None:
            cmd += ["--max-line-length", str(line_length)]
        cmd += ["--aggressive"] * max(0, aggressive)
        if check:
            cmd += ["--exit-code", "--diff"]
        elif diff:
            cmd += ["--diff"]
        else:
            cmd += ["--in-place"]
    cmd += file_args
    rc = _worse(rc, _run(cmd, verbose=verbose))

    return rc if rc <= EXIT_ISSUES else EXIT_ERROR


# ---------------------------------------------------------------------------
# Ruff backend
# ---------------------------------------------------------------------------


def _ruff_targets(paths: Sequence[str], *, recursive: bool) -> list[str]:
    """Arguments to hand to ruff.

    When recursive (the default) we pass the user's paths straight through so
    ruff does its own fast, gitignore-aware walk.  With ``--no-recursive`` we
    expand directories to their top-level ``*.py`` files ourselves.
    """
    if recursive:
        return list(paths)
    out: list[str] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            out.extend(str(f) for f in p.glob("*.py"))
        else:
            out.append(str(p))  # let ruff report "file not found"
    return out


def _run_ruff(
    targets: Sequence[str],
    *,
    check: bool,
    diff: bool,
    line_length: int | None,
    excludes: Sequence[str],
    verbose: bool,
) -> int:
    if not targets:
        return EXIT_OK

    common: list[str] = []
    if line_length is not None:
        common += ["--line-length", str(line_length)]
    if excludes:
        common += ["--extend-exclude", ",".join(excludes)]

    # 1. ruff check -- lint (and fix unless --check / --diff)
    cmd = [_python(), "-m", "ruff", "check"]
    if check:
        pass
    elif diff:
        cmd += ["--diff"]
    else:
        cmd += ["--fix"]
    cmd += common + list(targets)
    rc = _run(cmd, verbose=verbose)

    # 2. ruff format -- formatting
    cmd = [_python(), "-m", "ruff", "format"]
    if check:
        cmd += ["--check"]
    elif diff:
        cmd += ["--diff"]
    cmd += common + list(targets)
    rc = _worse(rc, _run(cmd, verbose=verbose))

    return rc if rc <= EXIT_ISSUES else EXIT_ERROR


# ---------------------------------------------------------------------------
# Backend selection / dependency check
# ---------------------------------------------------------------------------


def _resolve_backend(requested: str) -> str:
    if requested != "auto":
        return requested
    return "ruff" if _module_available("ruff") else "legacy"


def _check_tools(backend: str) -> str | None:
    """Return an error message if the backend's tools are unavailable."""
    missing: list[str] = []
    if backend == "ruff":
        if not _module_available("ruff"):
            missing.append("ruff")
    else:
        for mod in ("autoflake", "isort"):
            if not _module_available(mod):
                missing.append(mod)
        if not (_module_available("black") or _module_available("autopep8")):
            missing.append("black or autopep8")
    if not missing:
        return None

    lines = [
        f"error: missing tools for backend {backend!r}: {', '.join(missing)}",
        "install with:",
        "  pip install ruff"
        if backend == "ruff"
        else "  pip install autoflake isort black   # or: ... autopep8",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="lint_fix",
        description="Apply Python lint/format fixes to files or directories.",
    )
    ap.add_argument(
        "paths",
        nargs="*",
        metavar="PATH",
        help="files or directories to process (default: .)",
    )
    ap.add_argument(
        "--backend",
        choices=("auto", "ruff", "legacy"),
        default="auto",
        help="auto = ruff if installed, otherwise legacy (default)",
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="report only; do not modify files (non-zero exit if issues)",
    )
    ap.add_argument(
        "--diff", action="store_true", help="print diffs instead of writing changes"
    )
    ap.add_argument(
        "--line-length",
        type=int,
        default=None,
        metavar="N",
        help="override formatter line length (default: use tool/project config)",
    )
    ap.add_argument(
        "--aggressive",
        type=int,
        default=2,
        metavar="N",
        help="autopep8 aggressiveness (legacy backend only; default: 2)",
    )
    ap.add_argument(
        "--no-recursive",
        action="store_true",
        help="only process *.py in the top level of each directory",
    )
    ap.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        metavar="NAME",
        help="directory name to exclude (repeatable)",
    )
    ap.add_argument(
        "--exclude-glob",
        action="append",
        default=[],
        metavar="PATTERN",
        help="gitignore-style pattern to exclude (repeatable)",
    )
    ap.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="print each command before running it",
    )
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    ns = _build_parser().parse_args(argv)

    if ns.check and ns.diff:
        print("error: --check and --diff are mutually exclusive", file=sys.stderr)
        return EXIT_ERROR
    if ns.line_length is not None and ns.line_length < 1:
        print("error: --line-length must be a positive integer", file=sys.stderr)
        return EXIT_ERROR
    if ns.aggressive < 0:
        print("error: --aggressive must be >= 0", file=sys.stderr)
        return EXIT_ERROR

    backend = _resolve_backend(ns.backend)
    problem = _check_tools(backend)
    if problem is not None:
        print(problem, file=sys.stderr)
        return EXIT_ERROR

    paths: list[str] = ns.paths or ["."]
    recursive = not ns.no_recursive
    t0 = time.monotonic()

    if backend == "ruff":
        targets = _ruff_targets(paths, recursive=recursive)
        excludes = [*ns.exclude_dir, *ns.exclude_glob]
        print(f"[ruff] {len(targets)} target(s)", flush=True)
        code = _run_ruff(
            targets,
            check=ns.check,
            diff=ns.diff,
            line_length=ns.line_length,
            excludes=excludes,
            verbose=ns.verbose,
        )
    else:
        exclude_dirs = LEGACY_EXCLUDE_DIRS | frozenset(
            d.lower() for d in ns.exclude_dir
        )
        exclude_globs = (*LEGACY_EXCLUDE_GLOBS, *ns.exclude_glob)

        files: list[Path] = []
        for raw in paths:
            try:
                files.extend(
                    _gather_py_files(
                        Path(raw),
                        recursive=recursive,
                        exclude_dirs=exclude_dirs,
                        exclude_globs=exclude_globs,
                    )
                )
            except FileNotFoundError as exc:
                print(f"error: path does not exist: {exc}", file=sys.stderr)
                return EXIT_ERROR

        # Deduplicate while preserving the walker's sorted order.
        seen: set[Path] = set()
        unique: list[Path] = []
        for f in files:
            rp = f.resolve()
            if rp not in seen:
                seen.add(rp)
                unique.append(f)

        print(f"[legacy] {len(unique)} file(s)", flush=True)
        if not unique:
            print("No Python files found.")
            return EXIT_OK
        code = _run_legacy(
            unique,
            check=ns.check,
            diff=ns.diff,
            line_length=ns.line_length,
            aggressive=ns.aggressive,
            verbose=ns.verbose,
        )

    dt = time.monotonic() - t0
    status = {EXIT_OK: "clean", EXIT_ISSUES: "issues", EXIT_ERROR: "error"}.get(
        code, "?"
    )
    print(f"done in {dt:.2f}s -- {status} (exit {code})")
    return code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        raise SystemExit(EXIT_INTERRUPT)

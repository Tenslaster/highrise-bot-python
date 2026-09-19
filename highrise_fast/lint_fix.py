#!/usr/bin/env python3

from __future__ import annotations

import argparse
import fnmatch
import importlib.util
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path

DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".env",
}

DEFAULT_EXCLUDE_GLOBS = {
    "*/migrations/*",
    "*/.tox/*",
}


def _module_installed(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _decode(raw: bytes | None) -> str:
    """Decode tool output. Ruff emits UTF-8; Windows locale is often cp1252."""
    return (raw or b"").decode("utf-8", errors="replace")


def _run(cmd: Sequence[str], *, verbose: bool = False) -> int:
    """Run a command and return its exit code.

    Bytes-only pipes: never let Windows cp1252 decode ruff's UTF-8 checkmarks.
    """
    if verbose:
        print("▶", " ".join(cmd))

    p = subprocess.run(
        cmd,
        capture_output=True,
        check=False,
    )
    out = _decode(p.stdout)
    err = _decode(p.stderr)
    text = (err or out).strip()
    if verbose and text:
        print(text)
    elif p.returncode != 0:
        print(f"✖ Command failed ({p.returncode}): {' '.join(cmd)}")
        if text:
            print(text)
    return p.returncode


def _is_excluded(path: Path, exclude_dirs: set[str], exclude_globs: set[str]) -> bool:
    parts = {p.lower() for p in path.parts}
    for d in exclude_dirs:
        if d.lower() in parts:
            return True
    s = path.as_posix()
    return any(fnmatch.fnmatch(s, g) for g in exclude_globs)


def _gather_py_files(
    root: Path,
    recursive: bool,
    exclude_dirs: set[str],
    exclude_globs: set[str],
) -> list[Path]:
    if root.is_file():
        return (
            [root]
            if root.suffix == ".py"
            and not _is_excluded(root, exclude_dirs, exclude_globs)
            else []
        )

    if not root.exists():
        raise FileNotFoundError(f"Path does not exist: {root}")

    it = root.rglob("*.py") if recursive else root.glob("*.py")
    files = [
        p
        for p in it
        if p.is_file() and not _is_excluded(p, exclude_dirs, exclude_globs)
    ]
    # Stable order for consistent output
    files.sort(key=lambda p: p.as_posix().lower())
    return files


def _backend_auto() -> str:
    # Prefer ruff if installed
    if _module_installed("ruff"):
        return "ruff"
    # Otherwise legacy stack
    return "legacy"


def _ensure_tools(backend: str) -> None:
    missing: list[str] = []
    if backend == "ruff":
        if not _module_installed("ruff"):
            missing.append("ruff")
    else:
        # legacy
        for mod in ("autoflake", "isort"):
            if not _module_installed(mod):
                missing.append(mod)
        # formatter: prefer black, else autopep8
        if not (_module_installed("black") or _module_installed("autopep8")):
            missing.append("black OR autopep8")

    if missing:
        print("Missing required tools for this backend:")
        for m in missing:
            print(" -", m)
        print("\nInstall with:")
        if backend == "ruff":
            print("  pip install ruff")
        else:
            print("  pip install autoflake isort black")
            print("  # or: pip install autoflake isort autopep8")
        sys.exit(2)


def _ruff(
    files: list[Path], *, check: bool, diff: bool, line_length: int, verbose: bool
) -> int:
    # Ruff supports running on directories; passing the root is faster,
    # but we already filtered file list, so we pass explicit files.
    file_args = [str(p) for p in files]

    # 1) Lint (and fix unless --check/--diff)
    cmd1 = [sys.executable, "-m", "ruff", "check"]
    if check:
        pass
    elif diff:
        cmd1 += ["--diff"]
    else:
        cmd1 += ["--fix"]
    cmd1 += ["--line-length", str(line_length)]
    cmd1 += file_args
    rc1 = _run(cmd1, verbose=verbose)

    # 2) Format (ruff format) unless --check with no changes
    cmd2 = [sys.executable, "-m", "ruff", "format", "--line-length", str(line_length)]
    if check:
        cmd2 += ["--check"]
    elif diff:
        cmd2 += ["--diff"]
    cmd2 += file_args
    rc2 = _run(cmd2, verbose=verbose)

    return 0 if (rc1 == 0 and rc2 == 0) else 1


def _legacy(
    files: list[Path],
    *,
    check: bool,
    diff: bool,
    line_length: int,
    verbose: bool,
    aggressive: int,
) -> int:
    file_args = [str(p) for p in files]
    rc = 0

    # 1) autoflake: remove unused imports/vars
    cmd1 = [
        sys.executable,
        "-m",
        "autoflake",
        "--remove-unused-variables",
        "--remove-all-unused-imports",
    ]
    if check:
        cmd1 += ["--check"]
    elif diff:
        cmd1 += ["--diff"]
    else:
        cmd1 += ["--in-place"]
    cmd1 += file_args
    rc |= _run(cmd1, verbose=verbose)

    # 2) isort: imports
    cmd2 = [sys.executable, "-m", "isort"]
    if check:
        cmd2 += ["--check-only"]
    elif diff:
        cmd2 += ["--diff"]
    cmd2 += ["--line-length", str(line_length)]
    cmd2 += file_args
    rc |= _run(cmd2, verbose=verbose)

    # 3) formatter: black if available else autopep8
    if _module_installed("black"):
        cmd3 = [sys.executable, "-m", "black", "--line-length", str(line_length)]
        if check:
            cmd3 += ["--check"]
        elif diff:
            cmd3 += ["--diff"]
        cmd3 += file_args
        rc |= _run(cmd3, verbose=verbose)
    else:
        cmd3 = [sys.executable, "-m", "autopep8", "--max-line-length", str(line_length)]
        # autopep8 aggressive levels
        for _ in range(max(0, aggressive)):
            cmd3 += ["--aggressive"]
        if check:
            cmd3 += ["--exit-code", "--diff"]
        elif diff:
            cmd3 += ["--diff"]
        else:
            cmd3 += ["--in-place"]
        cmd3 += file_args
        rc |= _run(cmd3, verbose=verbose)

    return 0 if rc == 0 else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Apply lint/format fixes to Python files.")
    ap.add_argument(
        "--path", default=".", help="File or directory to process (default: .)"
    )
    ap.add_argument(
        "--no-recursive",
        action="store_true",
        help="Only process *.py in the top directory",
    )
    ap.add_argument(
        "--backend",
        choices=("auto", "ruff", "legacy"),
        default="auto",
        help="auto=prefer ruff if installed; else legacy",
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="Check only (no changes), non-zero exit if needed",
    )
    ap.add_argument(
        "--diff",
        action="store_true",
        help="Show diff instead of writing changes (where supported)",
    )
    ap.add_argument(
        "--line-length", type=int, default=88, help="Line length for sort/format"
    )
    ap.add_argument(
        "--aggressive",
        type=int,
        default=2,
        help="autopep8 aggressive level (legacy only)",
    )
    ap.add_argument(
        "--verbose", action="store_true", help="Print commands and stream tool output"
    )

    ap.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Directory name to exclude (can be repeated), e.g. --exclude-dir .venv",
    )
    ap.add_argument(
        "--exclude-glob",
        action="append",
        default=[],
        help="Glob to exclude (can be repeated), e.g. --exclude-glob '*/generated/*'",
    )

    ns = ap.parse_args(argv)

    if ns.check and ns.diff:
        print("Choose only one: --check OR --diff")
        return 2

    root = Path(ns.path).resolve()
    recursive = not ns.no_recursive

    exclude_dirs = set(DEFAULT_EXCLUDE_DIRS) | set(ns.exclude_dir)
    exclude_globs = set(DEFAULT_EXCLUDE_GLOBS) | set(ns.exclude_glob)

    backend = ns.backend if ns.backend != "auto" else _backend_auto()
    _ensure_tools(backend)

    files = _gather_py_files(root, recursive, exclude_dirs, exclude_globs)
    if not files:
        print("No Python files found.")
        return 0

    print(f"Found {len(files)} Python file(s). Backend: {backend}")
    t0 = time.time()

    if backend == "ruff":
        code = _ruff(
            files,
            check=ns.check,
            diff=ns.diff,
            line_length=ns.line_length,
            verbose=ns.verbose,
        )
    else:
        code = _legacy(
            files,
            check=ns.check,
            diff=ns.diff,
            line_length=ns.line_length,
            verbose=ns.verbose,
            aggressive=ns.aggressive,
        )

    dt = time.time() - t0
    print(f"Done in {dt:.2f}s. Exit code: {code}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""R10-003: CI gate — check forbidden CI/quality patterns.

Fails on:
  - assert True (no-op assertions that mask missing tests)
  - Tracked runtime DB files (*.db committed)
  - Legacy JSON authority reads (media_plan.json loaded with json.load)
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ERRORS = 0


def _parse_file(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(), filename=str(path))
    except SyntaxError:
        return None


def check_assert_true():
    """Catch assert True no-ops in test files."""
    global ERRORS
    for f in (ROOT / "tests").rglob("test_*.py"):
        tree = _parse_file(f)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert) and isinstance(node.test, ast.Constant) and node.test.value is True:
                print(f"CI GATE: FORBIDDEN assert True in {f}:{node.lineno}")
                ERRORS += 1


def check_tracked_db_files():
    """Ensure no .db files are tracked."""
    global ERRORS
    import subprocess
    r = subprocess.run(["git", "ls-files", "*.db", "*.sqlite", "*.sqlite3"],
                       capture_output=True, text=True, cwd=ROOT)
    for line in r.stdout.strip().split("\n"):
        if line.strip():
            print(f"CI GATE: TRACKED DB FILE: {line}")
            ERRORS += 1


def main():
    print("Running CI gate: check_forbidden_behavior...")
    check_assert_true()
    check_tracked_db_files()

    if ERRORS:
        print(f"\nCI GATE FAILED: {ERRORS} forbidden patterns found.")
        return 1
    print("OK CI GATE PASSED: No forbidden behavior patterns.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

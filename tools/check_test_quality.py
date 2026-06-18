#!/usr/bin/env python3
"""CI Gate: Detect low-quality test patterns.

Fails on: assert True no-ops, completely empty tests, tests that
only use SQL mocks without touching real DB functions, and the exact
placeholder lipsync PASS pattern (score=0.85 AND confidence=0.90 in one
test function) which mirrors the production placeholder the release guard
blocks.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = ROOT / "tests"
SCRIPTS_DIR = ROOT / "scripts"

# The exact placeholder pair the release guard blocks in production. A test that
# hardcodes BOTH constants is asserting against the placeholder, not a real model.
PLACEHOLDER_SCORE = 0.85
PLACEHOLDER_CONFIDENCE = 0.90


def _collect_script_function_names() -> set[str]:
    names = set()
    for py_file in SCRIPTS_DIR.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(), filename=str(py_file))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                names.add(node.name)
    return names


SCRIPT_FUNCTIONS = _collect_script_function_names()


def _check_test_function(node: ast.FunctionDef) -> list[str]:
    violations = []

    body = [s for s in node.body if not isinstance(s, ast.Expr) or not isinstance(s.value, ast.Constant)]
    has_mark = any(
        isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "mark"
        for d in node.decorator_list
    )

    # Empty test (no executable statements)
    if not body:
        violations.append(f"  {node.name}: empty test with no assertions")
        return violations

    # Single assert True
    if len(body) == 1:
        stmt = body[0]
        if isinstance(stmt, ast.Assert) and isinstance(stmt.test, ast.Constant) and stmt.test.value is True:
            violations.append(f"  {node.name}: single assert True no-op")
            return violations

    # Detect all-SQL-mocked: test only touches mocked DB, never calls real script functions
    called_names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                called_names.add(child.func.id)
            elif isinstance(child.func, ast.Attribute):
                called_names.add(child.func.attr)

    real_script_calls = called_names & SCRIPT_FUNCTIONS
    has_db_import = any(
        isinstance(child, ast.ImportFrom) and child.module and "production_db" in child.module
        for child in ast.walk(node)
    )

    if not real_script_calls and not has_mark:
        if any(isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute)
               and child.func.attr in ("connect", "transaction", "execute", "migrate")
               for child in ast.walk(node)):
            violations.append(f"  {node.name}: mock-only test — zero calls to real script functions")

    # Placeholder lipsync PASS pattern: both 0.85 (score) and 0.90 (confidence)
    # hardcoded in the same test function. This mirrors the production placeholder
    # the release guard blocks; a real test must use a calibrated model/fixture.
    floats_in_test = {
        child.value for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, float)
    }
    if PLACEHOLDER_SCORE in floats_in_test and PLACEHOLDER_CONFIDENCE in floats_in_test:
        violations.append(
            f"  {node.name}: hardcoded placeholder PASS (score={PLACEHOLDER_SCORE}, "
            f"confidence={PLACEHOLDER_CONFIDENCE}) — use a real calibrated model/fixture")

    return violations


def check_file(filepath: Path) -> list[tuple[int, str]]:
    violations = []
    try:
        tree = ast.parse(filepath.read_text(), filename=str(filepath))
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            v = _check_test_function(node)
            violations.extend([(node.lineno, vv) for vv in v])

    return violations


def main():
    print("Running CI gate: check_test_quality...")
    total_violations = 0

    for py_file in sorted(TESTS_DIR.rglob("test_*.py")):
        rel_path = str(py_file.relative_to(ROOT))
        violations = check_file(py_file)
        if violations:
            total_violations += len(violations)
            print(f"\nX TEST QUALITY ISSUES in {rel_path}:")
            for lineno, msg in violations:
                print(f"   Line {lineno}:{msg}")

    if total_violations > 0:
        print(f"\nX CI GATE FAILED: {total_violations} test quality issues found.")
        print("   Action: Replace no-ops with real assertions; wire tests to real script functions.")
        sys.exit(1)
    else:
        print("OK CI GATE PASSED: No test quality issues.")
        sys.exit(0)


if __name__ == "__main__":
    main()

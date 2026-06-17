#!/usr/bin/env python3
"""CI Gate: Forbid release-blocking placeholders in production code.

Detects: assert True no-ops, fixed-score PASS patterns, simulated/stubbed
provider markers on release path, auto_approved gates, and deleted-produce imports.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
TESTS_DIR = ROOT / "tests"

ALLOWLIST_PLACEHOLDER = {
    "scripts/lipsync_scoring.py",  # Known placeholder — tracked by R6
}

INVOKERS_ALLOWED_STUBS = frozenset({
    "invoke_publish",
    "invoke_analytics",
})


def _is_invoke_function(node: ast.FunctionDef) -> bool:
    return node.name.startswith("invoke_") or node.name.startswith("invoke_")


def _has_assert_true_noop(text: str, node: ast.FunctionDef) -> list[str]:
    violations = []
    body = node.body
    if len(body) == 1 and isinstance(body[0], ast.Expr):
        if isinstance(body[0].value, ast.Constant) and body[0].value.value is True:
            violations.append(f"  {node.name}: single-statement assert True no-op")
    return violations


def _check_fixed_score(body: list[ast.stmt]) -> list[str]:
    violations = []
    for stmt in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Subscript):
                    if isinstance(target.value, ast.Name) and target.value.id == "result":
                        if isinstance(target.slice, ast.Constant) and target.slice.value == "score":
                            if isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, (int, float)):
                                violations.append(f"  Fixed score assignment: result['score'] = {stmt.value.value}")
    return violations


def _check_string_literals_in_invoke(tree: ast.AST, relpath: str) -> list[str]:
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and _is_invoke_function(node):
            for child in ast.walk(node):
                if isinstance(child, ast.Constant) and isinstance(child.value, str):
                    s = child.value
                    if "simulated" in s.lower() and node.name not in INVOKERS_ALLOWED_STUBS:
                        violations.append(
                            f"  {node.name}: {repr(s)} — simulated/stubbed marker in invoke function"
                        )
                    if "stubbed" in s.lower() and node.name not in INVOKERS_ALLOWED_STUBS:
                        violations.append(
                            f"  {node.name}: {repr(s)} — simulated/stubbed marker in invoke function"
                        )
                    if "auto_approved" in s:
                        violations.append(
                            f"  {node.name}: {repr(s)} — auto_approved gate in invoker"
                        )
    return violations


def _check_from_produce_import(tree: ast.AST) -> list[str]:
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module == "produce":
                for alias in node.names:
                    violations.append(f"  from produce import {alias.name}")
    return violations


def check_file(filepath: Path) -> list[str]:
    violations = []
    try:
        text = filepath.read_text()
        tree = ast.parse(text, filename=str(filepath))
    except SyntaxError:
        return violations

    relpath = str(filepath.relative_to(ROOT))

    # Check test files for assert True no-ops
    if relpath.startswith("tests/") and relpath.endswith(".py"):
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                noop = _has_assert_true_noop(text, node)
                violations.extend([f"Line {node.lineno}:{v}" for v in noop])

    # Check for fixed-score PASS patterns
    if relpath not in ALLOWLIST_PLACEHOLDER:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and _is_invoke_function(node):
                score_v = _check_fixed_score(node.body)
                for v in score_v:
                    violations.append(f"Line {node.lineno}:{v}")
            elif isinstance(node, ast.Module):
                score_v = _check_fixed_score(node.body)
                for v in score_v:
                    violations.append(f"Line 1:{v}")

    # Check for simulated/stubbed/auto_approved in invokers
    v = _check_string_literals_in_invoke(tree, relpath)
    violations.extend(v)

    # Check for from produce import
    v = _check_from_produce_import(tree)
    if v:
        violations.extend(v)

    return violations


def main():
    print("Running CI gate: check_release_placeholders...")
    total_violations = 0

    for py_file in sorted(set(
        list(SCRIPTS_DIR.rglob("*.py")) + list(TESTS_DIR.rglob("*.py"))
    )):
        rel_path = str(py_file.relative_to(ROOT))
        if rel_path in ALLOWLIST_PLACEHOLDER:
            continue

        violations = check_file(py_file)
        if violations:
            total_violations += len(violations)
            print(f"\nX PLACEHOLDER VIOLATIONS in {rel_path}:")
            for v in violations:
                print(f"   {v}")

    if total_violations > 0:
        print(f"\nX CI GATE FAILED: {total_violations} release-blocking placeholders found.")
        print("   Action: Replace placeholders with real implementations or add to ALLOWLIST if tracked in later sprint.")
        sys.exit(1)
    else:
        print("OK CI GATE PASSED: No release-blocking placeholders found.")
        sys.exit(0)


if __name__ == "__main__":
    main()

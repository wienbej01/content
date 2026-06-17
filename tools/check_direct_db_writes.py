#!/usr/bin/env python3
"""CI Gate: Forbid direct INSERT/UPDATE into constrained tables outside repository services.

Direct DB writes on render_units, change_requests, and approval_requests must
go through the dedicated repository service modules, not raw SQL in produce_db.py.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"

CONSTRAINED_TABLES = frozenset({
    "render_units",
    "change_requests",
    "approval_requests",
})

REPOSITORY_SERVICES = frozenset({
    "scripts/tts_service.py",
    "scripts/authoring_service.py",
    "scripts/media_service.py",
    "scripts/assembly_db.py",
})

TARGET_FILE = "scripts/produce_db.py"


def _extract_table_name(sql: str) -> str | None:
    for table in CONSTRAINED_TABLES:
        if table in sql.lower():
            sql_upper = sql.upper()
            if f"INSERT INTO {table.upper()}" in sql_upper:
                return table
            if f"INSERT INTO  {table.upper()}" in sql_upper:
                return table
            if f"UPDATE {table.upper()}" in sql_upper:
                return table
    return None


def check_file(filepath: Path) -> list[str]:
    violations = []
    try:
        tree = ast.parse(filepath.read_text(), filename=str(filepath))
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func
        if not isinstance(func, ast.Attribute):
            continue

        if func.attr != "execute":
            continue

        if not node.args:
            continue

        first_arg = node.args[0]
        if not isinstance(first_arg, ast.Constant) or not isinstance(first_arg.value, str):
            continue

        sql = first_arg.value
        table = _extract_table_name(sql)
        if table is not None:
            violations.append(
                f"Line {node.lineno}: Direct conn.execute() on {repr(table)}: "
                f"{' '.join(sql.split()[:6])}..."
            )

    return violations


def main():
    print("Running CI gate: check_direct_db_writes...")
    total_violations = 0

    for py_file in SCRIPTS_DIR.rglob("*.py"):
        rel_path = str(py_file.relative_to(ROOT))
        if rel_path not in (TARGET_FILE,) and rel_path not in REPOSITORY_SERVICES:
            continue

        violations = check_file(py_file)
        is_service = rel_path in REPOSITORY_SERVICES

        if violations:
            if is_service:
                print(f"\n  OK (allowed): Direct writes in repository service {rel_path}")
                continue

            total_violations += len(violations)
            print(f"\nX DIRECT DB WRITES in {rel_path}:")
            for v in violations:
                print(f"   {v}")

    if total_violations > 0:
        print(f"\nX CI GATE FAILED: {total_violations} direct DB writes into constrained tables outside repository services.")
        print("   Action: Use repository service functions instead of raw SQL for constrained tables.")
        sys.exit(1)
    else:
        print("OK CI GATE PASSED: No unauthorized direct DB writes.")
        sys.exit(0)


if __name__ == "__main__":
    main()

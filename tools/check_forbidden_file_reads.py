#!/usr/bin/env python3
"""CI Gate: Forbid reading legacy authority files as production inputs.

This prevents stages from relying on file-based state instead of the unified ledger.
See ADR-001: Orchestrator Authority.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"

FORBIDDEN_FILES = {
    "state.json",
    "gates.json",
    "media_plan.json",
    "beat_timing_map.json",
    "manifest.json",
}

# Allowlist for files that are explicitly permitted to read these 
# (e.g., migration scripts, legacy adapters, transitional scripts)
ALLOWLIST = {
    "scripts/migrate_legacy.py",  # Migration script
    "scripts/build_manifest.py",  # Transitional manifest builder
    "scripts/assemble.py",  # Transitional assembly script (reads manifest, will be updated in Sprint F)
    "scripts/qa_media.py",  # Transitional QA script
    "scripts/import_legacy_production.py",  # Legacy importer
}


def check_file(filepath: Path) -> list[str]:
    """Check a Python file for forbidden legacy file reads."""
    violations = []
    try:
        tree = ast.parse(filepath.read_text(), filename=str(filepath))
    except SyntaxError:
        return violations  # Skip files with syntax errors (let linter handle them)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            
            # Check open(".../state.json")
            if isinstance(func, ast.Name) and func.id == "open":
                if node.args and isinstance(node.args[0], ast.Constant):
                    filename = str(node.args[0].value)
                    if any(f in filename for f in FORBIDDEN_FILES):
                        violations.append(f"Line {node.lineno}: Forbidden open() of legacy file '{filename}'")
            
            # Check Path(...).read_text() or Path(...).read_bytes()
            elif isinstance(func, ast.Attribute) and func.attr in ("read_text", "read_bytes"):
                if isinstance(func.value, ast.Call) and isinstance(func.value.func, ast.Name) and func.value.func.id == "Path":
                    if func.value.args and isinstance(func.value.args[0], ast.Constant):
                        filename = str(func.value.args[0].value)
                        if any(f in filename for f in FORBIDDEN_FILES):
                            violations.append(f"Line {node.lineno}: Forbidden Path().read_text()/read_bytes() of legacy file '{filename}'")
            
            # Check json.loads(Path(...).read_text())
            elif isinstance(func, ast.Attribute) and func.attr == "loads":
                if node.args and isinstance(node.args[0], ast.Call):
                    inner_call = node.args[0]
                    if isinstance(inner_call.func, ast.Attribute) and inner_call.func.attr in ("read_text", "read_bytes"):
                        if isinstance(inner_call.func.value, ast.Call) and isinstance(inner_call.func.value.func, ast.Name) and inner_call.func.value.func.id == "Path":
                            if inner_call.func.value.args and isinstance(inner_call.func.value.args[0], ast.Constant):
                                filename = str(inner_call.func.value.args[0].value)
                                if any(f in filename for f in FORBIDDEN_FILES):
                                    violations.append(f"Line {node.lineno}: Forbidden json.loads(Path().read_text()) of legacy file '{filename}'")

    return violations


def main():
    print("Running CI gate: check_forbidden_file_reads...")
    total_violations = 0
    
    for py_file in SCRIPTS_DIR.rglob("*.py"):
        rel_path = str(py_file.relative_to(ROOT))
        if rel_path in ALLOWLIST:
            continue
            
        violations = check_file(py_file)
        if violations:
            total_violations += len(violations)
            print(f"\n❌ FORBIDDEN FILE READ in {rel_path}:")
            for v in violations:
                print(f"   {v}")
                
    if total_violations > 0:
        print(f"\n❌ CI GATE FAILED: {total_violations} forbidden legacy file reads found.")
        print("   Action: Use DB queries via production_db or clip_db instead of reading legacy JSON files.")
        print("   If this is a legitimate migration/legacy adapter, add it to the ALLOWLIST in this script.")
        sys.exit(1)
    else:
        print("✅ CI GATE PASSED: No forbidden legacy file reads found in service code.")
        sys.exit(0)


if __name__ == "__main__":
    main()

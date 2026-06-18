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
    "script.json",
    "storyboard.json",
    "research_brief.json",
    "production_storyboard.json",
}

# Allowlist for files that are explicitly permitted to read these
# (e.g., migration scripts, legacy adapters, transitional scripts)
ALLOWLIST = {
    "scripts/migrate_legacy.py",  # Migration script
    "scripts/build_manifest.py",  # Transitional manifest builder
    "scripts/assemble.py",  # Transitional assembly script (reads manifest, will be updated in Sprint F)
    "scripts/qa_media.py",  # Transitional QA script
    "scripts/import_legacy_production.py",  # Legacy importer
    "scripts/run_episode.py",  # Legacy file-based entry point (not on DB-native stage graph)
    "scripts/slice_continuous_lipsync.py",  # Legacy slicer (slice_hero_from_master; not DB-native)
    "scripts/reconcile_duration.py",  # Legacy reconciler (not DB-native)
    "scripts/reconcile_production_storyboard.py",  # Legacy reconciler (not DB-native)
    "scripts/review_media_plan.py",  # Legacy reviewer (not DB-native)
    "scripts/upscale_media.py",  # Legacy upscale (not DB-native)
    "scripts/render_graphics.py",  # Legacy graphics renderer (not DB-native)
    "scripts/audio_timing.py",  # Takes script.json as CLI arg (legacy CLI, not DB-native invoker)
    "scripts/generate_hooks.py",  # Takes script.json as CLI arg (legacy CLI)
    "scripts/migrate_legacy.py",
    "scripts/insert_emphasis_pauses.py",  # Legacy emphasis-pause tool (not DB-native)
}


def _extract_string_constants(node) -> list[str]:
    """Recursively extract string constants from a path-expression node.

    Catches dynamic path construction that the old literal-only gate missed:
      - Path(project_dir / "media_plan.json").read_text()
      - Path(f"{project_dir}/media_plan.json").read_text()
      - json.loads((base / "script.json").read_text())
    Returns all string-literal fragments found in the expression.
    """
    strings = []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        strings.append(node.value)
    elif isinstance(node, ast.BinOp):
        strings.extend(_extract_string_constants(node.left))
        strings.extend(_extract_string_constants(node.right))
    elif isinstance(node, ast.JoinedStr):
        for val in node.values:
            if isinstance(val, ast.Constant) and isinstance(val.value, str):
                strings.append(val.value)
    elif isinstance(node, ast.FormattedValue):
        # f-string expression part — skip (not a constant)
        pass
    elif isinstance(node, ast.Call):
        # Path(...) or open(...) — inspect args
        for arg in node.args:
            strings.extend(_extract_string_constants(arg))
    elif isinstance(node, ast.Attribute):
        strings.extend(_extract_string_constants(node.value))
    return strings


def _check_forbidden_in_strings(strings: list[str], lineno: int, context: str) -> list[str]:
    """Check if any string constant contains a forbidden filename."""
    violations = []
    for s in strings:
        for forbidden in FORBIDDEN_FILES:
            if forbidden in s:
                violations.append(
                    f"Line {lineno}: Forbidden {context} of legacy authority file "
                    f"'{forbidden}' (found in path expression)")
    return violations


def check_file(filepath: Path) -> list[str]:
    """Check a Python file for forbidden legacy file reads.

    Detects both literal-string reads and dynamically-constructed paths
    (Path division, f-strings, concatenation) that resolve to a forbidden
    authority filename.
    """
    violations = []
    try:
        tree = ast.parse(filepath.read_text(), filename=str(filepath))
    except SyntaxError:
        return violations  # Skip files with syntax errors (let linter handle them)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func

            # open(".../state.json") — resolve path arg dynamically
            if isinstance(func, ast.Name) and func.id == "open":
                if node.args:
                    strings = _extract_string_constants(node.args[0])
                    violations.extend(
                        _check_forbidden_in_strings(strings, node.lineno, "open()"))

            # Path(...).read_text() / .read_bytes() — resolve the Path arg
            elif isinstance(func, ast.Attribute) and func.attr in ("read_text", "read_bytes"):
                strings = _extract_string_constants(func.value)
                violations.extend(
                    _check_forbidden_in_strings(strings, node.lineno, "read_text/read_bytes"))

            # json.loads(...read_text()...) — resolve the inner path
            elif isinstance(func, ast.Attribute) and func.attr == "loads":
                if node.args:
                    strings = _extract_string_constants(node.args[0])
                    violations.extend(
                        _check_forbidden_in_strings(strings, node.lineno, "json.loads(read_text)"))

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

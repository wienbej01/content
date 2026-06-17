#!/usr/bin/env python3
"""CI Gate: Forbid 'beat_id' as a primary dictionary lookup key in service code.

This prevents the overloaded 'beat_id' from being used as a relational key,
enforcing the identity split (creative_beat_id/source_beat_id, timeline_span_id, render_unit_id).
See ADR-002: Identity Split.

Usage:
    python3 tools/check_forbidden_beat_id_lookups.py
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"

# Allowlist for files that are explicitly permitted to use 'beat_id' during migration.
# These are legacy adapters or transitional scripts that will be refactored or deleted.
# TODO(ALN-B1): Remove from allowlist as each script is migrated to split IDs.
ALLOWLIST = {
    "scripts/compile_media_prompts.py",
    "scripts/reconcile_duration.py",
    "scripts/build_manifest.py",
    "scripts/assemble.py",
    "scripts/qa_media.py",
    "scripts/storyboard.py",
    "scripts/repair_storyboard_beats.py",
    "scripts/review_storyboard.py",
    "scripts/review_production_storyboard.py",
    "scripts/hero_grouping.py",  # Internal group planning, uses beat_id for member identity
    "scripts/production_repo.py",
    "scripts/slice_continuous_lipsync.py",
    "scripts/insert_emphasis_pauses.py",
    "scripts/generate_media.py",
    "scripts/upscale_media.py",
    "scripts/audio_timing.py",
    "scripts/budget.py",
    "scripts/tts_service.py",
    "scripts/production_storyboard.py",
    "scripts/render_graphics.py",
    "scripts/review_media_plan.py",
    "scripts/reconcile_production_storyboard.py",
    "scripts/qa_final.py",
    "scripts/build_quality_report.py",
    "scripts/direct_storyboard.py",
    "scripts/clip_db.py",
}


def check_file(filepath: Path) -> list[str]:
    """Check a Python file for forbidden 'beat_id' dictionary lookups."""
    violations = []
    try:
        tree = ast.parse(filepath.read_text(), filename=str(filepath))
    except SyntaxError:
        return violations  # Skip files with syntax errors (let linter handle them)

    for node in ast.walk(tree):
        # Check for dict subscript: dict["beat_id"] or dict['beat_id']
        if isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Constant) and node.slice.value == "beat_id":
                violations.append(f"Line {node.lineno}: Forbidden dictionary lookup ['beat_id']")
        
        # Check for dict.get("beat_id")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
                if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "beat_id":
                    violations.append(f"Line {node.lineno}: Forbidden .get('beat_id')")

    return violations


def main():
    print("Running CI gate: check_forbidden_beat_id_lookups...")
    total_violations = 0
    
    for py_file in SCRIPTS_DIR.rglob("*.py"):
        rel_path = str(py_file.relative_to(ROOT))
        if rel_path in ALLOWLIST:
            continue
            
        violations = check_file(py_file)
        if violations:
            total_violations += len(violations)
            print(f"\n❌ FORBIDDEN 'beat_id' LOOKUP in {rel_path}:")
            for v in violations:
                print(f"   {v}")
                
    if total_violations > 0:
        print(f"\n❌ CI GATE FAILED: {total_violations} forbidden 'beat_id' lookups found.")
        print("   Action: Use 'render_unit_id', 'timeline_span_id', or 'source_beat_id' instead.")
        print("   If this is a legacy transitional file, add it to the ALLOWLIST in this script.")
        sys.exit(1)
    else:
        print("✅ CI GATE PASSED: No forbidden 'beat_id' lookups found in service code.")
        sys.exit(0)


if __name__ == "__main__":
    main()

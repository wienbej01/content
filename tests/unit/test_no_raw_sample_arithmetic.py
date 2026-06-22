"""Guard test: no raw sample-rate arithmetic outside timeline_utils.py.

All ms→samples and seconds→samples conversions must go through
timeline_utils.ms_to_samples() or timeline_utils.samples_to_ms().

This test scans all .py files in scripts/ for raw patterns like:
  * MASTER_SAMPLE_RATE
  * CANONICAL_SAMPLE_RATE  
  * 48000

If a new file needs a conversion, it must import and use ms_to_samples().
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = ROOT / "scripts"
TIMELINE_UTILS = SCRIPTS_DIR / "timeline_utils.py"


def _find_raw_arithemtic(filepath: Path) -> list[str]:
    """Scan a single file for raw sample-rate arithmetic patterns."""
    violations = []
    text = filepath.read_text()

    # Pattern 1: * MASTER_SAMPLE_RATE (must go through ms_to_samples)
    # Find occurrences not in import statements or constants
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        # Skip comments and imports
        if stripped.startswith("#") or stripped.startswith("import") or stripped.startswith("from"):
            continue

        # Check for raw * MASTER_SAMPLE_RATE or * CANONICAL_SAMPLE_RATE in expressions
        if "* MASTER_SAMPLE_RATE" in stripped or "* CANONICAL_SAMPLE_RATE" in stripped:
            violations.append(f"  {filepath.name}:{lineno}: {stripped.strip()}")

        # Check for raw * 48000 (but only multiplications, not in string literals or comments)
        if "* 48000" in stripped:
            violations.append(f"  {filepath.name}:{lineno}: {stripped.strip()}")

    return violations


def test_no_raw_master_sample_rate_outside_timeline_utils():
    """No raw * MASTER_SAMPLE_RATE arithmetic outside timeline_utils.py.

    All ms↔samples conversions must go through ms_to_samples() / samples_to_ms().
    """
    all_violations = []
    for py_file in sorted(SCRIPTS_DIR.glob("*.py")):
        if py_file.resolve() == TIMELINE_UTILS.resolve():
            continue  # canonical definition site — allowed
        violations = _find_raw_arithemtic(py_file)
        if violations:
            all_violations.extend(violations)

    if all_violations:
        msg = (
            "Raw sample-rate arithmetic detected outside timeline_utils.py.\n"
            "All ms↔samples conversions must use ms_to_samples() or samples_to_ms().\n"
            "Violations:\n" + "\n".join(all_violations)
        )
        assert False, msg


def test_guard_catches_violation():
    """Verify the guard test catches violations (temporarily add one)."""
    # Temporarily create a file with a known violation
    temp_file = SCRIPTS_DIR / "_temp_violation_check.py"
    try:
        temp_file.write_text("# temp violation check\nx = ms * 48000\n")
        violations = _find_raw_arithemtic(temp_file)
        assert len(violations) == 1, f"Expected 1 violation, got {len(violations)}: {violations}"
        assert "* 48000" in violations[0]
    finally:
        if temp_file.exists():
            temp_file.unlink()

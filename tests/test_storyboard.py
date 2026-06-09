#!/usr/bin/env python3
"""tests/test_storyboard.py — Property tests for storyboard.py."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SB = ROOT / "scripts" / "storyboard.py"
SAMPLE = ROOT / "scripts" / "generated" / "james_growth_system_teaser_01.json"


def run_sb(script_dict=None, args=None, script_path=None):
    if script_path is None:
        td = tempfile.mkdtemp()
        script_path = Path(td) / "script.json"
        with open(script_path, "w") as f:
            json.dump(script_dict, f)
    cmd = [sys.executable, str(SB), str(script_path)] + (args or [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def test_valid_script_generates():
    code, out, err = run_sb(script_path=SAMPLE, args=["--dry-run"])
    assert code == 0, f"FAIL: {err}"
    assert "DRY RUN" in out
    print("  ✓ Valid script generates storyboard (dry-run)")


def test_missing_segments_fails():
    code, out, err = run_sb({"project_id": "t"})
    assert code == 1
    assert "segments" in err
    print("  ✓ Missing segments fails")


def test_missing_text_fails():
    code, out, err = run_sb({"project_id": "t", "segments": [{"id": "s", "audio_mode": "generated_tts"}]})
    assert code == 1
    assert "text" in err
    print("  ✓ Missing text fails (for non-silent)")


def test_dry_run_writes_nothing():
    with tempfile.TemporaryDirectory() as td:
        out_path = Path(td) / "out.json"
        code, out, err = run_sb(script_path=SAMPLE, args=["--dry-run", "--output", str(out_path)])
        assert code == 0
        assert not out_path.exists()
        print("  ✓ Dry-run writes no file")


def test_validate_only():
    code, out, err = run_sb(script_path=SAMPLE, args=["--validate-only"])
    assert code == 0
    assert "VALID" in out
    print("  ✓ --validate-only works")


def test_output_has_required_fields():
    with tempfile.TemporaryDirectory() as td:
        out_path = Path(td) / "sb.json"
        code, out, err = run_sb(script_path=SAMPLE, args=["--output", str(out_path)])
        assert code == 0, f"FAIL: {err}"
        sb = json.load(open(out_path))
        assert "project_id" in sb
        assert "beats" in sb and len(sb["beats"]) > 0
        b = sb["beats"][0]
        for key in ("beat_id", "scene_type", "a_roll_or_b_roll", "james_presence",
                    "narration_text", "location_id", "audio_source", "crop_safety",
                    "text_policy", "camera", "lighting"):
            assert key in b, f"missing field: {key}"
        print("  ✓ Output has all required fields")


def test_includes_james_presence():
    with tempfile.TemporaryDirectory() as td:
        out_path = Path(td) / "sb.json"
        run_sb(script_path=SAMPLE, args=["--output", str(out_path)])
        sb = json.load(open(out_path))
        present = [b for b in sb["beats"] if b["james_presence"] != "absent"]
        assert len(present) > 0, "FAIL: no James-present beats"
        print("  ✓ Includes James-present beats")


def test_not_all_broll():
    with tempfile.TemporaryDirectory() as td:
        out_path = Path(td) / "sb.json"
        run_sb(script_path=SAMPLE, args=["--output", str(out_path)])
        sb = json.load(open(out_path))
        a_roll = [b for b in sb["beats"] if b["a_roll_or_b_roll"] == "a_roll"]
        assert len(a_roll) > 0, "FAIL: all-b-roll storyboard"
        print("  ✓ Not all-b-roll (has A-roll beats)")


def test_json_valid():
    with tempfile.TemporaryDirectory() as td:
        out_path = Path(td) / "sb.json"
        run_sb(script_path=SAMPLE, args=["--output", str(out_path)])
        sb = json.load(open(out_path))
        assert isinstance(sb, dict)
        print("  ✓ Output is valid JSON")


def main():
    print("M5.1 Storyboard Tests")
    tests = [test_valid_script_generates, test_missing_segments_fails, test_missing_text_fails,
             test_dry_run_writes_nothing, test_validate_only, test_output_has_required_fields,
             test_includes_james_presence, test_not_all_broll, test_json_valid]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {t.__name__}: {e}")
            failed += 1
    print(f"\n{'PASSED' if failed == 0 else 'FAILED'}: {passed}/{passed+failed}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()

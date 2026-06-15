#!/usr/bin/env python3
"""tests/test_review_script_prefilter.py — D1/R4 stutter pre-filter tests."""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _load():
    spec = importlib.util.spec_from_file_location("review_script", ROOT / "scripts" / "review_script.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_repetition_detected_blocks():
    """A script with repeated phrases triggers the pre-filter (no LLM call)."""
    rs = _load()
    repeated = "Read it. Sketch it. Explain it aloud. " * 10
    script = {"segments": [{"text": repeated, "id": "s1"}], "project_id": "test"}
    is_blocking, reason = rs.detect_repetition(script)
    assert is_blocking, f"expected blocking, got {reason}"
    assert "repetition" in reason.lower() or "repeat" in reason.lower()
    print(f"  ✓ repetition detected: {reason[:60]}")


def test_clean_script_passes_prefilter():
    """A clean script (flagship_001) passes the pre-filter."""
    rs = _load()
    script = json.load(open(ROOT / "scripts/generated/flagship_001_learn_half_time.json"))
    is_blocking, reason = rs.detect_repetition(script)
    assert not is_blocking, f"false positive: {reason}"
    print("  ✓ clean flagship script passes pre-filter")


def test_adjacent_duplicate_sentence_blocks():
    """Verbatim sentence repeat within a 5-sentence window triggers the filter."""
    rs = _load()
    text = ("The system works by encoding multiple modalities. "
            "First you read the material carefully. "
            "Then you sketch the concept from memory. "
            "The system works by encoding multiple modalities. "
            "Finally you explain it to yourself aloud.")
    script = {"segments": [{"text": text, "id": "s1"}], "project_id": "test"}
    is_blocking, reason = rs.detect_repetition(script)
    assert is_blocking, f"expected adjacent duplicate detection, got {reason}"
    assert "verbatim" in reason.lower() or "repeat" in reason.lower()
    print(f"  ✓ adjacent duplicate detected: {reason[:60]}")

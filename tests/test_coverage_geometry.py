"""Tests for PTC-06: coverage slot geometry validation (boundary continuity)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from production_storyboard import validate_coverage_geometry


def _beat(start, end, coverage):
    """Minimal beat with coverage_plan."""
    return {
        "beat_id": "B001",
        "audio_start_sec": start,
        "audio_end_sec": end,
        "audio_duration_sec": round(end - start, 3),
        "coverage_plan": coverage,
    }


def _slot(start, end, slot_id="s0", asset_type="generated_video"):
    return {
        "slot_id": slot_id,
        "asset_role": "primary",
        "asset_type": asset_type,
        "required_start_sec": start,
        "required_end_sec": end,
        "required_duration_sec": round(end - start, 3),
    }


def test_contiguous_slots_pass():
    """Slots [0-5, 5-10] for a 10s beat → pass."""
    beat = _beat(0, 10, [_slot(0, 5, "s0"), _slot(5, 10, "s1")])
    assert validate_coverage_geometry(beat) == []


def test_gap_fails():
    """Slots [0-4, 5-10] (1s gap) → fail."""
    beat = _beat(0, 10, [_slot(0, 4, "s0"), _slot(5, 10, "s1")])
    errors = validate_coverage_geometry(beat)
    assert any("gap" in e.lower() for e in errors)


def test_overlap_fails():
    """Slots [0-6, 5-10] (1s overlap) → fail."""
    beat = _beat(0, 10, [_slot(0, 6, "s0"), _slot(5, 10, "s1")])
    errors = validate_coverage_geometry(beat)
    assert any("overlap" in e.lower() for e in errors)


def test_first_slot_must_start_at_beat_start():
    """Slots [1-10] for beat starting at 0 → fail."""
    beat = _beat(0, 10, [_slot(1, 10, "s0")])
    errors = validate_coverage_geometry(beat)
    assert any("first slot" in e.lower() for e in errors)


def test_last_slot_must_end_at_beat_end():
    """Slots [0-9] for beat ending at 10 → fail."""
    beat = _beat(0, 10, [_slot(0, 9, "s0")])
    errors = validate_coverage_geometry(beat)
    assert any("last slot" in e.lower() for e in errors)


def test_equal_duration_but_shifted_fails():
    """Slots [1-6, 6-11] (sum=10 but shifted) for 0-10 beat → fail."""
    beat = _beat(0, 10, [_slot(1, 6, "s0"), _slot(6, 11, "s1")])
    errors = validate_coverage_geometry(beat)
    assert len(errors) > 0
    # Must catch the start misalignment and/or end misalignment
    assert any("first slot" in e.lower() or "last slot" in e.lower() for e in errors)


def test_duration_mismatch_fails():
    """Slot with required_duration_sec != end-start → fail."""
    slot = _slot(0, 10, "s0")
    slot["required_duration_sec"] = 8.0  # wrong
    beat = _beat(0, 10, [slot])
    errors = validate_coverage_geometry(beat)
    assert any("required_duration_sec" in e for e in errors)


def test_duplicate_slot_id_fails():
    """Two slots with same slot_id → fail."""
    beat = _beat(0, 10, [_slot(0, 5, "s0"), _slot(5, 10, "s0")])
    errors = validate_coverage_geometry(beat)
    assert any("duplicate" in e.lower() for e in errors)


def test_reversed_boundaries_fails():
    """Slot with end < start → fail."""
    slot = {"slot_id": "s0", "asset_role": "primary", "asset_type": "generated_video",
            "required_start_sec": 10, "required_end_sec": 5, "required_duration_sec": 5}
    beat = _beat(0, 10, [slot])
    errors = validate_coverage_geometry(beat)
    assert any("reversed" in e.lower() for e in errors)


def test_audio_only_slot_fails():
    """Slot with no visual asset_type → fail."""
    slot = _slot(0, 10, "s0")
    del slot["asset_type"]
    beat = _beat(0, 10, [slot])
    errors = validate_coverage_geometry(beat)
    assert any("asset_type" in e.lower() for e in errors)

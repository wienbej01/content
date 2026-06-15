"""Tests for production storyboard schema validation (PST-01)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from production_storyboard import validate_production_storyboard


def _make_beat(beat_id, start, end, source="B001", model_max=None, coverage=None,
               narration=None, split_index=None, split_total=None):
    """Helper to build a minimal valid beat."""
    dur = round(end - start, 3)
    beat = {
        "beat_id": beat_id,
        "source_beat_id": source,
        "audio_start_sec": start,
        "audio_end_sec": end,
        "audio_duration_sec": dur,
        "treatment": "broll",
        "shot_type": "broll_environment",
        "segment_id": "001_test",
        "coverage_plan": coverage if coverage is not None else [
            {"asset_role": "primary", "asset_type": "generated_video",
             "required_start_sec": start, "required_end_sec": end,
             "required_duration_sec": dur}
        ],
    }
    if model_max is not None:
        beat["model_max_duration_sec"] = model_max
    if narration is not None:
        beat["narration_text"] = narration
    if split_index is not None:
        beat["split_index"] = split_index
    if split_total is not None:
        beat["split_total"] = split_total
    return beat


def _make_storyboard(beats, master=None):
    """Wrap beats in a valid top-level storyboard."""
    if master is None:
        master = beats[-1]["audio_end_sec"] if beats else 0
    return {
        "schema_version": "1.0",
        "project_id": "test",
        "creative_storyboard_sha256": "a" * 64,
        "timing_map_sha256": "b" * 64,
        "master_audio_duration_sec": master,
        "total_beats": len(beats),
        "created_at": "2026-06-14T00:00:00Z",
        "beats": beats,
    }


def test_valid_schema_passes():
    """A minimal valid 3-beat production storyboard validates with no errors."""
    beats = [
        _make_beat("B001", 0.0, 5.0, source="B001"),
        _make_beat("B002", 5.0, 10.0, source="B002"),
        _make_beat("B003", 10.0, 15.0, source="B003"),
    ]
    errors = validate_production_storyboard(_make_storyboard(beats))
    assert errors == []


def test_gap_rejected():
    """0.1s gap between beats fails with gap error."""
    beats = [
        _make_beat("B001", 0.0, 5.0, source="B001"),
        _make_beat("B002", 5.1, 10.0, source="B002"),  # 0.1s gap
        _make_beat("B003", 10.0, 15.0, source="B003"),
    ]
    errors = validate_production_storyboard(_make_storyboard(beats))
    assert any("gap" in e.lower() or "Gap" in e for e in errors)


def test_overlap_rejected():
    """Beat n+1 starts before beat n ends → overlap error."""
    beats = [
        _make_beat("B001", 0.0, 5.0, source="B001"),
        _make_beat("B002", 4.5, 10.0, source="B002"),  # overlap
        _make_beat("B003", 10.0, 15.0, source="B003"),
    ]
    errors = validate_production_storyboard(_make_storyboard(beats))
    assert any("overlap" in e.lower() or "Overlap" in e for e in errors)


def test_model_limit_exceeded_rejected():
    """Beat with audio_duration_sec=12.0 and model_max=10.0 fails."""
    beats = [
        _make_beat("B001", 0.0, 12.0, source="B001", model_max=10.0),
        _make_beat("B002", 12.0, 15.0, source="B002"),
    ]
    errors = validate_production_storyboard(_make_storyboard(beats))
    assert any("model_max" in e or "exceeds" in e for e in errors)


def test_missing_coverage_rejected():
    """Empty coverage_plan fails."""
    beats = [
        _make_beat("B001", 0.0, 5.0, source="B001", coverage=[]),
        _make_beat("B002", 5.0, 10.0, source="B002"),
    ]
    errors = validate_production_storyboard(_make_storyboard(beats))
    assert any("coverage" in e.lower() for e in errors)


def test_missing_provenance_rejected():
    """Missing source_beat_id fails."""
    beats = [
        _make_beat("B001", 0.0, 5.0, source="B001"),
        _make_beat("B002", 5.0, 10.0, source="B002"),
    ]
    beats[0]["source_beat_id"] = ""
    errors = validate_production_storyboard(_make_storyboard(beats))
    assert any("source_beat_id" in e for e in errors)


def test_incomplete_coverage_rejected():
    """Coverage_plan covers only 5s of a 10s beat → fails."""
    partial_coverage = [
        {"asset_role": "primary", "asset_type": "generated_video",
         "required_start_sec": 0.0, "required_end_sec": 5.0,
         "required_duration_sec": 5.0}
    ]
    beats = [
        _make_beat("B001", 0.0, 10.0, source="B001", coverage=partial_coverage),
        _make_beat("B002", 10.0, 15.0, source="B002"),
    ]
    errors = validate_production_storyboard(_make_storyboard(beats))
    assert any("last slot" in e.lower() or ("coverage" in e.lower() and "covers" in e.lower()) for e in errors)


def test_split_integrity_checked():
    """Split beat with split_total=2 but only one sibling present fails."""
    beats = [
        _make_beat("B001a", 0.0, 5.0, source="B001", split_index=0, split_total=2),
        # B001b (split_index=1) is missing
        _make_beat("B002", 5.0, 10.0, source="B002"),
    ]
    errors = validate_production_storyboard(_make_storyboard(beats))
    assert any("split" in e.lower() or "Split" in e for e in errors)


def test_narration_text_preserved():
    """Narration_text with zero audio_duration fails."""
    beats = [
        _make_beat("B001", 0.0, 5.0, source="B001"),
    ]
    beats[0]["narration_text"] = "Some text here"
    beats[0]["audio_duration_sec"] = 0
    beats[0]["audio_end_sec"] = 0.0
    beats[0]["audio_start_sec"] = 0.0
    # Fix storyboard master to match
    sb = _make_storyboard(beats, master=0.0)
    errors = validate_production_storyboard(sb)
    assert any("narration_text" in e for e in errors)


def test_timeline_end_must_match_master():
    """Last beat ending at 140.0s when master is 146.599s fails."""
    beats = [
        _make_beat("B001", 0.0, 5.0, source="B001"),
        _make_beat("B002", 5.0, 10.0, source="B002"),
        _make_beat("B003", 10.0, 140.0, source="B003"),
    ]
    sb = _make_storyboard(beats, master=146.599)
    errors = validate_production_storyboard(sb)
    assert any("timeline end" in e.lower() or "Timeline end" in e for e in errors)

#!/usr/bin/env python3
"""TKT-601 tests for EDL override schema + constraint validation."""
import json
import tempfile
from pathlib import Path

import pytest
import yaml

from scripts.edl import parse_edl, validate_edl, compute_emotional_holds, apply_edl_overrides


@pytest.fixture
def sample_storyboard():
    return {
        "project_id": "test_edl",
        "video_type": "explainer",
        "beats": [
            {"beat_id": "B001", "narrative_function": "hook", "shot_type": "hero_lipsync", "est_duration_sec": 5.0, "act": 1},
            {"beat_id": "B002", "narrative_function": "thesis_close", "shot_type": "hero_lipsync", "est_duration_sec": 6.0, "act": 2},
            {"beat_id": "B003", "narrative_function": "evidence", "shot_type": "broll_archival", "est_duration_sec": 5.0, "act": 3},
        ],
    }


def test_parse_edl_yaml(tmp_path):
    """Parse a YAML EDL file."""
    edl_path = tmp_path / "edl.yaml"
    edl_path.write_text(yaml.dump({
        "overrides": [
            {"beat_id": "B001", "trim_end_sec": 0.5},
            {"beat_id": "B002", "music_duck_db": -12.0},
        ]
    }))
    overrides = parse_edl(edl_path)
    assert len(overrides) == 2
    assert overrides[0]["beat_id"] == "B001"
    assert overrides[0]["trim_end_sec"] == 0.5


def test_parse_edl_json(tmp_path):
    """Parse a JSON EDL file."""
    edl_path = tmp_path / "edl.json"
    edl_path.write_text(json.dumps({
        "overrides": [{"beat_id": "B003", "trim_start_sec": 0.3}]
    }))
    overrides = parse_edl(edl_path)
    assert len(overrides) == 1
    assert overrides[0]["trim_start_sec"] == 0.3


def test_validate_edl_valid(sample_storyboard):
    """Valid EDL passes validation."""
    overrides = [
        {"beat_id": "B001", "trim_start_sec": 0.0, "trim_end_sec": 0.5, "reorder_after": None, "music_duck_db": 0.0},
    ]
    valid, errors = validate_edl(overrides, sample_storyboard)
    assert len(errors) == 0


def test_validate_edl_trims_too_aggressive(sample_storyboard):
    """EDL that pushes beat below BEAT_MIN_SEC is rejected."""
    overrides = [
        {"beat_id": "B001", "trim_start_sec": 3.0, "trim_end_sec": 2.0, "reorder_after": None, "music_duck_db": 0.0},
    ]
    valid, errors = validate_edl(overrides, sample_storyboard)
    assert len(errors) > 0
    assert any("minimum" in e.lower() or "below" in e.lower() for e in errors)


def test_validate_edl_missing_beat(sample_storyboard):
    """EDL referencing non-existent beat is rejected."""
    overrides = [
        {"beat_id": "B999", "trim_end_sec": 0.5, "trim_start_sec": 0.0, "reorder_after": None, "music_duck_db": 0.0},
    ]
    valid, errors = validate_edl(overrides, sample_storyboard)
    assert any("not found" in e for e in errors)


def test_compute_emotional_holds(sample_storyboard):
    """Emotional holds computed for thesis_close beats."""
    holds = compute_emotional_holds(sample_storyboard)
    assert "B002" in holds  # thesis_close
    assert "B001" not in holds  # hook


def test_apply_edl_overrides():
    """EDL overrides applied to assembly segments."""
    segments = [
        {"beat_id": "B001", "est_duration_sec": 5.0},
        {"beat_id": "B002", "est_duration_sec": 6.0},
    ]
    overrides = [
        {"beat_id": "B001", "trim_start_sec": 0.0, "trim_end_sec": 0.5, "reorder_after": None, "music_duck_db": -12.0},
    ]
    result = apply_edl_overrides(segments, overrides)
    assert "trim" in result[0]
    assert result[0]["music_duck_db"] == -12.0
    assert "trim" not in result[1]


def test_parse_edl_missing_beat_id(tmp_path):
    """EDL without beat_id raises ValueError."""
    edl_path = tmp_path / "bad.yaml"
    edl_path.write_text(yaml.dump({"overrides": [{"trim_end_sec": 0.5}]}))
    with pytest.raises(ValueError, match="beat_id"):
        parse_edl(edl_path)

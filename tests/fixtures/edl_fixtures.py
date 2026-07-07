#!/usr/bin/env python3
"""Deterministic EDL override fixtures for TKT-005.

Generates three fixture types for testing edit-decision-list override validation:
1. Valid EDL override — trim ±0.5s on non-hero beats, no constraint violation.
2. Invalid EDL override — trim that pushes a beat below BEAT_MIN_SEC or violates shot-mix bands.
3. Valid reorder override — swap two adjacent non-hero beats.

All outputs are JSON configs; no external dependencies.
"""
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Fixture data
# ---------------------------------------------------------------------------

SAMPLE_STORYBOARD = {
    "project_id": "test_edl_fixtures",
    "video_type": "explainer",
    "schema_version": "2.0",
    "beats": [
        {"beat_id": "B001", "order": 1, "act": 1, "shot_type": "hero_lipsync", "est_duration_sec": 5.0,
         "narrative_function": "hook", "visual_brief": "James to camera"},
        {"beat_id": "B002", "order": 2, "act": 1, "shot_type": "broll_environment", "est_duration_sec": 5.0,
         "narrative_function": "metaphorical_b_roll", "visual_brief": "City skyline at dawn"},
        {"beat_id": "B003", "order": 3, "act": 2, "shot_type": "hero_lipsync", "est_duration_sec": 6.0,
         "narrative_function": "thesis", "visual_brief": "James delivers framework"},
        {"beat_id": "B004", "order": 4, "act": 2, "shot_type": "graphic_progressive", "est_duration_sec": 4.0,
         "narrative_function": "framework_reveal", "visual_brief": "Progressive framework graphic"},
        {"beat_id": "B005", "order": 5, "act": 3, "shot_type": "broll_archival", "est_duration_sec": 5.0,
         "narrative_function": "evidence", "visual_brief": "Archival footage of researcher"},
        {"beat_id": "B006", "order": 6, "act": 4, "shot_type": "hero_lipsync", "est_duration_sec": 5.0,
         "narrative_function": "thesis_close", "visual_brief": "James closing argument"},
    ],
}


# ---------------------------------------------------------------------------
# Fixture 1: Valid EDL override
# ---------------------------------------------------------------------------

def generate_valid_edl_override(tmp_path: Path) -> dict[str, Any]:
    """Generate a valid EDL override that trims non-hero beats within acceptable bounds."""
    override = {
        "fixture_type": "valid_edl",
        "description": "Valid EDL: trim ±0.5s on non-hero beats, no reorder, no violation",
        "is_valid": True,
        "overrides": [
            {
                "beat_id": "B002",
                "trim_start_sec": 0.0,
                "trim_end_sec": 0.5,
                "reorder_after": None,
                "music_duck_db": -12.0,
            },
            {
                "beat_id": "B005",
                "trim_start_sec": 0.3,
                "trim_end_sec": 0.0,
                "reorder_after": None,
                "music_duck_db": -10.0,
            },
        ],
    }
    tmp_path.mkdir(exist_ok=True, parents=True)
    out = tmp_path / "edl_valid.json"
    out.write_text(json.dumps(override, indent=2, sort_keys=True))
    return {
        "path": str(out),
        "override": override,
        "is_valid": True,
        "fixture_type": "valid_edl",
        "storyboard": SAMPLE_STORYBOARD,
    }


# ---------------------------------------------------------------------------
# Fixture 2: Invalid EDL override
# ---------------------------------------------------------------------------

def generate_invalid_edl_override(tmp_path: Path) -> dict[str, Any]:
    """Generate an EDL override that pushes a beat below BEAT_MIN_SEC."""
    override = {
        "fixture_type": "invalid_edl",
        "description": "Invalid EDL: B004 trim exceeds beat minimum (would push 4.0s beat below 2.0s)",
        "is_valid": False,
        "violation": "BEAT_MIN_SEC",
        "overrides": [
            {
                "beat_id": "B004",
                "trim_start_sec": 3.0,  # Would leave only 1.0s (below BEAT_MIN_SEC)
                "trim_end_sec": 0.0,
                "reorder_after": None,
                "music_duck_db": 0.0,
            },
        ],
    }
    tmp_path.mkdir(exist_ok=True, parents=True)
    out = tmp_path / "edl_invalid.json"
    out.write_text(json.dumps(override, indent=2, sort_keys=True))
    return {
        "path": str(out),
        "override": override,
        "is_valid": False,
        "fixture_type": "invalid_edl",
        "storyboard": SAMPLE_STORYBOARD,
        "expected_error": "BEAT_MIN_SEC violation",
    }


# ---------------------------------------------------------------------------
# Fixture 3: Valid reorder EDL override
# ---------------------------------------------------------------------------

def generate_reorder_edl_override(tmp_path: Path) -> dict[str, Any]:
    """Generate a valid EDL override that reorders two adjacent non-hero beats."""
    override = {
        "fixture_type": "reorder_edl",
        "description": "Valid EDL: swap two adjacent non-hero beats (B004, B005)",
        "is_valid": True,
        "overrides": [
            {
                "beat_id": "B004",
                "trim_start_sec": 0.0,
                "trim_end_sec": 0.0,
                "reorder_after": "B005",  # Move B004 after B005
                "music_duck_db": 0.0,
            },
        ],
    }
    tmp_path.mkdir(exist_ok=True, parents=True)
    out = tmp_path / "edl_reorder.json"
    out.write_text(json.dumps(override, indent=2, sort_keys=True))
    return {
        "path": str(out),
        "override": override,
        "is_valid": True,
        "fixture_type": "reorder_edl",
        "storyboard": SAMPLE_STORYBOARD,
    }


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_edl(tmp_path):
    yield generate_valid_edl_override(tmp_path)


@pytest.fixture
def invalid_edl(tmp_path):
    yield generate_invalid_edl_override(tmp_path)


@pytest.fixture
def reorder_edl(tmp_path):
    yield generate_reorder_edl_override(tmp_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_valid_edl(valid_edl):
    """Valid EDL fixture: JSON parses, metadata label is valid."""
    p = Path(valid_edl["path"])
    assert p.exists(), "valid EDL JSON not created"
    data = json.loads(p.read_text())
    assert data["is_valid"] is True
    assert data["fixture_type"] == "valid_edl"
    assert len(data["overrides"]) == 2
    # All trims within ±0.5s on non-hero beats
    for ov in data["overrides"]:
        assert abs(ov["trim_start_sec"]) <= 0.5, f"trim_start {ov['trim_start_sec']} exceeds 0.5s"
        assert abs(ov["trim_end_sec"]) <= 0.5, f"trim_end {ov['trim_end_sec']} exceeds 0.5s"


def test_invalid_edl(invalid_edl):
    """Invalid EDL fixture: JSON parses, metadata label is invalid."""
    p = Path(invalid_edl["path"])
    assert p.exists()
    data = json.loads(p.read_text())
    assert data["is_valid"] is False
    assert data["fixture_type"] == "invalid_edl"
    assert data["violation"] == "BEAT_MIN_SEC"
    assert "expected_error" in invalid_edl


def test_reorder_edl(reorder_edl):
    """Reorder EDL fixture: JSON parses, reorder_after field present."""
    p = Path(reorder_edl["path"])
    assert p.exists()
    data = json.loads(p.read_text())
    assert data["is_valid"] is True
    assert data["fixture_type"] == "reorder_edl"
    assert data["overrides"][0]["reorder_after"] == "B005"


def test_fixture_determinism(tmp_path):
    """Same inputs produce same JSON output (hash match across runs)."""
    m1 = generate_valid_edl_override(tmp_path / "run1")
    m2 = generate_valid_edl_override(tmp_path / "run2")
    assert Path(m1["path"]).read_bytes() == Path(m2["path"]).read_bytes(), \
        "valid EDL fixture generation is not deterministic"


def test_storyboard_reference(valid_edl):
    """EDL fixture references a valid storyboard."""
    sb = valid_edl["storyboard"]
    assert sb["project_id"] == "test_edl_fixtures"
    assert len(sb["beats"]) == 6
    # All beats have required fields
    for b in sb["beats"]:
        assert "beat_id" in b
        assert "shot_type" in b
        assert "est_duration_sec" in b

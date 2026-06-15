"""Tests for scripts/reconcile_production_storyboard.py"""
import json as _json; from pathlib import Path as _P
_MODEL_MAX = float(_json.loads((_P(__file__).resolve().parent.parent / "docs" / "channel_universe" / "constraints.json").read_text()).get("lipsync_render_rules", {}).get("max_clip_duration_sec", 15))
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from reconcile_production_storyboard import reconcile
from production_storyboard import validate_production_storyboard

from conftest_constants import TEST_CONSTRAINTS as CONSTRAINTS, OVER_LIMIT_DURATION



def _storyboard(beats):
    return {"schema_version": "2.0", "project_id": "test", "beats": beats}


def _timing_map(beats, total=None):
    if total is None:
        total = beats[-1]["end"] if beats else 0
    return {"beats": beats, "total_duration": total, "beat_count": len(beats)}


def _beat(beat_id, narration, shot_type="hero_lipsync", lipsync=True, model="seedance_2_0", graphic=None):
    b = {
        "beat_id": beat_id,
        "narration_text": narration,
        "shot_type": shot_type,
        "segment_id": "001_test",
        "lipsync_required": lipsync,
        "model": model,
    }
    if graphic:
        b["graphic"] = graphic
    return b


def test_simple_beat_gets_timing():
    """Single beat B001 in storyboard, B001 in timing map → production beat has exact timing."""
    sb = _storyboard([_beat("B001", "Short sentence here.", shot_type="hero_lipsync")])
    tm = _timing_map([{"beat_id": "B001", "start": 0.0, "end": 5.0, "duration": 5.0}])

    result, issues = reconcile(sb, tm, CONSTRAINTS)
    beat = result["beats"][0]

    assert beat["audio_start_sec"] == 0.0
    assert beat["audio_end_sec"] == 5.0
    assert beat["audio_duration_sec"] == 5.0
    assert beat["source_beat_id"] == "B001"


def test_overlong_hero_split():
    """B001 14s hero_lipsync without audio → needs_repair (PTC-02: no audio = no split)."""
    narration = "First sentence takes about half. Second sentence takes the rest."
    sb = _storyboard([_beat("B001", narration)])
    tm = _timing_map([{"beat_id": "B001", "start": 0.0, "end": 18.0, "duration": 18.0}])

    result, issues = reconcile(sb, tm, CONSTRAINTS)
    beats = result["beats"]

    # Without audio, measured boundaries cannot be determined → needs_repair
    assert len(beats) == 1
    assert beats[0]["needs_repair"] is True
    assert any("NEEDS_REPAIR" in i for i in issues)


def test_no_word_split():
    """Single-sentence 18s beat → rerouted to hero_cutaway (PTC-03)."""
    narration = "This is one very long sentence without any period or boundary that keeps going and going"
    sb = _storyboard([_beat("B001", narration)])
    tm = _timing_map([{"beat_id": "B001", "start": 0.0, "end": 18.0, "duration": 18.0}])

    result, issues = reconcile(sb, tm, CONSTRAINTS)

    beat = result["beats"][0]
    assert beat.get("needs_repair") is False
    assert beat["treatment"] == "hero_cutaway"
    assert beat["narration_text"] == narration


def test_broll_long_gets_coverage_slots():
    """B003 18.894s broll → coverage_plan has 3+ entries."""
    sb = _storyboard([_beat("B003", "Some narration text.", shot_type="broll_environment", lipsync=False, model="kling3_0")])
    tm = _timing_map([{"beat_id": "B003", "start": 0.0, "end": 18.894, "duration": 18.894}])

    result, issues = reconcile(sb, tm, CONSTRAINTS)
    beat = result["beats"][0]
    coverage = beat["coverage_plan"]

    # 18.894 / 6.0 = 3.149 → ceil = 4 slots (or 3+ covering full duration)
    assert len(coverage) >= 3
    total_covered = sum(e["required_duration_sec"] for e in coverage)
    assert abs(total_covered - 18.894) < 0.01


def test_missing_timing_entry_fails():
    """Beat in storyboard not in timing map → error in issues."""
    sb = _storyboard([_beat("B099", "Missing timing.")])
    tm = _timing_map([{"beat_id": "B001", "start": 0.0, "end": 5.0, "duration": 5.0}], total=5.0)

    result, issues = reconcile(sb, tm, CONSTRAINTS)

    assert any("ERROR" in i and "B099" in i for i in issues)


def test_narration_preserved_in_split():
    """Without audio, overlong beat goes to needs_repair (PTC-02: split requires audio)."""
    narration = "First sentence here. Second sentence there. Third one too."
    sb = _storyboard([_beat("B001", narration)])
    # Make it long enough to require split
    tm = _timing_map([{"beat_id": "B001", "start": 0.0, "end": 21.0, "duration": 21.0}])

    result, issues = reconcile(sb, tm, CONSTRAINTS)
    beats = result["beats"]

    # Without audio → needs_repair, narration preserved intact
    assert len(beats) == 1
    assert beats[0]["needs_repair"] is True
    assert beats[0]["narration_text"] == narration


def test_timeline_complete_after_reconcile():
    """Production storyboard passes PST-01 validation for a simple case."""
    sb = _storyboard([
        _beat("B001", "Short sentence.", shot_type="hero_lipsync"),
        _beat("B002", "Another line.", shot_type="broll_environment", lipsync=False, model="kling3_0"),
    ])
    tm = _timing_map([
        {"beat_id": "B001", "start": 0.0, "end": 5.0, "duration": 5.0},
        {"beat_id": "B002", "start": 5.0, "end": 9.0, "duration": 4.0},
    ], total=9.0)

    result, issues = reconcile(sb, tm, CONSTRAINTS)
    validation_errors = validate_production_storyboard(result)

    assert validation_errors == []


def test_graphics_inherited_by_split_children():
    """Parent with required graphic → both split children inherit it."""
    graphic = {"required": True, "layout": "lower_third", "text": "TEST GRAPHIC", "timing": "on_spoken_line"}
    narration = "First sentence here. Second sentence there."
    sb = _storyboard([_beat("B001", narration, graphic=graphic)])
    tm = _timing_map([{"beat_id": "B001", "start": 0.0, "end": 18.0, "duration": 18.0}])

    result, issues = reconcile(sb, tm, CONSTRAINTS)
    beats = result["beats"]

    # Without audio → needs_repair; graphics still preserved on repair beat
    assert len(beats) == 1
    assert beats[0]["needs_repair"] is True
    assert "graphics" in beats[0]
    assert beats[0]["graphics"][0]["text"] == "TEST GRAPHIC"

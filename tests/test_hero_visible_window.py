"""TKT-003: Populate visible windows on the main compile path.

Every HERO_SYNC_LOCKED unit compiled by produce_db.invoke_compile_media has
visible_start_sample/visible_end_sample set (== speech window), so
validate_hero_slicing_intervals enforces visible <= generation on real
productions.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as _db
import produce_db
from production_repo import PolicyValidationError, plan_render_units, validate_hero_slicing_intervals
from timeline_utils import MASTER_SAMPLE_RATE, ms_to_samples

_VISUAL_INTENT = {
    "visual_function": "illustrate",
    "concept_key": "test_visible_window",
    "concept_hash": "abc123",
    "narrative_claim": "Test claim",
    "information_to_show": "Test information",
    "viewer_takeaway": "Test takeaway",
    "required_action": "Test action",
    "distinctness_requirement": "Test distinctness",
    "semantic_acceptance_criteria": "Test criteria",
}


def _make_tone_wav(path, duration_sec):
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={duration_sec}",
        "-acodec", "pcm_s16le", "-ar", str(MASTER_SAMPLE_RATE), "-ac", "1",
        str(path),
    ], capture_output=True, check=True)


def _register_master(pid, duration_sec):
    from production_repo import register_artifact
    d = Path(tempfile.mkdtemp(prefix="visible_win_master_"))
    wav = d / "continuous.wav"
    _make_tone_wav(wav, duration_sec)
    return register_artifact(pid, wav, "tts_master", db_path=None)


def _make_hero_production(slug, span_start_ms, span_end_ms):
    from authoring_service import save_document_revision

    master_duration_sec = (span_end_ms / 1000.0) + 2.0

    prod = _db.ensure_production(slug, seed="test_visible_window", video_type="explainer")
    pid = prod["id"]
    storyboard_rev = save_document_revision(pid, "storyboard", {"beats": []}, db_path=None)

    beat_id = f"beat_{slug}"
    with _db.transaction(None) as conn:
        conn.execute(
            """INSERT INTO creative_beats
               (id, storyboard_revision_id, ordinal, label, shot_type,
                visual_intent_json, graphics_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (beat_id, storyboard_rev["id"], 1, slug, "hero_lipsync",
             json.dumps(_VISUAL_INTENT), json.dumps({}))
        )

    span_id = f"span_{slug}"
    duration_ms = span_end_ms - span_start_ms
    with _db.transaction(None) as conn:
        conn.execute(
            """INSERT INTO timeline_spans
               (id, production_id, creative_beat_id, label, start_ms, end_ms,
                duration_ms, status, ordinal)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (span_id, pid, beat_id, slug, span_start_ms, span_end_ms,
             duration_ms, "active", 1)
        )

    _register_master(pid, master_duration_sec)
    return pid


def _active_units(pid):
    return _db.connect(None).execute(
        "SELECT * FROM render_units WHERE production_id=? AND status!='stale' "
        "ORDER BY required_start_ms",
        (pid,)
    ).fetchall()


# ---------------------------------------------------------------------------
# Positive: visible windows populated on compile
# ---------------------------------------------------------------------------

def test_single_slot_hero_visible_window(tmp_path):
    """A single-slot hero unit has visible windows set equal to speech window."""
    pid = _make_hero_production("visible_win_single", 0, 10000)
    produce_db.invoke_compile_media({"production_id": pid}, tmp_path)

    units = _active_units(pid)
    hero_units = [u for u in units if u["audio_policy"] == "HERO_SYNC_LOCKED"]
    assert len(hero_units) == 1

    u = hero_units[0]
    assert u["visible_start_sample"] is not None, "visible_start_sample must be set"
    assert u["visible_end_sample"] is not None, "visible_end_sample must be set"
    assert u["visible_start_sample"] == u["speech_start_sample"]
    assert u["visible_end_sample"] == u["speech_end_sample"]
    assert u["visible_start_sample"] >= u["generation_start_sample"]
    assert u["visible_end_sample"] <= u["generation_end_sample"]


def test_multi_slot_hero_visible_window(tmp_path):
    """A multi-slot hero (spanning multiple clips) has visible windows on every slot."""
    pid = _make_hero_production("visible_win_multi", 0, 30000)
    produce_db.invoke_compile_media({"production_id": pid}, tmp_path)

    units = _active_units(pid)
    hero_units = [u for u in units if u["audio_policy"] == "HERO_SYNC_LOCKED"]
    assert len(hero_units) >= 2, f"Expected >=2 hero slots, got {len(hero_units)}"

    for u in hero_units:
        assert u["visible_start_sample"] is not None, \
            f"visible_start_sample must be set on unit {u['id']}"
        assert u["visible_end_sample"] is not None, \
            f"visible_end_sample must be set on unit {u['id']}"
        assert u["visible_start_sample"] == u["speech_start_sample"], \
            f"visible_start_sample == speech_start_sample on unit {u['id']}"
        assert u["visible_end_sample"] == u["speech_end_sample"], \
            f"visible_end_sample == speech_end_sample on unit {u['id']}"
        assert u["visible_start_sample"] >= u["generation_start_sample"], \
            f"visible_start_sample >= generation_start_sample on unit {u['id']}"
        assert u["visible_end_sample"] <= u["generation_end_sample"], \
            f"visible_end_sample <= generation_end_sample on unit {u['id']}"


def test_validate_hero_slicing_intervals_accepts_visible_units(tmp_path):
    """All compiled hero units pass validate_hero_slicing_intervals."""
    pid = _make_hero_production("visible_win_validate", 0, 15000)
    produce_db.invoke_compile_media({"production_id": pid}, tmp_path)

    units = _active_units(pid)
    hero_units = [u for u in units if u["audio_policy"] == "HERO_SYNC_LOCKED"]
    assert len(hero_units) >= 1

    for u in hero_units:
        validate_hero_slicing_intervals(dict(u))


# ---------------------------------------------------------------------------
# Negative: visible outside generation
# ---------------------------------------------------------------------------

def test_visible_outside_generation_rejected(tmp_path):
    """A render unit with visible_end_sample > generation_end_sample is rejected."""
    pid = _make_hero_production("visible_win_bad", 0, 10000)
    produce_db.invoke_compile_media({"production_id": pid}, tmp_path)

    hero_units = [dict(u) for u in _active_units(pid)
                  if u["audio_policy"] == "HERO_SYNC_LOCKED"]
    assert len(hero_units) == 1

    bad_unit = dict(hero_units[0])
    bad_unit["visible_end_sample"] = bad_unit["generation_end_sample"] + 48000
    bad_unit["visible_start_sample"] = bad_unit["generation_start_sample"]

    with pytest.raises(PolicyValidationError, match="Visible interval"):
        validate_hero_slicing_intervals(bad_unit)


def test_visible_before_generation_rejected(tmp_path):
    """A render unit with visible_start_sample < generation_start_sample is rejected."""
    pid = _make_hero_production("visible_win_bad2", 0, 10000)
    produce_db.invoke_compile_media({"production_id": pid}, tmp_path)

    hero_units = [dict(u) for u in _active_units(pid)
                  if u["audio_policy"] == "HERO_SYNC_LOCKED"]
    assert len(hero_units) == 1

    bad_unit = dict(hero_units[0])
    bad_unit["visible_start_sample"] = bad_unit["generation_start_sample"] - 48000
    bad_unit["visible_end_sample"] = bad_unit["generation_end_sample"]

    with pytest.raises(PolicyValidationError, match="Visible interval"):
        validate_hero_slicing_intervals(bad_unit)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

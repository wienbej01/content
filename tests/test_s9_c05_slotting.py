"""S9-C05: Multi-clip slotting + per-slot hero audio slices.

Tests that beats longer than max_clip are split into multiple slots that tile the span
exactly, and that each HERO_SYNC_LOCKED slot has a materialized master-narration audio
slice (real ffmpeg output, SHA-verified, registered as an artifact, linked to the unit).
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
from timeline_utils import MASTER_SAMPLE_RATE, ms_to_samples


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_VISUAL_INTENT = {
    "visual_function": "illustrate",
    "concept_key": "test_concept",
    "concept_hash": "abc123",
    "narrative_claim": "Test claim",
    "information_to_show": "Test information",
    "viewer_takeaway": "Test takeaway",
    "required_action": "Test action",
    "distinctness_requirement": "Test distinctness",
    "semantic_acceptance_criteria": "Test criteria",
}


def load_clip_constraints():
    """Load clip duration bounds from constraints.json (single source of truth)."""
    constraints_path = Path("docs/channel_universe/constraints.json")
    with open(constraints_path) as f:
        constraints = json.load(f)
    return {
        "min_clip_sec": constraints["lipsync_render_rules"]["min_clip_duration_sec"],
        "max_clip_sec": constraints["lipsync_render_rules"]["max_clip_duration_sec"],
    }


def _make_tone_wav(path: Path, duration_sec: float) -> None:
    """Generate a real, ffprobe-valid mono PCM tone (so slices have audio + a SHA)."""
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={duration_sec}",
        "-acodec", "pcm_s16le", "-ar", str(MASTER_SAMPLE_RATE), "-ac", "1",
        str(path),
    ], capture_output=True, check=True)


def _register_master(pid: str, duration_sec: float) -> dict:
    """Register a real tts_master narration artifact of the requested duration."""
    from production_repo import register_artifact
    d = Path(tempfile.mkdtemp(prefix="c05_master_"))
    wav = d / "continuous.wav"
    _make_tone_wav(wav, duration_sec)
    return register_artifact(pid, wav, "tts_master", db_path=None)


def _make_hero_production(slug, span_start_ms, span_end_ms, *, register_master=True,
                          master_duration_sec=None):
    """Create a production with one hero_lipsync span [start,end]ms.

    When register_master is True, also registers a tts_master long enough to cover the
    span (required for slice materialization). Returns (pid, master_art_or_None).
    """
    from authoring_service import save_document_revision

    if master_duration_sec is None:
        master_duration_sec = (span_end_ms / 1000.0) + 2.0

    prod = _db.ensure_production(slug, seed="test_slotting", video_type="explainer")
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

    master_art = _register_master(pid, master_duration_sec) if register_master else None
    return pid, master_art


def _active_units(pid):
    return _db.connect(None).execute(
        "SELECT * FROM render_units WHERE production_id=? AND status!='stale' "
        "ORDER BY required_start_ms",
        (pid,)
    ).fetchall()


# ---------------------------------------------------------------------------
# Slot structure (original acceptance gates)
# ---------------------------------------------------------------------------

def test_long_span_slots_within_bounds(tmp_path):
    """A 30s hero span is split into N slots each within [min, max]."""
    constraints = load_clip_constraints()
    min_sec, max_sec = constraints["min_clip_sec"], constraints["max_clip_sec"]

    pid, _ = _make_hero_production("s9_c05_long_span", 0, 30000)
    produce_db.invoke_compile_media({"production_id": pid}, tmp_path)

    units = _active_units(pid)
    assert len(units) >= 2, f"Expected >=2 slots for 30s span, got {len(units)}"

    for unit in units:
        duration_sec = (unit["required_end_ms"] - unit["required_start_ms"]) / 1000.0
        assert min_sec <= duration_sec <= max_sec, \
            f"Slot duration {duration_sec}s not within [{min_sec}, {max_sec}]"


def test_slots_tile_span_exactly(tmp_path):
    """Slots tile the span exactly with no gaps or overlaps."""
    pid, _ = _make_hero_production("s9_c05_contiguity", 0, 30000)
    produce_db.invoke_compile_media({"production_id": pid}, tmp_path)

    units = _active_units(pid)
    assert len(units) >= 2, f"Need >=2 slots to test contiguity, got {len(units)}"

    assert units[0]["required_start_ms"] == 0, \
        f"First slot should start at 0ms, got {units[0]['required_start_ms']}"
    assert units[-1]["required_end_ms"] == 30000, \
        f"Last slot should end at 30000ms, got {units[-1]['required_end_ms']}"

    for i in range(1, len(units)):
        prev_end = units[i - 1]["required_end_ms"]
        curr_start = units[i]["required_start_ms"]
        assert prev_end == curr_start, \
            f"Gap/overlap: slot {i-1} ends {prev_end}ms, slot {i} starts {curr_start}ms"


def test_boundary_span_max_duration(tmp_path):
    """Span==max -> 1 slot; span==max+1ms -> 2 slots."""
    max_ms = int(load_clip_constraints()["max_clip_sec"] * 1000)

    pid_1, _ = _make_hero_production("s9_c05_max_1slot", 0, max_ms)
    produce_db.invoke_compile_media({"production_id": pid_1}, tmp_path)
    assert len(_active_units(pid_1)) == 1, "Expected 1 slot for span==max"

    pid_2, _ = _make_hero_production("s9_c05_max_2slots", 0, max_ms + 1)
    produce_db.invoke_compile_media({"production_id": pid_2}, tmp_path)
    assert len(_active_units(pid_2)) == 2, "Expected 2 slots for span==max+1"


# ---------------------------------------------------------------------------
# F-001: hero audio slice materialization (the blocking finding)
# ---------------------------------------------------------------------------

def _slice_artifact_for(unit_id):
    """Resolve the hero_audio_slice artifact linked to a render unit (S9-C06 contract:
    slice artifacts carry render_unit_id in metadata)."""
    conn = _db.connect(None)
    rows = conn.execute(
        "SELECT * FROM artifacts WHERE kind='hero_audio_slice'"
    ).fetchall()
    for r in rows:
        meta = json.loads(r["metadata_json"]) if r["metadata_json"] else {}
        if meta.get("render_unit_id") == unit_id:
            return dict(r)
    return None


def test_hero_slice_materialized(tmp_path):
    """Each hero slot has a real ffmpeg slice file whose SHA matches the master subrange,
    registered as a hero_audio_slice artifact and linked to the unit (slice metadata
    render_unit_id); the unit row carries master provenance + the speech sample interval."""
    from production_repo import get_artifact
    from slice_continuous_lipsync import _sha, probe_media

    pid, master_art = _make_hero_production("s9_c05_slice", 0, 30000)
    result = produce_db.invoke_compile_media({"production_id": pid}, tmp_path)
    assert result["hero_slice_count"] >= 2, "compile should report >=2 hero slices"

    units = _active_units(pid)
    hero_units = [u for u in units if u["audio_policy"] == "HERO_SYNC_LOCKED"]
    assert len(hero_units) >= 2

    master_path = Path(master_art["uri"])
    master_sha = master_art["sha256"]

    for u in hero_units:
        # 1. Master provenance + speech interval persisted on the unit row. The unit's
        #    master_audio_artifact_id is the MASTER (provenance), not the slice.
        assert u["master_audio_artifact_id"], f"unit {u['id']} missing master_audio_artifact_id"
        master_ref = get_artifact(u["master_audio_artifact_id"], db_path=None)
        assert master_ref is not None and master_ref["kind"] == "tts_master"
        assert u["master_audio_sha256"] == master_sha
        assert u["speech_start_sample"] == ms_to_samples(u["required_start_ms"])
        assert u["speech_end_sample"] == ms_to_samples(u["required_end_ms"])

        # 2. A distinct hero_audio_slice artifact is linked to the unit (metadata).
        slice_art = _slice_artifact_for(u["id"])
        assert slice_art is not None, f"no hero_audio_slice artifact for unit {u['id']}"
        assert slice_art["kind"] == "hero_audio_slice"
        meta = json.loads(slice_art["metadata_json"])
        assert meta["render_unit_id"] == u["id"]
        assert meta["master_sha256"] == master_sha

        # 3. A real ffmpeg-produced file exists at the artifact URI.
        slice_path = Path(slice_art["uri"])
        assert slice_path.exists(), f"slice file missing: {slice_path}"

        # 4. It is valid audio media whose duration matches the slot (no padding for a
        #    tiled 30s hero; speech == generation interval).
        probe = probe_media(slice_path)
        assert probe is not None and probe.has_audio == 1, "slice must be audio media"
        slot_ms = u["required_end_ms"] - u["required_start_ms"]
        assert abs(probe.duration_ms - slot_ms) <= 60, \
            f"slice duration {probe.duration_ms}ms != slot {slot_ms}ms (no pad expected)"

        # 5. SHA matches the master subrange: independently re-extracting the same
        #    [start,end] range from the master reproduces the slice byte-for-byte.
        ss = u["speech_start_sample"] / MASTER_SAMPLE_RATE
        dur = (u["speech_end_sample"] - u["speech_start_sample"]) / MASTER_SAMPLE_RATE
        with tempfile.TemporaryDirectory(prefix="c05_reextract_") as td:
            reextract = Path(td) / "reextract.wav"
            subprocess.run([
                "ffmpeg", "-y",
                "-ss", f"{ss:.6f}", "-t", f"{dur:.6f}",
                "-i", str(master_path),
                "-acodec", "pcm_s16le", "-ar", str(MASTER_SAMPLE_RATE), "-ac", "1",
                str(reextract),
            ], capture_output=True, check=True)
            assert _sha(reextract) == slice_art["sha256"], \
                "slice SHA must equal an independent re-extraction of the master subrange"


def test_hero_span_without_master_fails(tmp_path):
    """Hero spans without a tts_master narration artifact fail loudly (no silent fallback)."""
    pid, _ = _make_hero_production("s9_c05_no_master", 0, 30000, register_master=False)
    with pytest.raises(RuntimeError, match="tts_master"):
        produce_db.invoke_compile_media({"production_id": pid}, tmp_path)


# ---------------------------------------------------------------------------
# F-002: per-slot minimum duration validation
# ---------------------------------------------------------------------------

def test_sub_min_hero_span_fails(tmp_path):
    """A hero span shorter than min_clip_duration_sec fails loudly rather than planning
    an unrenderable (<4s) slot."""
    min_ms = int(load_clip_constraints()["min_clip_sec"] * 1000)
    pid, _ = _make_hero_production("s9_c05_submin", 0, min_ms - 500, register_master=False)
    with pytest.raises(RuntimeError, match="min_clip_duration_sec"):
        produce_db.invoke_compile_media({"production_id": pid}, tmp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

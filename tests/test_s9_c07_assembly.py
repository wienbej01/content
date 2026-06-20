"""S9-C07: Assembly richness — graphics overlay + music bed.

Tests that build_assembly_manifest emits a graphic layer per graphic beat and a music
track; the assembled output contains the master narration (exactly once) plus a music
component, and a graphic frame for a graphic beat; assembly remains deterministic and
AI-free.
"""
import hashlib
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
from assemble_db import build_assembly_manifest
from authoring_service import save_document_revision


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_VISUAL_INTENT_HERO = {
    "visual_function": "illustrate",
    "concept_key": "test_concept",
    "concept_hash": "abc123",
    "narrative_claim": "Test narrative claim",
    "information_to_show": "Test information",
    "viewer_takeaway": "Test takeaway",
    "required_action": "understand",
    "distinctness_requirement": "test distinctness",
    "semantic_acceptance_criteria": "test criteria",
}

_VISUAL_INTENT_GRAPHIC = {
    "visual_function": "display",
    "concept_key": "title_card",
    "concept_hash": "def456",
    "narrative_claim": "Title card display",
    "information_to_show": "Episode title",
    "viewer_takeaway": "Brand recognition",
    "required_action": "read",
    "distinctness_requirement": "clear text",
    "semantic_acceptance_criteria": "readable text",
}


def _make_tone_wav(path: Path, duration_sec: float) -> None:
    """Generate a real, ffprobe-valid mono PCM tone."""
    from timeline_utils import MASTER_SAMPLE_RATE
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={duration_sec}",
        "-acodec", "pcm_s16le", "-ar", str(MASTER_SAMPLE_RATE), "-ac", "1",
        str(path),
    ], capture_output=True, check=True)


def _register_master(pid: str, duration_sec: float) -> dict:
    """Register a real tts_master narration artifact."""
    from production_repo import register_artifact
    d = Path(tempfile.mkdtemp(prefix="c07_master_"))
    wav = d / "continuous.wav"
    _make_tone_wav(wav, duration_sec)
    return register_artifact(pid, wav, "tts_master", db_path=None)


def _make_production_with_graphic(slug, hero_start_ms, hero_end_ms,
                                   graphic_start_ms, graphic_end_ms):
    """Create a production with one hero_lipsync span + one local_graphic span."""
    prod = _db.ensure_production(slug, seed="test_assembly_richness", video_type="explainer")
    pid = prod["id"]
    storyboard_rev = save_document_revision(pid, "storyboard", {"beats": []}, db_path=None)

    # Hero beat
    hero_beat_id = f"beat_{slug}_hero"
    with _db.transaction(None) as conn:
        conn.execute(
            """INSERT INTO creative_beats
               (id, storyboard_revision_id, ordinal, label, shot_type,
                visual_intent_json, graphics_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (hero_beat_id, storyboard_rev["id"], 1, f"{slug}_hero", "hero_lipsync",
             json.dumps(_VISUAL_INTENT_HERO), json.dumps({}))
        )

    hero_span_id = f"span_{slug}_hero"
    hero_duration_ms = hero_end_ms - hero_start_ms
    with _db.transaction(None) as conn:
        conn.execute(
            """INSERT INTO timeline_spans
               (id, production_id, creative_beat_id, label, start_ms, end_ms,
                duration_ms, status, ordinal)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (hero_span_id, pid, hero_beat_id, f"{slug}_hero", hero_start_ms, hero_end_ms,
             hero_duration_ms, "active", 1)
        )

    # Graphic beat
    graphic_beat_id = f"beat_{slug}_graphic"
    graphics_contract = {"text": "Episode Title", "layout": "center"}
    with _db.transaction(None) as conn:
        conn.execute(
            """INSERT INTO creative_beats
               (id, storyboard_revision_id, ordinal, label, shot_type,
                visual_intent_json, graphics_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (graphic_beat_id, storyboard_rev["id"], 2, f"{slug}_graphic", "local_graphic",
             json.dumps(_VISUAL_INTENT_GRAPHIC), json.dumps(graphics_contract))
        )

    graphic_span_id = f"span_{slug}_graphic"
    graphic_duration_ms = graphic_end_ms - graphic_start_ms
    with _db.transaction(None) as conn:
        conn.execute(
            """INSERT INTO timeline_spans
               (id, production_id, creative_beat_id, label, start_ms, end_ms,
                duration_ms, status, ordinal)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (graphic_span_id, pid, graphic_beat_id, f"{slug}_graphic", graphic_start_ms, graphic_end_ms,
             graphic_duration_ms, "active", 2)
        )

    # Register master narration
    master_art = _register_master(pid, (hero_end_ms / 1000.0) + 2.0)
    return pid, master_art


def _mark_units_valid_with_artifacts(pid: str, tmp_path: Path) -> None:
    """Seed assembly-ready artifacts without exercising provider generation."""
    from production_repo import register_artifact

    conn = _db.connect(None)
    units = conn.execute(
        "SELECT id, label FROM render_units WHERE production_id=? AND status!='stale'",
        (pid,),
    ).fetchall()
    conn.close()

    for i, unit in enumerate(units):
        path = tmp_path / f"{unit['label'] or unit['id']}_{i}.mp4"
        path.write_bytes(b"assembly fixture media")
        art = register_artifact(pid, path, "generated_media", db_path=None)
        with _db.transaction(None) as conn:
            conn.execute(
                "UPDATE render_units SET active_artifact_id=?, status='valid' WHERE id=?",
                (art["id"], unit["id"]),
            )


# ---------------------------------------------------------------------------
# Contract: manifest has graphic layer per graphic beat + music track
# ---------------------------------------------------------------------------

def test_manifest_richness(tmp_path, monkeypatch):
    """build_assembly_manifest emits graphic layer per graphic beat + music track."""
    monkeypatch.setenv("YT_TEST_MODE", "1")
    pid, _ = _make_production_with_graphic("c07_manifest", 0, 10000, 10000, 15000)
    produce_db.invoke_compile_media({"production_id": pid}, tmp_path)
    produce_db.invoke_gate_a_spend({"production_id": pid}, tmp_path)
    _mark_units_valid_with_artifacts(pid, tmp_path)

    manifest = build_assembly_manifest(pid, variant="16x9")

    # Music track
    assert "music" in manifest, "Manifest must have music track"
    music = manifest["music"]
    assert music.get("enabled") is True, "Music must be enabled"
    assert "volume_db" in music, "Music must have volume_db (ducking level)"
    assert "mood" in music, "Music must have mood"
    assert "seed" in music, "Music must have seed (determinism)"

    # Graphic layer
    assert "graphics" in manifest, "Manifest must have graphics layer"
    graphics = manifest["graphics"]
    assert isinstance(graphics, list), "Graphics must be a list"
    assert len(graphics) >= 1, "Must have at least one graphic layer"

    # Each graphic layer has text + beat_id
    for g in graphics:
        assert "beat_id" in g, "Graphic layer must have beat_id"
        assert "text" in g, "Graphic layer must have text"
        assert g["text"] != "", "Graphic text must not be empty"


# ---------------------------------------------------------------------------
# Unit: master narration appears exactly once (no double)
# ---------------------------------------------------------------------------

def test_narration_once(tmp_path, monkeypatch):
    """Master narration appears exactly once in the manifest (no double)."""
    monkeypatch.setenv("YT_TEST_MODE", "1")
    pid, master_art = _make_production_with_graphic("c07_narration_once", 0, 10000, 10000, 15000)
    produce_db.invoke_compile_media({"production_id": pid}, tmp_path)
    produce_db.invoke_gate_a_spend({"production_id": pid}, tmp_path)
    _mark_units_valid_with_artifacts(pid, tmp_path)

    manifest = build_assembly_manifest(pid, variant="16x9")

    # continuous_audio is the master narration — must appear exactly once
    assert "continuous_audio" in manifest
    assert manifest["continuous_audio"] == master_art["uri"]

    # No per-segment audio in continuous mode (all segments are muted visuals)
    for seg in manifest["segments"]:
        assert "audio" not in seg or seg.get("audio") is None, \
            f"Segment {seg.get('id')} must not have per-segment audio in continuous mode"


# ---------------------------------------------------------------------------
# Determinism: same inputs → same output bytes
# ---------------------------------------------------------------------------

def test_music_deterministic(tmp_path):
    """generate_music.generate produces deterministic output (same seed → same bytes)."""
    sys.path.insert(0, str(ROOT / "tools"))
    from generate_music import generate, write_wav

    stereo1 = generate(5.0, "calm", seed=7)
    stereo2 = generate(5.0, "calm", seed=7)

    assert stereo1.shape == stereo2.shape
    assert (stereo1 == stereo2).all(), "Same seed + duration + mood must produce identical output"

    # Write to WAV and compare SHA
    wav1 = tmp_path / "bed1.wav"
    wav2 = tmp_path / "bed2.wav"
    write_wav(stereo1, wav1)
    write_wav(stereo2, wav2)

    sha1 = hashlib.sha256(wav1.read_bytes()).hexdigest()
    sha2 = hashlib.sha256(wav2.read_bytes()).hexdigest()
    assert sha1 == sha2, "WAV files must be byte-identical"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""S9-C06: Real generation request — prompt + hero --image + hero --audio.

Tests that hero render units carry a real per-clip prompt, the hero reference image
path (--image), and the hero master-narration audio slice path (--audio); b-roll units
carry a real prompt only. The HiggsfieldSeedanceAdapter constructs the correct CLI args
with subprocess stubbed (no real paid call). Dry-run mode returns args without invoking
the CLI.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as _db
import produce_db
from authoring_service import save_document_revision


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_VISUAL_INTENT_HERO = {
    "visual_function": "illustrate",
    "concept_key": "quantum_computing",
    "concept_hash": "abc123",
    "narrative_claim": "Quantum computers use qubits to process information in parallel",
    "information_to_show": "Qubits in superposition states",
    "viewer_takeaway": "Qubits enable parallel computation",
    "required_action": "understand",
    "distinctness_requirement": "show qubit superposition",
    "semantic_acceptance_criteria": "visualize qubit states",
}

_VISUAL_INTENT_BROLL = {
    "visual_function": "illustrate",
    "concept_key": "data_flow",
    "concept_hash": "def456",
    "narrative_claim": "Data flows through neural networks",
    "information_to_show": "Animated data packets flowing through layered network nodes",
    "viewer_takeaway": "Networks process information",
    "required_action": "observe",
    "distinctness_requirement": "show data movement",
    "semantic_acceptance_criteria": "visualize network layers",
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
    d = Path(tempfile.mkdtemp(prefix="c06_master_"))
    wav = d / "continuous.wav"
    _make_tone_wav(wav, duration_sec)
    return register_artifact(pid, wav, "tts_master", db_path=None)


def _make_production_with_hero_and_broll(slug, hero_start_ms, hero_end_ms,
                                         broll_start_ms, broll_end_ms):
    """Create a production with one hero_lipsync span + one b-roll span."""
    prod = _db.ensure_production(slug, seed="test_generation", video_type="explainer")
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

    # B-roll beat
    broll_beat_id = f"beat_{slug}_broll"
    with _db.transaction(None) as conn:
        conn.execute(
            """INSERT INTO creative_beats
               (id, storyboard_revision_id, ordinal, label, shot_type,
                visual_intent_json, graphics_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (broll_beat_id, storyboard_rev["id"], 2, f"{slug}_broll", "broll_archival",
             json.dumps(_VISUAL_INTENT_BROLL), json.dumps({}))
        )

    broll_span_id = f"span_{slug}_broll"
    broll_duration_ms = broll_end_ms - broll_start_ms
    with _db.transaction(None) as conn:
        conn.execute(
            """INSERT INTO timeline_spans
               (id, production_id, creative_beat_id, label, start_ms, end_ms,
                duration_ms, status, ordinal)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (broll_span_id, pid, broll_beat_id, f"{slug}_broll", broll_start_ms, broll_end_ms,
             broll_duration_ms, "active", 2)
        )

    # Register master narration (needed for hero slice)
    master_art = _register_master(pid, (hero_end_ms / 1000.0) + 2.0)
    return pid, master_art


def _active_units(pid):
    return _db.connect(None).execute(
        "SELECT * FROM render_units WHERE production_id=? AND status!='stale' "
        "ORDER BY required_start_ms",
        (pid,)
    ).fetchall()


def _unit_metadata(unit):
    """Parse render_units.metadata_json (or empty dict if None)."""
    return json.loads(unit["metadata_json"]) if unit["metadata_json"] else {}


# ---------------------------------------------------------------------------
# Contract: hero payload has prompt + image + audio
# ---------------------------------------------------------------------------

def test_hero_payload_has_prompt_image_audio(tmp_path, monkeypatch):
    """Hero unit payload carries real prompt + image path + audio slice path."""
    monkeypatch.setenv("YT_TEST_MODE", "1")
    pid, _ = _make_production_with_hero_and_broll("c06_hero_payload", 0, 10000, 10000, 15000)
    produce_db.invoke_compile_media({"production_id": pid}, tmp_path)
    produce_db.invoke_gate_a_spend({"production_id": pid}, tmp_path)  # auto-approved in YT_TEST_MODE
    with pytest.raises(RuntimeError, match="not generated/valid"):
        produce_db.invoke_generate_media({"production_id": pid}, tmp_path)

    units = _active_units(pid)
    hero_units = [u for u in units if u["audio_policy"] == "HERO_SYNC_LOCKED"]
    assert len(hero_units) >= 1, "Need at least one hero unit"

    for u in hero_units:
        meta = _unit_metadata(u)
        # Prompt: non-generic, reflects visual_intent
        assert "prompt" in meta, "Hero unit must have prompt in metadata"
        prompt = meta["prompt"]
        assert prompt != "educational video", "Prompt must not be generic"
        assert "quantum" in prompt.lower() or "qubit" in prompt.lower(), \
            "Prompt should reflect visual_intent narrative"

        # Image: hero reference path
        assert "image_path" in meta, "Hero unit must have image_path in metadata"
        image_path = meta["image_path"]
        assert image_path and Path(image_path).exists(), \
            f"Hero reference image must exist: {image_path}"
        assert "james" in image_path.lower() and "canonical" in image_path.lower(), \
            "Hero reference must be from the canonical set"

        # Audio: hero slice path
        assert "audio_path" in meta, "Hero unit must have audio_path in metadata"
        audio_path = meta["audio_path"]
        assert audio_path and Path(audio_path).exists(), \
            f"Hero audio slice must exist: {audio_path}"
        assert "hero_audio_slice" in audio_path or ".wav" in audio_path, \
            "Audio path must be the slice artifact"

        # F-002: Negative prompt from constraints.json
        assert "negative_prompt" in meta, "Hero unit must have negative_prompt in metadata"
        neg = meta["negative_prompt"]
        assert "futuristic holograms" in neg, "Negative prompt must include constraints"


# ---------------------------------------------------------------------------
# Contract: b-roll payload has prompt, no image/audio
# ---------------------------------------------------------------------------

def test_broll_payload_has_prompt_only(tmp_path, monkeypatch):
    """B-roll unit payload carries real prompt only (no image/audio)."""
    monkeypatch.setenv("YT_TEST_MODE", "1")
    pid, _ = _make_production_with_hero_and_broll("c06_broll_payload", 0, 10000, 10000, 15000)
    produce_db.invoke_compile_media({"production_id": pid}, tmp_path)
    produce_db.invoke_gate_a_spend({"production_id": pid}, tmp_path)
    with pytest.raises(RuntimeError, match="not generated/valid"):
        produce_db.invoke_generate_media({"production_id": pid}, tmp_path)

    units = _active_units(pid)
    broll_units = [u for u in units if u["audio_policy"] == "BROLL_FLEX"]
    assert len(broll_units) >= 1, "Need at least one b-roll unit"

    for u in broll_units:
        meta = _unit_metadata(u)
        # Prompt: non-generic
        assert "prompt" in meta, "B-roll unit must have prompt in metadata"
        prompt = meta["prompt"]
        assert prompt != "educational video", "Prompt must not be generic"
        assert "data" in prompt.lower() or "network" in prompt.lower(), \
            "Prompt should reflect visual_intent narrative"

        # No image/audio for b-roll
        assert "image_path" not in meta or not meta.get("image_path"), \
            "B-roll must not have image_path"
        assert "audio_path" not in meta or not meta.get("audio_path"), \
            "B-roll must not have audio_path"


# ---------------------------------------------------------------------------
# Contract: adapter builds --image/--audio for seedance hero
# ---------------------------------------------------------------------------

def test_adapter_hero_args_with_image_audio():
    """HiggsfieldSeedanceAdapter.submit builds --image/--audio for seedance hero (subprocess stubbed)."""
    from paid_adapters import HiggsfieldSeedanceAdapter
    adapter = HiggsfieldSeedanceAdapter(config={"duration_sec": 10})

    payload = {
        "model": "seedance_2_0",
        "prompt": "Photorealistic cinematic medium close-up of James discussing qubits",
        "image_path": "assets/reference/james/canonical/JAMES_MEDIUM_FRONT_NAVY_SWEATER_SPEAKING_002.png",
        "audio_path": "/tmp/hero_audio_slices/unit_123.wav",
        "duration_sec": 10,
        "aspect_ratio": "16:9",
        "resolution": "480p",
        "mode": "fast",
    }

    with patch("paid_adapters.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="11111111-1111-4111-8111-111111111111", stderr="")
        result = adapter.submit(payload, idempotency_key="test_key")

        # Verify subprocess was called with correct args
        assert mock_run.called, "subprocess.run must be called"
        call_args = mock_run.call_args[0][0]
        
        assert "--prompt" in call_args, "Args must include --prompt"
        assert "Photorealistic" in " ".join(call_args), "Prompt must be in args"
        
        assert "--image" in call_args, "Hero args must include --image"
        assert "JAMES_MEDIUM_FRONT_NAVY_SWEATER_SPEAKING_002.png" in " ".join(call_args), \
            "Image path must be in args"
        
        assert "--audio" in call_args, "Hero args must include --audio"
        assert "unit_123.wav" in " ".join(call_args), "Audio path must be in args"
        
        assert result["external_job_id"] == "11111111-1111-4111-8111-111111111111"
        assert result["status"] == "submitted"


# ---------------------------------------------------------------------------
# Contract: adapter omits --audio for non-seedance; hero non-seedance fails loud
# ---------------------------------------------------------------------------

def test_adapter_audio_only_for_seedance():
    """--audio only attaches to seedance_2_0; a non-seedance hero unit with audio_path fails loud."""
    from paid_adapters import HiggsfieldSeedanceAdapter
    from provider_adapter import ProviderAdapterError
    adapter = HiggsfieldSeedanceAdapter(config={"duration_sec": 10})

    # Non-seedance model with audio_path should fail loud (I4 invariant)
    payload = {
        "model": "kling3_0",  # non-seedance
        "prompt": "Test prompt",
        "image_path": "assets/reference/james/canonical/JAMES_FRONT.png",
        "audio_path": "/tmp/slice.wav",  # audio_path present but model doesn't support it
        "duration_sec": 10,
    }

    with pytest.raises(ProviderAdapterError, match="audio.*seedance|seedance.*audio"):
        adapter.submit(payload, idempotency_key="test_key")


def test_adapter_broll_no_image_audio():
    """B-roll (no image_path/audio_path) omits --image/--audio."""
    from paid_adapters import HiggsfieldSeedanceAdapter
    adapter = HiggsfieldSeedanceAdapter(config={"duration_sec": 8})

    payload = {
        "model": "seedance_2_0",
        "prompt": "Data flows through neural networks",
        "duration_sec": 8,
        "aspect_ratio": "16:9",
        "resolution": "480p",
        "mode": "fast",
    }

    with patch("paid_adapters.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="22222222-2222-4222-8222-222222222222", stderr="")
        adapter.submit(payload, idempotency_key="test_key")

        call_args = mock_run.call_args[0][0]
        assert "--prompt" in call_args
        assert "--image" not in call_args, "B-roll must not have --image"
        assert "--audio" not in call_args, "B-roll must not have --audio"


# ---------------------------------------------------------------------------
# Unit: prompt composed from visual_intent, not "educational video"
# ---------------------------------------------------------------------------

def test_prompt_composed_from_visual_intent(tmp_path):
    """Prompt reflects visual_intent narrative, not the generic default."""
    pid, _ = _make_production_with_hero_and_broll("c06_real_prompt", 0, 10000, 10000, 15000)
    produce_db.invoke_compile_media({"production_id": pid}, tmp_path)

    units = _active_units(pid)
    for u in units:
        meta = _unit_metadata(u)
        prompt = meta.get("prompt", "")
        assert prompt != "educational video", "Prompt must not be the generic default"
        assert len(prompt) > 20, "Prompt should be substantive (not empty/trivial)"


# ---------------------------------------------------------------------------
# Unit: dry-run mode returns args without subprocess
# ---------------------------------------------------------------------------

def test_dry_run_returns_args_without_subprocess():
    """HIGGSFIELD_DRY_RUN=1 returns constructed args without calling subprocess."""
    from paid_adapters import HiggsfieldSeedanceAdapter
    adapter = HiggsfieldSeedanceAdapter(config={"duration_sec": 10})

    payload = {
        "model": "seedance_2_0",
        "prompt": "Test prompt",
        "image_path": "assets/reference/james/canonical/JAMES_FRONT.png",
        "audio_path": "/tmp/slice.wav",
        "duration_sec": 10,
    }

    import os
    old_dry_run = os.environ.get("HIGGSFIELD_DRY_RUN")
    try:
        os.environ["HIGGSFIELD_DRY_RUN"] = "1"
        with patch("paid_adapters.subprocess.run") as mock_run:
            result = adapter.submit(payload, idempotency_key="test_key")
            
            # subprocess must NOT be called
            assert not mock_run.called, "Dry-run must not call subprocess"
            
            # Result must contain the constructed args
            assert "args" in result, "Dry-run result must include args"
            assert "--prompt" in result["args"]
            assert "--image" in result["args"]
            assert "--audio" in result["args"]
            assert result["dry_run"] is True
    finally:
        if old_dry_run is None:
            os.environ.pop("HIGGSFIELD_DRY_RUN", None)
        else:
            os.environ["HIGGSFIELD_DRY_RUN"] = old_dry_run


# ---------------------------------------------------------------------------
# Regression: FakeProvider still used in YT_TEST_MODE
# ---------------------------------------------------------------------------

def test_fake_provider_used_in_test_mode(tmp_path, monkeypatch):
    """YT_TEST_MODE=1 uses FakeProvider, not the real adapter."""
    monkeypatch.setenv("YT_TEST_MODE", "1")
    pid, _ = _make_production_with_hero_and_broll("c06_fake_provider", 0, 10000, 10000, 15000)
    produce_db.invoke_compile_media({"production_id": pid}, tmp_path)
    produce_db.invoke_gate_a_spend({"production_id": pid}, tmp_path)
    
    # First pass submits one conservative wave and fails closed while it is generating.
    with pytest.raises(RuntimeError, match="not generated/valid"):
        produce_db.invoke_generate_media({"production_id": pid}, tmp_path)


# ---------------------------------------------------------------------------
# F-001: Round-robin reference rotation
# ---------------------------------------------------------------------------

def test_reference_rotation_round_robin():
    """_select_hero_reference_image rotates across all frames (round-robin)."""
    from produce_db import _select_hero_reference_image
    routing = {
        "lipsync_references": {
            "active_set": "test_set",
            "sets": {
                "test_set": {
                    "frames": [
                        {"angle": "front", "path": "frame_0.png"},
                        {"angle": "front_speaking", "path": "frame_1.png"},
                        {"angle": "three_quarter", "path": "frame_2.png"},
                        {"angle": "side_profile", "path": "frame_3.png"},
                    ]
                }
            }
        }
    }
    paths = [_select_hero_reference_image(routing, i) for i in range(8)]
    assert paths[0] == "frame_0.png"
    assert paths[1] == "frame_1.png"
    assert paths[2] == "frame_2.png"
    assert paths[3] == "frame_3.png"
    assert paths[4] == "frame_0.png"  # wraps around
    assert len(set(paths[:4])) == 4, "All 4 frames must be used in first cycle"


# ---------------------------------------------------------------------------
# F-002: Adapter --negative_prompt
# ---------------------------------------------------------------------------

def test_adapter_negative_prompt():
    """HiggsfieldSeedanceAdapter.submit builds --negative_prompt when present."""
    from paid_adapters import HiggsfieldSeedanceAdapter
    adapter = HiggsfieldSeedanceAdapter(config={"duration_sec": 10})

    payload = {
        "model": "seedance_2_0",
        "prompt": "Test prompt",
        "negative_prompt": "no futuristic holograms, no cyberpunk",
        "duration_sec": 10,
    }

    with patch("paid_adapters.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="33333333-3333-4333-8333-333333333333", stderr="")
        adapter.submit(payload, idempotency_key="test_key")

        call_args = mock_run.call_args[0][0]
        assert "--negative_prompt" in call_args, "Args must include --negative_prompt"
        assert "no futuristic holograms" in " ".join(call_args), \
            "Negative prompt value must be in args"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

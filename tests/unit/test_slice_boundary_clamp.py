"""Unit test: speech-bound overshoot clamp in slice_continuous_lipsync.py.

Reproduces the 1ms rounding divergence and verifies the clamp:
- Overshoot ≤ 96 samples (2ms): clamped to master_duration_samples, no error
- Overshoot > 96 samples: still raises ValueError
- Negative ss_start: still raises ValueError  (never clamped)

Uses a synthetic master audio generated via FFmpeg lavfi to reproduce
the exact boundary condition from prod_880997f34e9a4d87ac6e951cc011ed43.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as _db
from production_repo import register_artifact
from timeline_utils import MASTER_SAMPLE_RATE, ms_to_samples

# The exact divergence magnitude from the incident
OVERSHOOT_1MS_SAMPLES = 48   # 1ms at 48kHz (proven divergence)
CLAMP_TOLERANCE_SAMPLES = 96  # 2ms tolerance per spec
MASTER_MS = 192130           # truncation path: int(192.1308 * 1000)
SPAN_MS = 192131             # round-up path: int(round(192.1308, 3) * 1000)


@pytest.fixture
def db():
    """Set up a minimal production DB with a synthetic master audio."""
    db_path = tempfile.mktemp(suffix=".db")
    _db._db_path_override = db_path
    _db.migrate(db_path)

    prod = _db.ensure_production("test_clamp_sprint", video_type="short", db_path=db_path)

    # Create a synthetic master audio of exactly MASTER_MS duration
    # at MASTER_SAMPLE_RATE (mono, 16-bit PCM)
    master_dir = Path(tempfile.mkdtemp(prefix="master_audio_"))
    master_path = master_dir / "continuous.wav"
    dur_sec = MASTER_MS / 1000.0  # 192.130 seconds
    result = subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"anullsrc=channel_layout=mono:sample_rate={MASTER_SAMPLE_RATE}:duration={dur_sec:.6f}",
        "-acodec", "pcm_s16le",
        "-ar", str(MASTER_SAMPLE_RATE),
        "-ac", "1",
        str(master_path),
    ], capture_output=True, text=True)
    if result.returncode != 0:
        pytest.skip(f"FFmpeg not available: {result.stderr}")

    assert master_path.exists(), f"Master audio not created: {master_path}"

    art = register_artifact(
        prod["id"], master_path, kind="tts_master",
        extra_metadata={"test_master": True},
        db_path=db_path,
    )

    yield {"prod": prod, "db_path": db_path, "master_artifact_id": art["id"], "master_path": master_path}

    # Cleanup
    _db._db_path_override = None
    import shutil
    shutil.rmtree(master_dir, ignore_errors=True)
    try:
        os.unlink(db_path)
    except OSError:
        pass


def _call_materialize_slices(db, bounds_list):
    """Helper: call materialize_hero_slot_slices with given bounds, return results."""
    from scripts.slice_continuous_lipsync import materialize_hero_slot_slices

    # Create a temp output dir
    output_dir = Path(tempfile.mkdtemp(prefix="hero_slices_"))

    try:
        results = materialize_hero_slot_slices(
            production_id=db["prod"]["id"],
            master_artifact_id=db["master_artifact_id"],
            slot_bounds=bounds_list,
            db_path=db["db_path"],
        )
        return results
    finally:
        import shutil
        shutil.rmtree(output_dir, ignore_errors=True)


def test_overshoot_1ms_clamped(db):
    """1ms overshoot (48 samples) is clamped, not rejected."""
    master_dur_samples = ms_to_samples(MASTER_MS)  # 9222240

    bounds = [{
        "render_unit_id": "test_unit_1ms",
        "speech_start_sample": 0,
        "speech_end_sample": ms_to_samples(SPAN_MS),       # 9222288 — overshoots by 48
        "generation_start_sample": 0,
        "generation_end_sample": ms_to_samples(SPAN_MS),   # 9222288
    }]
    # Should not raise — clamp absorbs the 1ms drift
    results = _call_materialize_slices(db, bounds)
    assert len(results) == 1
    # Verify the clamp brought speech_end_sample down to master duration
    assert results[0]["speech_end_sample"] == master_dur_samples, (
        f"Expected clamp to {master_dur_samples}, got {results[0]['speech_end_sample']}"
    )


def test_overshoot_2ms_clamped(db):
    """2ms overshoot (96 samples, exactly at tolerance boundary) is clamped."""
    master_dur_samples = ms_to_samples(MASTER_MS)
    overshoot_end = master_dur_samples + CLAMP_TOLERANCE_SAMPLES

    bounds = [{
        "render_unit_id": "test_unit_2ms",
        "speech_start_sample": 0,
        "speech_end_sample": overshoot_end,
    }]
    results = _call_materialize_slices(db, bounds)
    assert len(results) == 1
    assert results[0]["speech_end_sample"] == master_dur_samples, (
        f"Expected clamp to {master_dur_samples}, got {results[0]['speech_end_sample']}"
    )


def test_overshoot_excessive_still_raises(db):
    """Overshoot > CLAMP_TOLERANCE_SAMPLES still raises ValueError."""
    master_dur_samples = ms_to_samples(MASTER_MS)
    overshoot_end = master_dur_samples + CLAMP_TOLERANCE_SAMPLES + 1  # 97 samples, just over

    bounds = [{
        "render_unit_id": "test_unit_excessive",
        "speech_start_sample": 0,
        "speech_end_sample": overshoot_end,
    }]
    with pytest.raises(ValueError, match="speech bounds"):
        _call_materialize_slices(db, bounds)


def test_negative_start_still_raises(db):
    """Negative ss_start must never be clamped — it indicates a real bug."""
    bounds = [{
        "render_unit_id": "test_unit_neg_start",
        "speech_start_sample": -1,
        "speech_end_sample": ms_to_samples(MASTER_MS),
    }]
    with pytest.raises(ValueError, match="speech_start.*negative"):
        _call_materialize_slices(db, bounds)


def test_overshoot_tolerance_constant_defined(db):
    """Verify the CLAMP_TOLERANCE_SAMPLES constant exists in the module."""
    import scripts.slice_continuous_lipsync as scl
    assert hasattr(scl, "CLAMP_TOLERANCE_SAMPLES"), "CLAMP_TOLERANCE_SAMPLES constant not found"
    assert scl.CLAMP_TOLERANCE_SAMPLES == 96, (
        f"Expected CLAMP_TOLERANCE_SAMPLES=96, got {scl.CLAMP_TOLERANCE_SAMPLES}"
    )

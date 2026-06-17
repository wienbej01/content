"""Systemic regression: assemble derives audio/words requirements from the authoritative
audio_policy (DB/plan contract), NOT from re-inferring via the media file extension.

The failure this locks: in continuous_voiceover mode, silent local_graphic image segments
(audio_policy=strip/post_overlay, words=0) were wrongly rejected with 'image media requires
audio field' and 'words must be a positive integer'. The narration is a single master track;
these are silent visuals under it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import assemble


def _png(tmp_path, name="card.png"):
    """Create a tiny PNG fixture."""
    import subprocess
    p = tmp_path / name
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=navy:s=320x240:d=1",
                    "-frames:v", "1", str(p)], capture_output=True, check=True)
    return p


def _base_manifest(media_rel, audio_policy, words, continuous=True, asset_type="local_graphic"):
    return {
        "id": "proj",
        "narration_mode": "continuous_voiceover" if continuous else "segment_tts",
        "segments": [{
            "clip_id": "proj::B003::B003-s0", "id": "proj::B003::B003-s0",
            "source_beat_id": "B003", "segment_id": "002",
            "media": media_rel, "audio_policy": audio_policy, "asset_type": asset_type,
            "words": words, "timing_in": 0.0, "timing_out": 5.0, "duration_required": 5.0,
        }],
        "pacing": {"reference": 0, "baseline_speed": 1.0},
    }


def test_continuous_silent_image_segment_validates(tmp_path):
    """A local_graphic PNG with audio_policy=strip, words=0, continuous mode → VALID (no audio needed)."""
    png = _png(tmp_path)
    m = _base_manifest(png.name, "BROLL_FLEX", 0, continuous=True)
    errors = assemble.validate_manifest(m, tmp_path)
    assert errors == [], f"silent continuous graphic should validate: {errors}"


def test_post_overlay_image_segment_validates(tmp_path):
    """audio_policy=post_overlay image in continuous mode → VALID."""
    png = _png(tmp_path)
    m = _base_manifest(png.name, "post_overlay", 0, continuous=True)
    errors = assemble.validate_manifest(m, tmp_path)
    assert errors == [], f"post_overlay graphic should validate: {errors}"


def test_segment_tts_image_still_needs_audio(tmp_path):
    """In segment_tts (non-continuous) mode, an image segment STILL needs its own audio."""
    png = _png(tmp_path)
    m = _base_manifest(png.name, "BROLL_FLEX", 5, continuous=False)  # words present, but no audio
    errors = assemble.validate_manifest(m, tmp_path)
    assert any("image media requires" in e for e in errors), \
        f"segment_tts image without audio should error: {errors}"


def test_segment_tts_zero_words_still_errors(tmp_path):
    """In segment_tts mode, words=0 is still an error (every segment carries narration)."""
    png = _png(tmp_path)
    m = _base_manifest(png.name, "BROLL_FLEX", 0, continuous=False)
    errors = assemble.validate_manifest(m, tmp_path)
    assert any("words" in e for e in errors), f"segment_tts words=0 should error: {errors}"


def test_continuous_zero_words_ok(tmp_path):
    """In continuous mode, a silent graphic with words=0 is valid."""
    png = _png(tmp_path)
    m = _base_manifest(png.name, "BROLL_FLEX", 0, continuous=True)
    errors = assemble.validate_manifest(m, tmp_path)
    assert not any("words" in e for e in errors), f"continuous words=0 should be ok: {errors}"

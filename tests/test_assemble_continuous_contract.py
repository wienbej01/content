"""Regression coverage for clip-contract-driven continuous assembly."""
import json
import subprocess
from pathlib import Path

import pytest

from scripts import assemble


def _run_ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y", *args], capture_output=True, check=True)


def _probe_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def test_continuous_speed_alignment_never_measures_segment_media(monkeypatch, tmp_path):
    def fail_measure(*args, **kwargs):
        raise AssertionError("continuous mode must not measure per-segment media pace")

    monkeypatch.setattr(assemble, "measure_pace", fail_measure)
    speeds, wps, target = assemble.compute_speeds(
        [{"media": "card.png", "audio_policy": "strip", "words": 10}],
        {"reference": 0, "baseline_speed": 1.0}, tmp_path,
        narration_mode="continuous_voiceover",
    )

    assert speeds == [1.0]
    assert wps == [None]
    assert target is None


def test_continuous_local_graphic_uses_clip_timing_not_png_probe_or_parent_map(tmp_path):
    duration = 1.2
    png = tmp_path / "card.png"
    audio = tmp_path / "continuous.wav"
    _run_ffmpeg("-f", "lavfi", "-i", "color=c=navy:s=320x180", "-frames:v", "1", str(png))
    _run_ffmpeg("-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}", str(audio))

    timing_map = tmp_path / "beat_timing_map.json"
    timing_map.write_text(json.dumps({
        "total_duration": 3.0,
        "beats": [{"beat_id": "B001", "start": 0.0, "end": 3.0}],
    }))
    manifest = {
        "id": "continuous_still_contract",
        "narration_mode": "continuous_voiceover",
        "continuous_audio": audio.name,
        "beat_timing_map": timing_map.name,
        "segments": [{
            "id": "proj::B001::whole",
            "media": png.name,
            "asset_type": "local_graphic",
            "audio_policy": "strip",
            "words": 0,
            "timing_in": 0.0,
            "timing_out": duration,
            "duration_required": duration,
        }],
        "pacing": {"reference": 0, "baseline_speed": 1.0},
        "music": {"enabled": False},
        "brand": {},
        "render": {"fps": 24, "crf": 28, "grade": "null"},
        "output": {"directory": "out", "prefix": "result"},
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    log = assemble.assemble(str(manifest_path), formats=["16x9"])

    normalized = tmp_path / "out" / "_tmp" / "16x9" / "cont_seg_0.mp4"
    final = Path(log["formats"]["16x9"]["path"])
    assert final.exists()
    assert _probe_duration(normalized) == pytest.approx(duration, abs=0.08)
    assert _probe_duration(final) == pytest.approx(duration, abs=0.25)

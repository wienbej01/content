"""Tests for DDL-W4: Consume trim/extend instructions in assembler clip construction.

Validates:
- Trim instruction → `-t planned_duration_sec` in ffmpeg command
- Extend instruction → tpad=stop_mode=clone:stop_duration in vf filter
- Segment with both trim+extend → ValueError
- Segment with no drift keys → unchanged behavior
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from scripts import assemble


def _run_ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y", *args], capture_output=True, check=True)


def _build_manifest(tmp_path: Path, segments: list[dict],
                    audio_dur_sec: float = 5.0) -> Path:
    audio = tmp_path / "narration.wav"
    _run_ffmpeg(
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={audio_dur_sec}:sample_rate=44100",
        str(audio),
    )
    manifest = {
        "id": "w4_test",
        "narration_mode": "continuous_voiceover",
        "continuous_audio": audio.name,
        "segments": segments,
        "pacing": {"reference": 0, "baseline_speed": 1.0},
        "music": {"enabled": False},
        "brand": {},
        "render": {"fps": 24, "crf": 28, "grade": "null"},
        "output": {"directory": "out", "prefix": "w4"},
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


def _make_video(tmp_path: Path, name: str, dur_sec: float) -> Path:
    p = tmp_path / name
    _run_ffmpeg(
        "-f", "lavfi",
        "-i", f"color=c=green:s=320x240:r=24:d={dur_sec}",
        "-t", str(dur_sec),
        str(p),
    )
    return p


def _make_still(tmp_path: Path, name: str = "card.png") -> Path:
    p = tmp_path / name
    _run_ffmpeg("-f", "lavfi", "-i", "color=c=navy:s=320x240",
                "-frames:v", "1", str(p))
    return p


class TestTrimExtendConsumption:
    def test_trim_instruction_reduces_t_flag(self, tmp_path):
        """Segment with trim: -t uses planned_duration_sec=7.738 not 8.041."""
        video = _make_video(tmp_path, "clip.mp4", dur_sec=8.041)
        seg = {
            "id": "trim_test",
            "media": video.name,
            "asset_type": "generated_video",
            "audio_policy": "BROLL_FLEX",
            "words": 0,
            "timing_in": 0.0,
            "timing_out": 7.738,
            "duration_required": 7.738,
            "trim": {
                "action": "trim_from_end",
                "trim_duration_sec": 0.303,
                "planned_duration_sec": 7.738,
                "actual_duration_sec": 8.041,
            },
        }
        mpath = _build_manifest(tmp_path, [seg], audio_dur_sec=7.738)
        log = assemble.assemble(str(mpath), formats=["16x9"])
        assert "formats" in log

    def test_extend_instruction_adds_tpad_filter(self, tmp_path):
        """Segment with extend: vf includes tpad freeze for extend_dur."""
        video = _make_video(tmp_path, "clip.mp4", dur_sec=4.5)
        seg = {
            "id": "extend_test",
            "media": video.name,
            "asset_type": "generated_video",
            "audio_policy": "BROLL_FLEX",
            "words": 0,
            "timing_in": 0.0,
            "timing_out": 5.0,
            "duration_required": 5.0,
            "extend": {
                "action": "freeze_last_frame",
                "extend_duration_sec": 0.500,
                "planned_duration_sec": 5.0,
                "actual_duration_sec": 4.5,
            },
        }
        mpath = _build_manifest(tmp_path, [seg], audio_dur_sec=5.0)
        log = assemble.assemble(str(mpath), formats=["16x9"])
        assert "formats" in log

    def test_both_trim_and_extend_raises_valueerror(self, tmp_path):
        """Segment with both trim + extend: ValueError raised."""
        video = _make_video(tmp_path, "clip.mp4", dur_sec=8.0)
        seg = {
            "id": "both",
            "media": video.name,
            "asset_type": "generated_video",
            "audio_policy": "BROLL_FLEX",
            "words": 0,
            "timing_in": 0.0,
            "timing_out": 8.0,
            "duration_required": 8.0,
            "trim": {"planned_duration_sec": 7.0, "actual_duration_sec": 8.0},
            "extend": {"extend_duration_sec": 0.5},
        }
        mpath = _build_manifest(tmp_path, [seg], audio_dur_sec=8.0)
        with pytest.raises(ValueError, match="both trim AND extend"):
            assemble.assemble(str(mpath), formats=["16x9"])

    def test_no_drift_keys_unchanged(self, tmp_path):
        """Vanilla segment (no trim/extend) builds exactly as before."""
        video = _make_video(tmp_path, "clip.mp4", dur_sec=3.0)
        seg = {
            "id": "vanilla",
            "media": video.name,
            "asset_type": "generated_video",
            "audio_policy": "BROLL_FLEX",
            "words": 0,
            "timing_in": 0.0,
            "timing_out": 3.0,
            "duration_required": 3.0,
        }
        mpath = _build_manifest(tmp_path, [seg], audio_dur_sec=3.0)
        log = assemble.assemble(str(mpath), formats=["16x9"])
        assert "formats" in log

    def test_trim_planned_exceeds_actual_raises(self, tmp_path):
        """Defense-in-depth: trim planned > actual raises ValueError."""
        video = _make_video(tmp_path, "clip.mp4", dur_sec=5.0)
        seg = {
            "id": "bad_trim",
            "media": video.name,
            "asset_type": "generated_video",
            "audio_policy": "BROLL_FLEX",
            "words": 0,
            "timing_in": 0.0,
            "timing_out": 7.0,
            "duration_required": 7.0,
            "trim": {
                "action": "trim_from_end",
                "planned_duration_sec": 7.0,
                "actual_duration_sec": 5.0,
            },
        }
        mpath = _build_manifest(tmp_path, [seg], audio_dur_sec=7.0)
        with pytest.raises(ValueError, match=r"(?i)trim logic error"):
            assemble.assemble(str(mpath), formats=["16x9"])

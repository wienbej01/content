"""Tests for DDL-W3: Frame-precision aggregate assembly tolerance.

Validates that:
- Frame-precision quality gate rejects drift > 1/FPS
- Legacy 3.0s check exists as separate CONSISTENCY_... guard
- Drift-free production passes both checks
- Boundary cases at frame precision edge
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts import assemble


def _run_ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y", *args], capture_output=True, check=True)


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def _make_manifest_contract(tmp_path: Path, clip_total_sec: float,
                            audio_dur_sec: float) -> Path:
    """Build a minimal continuous_voiceover manifest with controlled durations.

    clip_total_sec is the sum of timing_out across segments.
    audio_dur_sec is the probe_dur of the generated continuous audio.
    """
    audio = tmp_path / "narration.wav"
    _run_ffmpeg(
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={audio_dur_sec}:sample_rate=44100",
        str(audio),
    )

    half = clip_total_sec / 2
    seg_a = tmp_path / "seg_a.mp4"
    _run_ffmpeg(
        "-f", "lavfi",
        "-i", f"color=c=red:s=320x240:r=30:d={half}",
        "-t", str(half),
        str(seg_a),
    )
    seg_b = tmp_path / "seg_b.mp4"
    _run_ffmpeg(
        "-f", "lavfi",
        "-i", f"color=c=blue:s=320x240:r=30:d={half}",
        "-t", str(half),
        str(seg_b),
    )

    manifest = {
        "id": "w3_contract_test",
        "narration_mode": "continuous_voiceover",
        "continuous_audio": audio.name,
        "segments": [
            {
                "id": "seg_a",
                "media": seg_a.name,
                "asset_type": "generated_video",
                "audio_policy": "BROLL_FLEX",
                "words": 0,
                "timing_in": 0.0,
                "timing_out": half,
                "duration_required": half,
            },
            {
                "id": "seg_b",
                "media": seg_b.name,
                "asset_type": "generated_video",
                "audio_policy": "BROLL_FLEX",
                "words": 0,
                "timing_in": half,
                "timing_out": clip_total_sec,
                "duration_required": half,
            },
        ],
        "pacing": {"reference": 0, "baseline_speed": 1.0},
        "music": {"enabled": False},
        "brand": {},
        "render": {"fps": 30, "crf": 28, "grade": "null"},
        "output": {"directory": "out", "prefix": "w3"},
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


class TestFramePrecisionQualityGate:
    """W3 acceptance gates for aggregate timeline duration check."""

    def test_delta_within_frame_precision_passes(self, tmp_path):
        """177.400s clips vs 177.398s audio => delta=2ms < 33ms at 30fps. Pass."""
        mpath = _make_manifest_contract(tmp_path, clip_total_sec=177.400,
                                        audio_dur_sec=177.398)
        log = assemble.assemble(str(mpath), formats=["16x9"])
        assert "formats" in log
        assert "16x9" in log["formats"]

    def test_delta_exceeds_frame_precision_fails_quality_gate(self, tmp_path):
        """177.400s clips vs 177.500s audio => delta=100ms > 33ms at 30fps. Fail."""
        mpath = _make_manifest_contract(tmp_path, clip_total_sec=177.400,
                                        audio_dur_sec=177.500)
        with pytest.raises(RuntimeError, match=r"AGGREGATE_TIMELINE_QUALITY_GATE_FAILED"):
            assemble.assemble(str(mpath), formats=["16x9"])

    def test_large_delta_triggers_consistency_guard_not_quality_gate(self, tmp_path):
        """Delta=3.5s > 3.0s: consistency guard fires, not quality gate."""
        mpath = _make_manifest_contract(tmp_path, clip_total_sec=180.0,
                                        audio_dur_sec=183.5)
        with pytest.raises(RuntimeError,
                           match=r"CONSISTENCY_ASSEMBLY_MANIFEST_DB_MISMATCH"):
            assemble.assemble(str(mpath), formats=["16x9"])

    def test_delta_2s_triggers_quality_gate_not_consistency(self, tmp_path):
        """Delta=2.0s: > 33ms but < 3.0s -> quality gate (not consistency guard)."""
        mpath = _make_manifest_contract(tmp_path, clip_total_sec=180.0,
                                        audio_dur_sec=182.0)
        with pytest.raises(RuntimeError,
                           match=r"AGGREGATE_TIMELINE_QUALITY_GATE_FAILED"):
            assemble.assemble(str(mpath), formats=["16x9"])

    def test_evidence_json_emitted_in_error(self, tmp_path):
        """Both error types include evidence JSON with proper fields."""
        mpath = _make_manifest_contract(tmp_path, clip_total_sec=180.0,
                                        audio_dur_sec=180.1)
        with pytest.raises(RuntimeError) as excinfo:
            assemble.assemble(str(mpath), formats=["16x9"])
        msg = str(excinfo.value)
        assert "evidence=" in msg
        ev_start = msg.index("evidence=") + len("evidence=")
        ev = json.loads(msg[ev_start:])
        assert ev["check"] == "aggregate_timeline_duration_gate"
        assert "contract_total_sec" in ev
        assert "total_nar_dur_sec" in ev
        assert "delta_sec" in ev
        assert ev["fps"] == 30

    def test_drift_free_normal_manifest_passes(self, tmp_path):
        """3.0s clip vs 3.0s audio with no drift passes both checks."""
        mpath = _make_manifest_contract(tmp_path, clip_total_sec=3.0,
                                        audio_dur_sec=3.0)
        log = assemble.assemble(str(mpath), formats=["16x9"])
        assert "formats" in log
        assert "16x9" in log["formats"]

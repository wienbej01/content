"""Tests for TKT-104 SyncNet scorer drift check."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "evals" / "check_sync_scorer_drift.py"

sys.path.insert(0, str(ROOT))

from scripts.evals import check_sync_scorer_drift


def _valid_fixture(name: str, tmp_path: Path) -> Path:
    out = tmp_path / f"{name}.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", f"color=c=blue:s=320x240:d=5:r=1",
         "-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=16000:d=5",
         "-shortest", str(out)],
        check=True,
    )
    return out


class TestPinnedBaselines:
    def test_pinned_baselines_complete(self):
        assert len(check_sync_scorer_drift._PINNED) >= 3
        for name, expected in check_sync_scorer_drift._PINNED.items():
            assert "offset_ms" in expected
            assert "confidence" in expected
            assert "face_track_found" in expected


class TestDriftCheckInvocation:
    def test_script_help(self):
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True, text=True,
        )
        assert r.returncode == 0

    def test_script_no_drift(self, tmp_path: Path, monkeypatch):
        """Run the drift check against the fixture backend with no drift."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "reports").mkdir()
        pin_file = tmp_path / "test.pin"
        baseline = {
            "freeze_clip": {"offset_ms": 10.0, "confidence": 0.80, "face_track_found": True},
        }
        pin_file.write_text(json.dumps(baseline))
        monkeypatch.setattr(check_sync_scorer_drift, "_PINNED", baseline)

        r = subprocess.run(
            [sys.executable, str(SCRIPT),
             "--fixtures", "freeze_clip",
             "--tolerance", "40",
             "--json", str(tmp_path / "reports" / "drift.json"),
             "--pin-file", str(pin_file)],
            capture_output=True, text=True,
        )
        assert r.returncode == 0, f"stdout={r.stdout!r} stderr={r.stderr!r}"

    def test_script_drift_detected(self, tmp_path: Path):
        """If pin is set far from fixture value, drift check should exit 2."""
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.chdir(tmp_path)
        (tmp_path / "reports").mkdir()
        drifted = {
            "freeze_clip": {"offset_ms": 500.0, "confidence": 0.80, "face_track_found": True},
        }
        pin_file = tmp_path / "test.pin"
        pin_file.write_text(json.dumps(drifted))
        monkeypatch.setattr(check_sync_scorer_drift, "_PINNED", drifted)

        r = subprocess.run(
            [sys.executable, str(SCRIPT),
             "--fixtures", "freeze_clip",
             "--tolerance", "40",
             "--json", str(tmp_path / "reports" / "drift.json"),
             "--pin-file", str(pin_file)],
            capture_output=True, text=True,
        )
        assert r.returncode == 2

    def test_script_output_json(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "reports").mkdir()
        baseline = {
            "freeze_clip": {"offset_ms": 10.0, "confidence": 0.80, "face_track_found": True},
        }
        pin_file = tmp_path / "test.pin"
        pin_file.write_text(json.dumps(baseline))
        monkeypatch.setattr(check_sync_scorer_drift, "_PINNED", baseline)

        out_json = tmp_path / "reports" / "drift.json"
        r = subprocess.run(
            [sys.executable, str(SCRIPT),
             "--fixtures", "freeze_clip",
             "--json", str(out_json),
             "--pin-file", str(pin_file)],
            capture_output=True, text=True,
        )
        assert r.returncode == 0
        data = json.loads(out_json.read_text())
        assert data["drift_detected"] is False
        assert len(data["results"]) == 1
        assert data["results"][0]["passed"] is True


class TestGenerateFixture:
    def test_generates_mp4(self, tmp_path: Path):
        video = check_sync_scorer_drift._generate_fixture(tmp_path, "freeze_clip")
        assert video.exists()
        assert video.suffix == ".mp4"

    def test_deterministic(self, tmp_path: Path):
        v1 = check_sync_scorer_drift._generate_fixture(tmp_path / "a", "freeze_clip")
        v2 = check_sync_scorer_drift._generate_fixture(tmp_path / "b", "freeze_clip")
        assert v1.read_bytes() == v2.read_bytes()

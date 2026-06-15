#!/usr/bin/env python3
"""tests/test_uci04_assemble_db.py — UCI-04: assemble reads clip paths from clip DB."""
import json
import subprocess
import sys
import warnings
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import clip_db


def _make_clip(path, duration=2.0, with_audio=True):
    """Create a tiny mp4 clip via ffmpeg."""
    path.parent.mkdir(parents=True, exist_ok=True)
    audio_args = ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"] if with_audio else []
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=blue:s=1920x1080:d={duration}:r=24"]
        + audio_args
        + ["-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
           "-shortest", "-t", str(duration), str(path)],
        capture_output=True,
    )
    assert path.exists(), f"Failed to create fixture: {path}"


def _make_audio(path, duration=2.0):
    """Create a tiny wav audio file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"sine=frequency=440:duration={duration}",
         "-ar", "48000", "-ac", "2", str(path)],
        capture_output=True,
    )


def _minimal_manifest(tmp_path, segments, project_id="test_proj"):
    """Write a minimal manifest and return its path."""
    manifest = {
        "id": project_id,
        "segments": segments,
        "pacing": {"reference": 0, "baseline_speed": 1.0},
        "render": {"fps": 24, "crf": 23},
        "output": {"directory": str(tmp_path / "out"), "prefix": project_id},
    }
    mp = tmp_path / "manifest.json"
    mp.write_text(json.dumps(manifest))
    return mp


def _register_clip(project_id, clip_id, output_path, status="valid", db_path=None):
    """Insert a clip row into the DB."""
    clip_db.init_db(db_path)
    conn = clip_db.get_db(db_path)
    conn.execute(
        """INSERT INTO clips (clip_id, project_id, source_beat_id, production_beat_id,
           output_path, asset_type, model, audio_policy, lipsync_required,
           required_start_sec, required_end_sec, required_dur_sec,
           status, status_reason, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (clip_id, project_id, "B001", "B001", str(output_path),
         "generated_video", "kling", "voiceover", 0,
         0.0, 2.0, 2.0, status, None, "2026-01-01T00:00:00+00:00"))
    conn.commit()
    conn.close()


class TestAssembleResolvesPathFromDB:
    """UCI-04 AC1: segment with clip_id resolves media via clip_db.get_path."""

    def test_assemble_resolves_path_from_db(self, tmp_path):
        """clip_id in segment → media resolved from DB path, not manifest field."""
        clip_path = tmp_path / "db_clip.mp4"
        _make_clip(clip_path)
        audio_path = tmp_path / "narration.wav"
        _make_audio(audio_path, 1.5)

        project_id = "test_proj"
        clip_id = "test_proj::B001::whole"
        _register_clip(project_id, clip_id, str(clip_path))

        seg = {
            "clip_id": clip_id,
            "media": "nonexistent.mp4",  # would fail if used
            "words": 10,
            "audio": str(audio_path),
        }
        mp = _minimal_manifest(tmp_path, [seg], project_id)

        import assemble
        # Patch validate_manifest to skip file-exists check on the dummy media field
        with patch.object(assemble, "validate_manifest", return_value=[]):
            log = assemble.assemble(str(mp), formats=["16x9"], tmp_base=str(tmp_path / "_tmp"))

        assert log["formats"]["16x9"]["path"]
        assert Path(log["formats"]["16x9"]["path"]).exists()


class TestAssembleBlockedWhenClipNotValid:
    """UCI-04 AC2: non-valid clip blocks assembly."""

    def test_assemble_blocked_when_clip_not_valid(self, tmp_path):
        """A clip in 'ordered' status blocks assembly with actionable error."""
        clip_path = tmp_path / "ordered_clip.mp4"
        _make_clip(clip_path)

        project_id = "test_proj"
        clip_id = "test_proj::B001::whole"
        _register_clip(project_id, clip_id, str(clip_path), status="ordered")

        seg = {
            "clip_id": clip_id,
            "media": str(clip_path),
            "words": 10,
            "audio": str(tmp_path / "narr.wav"),
        }
        _make_audio(tmp_path / "narr.wav", 1.5)
        mp = _minimal_manifest(tmp_path, [seg], project_id)

        import assemble
        with patch.object(assemble, "validate_manifest", return_value=[]):
            with pytest.raises(RuntimeError, match="UCI-04 assembly gate FAILED"):
                assemble.assemble(str(mp), formats=["16x9"], tmp_base=str(tmp_path / "_tmp"))

    def test_assemble_blocked_on_change_request(self, tmp_path):
        """A clip with an open change request blocks assembly."""
        clip_path = tmp_path / "cr_clip.mp4"
        _make_clip(clip_path)

        project_id = "test_proj"
        clip_id = "test_proj::B001::whole"
        _register_clip(project_id, clip_id, str(clip_path), status="valid")

        # Add an open change request
        clip_db.init_db()
        conn = clip_db.get_db()
        conn.execute(
            """INSERT INTO clip_change_requests
               (clip_id, change_type, requested_by, target_step, reason, status, requested_at)
               VALUES (?,?,?,?,?,?,?)""",
            (clip_id, "regenerate", "qa", "generate", "bad quality", "open", "2026-01-01T00:00:00+00:00"))
        conn.commit()
        conn.close()

        seg = {
            "clip_id": clip_id,
            "media": str(clip_path),
            "words": 10,
            "audio": str(tmp_path / "narr.wav"),
        }
        _make_audio(tmp_path / "narr.wav", 1.5)
        mp = _minimal_manifest(tmp_path, [seg], project_id)

        import assemble
        with patch.object(assemble, "validate_manifest", return_value=[]):
            with pytest.raises(RuntimeError, match="UCI-04 assembly gate FAILED"):
                assemble.assemble(str(mp), formats=["16x9"], tmp_base=str(tmp_path / "_tmp"))


class TestAssembleProceedsWhenAllValid:
    """UCI-04 AC3: all clips valid → assembly proceeds."""

    def test_assemble_proceeds_when_all_valid(self, tmp_path):
        """All clips valid in DB → full assembly completes."""
        clip_path = tmp_path / "good_clip.mp4"
        _make_clip(clip_path)
        audio_path = tmp_path / "narration.wav"
        _make_audio(audio_path, 1.5)

        project_id = "test_proj"
        clip_id = "test_proj::B001::whole"
        _register_clip(project_id, clip_id, str(clip_path))

        seg = {
            "clip_id": clip_id,
            "media": str(clip_path),
            "words": 10,
            "audio": str(audio_path),
        }
        mp = _minimal_manifest(tmp_path, [seg], project_id)

        import assemble
        with patch.object(assemble, "validate_manifest", return_value=[]):
            log = assemble.assemble(str(mp), formats=["16x9"], tmp_base=str(tmp_path / "_tmp"))

        assert "16x9" in log["formats"]
        out = Path(log["formats"]["16x9"]["path"])
        assert out.exists()
        assert log["formats"]["16x9"]["duration_s"] > 0


class TestLegacyManifestSkipsDBGate:
    """UCI-04 AC4: manifest without clip_ids → backward compat, skips gate."""

    def test_legacy_manifest_no_clipid_skips_db_gate(self, tmp_path):
        """Legacy manifest (no clip_id on segments) assembles with warning."""
        clip_path = tmp_path / "legacy_clip.mp4"
        _make_clip(clip_path)
        audio_path = tmp_path / "narration.wav"
        _make_audio(audio_path, 1.5)

        seg = {
            "media": str(clip_path),
            "words": 10,
            "audio": str(audio_path),
        }
        mp = _minimal_manifest(tmp_path, [seg], "legacy_proj")

        import assemble
        with patch.object(assemble, "validate_manifest", return_value=[]):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                log = assemble.assemble(str(mp), formats=["16x9"], tmp_base=str(tmp_path / "_tmp"))

        # Should have emitted the legacy warning
        uci_warnings = [x for x in w if "UCI-04" in str(x.message)]
        assert len(uci_warnings) == 1
        assert "legacy mode" in str(uci_warnings[0].message)

        # Assembly should succeed
        assert "16x9" in log["formats"]
        assert Path(log["formats"]["16x9"]["path"]).exists()

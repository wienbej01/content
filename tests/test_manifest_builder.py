#!/usr/bin/env python3
"""tests/test_manifest_builder.py — Tests for scripts/build_manifest.py"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "build_manifest.py"


def _make_clip(path, duration=2.0):
    """Create a tiny valid mp4 clip via ffmpeg."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=black:s=64x64:d={duration}",
         "-c:v", "libx264", "-t", str(duration), str(path)],
        capture_output=True,
    )


def _write_fixtures(tmp_path, beats_plan, beats_timing, total_duration):
    """Write media_plan.json and beat_timing_map.json under tmp_path."""
    plan = {"project_id": "test_proj", "beats": beats_plan}
    (tmp_path / "media_plan.json").write_text(json.dumps(plan))

    narr_dir = tmp_path / "narration"
    narr_dir.mkdir(exist_ok=True)
    timing = {"total_duration": total_duration, "beat_count": len(beats_timing), "beats": beats_timing}
    (narr_dir / "beat_timing_map.json").write_text(json.dumps(timing))


def _run(project_dir, allow_missing=False):
    """Run build_manifest.py, return (returncode, stdout, stderr)."""
    cmd = [sys.executable, str(SCRIPT), str(project_dir)]
    if allow_missing:
        cmd.append("--allow-missing")
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    return r.returncode, r.stdout, r.stderr


class TestManifestBuilder:

    def test_clip_db_contract_overrides_stale_plan_fields(self, tmp_path, monkeypatch):
        """DB path, type, policy, and timing remain authoritative at manifest build."""
        import importlib.util

        sys.path.insert(0, str(ROOT / "scripts"))
        import clip_db

        monkeypatch.setattr(clip_db, "ROOT", tmp_path)
        clip_db.init_db()
        clip = clip_db.order_clip(
            project_id="test_proj", source_beat_id="B011", production_beat_id="B011b",
            segment_id="004_cta", asset_type="local_graphic", model="local_graphic",
            audio_policy="post_overlay", lipsync_required=False,
            required_start_sec=0.0, required_end_sec=2.0,
        )
        media_path = tmp_path / clip["output_path"]
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_bytes(b"PNG_FIXTURE")
        sha = clip_db._sha256_file(media_path)
        clip_db.record_generated(clip["clip_id"], 2.0, 320, 180, False, sha)
        clip_db.mark_valid(clip["clip_id"])

        beats_plan = [{
            "beat_id": "B011b", "source_beat_id": "B011", "clip_id": clip["clip_id"],
            "segment_id": "004_cta", "output_path": "stale/wrong.mp4",
            "asset_type": "generated_video", "audio_policy": "BROLL_FLEX", "final_audio_source": "none", "provider_audio_usage": "discarded", "text_policy": "NO_VISIBLE_TEXT",
            "required_start_sec": None, "required_end_sec": None,
            "narration_text": "",
        }]
        beats_timing = [{"beat_id": "B011", "start": 0.0, "end": 2.0, "duration": 2.0}]
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        _write_fixtures(project_dir, beats_plan, beats_timing, total_duration=2.0)

        spec = importlib.util.spec_from_file_location("build_manifest_db_contract", str(SCRIPT))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.ROOT = tmp_path
        manifest, errors, _warnings = mod.build(project_dir, format_str="teaser")

        assert errors == []
        seg = manifest["segments"][0]
        assert seg["media"] == clip["output_path"]
        assert seg["asset_type"] == "local_graphic"
        assert seg["audio_policy"] == "post_overlay"
        assert seg["timing_in"] == 0.0
        assert seg["timing_out"] == 2.0
        assert seg["duration_required"] == 2.0

    def test_valid_plan_produces_manifest(self, tmp_path):
        """A valid media plan + timing map produces manifest.json with all beats."""
        clip_path = tmp_path / "clips" / "B001.mp4"
        _make_clip(clip_path)
        rel_path = "clips/B001.mp4"

        beats_plan = [{
            "beat_id": "B001", "segment_id": "001_hook",
            "output_path": rel_path, "audio_policy": "BROLL_FLEX", "final_audio_source": "none", "provider_audio_usage": "discarded", "text_policy": "NO_VISIBLE_TEXT",
            "narration_text": "hello world test",
        }]
        beats_timing = [{"beat_id": "B001", "start": 0.0, "end": 5.0, "duration": 5.0}]
        _write_fixtures(tmp_path, beats_plan, beats_timing, total_duration=5.0)
        # Use a format that doesn't require music
        (tmp_path / "state.json").write_text(json.dumps({"format": "teaser"}))

        rc, stdout, stderr = _run(tmp_path)
        assert rc == 0, f"Expected exit 0, got {rc}: {stderr}"

        manifest = json.loads((tmp_path / "manifest.json").read_text())
        assert len(manifest["segments"]) == 1
        seg = manifest["segments"][0]
        assert seg["clip_id"] == "B001"
        assert seg["id"] == "B001"
        assert seg["source_beat_id"] == "B001"
        assert seg["timing_in"] == 0.0
        assert seg["timing_out"] == 5.0
        assert seg["duration_required"] == 5.0
        assert seg["media_sha256"] is not None
        assert "music" in manifest

    def test_missing_beat_fails(self, tmp_path):
        """Timing map total exceeds plan total; expect exit 1 (timeline mismatch).

        UCI-02: The cardinality check (beat in timing_map but not in plan) was
        removed because it breaks on split children. The timeline total check
        remains as the correct validation.
        """
        clip_path = tmp_path / "clips" / "B001.mp4"
        _make_clip(clip_path)

        beats_plan = [{
            "beat_id": "B001", "segment_id": "001_hook",
            "output_path": "clips/B001.mp4", "audio_policy": "BROLL_FLEX", "final_audio_source": "none", "provider_audio_usage": "discarded", "text_policy": "NO_VISIBLE_TEXT",
            "narration_text": "hello",
        }]
        # Timing map has B001 + B002, but plan only has B001
        beats_timing = [
            {"beat_id": "B001", "start": 0.0, "end": 5.0, "duration": 5.0},
            {"beat_id": "B002", "start": 5.0, "end": 10.0, "duration": 5.0},
        ]
        _write_fixtures(tmp_path, beats_plan, beats_timing, total_duration=10.0)

        rc, stdout, stderr = _run(tmp_path)
        assert rc == 1
        assert "Timeline mismatch" in stderr

    def test_duplicate_clip_id_fails(self, tmp_path):
        """Media plan has duplicate clip_id; expect exit 1."""
        clip_path = tmp_path / "clips" / "B001.mp4"
        _make_clip(clip_path)

        beats_plan = [
            {"beat_id": "B001", "clip_id": "proj::B001::s0", "segment_id": "001",
             "output_path": "clips/B001.mp4", "audio_policy": "BROLL_FLEX", "final_audio_source": "none", "provider_audio_usage": "discarded", "text_policy": "NO_VISIBLE_TEXT", "narration_text": "a",
             "required_start_sec": 0.0, "required_end_sec": 2.5},
            {"beat_id": "B001", "clip_id": "proj::B001::s0", "segment_id": "001",
             "output_path": "clips/B001.mp4", "audio_policy": "BROLL_FLEX", "final_audio_source": "none", "provider_audio_usage": "discarded", "text_policy": "NO_VISIBLE_TEXT", "narration_text": "b",
             "required_start_sec": 2.5, "required_end_sec": 5.0},
        ]
        beats_timing = [{"beat_id": "B001", "start": 0.0, "end": 5.0, "duration": 5.0}]
        _write_fixtures(tmp_path, beats_plan, beats_timing, total_duration=5.0)

        rc, stdout, stderr = _run(tmp_path)
        assert rc == 1
        assert "Duplicate" in stderr

    def test_missing_media_file_fails(self, tmp_path):
        """Media plan references nonexistent clip; expect exit 1 without --allow-missing."""
        beats_plan = [{
            "beat_id": "B001", "segment_id": "001_hook",
            "output_path": "nonexistent/B001.mp4", "audio_policy": "BROLL_FLEX", "final_audio_source": "none", "provider_audio_usage": "discarded", "text_policy": "NO_VISIBLE_TEXT",
            "narration_text": "test words here",
        }]
        beats_timing = [{"beat_id": "B001", "start": 0.0, "end": 5.0, "duration": 5.0}]
        _write_fixtures(tmp_path, beats_plan, beats_timing, total_duration=5.0)

        rc, stdout, stderr = _run(tmp_path)
        assert rc == 1
        assert "not found" in stderr.lower()

    def test_timeline_mismatch_fails(self, tmp_path):
        """Beats sum to 5s but timing_map total is 20s; expect exit 1."""
        clip_path = tmp_path / "clips" / "B001.mp4"
        _make_clip(clip_path)

        beats_plan = [{
            "beat_id": "B001", "segment_id": "001",
            "output_path": "clips/B001.mp4", "audio_policy": "BROLL_FLEX", "final_audio_source": "none", "provider_audio_usage": "discarded", "text_policy": "NO_VISIBLE_TEXT",
            "narration_text": "short beat",
        }]
        beats_timing = [{"beat_id": "B001", "start": 0.0, "end": 5.0, "duration": 5.0}]
        _write_fixtures(tmp_path, beats_plan, beats_timing, total_duration=20.0)

        rc, stdout, stderr = _run(tmp_path, allow_missing=True)
        assert rc == 1
        assert "mismatch" in stderr.lower()

    def test_required_overlay_recorded(self, tmp_path):
        """Beat with graphic.required=true has overlay spec in manifest."""
        clip_path = tmp_path / "clips" / "B001.mp4"
        _make_clip(clip_path)

        # Create the overlay asset at ROOT-relative path
        overlay_rel = "assets/overlays/B001_overlay.png"
        overlay_full = ROOT / overlay_rel
        overlay_full.parent.mkdir(parents=True, exist_ok=True)
        overlay_full.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

        beats_plan = [{
            "beat_id": "B001", "segment_id": "001_hook",
            "output_path": "clips/B001.mp4", "audio_policy": "BROLL_FLEX", "final_audio_source": "none", "provider_audio_usage": "discarded", "text_policy": "NO_VISIBLE_TEXT",
            "narration_text": "some words",
            "graphic": {"required": True, "type": "lower_third", "text": "Key Insight",
                        "asset_path": overlay_rel},
        }]
        beats_timing = [{"beat_id": "B001", "start": 0.0, "end": 5.0, "duration": 5.0}]
        _write_fixtures(tmp_path, beats_plan, beats_timing, total_duration=5.0)
        # Use a format that doesn't require music
        (tmp_path / "state.json").write_text(json.dumps({"format": "teaser"}))

        rc, stdout, stderr = _run(tmp_path, allow_missing=True)
        # Cleanup
        overlay_full.unlink(missing_ok=True)
        assert rc == 0, f"Expected exit 0: {stderr}"

        manifest = json.loads((tmp_path / "manifest.json").read_text())
        seg = manifest["segments"][0]
        assert "overlay" in seg
        assert seg["overlay"]["required"] is True
        assert seg["overlay"]["type"] == "lower_third"


class TestBSS04Hardening:
    """BSS-04: Harden manifest, music, and graphics ordering."""

    def test_music_uses_configured_path(self, tmp_path, monkeypatch):
        """Music path comes from constraints.json music.default_path, not dir scan."""
        # Create the configured music file
        music_file = tmp_path / "brand" / "music" / "night_snow.mp3"
        music_file.parent.mkdir(parents=True)
        music_file.write_bytes(b"\x00" * 100)

        # Write constraints.json with explicit default_path
        constraints_dir = tmp_path / "docs" / "channel_universe"
        constraints_dir.mkdir(parents=True)
        constraints = {
            "music": {
                "required_for_formats": ["short", "explainer"],
                "default_path": "brand/music/night_snow.mp3",
                "volume_db": -24,
                "fade_in_sec": 1.0,
                "fade_out_sec": 2.0,
            }
        }
        (constraints_dir / "constraints.json").write_text(json.dumps(constraints))

        # Create project fixtures
        clip_path = tmp_path / "project" / "clips" / "B001.mp4"
        _make_clip(clip_path)
        proj = tmp_path / "project"
        beats_plan = [{
            "beat_id": "B001", "segment_id": "001",
            "output_path": "clips/B001.mp4", "audio_policy": "BROLL_FLEX", "final_audio_source": "none", "provider_audio_usage": "discarded", "text_policy": "NO_VISIBLE_TEXT",
            "narration_text": "test",
        }]
        beats_timing = [{"beat_id": "B001", "start": 0.0, "end": 5.0, "duration": 5.0}]
        _write_fixtures(proj, beats_plan, beats_timing, total_duration=5.0)

        # Monkeypatch ROOT in the module
        import importlib.util
        spec = importlib.util.spec_from_file_location("build_manifest", str(SCRIPT))
        mod = importlib.util.module_from_spec(spec)
        mod.ROOT = tmp_path
        spec.loader.exec_module(mod)
        mod.ROOT = tmp_path

        manifest, errors, warnings = mod.build(proj, format_str="short")
        assert not errors, f"Unexpected errors: {errors}"
        assert manifest["music"]["enabled"] is True
        assert manifest["music"]["path"] == "brand/music/night_snow.mp3"

    def test_music_nondeterministic_directory_scan_rejected(self, tmp_path, monkeypatch):
        """With two MP3s in assets/music but no configured path, music must NOT pick one."""
        # No configured default_path in constraints
        constraints_dir = tmp_path / "docs" / "channel_universe"
        constraints_dir.mkdir(parents=True)
        constraints = {"music": {"required_for_formats": []}}
        (constraints_dir / "constraints.json").write_text(json.dumps(constraints))

        # Put two MP3s in assets/music (old code would pick first)
        music_dir = tmp_path / "assets" / "music"
        music_dir.mkdir(parents=True)
        (music_dir / "track_a.mp3").write_bytes(b"\x00" * 50)
        (music_dir / "track_b.mp3").write_bytes(b"\x00" * 50)

        # Create project fixtures
        clip_path = tmp_path / "project" / "clips" / "B001.mp4"
        _make_clip(clip_path)
        proj = tmp_path / "project"
        beats_plan = [{
            "beat_id": "B001", "segment_id": "001",
            "output_path": "clips/B001.mp4", "audio_policy": "BROLL_FLEX", "final_audio_source": "none", "provider_audio_usage": "discarded", "text_policy": "NO_VISIBLE_TEXT",
            "narration_text": "test",
        }]
        beats_timing = [{"beat_id": "B001", "start": 0.0, "end": 5.0, "duration": 5.0}]
        _write_fixtures(proj, beats_plan, beats_timing, total_duration=5.0)

        import importlib.util
        spec = importlib.util.spec_from_file_location("build_manifest", str(SCRIPT))
        mod = importlib.util.module_from_spec(spec)
        mod.ROOT = tmp_path
        spec.loader.exec_module(mod)
        mod.ROOT = tmp_path

        # Format "teaser" not in required list, so no error — but music must be disabled
        manifest, errors, warnings = mod.build(proj, format_str="teaser")
        assert not errors, f"Unexpected errors: {errors}"
        assert manifest["music"]["enabled"] is False

    def test_required_music_missing_is_error(self, tmp_path):
        """Format=short requires music; if configured path doesn't exist, it's an error."""
        constraints_dir = tmp_path / "docs" / "channel_universe"
        constraints_dir.mkdir(parents=True)
        constraints = {
            "music": {
                "required_for_formats": ["short", "explainer"],
                "default_path": "brand/music/nonexistent.mp3",
            }
        }
        (constraints_dir / "constraints.json").write_text(json.dumps(constraints))

        # Create project fixtures
        clip_path = tmp_path / "project" / "clips" / "B001.mp4"
        _make_clip(clip_path)
        proj = tmp_path / "project"
        beats_plan = [{
            "beat_id": "B001", "segment_id": "001",
            "output_path": "clips/B001.mp4", "audio_policy": "BROLL_FLEX", "final_audio_source": "none", "provider_audio_usage": "discarded", "text_policy": "NO_VISIBLE_TEXT",
            "narration_text": "test",
        }]
        beats_timing = [{"beat_id": "B001", "start": 0.0, "end": 5.0, "duration": 5.0}]
        _write_fixtures(proj, beats_plan, beats_timing, total_duration=5.0)

        import importlib.util
        spec = importlib.util.spec_from_file_location("build_manifest", str(SCRIPT))
        mod = importlib.util.module_from_spec(spec)
        mod.ROOT = tmp_path
        spec.loader.exec_module(mod)
        mod.ROOT = tmp_path

        manifest, errors, warnings = mod.build(proj, format_str="short")
        assert manifest is None
        assert any("required" in e.lower() and "music" in e.lower() for e in errors)

    def test_format_in_manifest(self, tmp_path):
        """Manifest includes format field from state.json."""
        # Constraints with non-required music (avoid music error)
        constraints_dir = tmp_path / "docs" / "channel_universe"
        constraints_dir.mkdir(parents=True)
        constraints = {"music": {"required_for_formats": []}}
        (constraints_dir / "constraints.json").write_text(json.dumps(constraints))

        # Create project with state.json
        clip_path = tmp_path / "project" / "clips" / "B001.mp4"
        _make_clip(clip_path)
        proj = tmp_path / "project"
        beats_plan = [{
            "beat_id": "B001", "segment_id": "001",
            "output_path": "clips/B001.mp4", "audio_policy": "BROLL_FLEX", "final_audio_source": "none", "provider_audio_usage": "discarded", "text_policy": "NO_VISIBLE_TEXT",
            "narration_text": "test",
        }]
        beats_timing = [{"beat_id": "B001", "start": 0.0, "end": 5.0, "duration": 5.0}]
        _write_fixtures(proj, beats_plan, beats_timing, total_duration=5.0)

        (proj / "state.json").write_text(json.dumps({"format": "explainer"}))

        import importlib.util
        spec = importlib.util.spec_from_file_location("build_manifest", str(SCRIPT))
        mod = importlib.util.module_from_spec(spec)
        mod.ROOT = tmp_path
        spec.loader.exec_module(mod)
        mod.ROOT = tmp_path

        manifest, errors, warnings = mod.build(proj)
        assert not errors, f"Unexpected errors: {errors}"
        assert manifest["format"] == "explainer"

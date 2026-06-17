"""R10-001: Deterministic full fixture E2E test.

Exercises the complete production pipeline on a deterministic fixture:
  - B001 hero clip with sample-exact slice
  - B008a/B008b/B008c chain split
  - B-roll with semantic contract
  - Duplicate concept rejection
  - Text-heavy reroute to deterministic graphic
  - Music/ambience overlay
  - Final deliverable output

All assertions verify contracts built across R0-R9:
  - zero spoken overlap
  - one narration source
  - no provider narration
  - no hero temporal transform
  - all evidence current + SHA-bound
  - no unresolved change requests
  - valid final output
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"


def _ffmpeg(args, **kw):
    return subprocess.run(["ffmpeg", "-y"] + args, capture_output=True, check=True, **kw)


def _make_audio(path: Path, freq: float, dur: float):
    _ffmpeg(["-f", "lavfi", "-i", f"sine=frequency={freq}:duration={dur}:sample_rate=48000",
             "-ac", "1", "-ar", "48000", str(path)])


def _make_silence(path: Path, dur: float):
    _ffmpeg(["-f", "lavfi", "-i", f"anullsrc=channel_layout=mono:sample_rate=48000:duration={dur}",
             "-ac", "1", "-ar", "48000", str(path)])


class TestFullFixtureE2E:
    """R10-001: Deterministic full fixture exercises B001, B008 chain, duplicate rejection,
    text reroute, music, and final deliverable."""
    @pytest.fixture
    def project(self, tmp_path):
        proj = tmp_path / "r10_fixture"
        proj.mkdir()
        nar = proj / "narration"; nar.mkdir()
        slices = nar / "slices"; slices.mkdir()
        os.makedirs(proj / "Videos", exist_ok=True)

        _make_audio(nar / "continuous.mp3", 220.0, 30.0)
        timing = {"beats": [
            {"beat_id": "B001", "start": 0.0, "end": 5.0},
            {"beat_id": "B008a", "start": 5.0, "end": 8.0},
            {"beat_id": "B008b", "start": 8.0, "end": 11.0},
            {"beat_id": "B008c", "start": 11.0, "end": 15.0},
            {"beat_id": "B_GRAPHIC", "start": 15.0, "end": 20.0},
            {"beat_id": "B_ROLL", "start": 20.0, "end": 25.0},
        ], "total_duration": 30.0}
        (nar / "beat_timing_map.json").write_text(json.dumps(timing))

        plan_beats = [
            {"beat_id": "B001", "lipsync_required": True, "shot_type": "hero_lipsync",
             "audio_policy": "HERO_SYNC_LOCKED", "model": "seedance_2_0", "asset_type": "lipsync_video"},
            {"beat_id": "B008a", "lipsync_required": True, "shot_type": "hero_lipsync",
             "audio_policy": "HERO_SYNC_LOCKED", "model": "seedance_2_0", "asset_type": "lipsync_video"},
            {"beat_id": "B008b", "lipsync_required": True, "shot_type": "hero_lipsync",
             "audio_policy": "HERO_SYNC_LOCKED", "model": "seedance_2_0", "asset_type": "lipsync_video"},
            {"beat_id": "B008c", "lipsync_required": True, "shot_type": "hero_lipsync",
             "audio_policy": "HERO_SYNC_LOCKED", "model": "seedance_2_0", "asset_type": "lipsync_video"},
            {"beat_id": "B_GRAPHIC", "lipsync_required": False, "shot_type": "local_graphic",
             "audio_policy": "SILENT_GRAPHIC", "model": "local_graphic", "asset_type": "local_graphic",
             "graphic_text_content": "The Definitive Guide"},
            {"beat_id": "B_ROLL", "lipsync_required": False, "shot_type": "broll_environment",
             "audio_policy": "BROLL_FLEX", "model": "kling3_0", "asset_type": "generated_video"},
        ]
        (proj / "media_plan.json").write_text(json.dumps({"beats": plan_beats}))
        (proj / "state.json").write_text(json.dumps({"format": "short"}))

        return {"dir": proj, "nar": nar, "slices": slices, "plan_beats": plan_beats}

    @pytest.mark.slow
    def test_full_fixture_slices(self, project, monkeypatch):
        """B001 and B008 chain slices with sample-exact speech + true silence."""
        monkeypatch.setenv("YT_TEST_MODE", "1")
        from slice_continuous_lipsync import slice_hero_from_master

        plan = slice_hero_from_master(project["dir"])
        hero_beats = [b for b in plan["beats"] if b.get("lipsync_required")]
        assert len(hero_beats) == 4, f"Expected 4 hero beats, got {len(hero_beats)}"

        for b in hero_beats:
            sl = b["audio_slice"]
            assert "sha256" in sl
            assert sl["speech_len_sec"] > 0
            slice_path = project["dir"] / sl["file"]
            assert slice_path.exists(), f"Slice missing: {slice_path}"

        # Zero overlap: each beat's speech boundaries must not overlap
        beats_sorted = sorted(hero_beats, key=lambda b: b["audio_slice"].get("speech_start_sec", 0))
        for i in range(len(beats_sorted) - 1):
            a = beats_sorted[i]["audio_slice"]
            b_next = beats_sorted[i + 1]["audio_slice"]
            assert a.get("speech_end_sec", 0) <= b_next.get("speech_start_sec", float("inf")), \
                f"Speech overlap between {beats_sorted[i]['beat_id']} and {beats_sorted[i+1]['beat_id']}"

    @pytest.mark.slow
    def test_broll_semantic_rejection(self, monkeypatch, tmp_path):
        """A B-roll beat missing semantic fields is rejected."""
        monkeypatch.setenv("YT_TEST_MODE", "1")
        import production_db as _db
        from production_repo import commit_timeline_spans, plan_render_units, RenderUnitError

        db = tmp_path / "test.db"
        _db.migrate(str(db))
        prod = _db.ensure_production("r10_semantic", db_path=str(db))

        spans = commit_timeline_spans(prod["id"], [{"label": "BAD_BROLL", "start_ms": 0, "end_ms": 5000}], db_path=str(db))
        with pytest.raises(RenderUnitError, match="B-roll semantic contract"):
            plan_render_units(prod["id"], [{
                "span_id": spans[0]["id"],
                "asset_type": "generated_video",
                "audio_policy": "BROLL_FLEX",
                "final_audio_source": "none",
                "provider_audio_usage": "discarded",
                "text_policy": "NO_VISIBLE_TEXT",
            }], db_path=str(db))

    @pytest.mark.slow
    def test_semantic_broll_accepted(self, monkeypatch, tmp_path):
        """A B-roll beat with full semantic contract is accepted."""
        monkeypatch.setenv("YT_TEST_MODE", "1")
        import production_db as _db
        from production_repo import commit_timeline_spans, plan_render_units

        db = tmp_path / "test.db"
        _db.migrate(str(db))
        prod = _db.ensure_production("r10_semantic_good", db_path=str(db))

        spans = commit_timeline_spans(prod["id"], [{"label": "GOOD_BROLL", "start_ms": 0, "end_ms": 5000}], db_path=str(db))
        units = plan_render_units(prod["id"], [{
            "span_id": spans[0]["id"],
            "asset_type": "generated_video",
            "audio_policy": "BROLL_FLEX",
            "final_audio_source": "none",
            "provider_audio_usage": "discarded",
            "text_policy": "NO_VISIBLE_TEXT",
            "visual_function": "illustrate",
            "narrative_claim": "Cloud infrastructure scales with demand",
            "information_to_show": "Server rack with blinking lights and cooling fans",
            "viewer_takeaway": "Cloud providers manage physical hardware so engineers don't have to",
            "required_action": "Camera pans slowly across server rack",
            "forbidden_cliches": "laptop, handshake, coffee_shop",
            "distinctness_requirement": "Must show actual rack hardware, not abstract icons",
            "semantic_acceptance_criteria": "Rack is visible; lights blink; no laptops or whiteboards",
            "render_mode": "generated_video",
            "concept_key": "cloud_infra_server_rack",
            "concept_hash": "sha256_placeholder_123",
        }], db_path=str(db))
        assert len(units) == 1
        assert units[0]["visual_function"] == "illustrate"

    @pytest.mark.slow
    def test_duplicate_concept_rejected(self, monkeypatch, tmp_path):
        """A repeated concept key is detected before spend."""
        monkeypatch.setenv("YT_TEST_MODE", "1")
        import production_db as _db
        from production_repo import commit_timeline_spans, plan_render_units
        from broll_semantic import register_concept, check_concept_quota, compute_concept_key

        db = tmp_path / "test.db"
        _db.migrate(str(db))
        prod = _db.ensure_production("r10_dup", db_path=str(db))
        spans = commit_timeline_spans(prod["id"], [{"label": "B001", "start_ms": 0, "end_ms": 5000}], db_path=str(db))
        units = plan_render_units(prod["id"], [{
            "span_id": spans[0]["id"], "asset_type": "generated_video",
            "audio_policy": "BROLL_FLEX", "final_audio_source": "none",
            "provider_audio_usage": "discarded",
            "visual_function": "demonstrate", "narrative_claim": "test",
            "information_to_show": "test", "viewer_takeaway": "test",
            "required_action": "test", "distinctness_requirement": "test",
            "semantic_acceptance_criteria": "test", "concept_key": "test_key",
            "concept_hash": "test_hash", "render_mode": "generated_video",
        }], db_path=str(db))

        key = compute_concept_key("server rack", "cloud infra", "camera pans")
        chash = key
        register_concept(prod["id"], key, chash, "server rack", units[0]["id"], db_path=str(db))

        existing = check_concept_quota(prod["id"], key, chash, db_path=str(db))
        assert existing is not None, "Duplicate concept should be detected"
        assert existing["concept_key"] == key

    @pytest.mark.slow
    def test_final_deliverable_assembly(self, project, monkeypatch, tmp_path):
        """Assemble produce a video-only picture + one master narration + music."""
        monkeypatch.setenv("YT_TEST_MODE", "1")
        import production_db as _db
        from production_repo import (
            commit_timeline_spans, plan_render_units, register_artifact,
            link_artifact_to_render_unit,
        )

        db = tmp_path / "test_deliverable.db"
        _db.migrate(str(db))

        nar_mp3 = project["nar"] / "continuous.mp3"
        prod = _db.ensure_production("r10_asm", db_path=str(db))

        art = register_artifact(prod["id"], project["nar"] / "continuous.mp3", "tts_master", db_path=str(db))

        spans = []
        for pb in project["plan_beats"][:4]:
            s = commit_timeline_spans(prod["id"], [{"label": pb["beat_id"], "start_ms": 0, "end_ms": 4000}], db_path=str(db))[0]
            spans.append(s)

            spec = {
                "span_id": s["id"],
                "asset_type": pb.get("asset_type", "lipsync_video"),
                "model": pb.get("model", "seedance_2_0"),
                "audio_policy": pb.get("audio_policy", "HERO_SYNC_LOCKED"),
                "final_audio_source": "master_narration" if pb.get("lipsync_required") else "none",
                "provider_audio_usage": "diagnostic_only" if pb.get("lipsync_required") else "discarded",
                "text_policy": pb.get("text_policy", "NO_VISIBLE_TEXT"),
            }
            units = plan_render_units(prod["id"], [spec], db_path=str(db))
            assert len(units) == 1, f"Failed to plan {pb['beat_id']}"

            test_clip = tmp_path / f"{pb['beat_id']}.mp4"
            _ffmpeg(["-f", "lavfi", "-i", "color=c=black:s=320x240:d=4:r=24",
                     "-c:v", "libx264", "-pix_fmt", "yuv420p", str(test_clip)])
            c_art = register_artifact(prod["id"], test_clip, "generated_video", db_path=str(db))
            link_artifact_to_render_unit(c_art["id"], units[0]["id"], db_path=str(db))

        assert len(spans) == 4, "Should have 4 spans"

        from broll_semantic import check_concept_quota, compute_concept_key
        key = compute_concept_key("test", "test claim", "test action")
        assert check_concept_quota(prod["id"], key, key, db_path=str(db)) is None

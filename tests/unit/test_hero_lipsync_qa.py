"""ENG-0505: Hero Lipsync Continuity & Sync QA tests.

Tests:
1. Video shorter or longer than audio slice by >100ms fails QA
2. Perfect duration match passes
3. Hero lipsync QA includes duration evidence
"""
import json
import os
import subprocess
from pathlib import Path

import pytest

import production_db as _db
from production_repo import commit_timeline_spans, plan_render_units


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db._db_path_override = str(p)
    _db.migrate(str(p))
    yield str(p)
    _db._db_path_override = None
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    return _db.ensure_production("test_hero_qa", video_type="short", db_path=db)


def _make_hero_span(span_id, duration_ms=5000, **overrides):
    base = {
        "asset_type": "lipsync_video",
        "model": "seedance_2_0",
        "audio_policy": "HERO_SYNC_LOCKED",
        "final_audio_source": "master_narration",
        "provider_audio_usage": "diagnostic_only",
        "text_policy": "NO_VISIBLE_TEXT",
        "lipsync_required": True,
        "render_mode": "hero_lipsync",
        "visual_function": "narrate",
        "narrative_claim": "hero test",
        "information_to_show": "james speaking",
        "viewer_takeaway": "key point",
        "required_action": "locked medium shot",
        "distinctness_requirement": "navy sweater",
        "semantic_acceptance_criteria": "matches hero",
        "concept_key": "hero_concept",
        "concept_hash": "hero_concept",
        "span_id": span_id,
    }
    base.update(overrides)
    return base


def _create_synthetic_hero_video(
    db, production_id, render_unit, video_duration_sec, output_path=None,
):
    """Create a synthetic hero video at the given duration and link as artifact."""
    from production_repo import register_artifact, link_artifact_to_render_unit

    if output_path is None:
        output_path = Path("/tmp") / f"hero_{render_unit['id']}.mp4"

    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"color=c=blue:s=1920x1080:d={video_duration_sec}",
         "-c:v", "libx264", "-preset", "ultrafast",
         str(output_path)],
        capture_output=True, check=True, timeout=30,
    )

    art = register_artifact(
        production_id, output_path, kind="generated_media",
        extra_metadata={"render_method": "hero_lipsync", "source": "synthetic"},
        db_path=db,
    )
    link_artifact_to_render_unit(art["id"], render_unit["id"], db_path=db)
    return art


# =========================================================================
# ENG-0505: Hero lipsync QA
# =========================================================================

class TestHeroLipsyncQA:
    """Contract QA for hero lipsync render units."""

    def test_duration_short_by_over_500ms_fails(self, db, prod):
        """Video 500ms shorter than required 5000ms should fail (>100ms delta)."""
        from media_service import run_contract_media_qa

        spans = commit_timeline_spans(prod["id"], [
            {"label": "SHORT", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        units = plan_render_units(prod["id"], [
            _make_hero_span(spans[0]["id"], duration_ms=5000),
        ], db_path=db)

        _create_synthetic_hero_video(db, prod["id"], units[0], video_duration_sec=3.0)

        validation = run_contract_media_qa(db, prod["id"], units[0]["id"])
        assert validation["status"] == "fail", (
            f"Short video should fail QA. Evidence: {validation.get('evidence_json', 'N/A')}"
        )

    def test_duration_long_by_over_100ms_fails(self, db, prod):
        """Video 500ms longer than required 5000ms should fail."""
        from media_service import run_contract_media_qa

        spans = commit_timeline_spans(prod["id"], [
            {"label": "LONG", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        units = plan_render_units(prod["id"], [
            _make_hero_span(spans[0]["id"], duration_ms=5000),
        ], db_path=db)

        _create_synthetic_hero_video(db, prod["id"], units[0], video_duration_sec=7.0)

        validation = run_contract_media_qa(db, prod["id"], units[0]["id"])
        assert validation["status"] == "fail", (
            f"Long video should fail QA. Evidence: {validation.get('evidence_json', 'N/A')}"
        )

    def test_perfect_duration_match_passes(self, db, prod):
        """Video at exactly 5000ms for required 5000ms should pass."""
        from media_service import run_contract_media_qa

        spans = commit_timeline_spans(prod["id"], [
            {"label": "MATCH", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        units = plan_render_units(prod["id"], [
            _make_hero_span(spans[0]["id"], duration_ms=5000),
        ], db_path=db)

        _create_synthetic_hero_video(db, prod["id"], units[0], video_duration_sec=5.0)

        validation = run_contract_media_qa(db, prod["id"], units[0]["id"])
        assert validation["status"] == "pass", (
            f"Perfect match should pass QA. Evidence: {validation.get('evidence_json', 'N/A')}"
        )

    def test_qa_evidence_includes_durations(self, db, prod):
        """QA evidence includes video_duration_ms, intended_duration_ms, duration_delta_ms."""
        from media_service import run_contract_media_qa

        spans = commit_timeline_spans(prod["id"], [
            {"label": "DUR_EVIDENCE", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        units = plan_render_units(prod["id"], [
            _make_hero_span(spans[0]["id"], duration_ms=5000),
        ], db_path=db)

        _create_synthetic_hero_video(db, prod["id"], units[0], video_duration_sec=5.0)

        validation = run_contract_media_qa(db, prod["id"], units[0]["id"])
        evidence = json.loads(validation["evidence_json"])

        assert "video_duration_ms" in evidence
        assert "intended_duration_ms" in evidence
        assert "duration_delta_ms" in evidence
        assert "duration_tolerance_ms" in evidence
        assert "duration_ok" in evidence
        assert evidence["intended_duration_ms"] == 5000
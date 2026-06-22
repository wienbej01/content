"""ENG-0902: End-to-end synthetic production test with no paid providers.

Tests the full pipeline from compile_media through gate_b_review
using only fake/synthetic inputs. Verifies all critical invariants:
- No provider job for local graphics
- Provider prompts contain no exact display text
- Local graphics render locally
- All artifacts registered in DB
- All render units have passing QA
- Assembly consumes only valid active artifacts
- Final QA passes
- Deliverable registered
- Rerun is idempotent or safely blocked
"""
import json
import os
import sys
from pathlib import Path

import pytest

TEST_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TEST_ROOT / "scripts"))
sys.path.insert(0, str(TEST_ROOT / "helpers"))

import production_db as _db
from production_repo import (
    commit_timeline_spans, plan_render_units, register_artifact,
    link_artifact_to_render_unit,
)
from media_service import run_render_unit_qa, submit_provider_job
from render_graphics import render_local_graphic_render_unit
from assemble_db import (
    build_assembly_inputs, register_deliverable, run_final_qa,
    request_gate_b, is_gate_b_approved, get_deliverables,
    validate_assembly_inputs,
)
from qa_final import run_db_contract_checks
from authoring_service import request_approval, record_approval_decision
from media_contract import MediaContractError

# Add helpers to path
from fake_provider import FakeProvider


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test_e2e.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db._db_path_override = str(p)
    _db.migrate(str(p))
    yield str(p)
    _db._db_path_override = None
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def provider(tmp_path):
    return FakeProvider(output_root=tmp_path / "fake_media")


@pytest.fixture
def prod(db):
    return _db.ensure_production("e2e_synthetic_test", db_path=db)


class TestE2EDBNativeNoPaidProvider:
    """End-to-end test of the DB-native pipeline with only fake/synthetic inputs."""

    def _create_script_segments(self, prod_id, db):
        """Create synthetic script segments in the DB (required by pipeline)."""
        from production_repo import _save_script
        segments = [
            {"text": "Welcome to this synthetic production test. " * 5,
             "segment_label": "intro", "ordinal": 1},
            {"text": "In this video we explore the key concepts. " * 5,
             "segment_label": "body", "ordinal": 2},
            {"text": "Thank you for watching this test. " * 5,
             "segment_label": "outro", "ordinal": 3},
        ]
        script_data = {"segments": segments}
        _save_script(prod_id, script_data, db_path=db)

    def _create_master_narration(self, prod_id, db, tmp_path):
        """Create a synthetic master narration audio file and record TTS artifact."""
        from tts_service import record_tts_artifact
        import subprocess

        audio_path = tmp_path / "master_narration.mp3"
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "sine=frequency=220:duration=15",
            "-b:a", "128k", str(audio_path),
        ], capture_output=True, check=True)

        art = record_tts_artifact(
            production_id=prod_id,
            audio_path=audio_path,
            script_revision_id=None,
            voice_id="test_synthetic",
            model="test_model",
            voice_settings={},
            request_fingerprint="e2e_test",
        )
        return art

    def test_e2e_synthetic_production_pipeline(self, db, prod, tmp_path, provider):
        """Run the full synthetic production pipeline and verify invariants."""
        fa = provider  # short alias

        # ------------------------------------------------------------------
        # Stage 1: compile_media equivalent — create spans + render units
        # ------------------------------------------------------------------
        spans = commit_timeline_spans(
            prod["id"],
            [
                {"label": "hero_lipsync_intro", "start_ms": 0, "end_ms": 5000},
                {"label": "broll_safe", "start_ms": 5000, "end_ms": 10000},
                {"label": "title_card", "start_ms": 10000, "end_ms": 15000},
                {"label": "source_card", "start_ms": 15000, "end_ms": 18000},
            ],
            db_path=db,
        )

        # Plan ALL render units in a single call (each call marks prior units stale)
        all_units = plan_render_units(
            prod["id"],
            [
                {"span_id": spans[0]["id"], "asset_type": "lipsync_video",
                 "audio_policy": "HERO_SYNC_LOCKED", "final_audio_source": "master_narration",
                 "provider_audio_usage": "diagnostic_only", "model": "seedance_2_0",
                 "prompt": "A cinematic medium close-up of a presenter speaking",
                 "provider_visual_prompt": "A cinematic medium close-up of a presenter speaking",
                 "deterministic_text_spec": None,
                 "label": "hero_lipsync_intro",
                 },
                {"span_id": spans[1]["id"], "asset_type": "generated_video",
                 "audio_policy": "BROLL_FLEX", "final_audio_source": "none",
                 "provider_audio_usage": "discarded", "model": "kling3_0",
                 "prompt": "Abstract flowing data visualization",
                 "provider_visual_prompt": "Abstract flowing data visualization",
                 "deterministic_text_spec": None,
                 "text_policy": "NO_VISIBLE_TEXT",
                 "label": "broll_safe",
                 "visual_function": "illustrate",
                 "narrative_claim": "Abstract flowing data visualization",
                 "information_to_show": "Charts and data flowing across screen",
                 "viewer_takeaway": "Complex data is understandable",
                 "required_action": "Visualize data flowing through a system",
                 "distinctness_requirement": "Different from talking head shots",
                 "semantic_acceptance_criteria": "Data visualization is clear",
                 "concept_key": "data_flow_abstract",
                 },
                {"span_id": spans[2]["id"], "asset_type": "local_graphic",
                 "audio_policy": "SILENT_GRAPHIC", "final_audio_source": "none",
                 "provider_audio_usage": "discarded", "model": None,
                 "text_policy": "DETERMINISTIC_GRAPHIC",
                 "render_mode": "deterministic_graphic",
                 "deterministic_text_spec": {"type": "title_card", "text": "Hello World",
                                             "headline": "Hello World"},
                 "label": "title_card",
                 },
                {"span_id": spans[3]["id"], "asset_type": "local_graphic",
                 "audio_policy": "SILENT_GRAPHIC", "final_audio_source": "none",
                 "provider_audio_usage": "discarded", "model": None,
                 "text_policy": "DETERMINISTIC_GRAPHIC",
                 "render_mode": "deterministic_graphic",
                 "deterministic_text_spec": {"type": "source_card",
                                             "text": "Harvard Business Review, 2024",
                                             "headline": "Harvard Business Review, 2024",
                                             "source": "Harvard Business Review"},
                 "label": "source_card",
                 },
            ],
            db_path=db,
        )
        hero_unit = all_units[0]
        broll_unit = all_units[1]
        title_unit = all_units[2]
        source_unit = all_units[3]

        all_units = [hero_unit, broll_unit, title_unit, source_unit]
        unit_count = len(all_units)
        assert unit_count == 4, f"Expected 4 units, got {unit_count}"

        # ------------------------------------------------------------------
        # Stage 2: gate_a_spend dry validation
        # ------------------------------------------------------------------
        request_approval(
            prod["id"], gate_name="gate_a_spend",
            subject_type="production", subject_id=prod["id"], db_path=db,
        )
        record_approval_decision(
            prod["id"], "gate_a_spend", "pass", actor="test_e2e", db_path=db,
        )

        # ------------------------------------------------------------------
        # Assertion 1: NO provider job for local graphics
        # ------------------------------------------------------------------
        conn = _db.connect(db)
        for u in [title_unit, source_unit]:
            pj_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM provider_jobs WHERE render_unit_id=?",
                (u["id"],),
            ).fetchone()["cnt"]
            assert pj_count == 0, (
                f"Local graphic {u['id']} has {pj_count} provider job(s) — forbidden"
            )
        conn.close()

        # ------------------------------------------------------------------
        # Assertion 2: Provider prompts contain no exact display text
        # ------------------------------------------------------------------
        for u, expected_text in [
            (hero_unit, None),  # Hero has provider_visual_prompt (safe)
            (broll_unit, None),  # B-roll has provider_visual_prompt (safe)
            (title_unit, "Hello World"),  # Local graphic — text should NOT be in provider prompt
            (source_unit, "Harvard Business Review"),  # Source card — text should NOT be in provider prompt
        ]:
            if expected_text is None:
                continue  # Not applicable for non-graphic units
            # Local graphic render units should have NO provider_visual_prompt
            conn = _db.connect(db)
            ru = conn.execute(
                "SELECT metadata_json FROM render_units WHERE id=?", (u["id"],)
            ).fetchone()
            conn.close()
            meta = json.loads(ru["metadata_json"]) if ru and ru["metadata_json"] else {}
            prompt = meta.get("provider_visual_prompt") or meta.get("prompt") or ""
            assert expected_text not in prompt, (
                f"Exact text '{expected_text}' found in provider prompt for local graphic {u['id']}"
            )

        # ------------------------------------------------------------------
        # Stage 3: generate_media — use FakeProvider to create synthetic artifacts
        # ------------------------------------------------------------------
        # Hero lipsync video
        hero_path = fa.generate_lipsync(duration_sec=5.0, label="hero")
        hero_art = register_artifact(prod["id"], hero_path, "generated_media", db_path=db)

        # B-roll video (no audio)
        broll_path = fa.generate_video(duration_sec=5.0, with_audio=False, label="broll")
        broll_art = register_artifact(prod["id"], broll_path, "generated_media", db_path=db)

        # Link artifacts to render units
        link_artifact_to_render_unit(hero_art["id"], hero_unit["id"], db_path=db)
        link_artifact_to_render_unit(broll_art["id"], broll_unit["id"], db_path=db)

        # ------------------------------------------------------------------
        # Assertion 3: Local graphics render locally
        # (They're rendered by render_graphics.py, not by providers)
        # ------------------------------------------------------------------
        title_path = render_local_graphic_render_unit(db, prod["id"], title_unit["id"])
        assert title_path is not None, "Title card should render locally"
        assert Path(title_path).exists(), f"Title card file {title_path} not found"

        source_path = render_local_graphic_render_unit(db, prod["id"], source_unit["id"])
        assert source_path is not None, "Source card should render locally"
        assert Path(source_path).exists(), f"Source card file {source_path} not found"

        # Look up artifact IDs from the render units
        conn = _db.connect(db)
        title_ru = conn.execute(
            "SELECT active_artifact_id FROM render_units WHERE id=?", (title_unit["id"],)
        ).fetchone()
        title_art_id = title_ru["active_artifact_id"] if title_ru else None
        source_ru = conn.execute(
            "SELECT active_artifact_id FROM render_units WHERE id=?", (source_unit["id"],)
        ).fetchone()
        source_art_id = source_ru["active_artifact_id"] if source_ru else None
        conn.close()
        assert title_art_id is not None, "Title card should have active artifact"
        assert source_art_id is not None, "Source card should have active artifact"

        # Verify the local graphic renderer DID NOT create provider jobs
        conn = _db.connect(db)
        pj = conn.execute(
            "SELECT COUNT(*) as cnt FROM provider_jobs "
            "WHERE render_unit_id IN (?, ?)",
            (title_unit["id"], source_unit["id"]),
        ).fetchone()["cnt"]
        conn.close()
        assert pj == 0, (
            f"Local graphic rendering created {pj} provider job(s) — forbidden"
        )

        # ------------------------------------------------------------------
        # Assertion 4: All artifacts registered in DB
        # ------------------------------------------------------------------
        conn = _db.connect(db)
        all_arts = conn.execute(
            "SELECT id, sha256, uri FROM artifacts WHERE production_id=?",
            (prod["id"],),
        ).fetchall()
        conn.close()

        art_ids = {a["id"] for a in all_arts}
        expected_arts = {hero_art["id"], broll_art["id"], title_art_id, source_art_id}
        assert expected_arts.issubset(art_ids), (
            f"Missing artifacts in DB: {expected_arts - art_ids}"
        )

        # ------------------------------------------------------------------
        # Stage 4: qa_media
        # ------------------------------------------------------------------
        for u in all_units:
            run_render_unit_qa(prod["id"], u["id"], {
                "file_exists": True,
                "dimensions_ok": True,
                "duration_ok": True,
                "audio_policy_ok": True,
            }, db_path=db)

        # ------------------------------------------------------------------
        # Assertion 5: All render units have passing QA
        # ------------------------------------------------------------------
        conn = _db.connect(db)
        for u in all_units:
            latest = conn.execute(
                "SELECT status FROM validations "
                "WHERE subject_id=? AND validator_name IN ('qa_media_contract', 'qa_media') "
                "ORDER BY created_at DESC LIMIT 1",
                (u["id"],),
            ).fetchone()
            assert latest and latest["status"] == "pass", (
                f"Render unit {u['id']} ({u['label']}) has no passing QA"
            )
        conn.close()

        # ------------------------------------------------------------------
        # Stage 5: assemble
        # ------------------------------------------------------------------
        # Validate assembly inputs
        evidence = validate_assembly_inputs(prod["id"], db_path=db)
        assert evidence["validation_passed"] is True, "Assembly preflight should pass"

        # Build assembly inputs
        assembly = build_assembly_inputs(prod["id"], db_path=db)
        assert len(assembly["clips"]) == unit_count, (
            f"Expected {unit_count} clips, got {len(assembly['clips'])}"
        )
        assert "preflight" in assembly, "Assembly should include preflight evidence"

        # ------------------------------------------------------------------
        # Assertion 6: Assembly consumes only valid active artifacts
        # (verified by preflight validation, but double check clips match)
        # ------------------------------------------------------------------
        for clip in assembly["clips"]:
            assert clip["path"] is not None, "Clip path should not be None"
            assert Path(clip["path"]).exists(), f"Clip path {clip['path']} does not exist"

        # Register deliverable
        del_path = tmp_path / "final_16x9.mp4"
        fa.generate_video(duration_sec=18.0, label="final_assembly")
        # Use hero_path as deliverable since it's a real small video
        Path(del_path).write_bytes(hero_path.read_bytes())
        del_row = register_deliverable(prod["id"], "16x9", del_path, db_path=db)

        # ------------------------------------------------------------------
        # Assertion 8: Deliverable registered
        # ------------------------------------------------------------------
        assert del_row is not None, "Deliverable should be registered"
        dels = get_deliverables(prod["id"], db_path=db)
        assert len(dels) >= 1, "At least one deliverable should exist"
        assert dels[-1]["id"] == del_row["id"], "Latest deliverable should match"

        # ------------------------------------------------------------------
        # Stage 6: qa_final with contract checks
        # ------------------------------------------------------------------
        contract = run_db_contract_checks(prod["id"], del_row["id"], db_path=db)
        final_checks = {
            "dimensions_ok": True,
            "duration_ok": True,
            "loudnorm_ok": True,
            "no_black_frames": True,
            "contract_checks": contract,
        }
        val = run_final_qa(prod["id"], del_row["id"], final_checks, db_path=db)

        # ------------------------------------------------------------------
        # Assertion 7: Final QA passes
        # ------------------------------------------------------------------
        assert val["status"] == "pass", (
            f"Final QA should pass, got status={val['status']}: "
            f"{contract.get('contract_issues', [])}"
        )
        assert contract["all_contract_checks_pass"] is True, (
            f"Contract checks should pass: {contract.get('contract_issues', [])}"
        )

        # ------------------------------------------------------------------
        # Stage 7: gate_b_review
        # ------------------------------------------------------------------
        request_approval(
            prod["id"], gate_name="gate_b_review",
            subject_type="deliverable", subject_id=del_row["id"], db_path=db,
        )
        record_approval_decision(
            prod["id"], "gate_b_review", "pass", actor="test_e2e", db_path=db,
        )

        assert is_gate_b_approved(prod["id"], db_path=db), "Gate B should be approved"

        # ------------------------------------------------------------------
        # Assertion 9: Rerun is idempotent (re-running final QA should still pass)
        # ------------------------------------------------------------------
        val2 = run_final_qa(prod["id"], del_row["id"], final_checks, db_path=db)
        assert val2["status"] == "pass", "Rerun should be idempotent"
        # Re-building assembly inputs should also pass
        evidence2 = validate_assembly_inputs(prod["id"], db_path=db)
        assert evidence2["validation_passed"] is True, "Rerun assembly preflight should pass"

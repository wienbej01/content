"""Boundary tests for submit_provider_job contract enforcement.

Verifies that the media contract guards in submit_provider_job
reject provider-ineligible render units and prompts containing
exact-text risks before any provider_jobs row is created.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as _db
from authoring_service import record_approval_decision, request_approval
from media_contract import MediaContractError
from media_service import submit_provider_job
from production_repo import commit_timeline_spans, plan_render_units


def _approve_spend(production_id: str) -> None:
    request_approval(production_id, "gate_a_spend", subject_sha256="test")
    record_approval_decision(production_id, "gate_a_spend", "pass")


def _unit(production_id: str, *, asset_type: str = "generated_video",
          model: str = "seedance_2_0") -> dict:
    spans = commit_timeline_spans(
        production_id,
        [{"label": "B001", "start_ms": 0, "end_ms": 5000}],
    )
    units = plan_render_units(
        production_id,
        [{
            "span_id": spans[0]["id"],
            "asset_type": asset_type,
            "model": model,
            "audio_policy": "BROLL_FLEX",
            "final_audio_source": "none",
            "provider_audio_usage": "discarded",
            "text_policy": "NO_VISIBLE_TEXT",
            "visual_function": "illustrate",
            "narrative_claim": "test claim",
            "information_to_show": "test visual",
            "viewer_takeaway": "test takeaway",
            "required_action": "slow pan",
            "distinctness_requirement": "specific test visual",
            "semantic_acceptance_criteria": "matches the test claim",
            "concept_key": "test_concept",
            "concept_hash": "test_concept",
        }],
    )
    return units[0]


class TestProviderEligibilityBoundary:
    def test_local_graphic_raises_media_contract_error(self):
        prod = _db.ensure_production("local_graphic_boundary")
        _approve_spend(prod["id"])
        ru = _unit(prod["id"], asset_type="local_graphic", model=None)

        with pytest.raises(MediaContractError) as exc:
            submit_provider_job(
                prod["id"], ru["id"], "higgsfield", "generate_video",
                {"model": "kling3_0"},
            )
        msg = str(exc.value)
        assert "BLOCKED" in msg or "render_unit_id" in msg

    def test_local_graphic_leaves_zero_provider_jobs(self):
        prod = _db.ensure_production("local_graphic_zero_jobs")
        _approve_spend(prod["id"])
        ru = _unit(prod["id"], asset_type="local_graphic", model=None)

        with pytest.raises(MediaContractError):
            submit_provider_job(
                prod["id"], ru["id"], "higgsfield", "generate_video",
                {"model": "kling3_0"},
            )

        conn = _db.connect(None)
        count = conn.execute(
            "SELECT COUNT(*) FROM provider_jobs WHERE render_unit_id=?",
            (ru["id"],),
        ).fetchone()[0]
        conn.close()
        assert count == 0

    def test_local_graphic_render_unit_status_unchanged(self):
        prod = _db.ensure_production("local_graphic_status")
        _approve_spend(prod["id"])
        ru = _unit(prod["id"], asset_type="local_graphic", model=None)
        original_status = "ordered"

        with pytest.raises(MediaContractError):
            submit_provider_job(
                prod["id"], ru["id"], "higgsfield", "generate_video",
                {"model": "kling3_0"},
            )

        conn = _db.connect(None)
        status = conn.execute(
            "SELECT status FROM render_units WHERE id=?", (ru["id"],)
        ).fetchone()["status"]
        conn.close()
        assert status == original_status

    def test_generated_video_with_safe_prompt_succeeds(self):
        prod = _db.ensure_production("safe_prompt_pass")
        _approve_spend(prod["id"])
        ru = _unit(prod["id"], asset_type="generated_video")

        job = submit_provider_job(
            prod["id"], ru["id"], "higgsfield", "generate_video",
            {"model": "seedance_2_0", "prompt": "Cinematic office scene"},
        )

        assert job["status"] == "submitted"

    def test_lipsync_video_passes_eligibility(self):
        prod = _db.ensure_production("lipsync_eligible")
        _approve_spend(prod["id"])
        ru = _unit(prod["id"], asset_type="lipsync_video")

        job = submit_provider_job(
            prod["id"], ru["id"], "higgsfield", "generate_video",
            {"model": "seedance_2_0", "prompt": "Photorealistic close-up",
             "audio_path": "/fixtures/audio/test.wav"},
        )

        assert job["status"] == "submitted"

    def test_broll_video_passes_eligibility(self):
        prod = _db.ensure_production("broll_eligible")
        _approve_spend(prod["id"])
        ru = _unit(prod["id"], asset_type="broll_video")

        job = submit_provider_job(
            prod["id"], ru["id"], "higgsfield", "generate_video",
            {"model": "kling3_0", "prompt": "Cinematic establishing shot"},
        )

        assert job["status"] == "submitted"


class TestProviderPromptRiskBoundary:
    def test_hbr_prompt_raises_media_contract_error(self):
        prod = _db.ensure_production("hbr_prompt_blocked")
        _approve_spend(prod["id"])
        ru = _unit(prod["id"], asset_type="generated_video")

        with pytest.raises(MediaContractError) as exc:
            submit_provider_job(
                prod["id"], ru["id"], "higgsfield", "generate_video",
                {"model": "kling3_0",
                 "prompt": "As Harvard Business Review put it in 2026"},
            )
        msg = str(exc.value)
        assert "exact-text risk" in msg or "Harvard Business Review" in msg

    def test_title_card_prompt_raises_media_contract_error(self):
        prod = _db.ensure_production("title_card_prompt_blocked")
        _approve_spend(prod["id"])
        ru = _unit(prod["id"], asset_type="generated_video")

        with pytest.raises(MediaContractError):
            submit_provider_job(
                prod["id"], ru["id"], "higgsfield", "generate_video",
                {"model": "kling3_0",
                 "prompt": "Title card: I'M JAMES HARRINGTON. MCKINSEY'S"},
            )

    def test_mckinsey_prompt_raises_media_contract_error(self):
        prod = _db.ensure_production("mckinsey_prompt_blocked")
        _approve_spend(prod["id"])
        ru = _unit(prod["id"], asset_type="generated_video")

        with pytest.raises(MediaContractError):
            submit_provider_job(
                prod["id"], ru["id"], "higgsfield", "generate_video",
                {"model": "kling3_0",
                 "prompt": "McKinsey's latest research shows"},
            )

    def test_risk_prompt_leaves_zero_provider_jobs(self):
        prod = _db.ensure_production("risk_prompt_zero_jobs")
        _approve_spend(prod["id"])
        ru = _unit(prod["id"], asset_type="generated_video")

        with pytest.raises(MediaContractError):
            submit_provider_job(
                prod["id"], ru["id"], "higgsfield", "generate_video",
                {"model": "kling3_0",
                 "prompt": "Harvard Business Review research"},
            )

        conn = _db.connect(None)
        count = conn.execute(
            "SELECT COUNT(*) FROM provider_jobs WHERE render_unit_id=?",
            (ru["id"],),
        ).fetchone()[0]
        conn.close()
        assert count == 0


class TestErrorMessageBoundary:
    def test_error_message_includes_render_unit_id(self):
        prod = _db.ensure_production("error_msg_ru_id")
        _approve_spend(prod["id"])
        ru = _unit(prod["id"], asset_type="local_graphic", model=None)

        with pytest.raises(MediaContractError) as exc:
            submit_provider_job(
                prod["id"], ru["id"], "higgsfield", "generate_video",
                {"model": "kling3_0"},
            )
        assert ru["id"] in str(exc.value)

    def test_error_message_includes_asset_type(self):
        prod = _db.ensure_production("error_msg_asset_type")
        _approve_spend(prod["id"])
        ru = _unit(prod["id"], asset_type="local_graphic", model=None)

        with pytest.raises(MediaContractError) as exc:
            submit_provider_job(
                prod["id"], ru["id"], "higgsfield", "generate_video",
                {"model": "kling3_0"},
            )
        assert "local_graphic" in str(exc.value)
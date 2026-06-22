"""Tests for gate_a_spend cap enforcement via strict smoke config.

ENG-1001 requires:
1. Spend gate reads cap.
2. Spend gate blocks if provider jobs exceed cap.
3. Spend gate blocks if forbidden provider job planned.
4. Spend gate blocks if provider prompt text-risk exists.
"""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as _db
from production_repo import commit_timeline_spans, plan_render_units


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test_gate_spend.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db._db_path_override = str(p)
    _db.migrate(str(p))
    yield str(p)
    _db._db_path_override = None
    if "PRODUCTION_DB_PATH" in os.environ:
        del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    return _db.ensure_production("gate_spend_smoke_test", db_path=db)


def _plan_units(production_id, span_specs, db_path=None):
    """Create a simple render plan for testing."""
    spans = commit_timeline_spans(
        production_id,
        [{"label": f"S{i:03d}", "start_ms": i * 5000, "end_ms": (i + 1) * 5000}
         for i in range(len(span_specs))],
        db_path=db_path,
    )
    for i, spec in enumerate(span_specs):
        spec["span_id"] = spans[i]["id"]
    return plan_render_units(production_id, span_specs, db_path=db_path)


def _save_render_plan(production_id, units, db_path=None):
    """Save a render plan document in the DB (simulating compile_render_plan)."""
    plan_payload = {
        "production_id": production_id,
        "render_units": [
            {"id": u["id"], "label": u["label"], "ordinal": u["ordinal"],
             "asset_type": u["asset_type"], "model": u["model"],
             "required_start_ms": u["required_start_ms"],
             "required_end_ms": u["required_end_ms"],
             "required_duration_ms": u["required_duration_ms"]}
            for u in units
        ],
        "estimated_usd": 0.12,
    }
    json_str = json.dumps(plan_payload)
    sha = _db._sha256_bytes(json_str.encode())
    with _db.transaction(db_path) as conn:
        conn.execute(
            "UPDATE document_revisions SET status='stale' "
            "WHERE production_id=? AND kind='render_plan' AND status='active'",
            (production_id,),
        )
        revision_id = _db._id("doc")
        now = _db._now()
        conn.execute(
            "INSERT INTO document_revisions "
            "(id, production_id, kind, revision, payload_json, payload_sha256, status, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (revision_id, production_id, "render_plan", 1,
             json_str, sha, "active", now),
        )
    return plan_payload


class TestGateASpendCapEnforcement:
    """Invoke gate_a_spend with smoke config cap enforcement."""

    def test_spend_cap_blocks_excessive_estimate(self, db, prod, tmp_path, monkeypatch):
        """Requirement 1: Spend gate reads cap from config and blocks if exceeded."""
        monkeypatch.setenv("PRODUCTION_DB_PATH", db)
        from scripts.produce_db import invoke_gate_a_spend

        units = _plan_units(prod["id"], [
            {"asset_type": "generated_video", "model": "seedance_2_0",
             "audio_policy": "BROLL_FLEX", "final_audio_source": "none",
             "provider_audio_usage": "discarded", "text_policy": "NO_VISIBLE_TEXT",
             "visual_function": "illustrate", "narrative_claim": "test",
             "information_to_show": "test", "viewer_takeaway": "test",
             "required_action": "slow pan", "distinctness_requirement": "test",
             "semantic_acceptance_criteria": "matches", "concept_key": "test"},
        ], db_path=db)

        _save_render_plan(prod["id"], units, db_path=db)
        # Override estimated_usd to exceed the default cap ($0.25)
        with _db.transaction(db) as conn:
            plan_record = conn.execute(
                "SELECT id, payload_json FROM document_revisions "
                "WHERE production_id=? AND kind='render_plan' AND status='active'",
                (prod["id"],),
            ).fetchone()
            plan = json.loads(plan_record["payload_json"])
            plan["estimated_usd"] = 0.50
            json_str = json.dumps(plan)
            conn.execute(
                "UPDATE document_revisions SET payload_json=?, payload_sha256=? WHERE id=?",
                (json_str, _db._sha256_bytes(json_str.encode()), plan_record["id"]),
            )

        with pytest.raises(RuntimeError) as exc:
            invoke_gate_a_spend({"production_id": prod["id"]}, tmp_path)
        assert "GATE_A_SPEND_BLOCKED" in str(exc.value)
        assert "exceeds max_total_usd" in str(exc.value)

    def test_provider_job_cap_blocks_too_many_units(self, db, prod, tmp_path):
        """Requirement 2: Blocks if provider jobs exceed max_paid_provider_jobs (default=2)."""
        from scripts.produce_db import invoke_gate_a_spend

        units = _plan_units(prod["id"], [
            {"asset_type": "generated_video", "model": "seedance_2_0",
             "audio_policy": "BROLL_FLEX", "final_audio_source": "none",
             "provider_audio_usage": "discarded", "text_policy": "NO_VISIBLE_TEXT",
             "visual_function": "illustrate", "narrative_claim": "test",
             "information_to_show": "test", "viewer_takeaway": "test",
             "required_action": "slow pan", "distinctness_requirement": "test",
             "semantic_acceptance_criteria": "matches", "concept_key": "test"},
            {"asset_type": "generated_video", "model": "kling3_0",
             "audio_policy": "BROLL_FLEX", "final_audio_source": "none",
             "provider_audio_usage": "discarded", "text_policy": "NO_VISIBLE_TEXT",
             "visual_function": "illustrate", "narrative_claim": "test",
             "information_to_show": "test", "viewer_takeaway": "test",
             "required_action": "slow pan", "distinctness_requirement": "test",
             "semantic_acceptance_criteria": "matches", "concept_key": "test"},
            {"asset_type": "generated_video", "model": "kling3_0",
             "audio_policy": "BROLL_FLEX", "final_audio_source": "none",
             "provider_audio_usage": "discarded", "text_policy": "NO_VISIBLE_TEXT",
             "visual_function": "illustrate", "narrative_claim": "test",
             "information_to_show": "test", "viewer_takeaway": "test",
             "required_action": "slow pan", "distinctness_requirement": "test",
             "semantic_acceptance_criteria": "matches", "concept_key": "test"},
        ], db_path=db)

        _save_render_plan(prod["id"], units, db_path=db)

        with pytest.raises(RuntimeError) as exc:
            invoke_gate_a_spend({"production_id": prod["id"]}, tmp_path)
        assert "GATE_A_SPEND_BLOCKED" in str(exc.value)
        assert "exceeding max_paid_provider_jobs" in str(exc.value)

    def test_allows_under_cap(self, db, prod, tmp_path, monkeypatch):
        """Gate passes when caps are within limits."""
        monkeypatch.setenv("YT_TEST_MODE", "1")
        from scripts.produce_db import invoke_gate_a_spend

        units = _plan_units(prod["id"], [
            {"asset_type": "generated_video", "model": "seedance_2_0",
             "audio_policy": "BROLL_FLEX", "final_audio_source": "none",
             "provider_audio_usage": "discarded", "text_policy": "NO_VISIBLE_TEXT",
             "visual_function": "illustrate", "narrative_claim": "test",
             "information_to_show": "test", "viewer_takeaway": "test",
             "required_action": "slow pan", "distinctness_requirement": "test",
             "semantic_acceptance_criteria": "matches", "concept_key": "test"},
        ], db_path=db)

        _save_render_plan(prod["id"], units, db_path=db)

        result = invoke_gate_a_spend({"production_id": prod["id"]}, tmp_path)
        assert result["status"] == "pass"

    def test_local_graphic_with_provider_prompt_blocks(self, db, prod, tmp_path):
        """Requirement 3: Blocks if local graphic has provider_visual_prompt."""
        from scripts.produce_db import invoke_gate_a_spend

        # Create a local_graphic render unit with a provider_visual_prompt in metadata
        units = _plan_units(prod["id"], [
            {"asset_type": "local_graphic", "model": None,
             "audio_policy": "SILENT_GRAPHIC", "final_audio_source": "none",
             "provider_audio_usage": "discarded", "text_policy": "DETERMINISTIC_GRAPHIC",
             "render_mode": "deterministic_graphic",
             "metadata": {"provider_visual_prompt": "This should not happen for local graphic"}},
        ], db_path=db)

        _save_render_plan(prod["id"], units, db_path=db)

        with pytest.raises(RuntimeError) as exc:
            invoke_gate_a_spend({"production_id": prod["id"]}, tmp_path)
        assert "GATE_A_SPEND_BLOCKED" in str(exc.value)
        assert "local-graphic" in str(exc.value).lower()

    def test_provider_prompt_text_risk_blocks(self, db, prod, tmp_path):
        """Requirement 4: Blocks if provider-eligible unit has text-risk prompt."""
        from scripts.produce_db import invoke_gate_a_spend

        # Create a provider-eligible unit with a text-risk prompt
        units = _plan_units(prod["id"], [
            {"asset_type": "generated_video", "model": "seedance_2_0",
             "audio_policy": "BROLL_FLEX", "final_audio_source": "none",
             "provider_audio_usage": "discarded", "text_policy": "NO_VISIBLE_TEXT",
             "visual_function": "illustrate", "narrative_claim": "test",
             "information_to_show": "test", "viewer_takeaway": "test",
             "required_action": "slow pan", "distinctness_requirement": "test",
             "semantic_acceptance_criteria": "matches", "concept_key": "test",
             "metadata": {"provider_visual_prompt": "Harvard Business Review says..."}},
        ], db_path=db)

        _save_render_plan(prod["id"], units, db_path=db)

        with pytest.raises(RuntimeError) as exc:
            invoke_gate_a_spend({"production_id": prod["id"]}, tmp_path)
        assert "GATE_A_SPEND_BLOCKED" in str(exc.value)
        assert "text-risk" in str(exc.value).lower()

    def test_fixed_estimated_usd_key(self, db, prod, tmp_path, monkeypatch):
        """The estimated_usd field now reads 'estimated_usd' (not 'estimated_cost_usd')."""
        monkeypatch.setenv("YT_TEST_MODE", "1")
        from scripts.produce_db import invoke_gate_a_spend

        units = _plan_units(prod["id"], [
            {"asset_type": "generated_video", "model": "seedance_2_0",
             "audio_policy": "BROLL_FLEX", "final_audio_source": "none",
             "provider_audio_usage": "discarded", "text_policy": "NO_VISIBLE_TEXT",
             "visual_function": "illustrate", "narrative_claim": "test",
             "information_to_show": "test", "viewer_takeaway": "test",
             "required_action": "slow pan", "distinctness_requirement": "test",
             "semantic_acceptance_criteria": "matches", "concept_key": "test"},
        ], db_path=db)

        _save_render_plan(prod["id"], units, db_path=db)
        result = invoke_gate_a_spend({"production_id": prod["id"]}, tmp_path)
        assert result["status"] == "pass"
        # estimated_usd should reflect the plan's value (0.12), not default to 0
        assert abs(result.get("estimated_usd", 0) - 0.12) < 0.001

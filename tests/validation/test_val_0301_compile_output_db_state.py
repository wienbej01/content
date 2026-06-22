"""VAL-0301: Validate compile output DB state — no exact text in provider prompts.

Creates render units via plan_render_units with the split metadata fields
(provider_visual_prompt + deterministic_text_spec) as produced by
_compose_generation_prompt from ENG-0303, then validates DB invariants.
"""
import json
import os
from pathlib import Path

import pytest

import production_db as _db
from production_repo import commit_timeline_spans, plan_render_units


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db.migrate(str(p))
    yield str(p)
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    return _db.ensure_production("val_0301_compile_output", db_path=db)


def _make_spec(span_id, **overrides):
    base = {
        "asset_type": "generated_video",
        "model": "kling3_0",
        "audio_policy": "BROLL_FLEX",
        "final_audio_source": "none",
        "provider_audio_usage": "discarded",
        "text_policy": "NO_VISIBLE_TEXT",
        "visual_function": "illustrate",
        "narrative_claim": "test narrative",
        "information_to_show": "test visual",
        "viewer_takeaway": "test takeaway",
        "required_action": "slow pan",
        "distinctness_requirement": "test distinctness",
        "semantic_acceptance_criteria": "matches test",
        "render_mode": "generated_video",
        "concept_key": "test_concept",
        "concept_hash": "test_hash",
        "span_id": span_id,
    }
    base.update(overrides)
    return base


class TestVal0301CompileOutputDbState:
    """Validate that exact text never leaks into provider-prompt metadata fields."""

    def test_exact_text_only_in_deterministic_spec(self, db, prod):
        """James intro, HBR, McKinsey → stored in deterministic_text_spec, not prompt."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "JAMES_INTRO", "start_ms": 0, "end_ms": 5000},
            {"label": "HBR_REF", "start_ms": 5000, "end_ms": 10000},
            {"label": "MCKINSEY_REF", "start_ms": 10000, "end_ms": 15000},
            {"label": "SAFE_BROLL", "start_ms": 15000, "end_ms": 20000},
        ], db_path=db)

        units = plan_render_units(prod["id"], [
            # James intro → deterministic_text_spec (title_card), no provider prompt
            _make_spec(spans[0]["id"],
                asset_type="local_graphic",
                text_policy="DETERMINISTIC_GRAPHIC",
                render_mode="deterministic_graphic",
                deterministic_text_spec={
                    "type": "title_card",
                    "headline": "I'M JAMES HARRINGTON",
                    "text": "I'M JAMES HARRINGTON. MCKINSEY'S",
                },
            ),
            # HBR source → deterministic_text_spec (source_card), no provider prompt
            _make_spec(spans[1]["id"],
                asset_type="local_graphic",
                text_policy="DETERMINISTIC_GRAPHIC",
                render_mode="deterministic_graphic",
                deterministic_text_spec={
                    "type": "source_card",
                    "headline": "Harvard Business Review",
                    "text": "Harvard Business Review 2026 study",
                },
            ),
            # McKinsey source → deterministic_text_spec (source_card), no provider prompt
            _make_spec(spans[2]["id"],
                asset_type="local_graphic",
                text_policy="DETERMINISTIC_GRAPHIC",
                render_mode="deterministic_graphic",
                deterministic_text_spec={
                    "type": "source_card",
                    "headline": "McKinsey",
                    "text": "McKinsey latest research",
                },
            ),
            # Safe b-roll → provider_visual_prompt only, no deterministic_text_spec
            _make_spec(spans[3]["id"],
                provider_visual_prompt="Cinematic establishing shot of a modern office with warm lighting",
                prompt="Cinematic establishing shot of a modern office with warm lighting",
            ),
        ], db_path=db)

        # Read back from DB
        conn = _db.connect(db)
        rows = conn.execute(
            "SELECT id, label, ordinal, asset_type, text_policy, render_mode, "
            "metadata_json FROM render_units "
            "WHERE production_id=? AND status!='stale' ORDER BY ordinal",
            (prod["id"],)
        ).fetchall()
        conn.close()

        assert len(rows) == 4

        # Validate each render unit
        for row in rows:
            meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
            dts = meta.get("deterministic_text_spec")
            pvp = meta.get("provider_visual_prompt") or meta.get("prompt")

            if row["label"] in ("JAMES_INTRO", "HBR_REF", "MCKINSEY_REF"):
                # These are deterministic-graphic units
                assert dts is not None, f"{row['label']}: expected deterministic_text_spec"
                assert row["asset_type"] == "local_graphic"
                assert row["text_policy"] == "DETERMINISTIC_GRAPHIC"
                assert row["render_mode"] == "deterministic_graphic"
                # Provider prompt must NOT contain exact text
                if pvp:
                    assert "Title card" not in pvp
                    assert "Harvard Business Review" not in pvp
                    assert "McKinsey" not in pvp
            else:
                # SAFE_BROLL: provider-visual only
                assert dts is None, f"{row['label']}: expected no deterministic_text_spec"
                assert row["asset_type"] == "generated_video"
                assert row["text_policy"] == "NO_VISIBLE_TEXT"
                assert row["render_mode"] == "generated_video"
                assert pvp is not None
                assert "Harvard Business Review" not in pvp
                assert "McKinsey" not in pvp

    def test_risk_query_returns_zero(self, db, prod):
        """SQL risk query must return zero rows: provider_visual_prompt with exact text."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "JAMES_INTRO", "start_ms": 0, "end_ms": 5000},
            {"label": "HBR_REF", "start_ms": 5000, "end_ms": 10000},
            {"label": "MCKINSEY_REF", "start_ms": 10000, "end_ms": 15000},
            {"label": "SAFE_BROLL", "start_ms": 15000, "end_ms": 20000},
        ], db_path=db)

        plan_render_units(prod["id"], [
            _make_spec(spans[0]["id"],
                asset_type="local_graphic",
                text_policy="DETERMINISTIC_GRAPHIC",
                render_mode="deterministic_graphic",
                deterministic_text_spec={"type": "title_card", "text": "I'M JAMES HARRINGTON"},
            ),
            _make_spec(spans[1]["id"],
                asset_type="local_graphic",
                text_policy="DETERMINISTIC_GRAPHIC",
                render_mode="deterministic_graphic",
                deterministic_text_spec={"type": "source_card", "text": "Harvard Business Review"},
            ),
            _make_spec(spans[2]["id"],
                asset_type="local_graphic",
                text_policy="DETERMINISTIC_GRAPHIC",
                render_mode="deterministic_graphic",
                deterministic_text_spec={"type": "source_card", "text": "McKinsey research"},
            ),
            _make_spec(spans[3]["id"],
                provider_visual_prompt="Cinematic office shot",
                prompt="Cinematic office shot",
            ),
        ], db_path=db)

        # Risk query: provider_visual_prompt containing Title card, HBR, or McKinsey
        conn = _db.connect(db)
        risky = conn.execute(
            """SELECT id, metadata_json FROM render_units
               WHERE production_id=?
                 AND metadata_json LIKE '%provider_visual_prompt%'
                 AND (
                      metadata_json LIKE '%Title card:%'
                   OR metadata_json LIKE '%Harvard Business Review%'
                   OR metadata_json LIKE '%McKinsey%'
                 )""",
            (prod["id"],)
        ).fetchall()
        conn.close()

        assert len(risky) == 0, (
            f"Expected zero risky rows, got {len(risky)}: "
            + "; ".join(r["id"] for r in risky)
        )

    def test_local_graphics_not_provider_eligible(self, db, prod):
        """local_graphic render units are NOT provider-eligible."""
        from media_contract import is_provider_eligible_asset_type

        spans = commit_timeline_spans(prod["id"], [
            {"label": "GRAPHIC", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        plan_render_units(prod["id"], [
            _make_spec(spans[0]["id"],
                asset_type="local_graphic",
                text_policy="DETERMINISTIC_GRAPHIC",
                render_mode="deterministic_graphic",
                deterministic_text_spec={"type": "title_card", "text": "Test"},
            ),
        ], db_path=db)

        conn = _db.connect(db)
        rows = conn.execute(
            "SELECT asset_type FROM render_units WHERE production_id=? AND status!='stale'",
            (prod["id"],)
        ).fetchall()
        conn.close()

        assert len(rows) == 1
        assert not is_provider_eligible_asset_type(rows[0]["asset_type"]), (
            f"local_graphic should not be provider-eligible"
        )
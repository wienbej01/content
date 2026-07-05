"""TKT-501: Claim-linked research anchors in compile-time prompts.

Verifies that _compose_generation_prompt resolves claim_refs/narrative_claim
to research brief facts and appends FACTUAL ANCHORS blocks.
"""
import json
import os
from pathlib import Path

import pytest

import production_db as _db
from produce_db import _compose_generation_prompt
from authoring_service import save_research_brief


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test_anchors.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db._db_path_override = str(p)
    _db.migrate(str(p))
    yield str(p)
    _db._db_path_override = None
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    return _db.ensure_production("test_anchors", video_type="short", db_path=db)


def _make_research_with_citations(prod_id, citations, db_path):
    brief_payload = {
        "seed": "test",
        "angle": "test angle",
        "key_claims": [
            {"claim": "The Eiffel Tower was built in 1889.", "source": {"title": "Wikipedia", "url": "https://example.com/1", "year": "2024"}},
            {"claim": "Paris has 2.1M residents as of 2023.", "source": {"title": "INSEE", "url": "https://example.com/2", "year": "2023"}},
        ],
        "research_text": "Test research text.",
        "sources": [s.get("source", s) for s in [
            {"title": "Wikipedia", "url": "https://example.com/1", "year": "2024"},
            {"title": "INSEE", "url": "https://example.com/2", "year": "2023"},
            {"title": "Britannica", "url": "https://example.com/3", "year": "2024"},
        ]],
    }
    return save_research_brief(
        production_id=prod_id,
        brief_payload=brief_payload,
        citations=citations,
        db_path=db_path,
    )


class TestPromptAnchorsBaseline:
    """Baseline: _compose_generation_prompt does not include research anchors."""

    def test_prompt_lacks_research_anchors_before_implementation(self):
        """Verify that the current prompt composition has no research anchors."""
        vi = {"visual_function": "illustrate", "narrative_claim": "The Eiffel Tower was built in 1889."}
        prompt, dts, override = _compose_generation_prompt(vi, "broll_environment", None)
        if prompt:
            assert "FACTUAL ANCHORS" not in prompt, (
                "Before TKT-501, prompts should NOT contain FACTUAL ANCHORS block"
            )


class TestPromptAnchors:
    """TKT-501: claim-linked research anchors in compile-time prompts."""

    def test_resolvable_claim_gets_anchors_in_prompt(self, db, prod):
        """Prompt includes FACTUAL ANCHORS when claim matches research key_claim."""
        citations = [
            {"url": "https://example.com/1", "title": "Wikipedia", "source_type": "web",
             "published_at": "2024", "is_primary": True, "id": "cit_001"},
            {"url": "https://example.com/2", "title": "INSEE", "source_type": "web",
             "published_at": "2023", "is_primary": True, "id": "cit_002"},
            {"url": "https://example.com/3", "title": "Britannica", "source_type": "web",
             "published_at": "2024", "is_primary": True, "id": "cit_003"},
        ]
        doc = _make_research_with_citations(prod["id"], citations, db)

        claim_lookup = {
            "C001": {
                "claim_id": "C001", "claim_text": "The Eiffel Tower was built in 1889.",
                "claim_type": "historical_fact", "source_id": "https://example.com/1",
                "citation_status": "verified", "requires_visual_reinforcement": True,
            },
        }

        vi = {
            "visual_function": "illustrate",
            "narrative_claim": "The Eiffel Tower was built in 1889.",
            "claim_refs": ["C001"],
        }
        prompt, dts, override, anchors_meta = _compose_generation_prompt(
            vi, "broll_environment", None,
            research_brief_doc=doc, citations=citations, claim_lookup=claim_lookup,
            return_anchors_meta=True,
        )

        assert prompt is not None
        assert "FACTUAL ANCHORS" in prompt, f"Expected FACTUAL ANCHORS in prompt: {prompt}"
        assert "Wikipedia" in prompt
        assert anchors_meta["anchor_status"] == "resolved"
        assert len(anchors_meta["citation_ids"]) >= 1

    def test_unresolvable_claim_records_unresolved(self, db, prod):
        """anchor_status is unresolved for claims with no matching research."""
        citations = [
            {"url": "https://example.com/1", "title": "Wiki", "source_type": "web",
             "published_at": "2024", "is_primary": True},
            {"url": "https://example.com/2", "title": "Site2", "source_type": "web",
             "published_at": "2023", "is_primary": True},
            {"url": "https://example.com/3", "title": "Site3", "source_type": "web",
             "published_at": "2024", "is_primary": True},
        ]
        doc = _make_research_with_citations(prod["id"], citations, db)

        vi = {
            "visual_function": "illustrate",
            "narrative_claim": "Some unresolvable claim with no match.",
            "claim_refs": ["C_Z"],
        }
        prompt, dts, override, anchors_meta = _compose_generation_prompt(
            vi, "broll_environment", None,
            research_brief_doc=doc, citations=citations, claim_lookup={},
            return_anchors_meta=True,
        )

        if prompt:
            assert "FACTUAL ANCHORS" not in prompt
        assert anchors_meta.get("anchor_status") == "unresolved"
        assert not anchors_meta.get("citation_ids")

    def test_prompt_without_claim_refs_no_anchors(self):
        """Non-claim beats don't get anchors."""
        vi = {"visual_function": "illustrate", "narrative_claim": ""}
        prompt, dts, override, anchors_meta = _compose_generation_prompt(
            vi, "broll_environment", None,
            return_anchors_meta=True,
        )
        if prompt:
            assert "FACTUAL ANCHORS" not in prompt
        assert anchors_meta.get("anchor_status") == "none_applicable"

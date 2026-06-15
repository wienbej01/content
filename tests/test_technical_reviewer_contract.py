#!/usr/bin/env python3
"""tests/test_technical_reviewer_contract.py — PTC-REVIEW-01: cost/duration must not block."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PROMPT_PATH = ROOT / "docs" / "reviewer_prompts" / "technical.md"


def _load_review():
    spec = importlib.util.spec_from_file_location("review", ROOT / "scripts" / "review.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_technical_prompt_does_not_block_on_cost():
    """The BLOCKING section must NOT list cost/budget as a blocking condition."""
    text = PROMPT_PATH.read_text()
    # Find the BLOCKING section
    block_start = text.index("BLOCKING conditions")
    block_section = text[block_start:]
    # Must contain the DO NOT block instruction for cost
    assert "DO NOT block on cost" in block_section
    # The old blocking bullet must be gone
    assert "Total cost over the budget cap" not in block_section
    assert ">$3 without justification" not in text


def test_technical_prompt_does_not_block_on_duration():
    """Duration-over-limit must NOT be a blocking condition."""
    text = PROMPT_PATH.read_text()
    block_start = text.index("BLOCKING conditions")
    block_section = text[block_start:]
    # Old blocking bullets removed
    assert "hero beat > 15s" not in block_section
    assert "b-roll beat > 6.5s" not in block_section
    assert "must split" not in block_section.split("DO NOT block")[0]
    # DO NOT block instruction covers duration
    assert "model-duration limits" in block_section


def test_technical_prompt_still_blocks_on_impossible_model():
    """Genuine feasibility issues must still block."""
    text = PROMPT_PATH.read_text()
    block_start = text.index("BLOCKING conditions")
    block_section = text[block_start:]
    assert "no valid generation model" in block_section
    assert "impossible asset assignment" in block_section


def test_technical_prompt_still_blocks_on_reference_required_false():
    """Hero beat with reference_required=false must still block."""
    text = PROMPT_PATH.read_text()
    block_start = text.index("BLOCKING conditions")
    block_section = text[block_start:]
    assert "reference_required=false" in block_section


def test_aggregate_recommendation_does_not_escalate():
    """A technical verdict with cost/duration in recommended_fixes (not blocking_issues) passes."""
    R = _load_review()

    def stub(name, artifact, kind):
        if name == "technical":
            return {
                "persona": "technical", "status": "pass", "overall_score": 4.0,
                "blocking_issues": [],
                "recommended_fixes": [
                    "B012: hero beat costs $4.20 — high but Gate A owns budget",
                    "B007: 8s b-roll exceeds 6s Kling limit — reconciliation will split",
                ],
            }
        return {"persona": name, "status": "pass", "overall_score": 4.2,
                "blocking_issues": [], "recommended_fixes": []}

    passed, report = R.review({"beats": [{"beat_id": "B001"}]}, "storyboard", stub=stub)
    assert passed, f"should pass when cost/duration are only recommendations: {report}"
    assert not report["has_mandatory"]
    assert len(report["recommendations"]) == 2


def test_aggregate_genuine_block_still_escalates():
    """A technical verdict with a real feasibility block still fails."""
    R = _load_review()

    def stub(name, artifact, kind):
        if name == "technical":
            return {
                "persona": "technical", "status": "fail", "overall_score": 2.0,
                "blocking_issues": ["B005: no valid generation model for beat type 'hologram'"],
                "recommended_fixes": [],
            }
        return {"persona": name, "status": "pass", "overall_score": 4.2,
                "blocking_issues": [], "recommended_fixes": []}

    passed, report = R.review({"beats": [{"beat_id": "B001"}]}, "storyboard", stub=stub)
    assert not passed, "genuine feasibility block must still escalate"
    assert report["has_mandatory"]
    assert any("hologram" in b["issue"] for b in report["blocking_issues"])

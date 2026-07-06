"""TKT-202: Unit tests for semantic_verifier module.

Tests:
1. Fixture verifier: pass verdict recorded with correct schema
2. Fixture verifier: must_avoid violation produces fail
3. get_verifier: backend none returns None
4. get_verifier: invalid backend raises ValueError
5. get_verifier: fixture backend returns FixtureVerifier
6. VisionQAVerifier verdict rules: pass conditions
7. VisionQAVerifier verdict rules: fail on claim not supported
8. VisionQAVerifier verdict rules: fail on must_avoid violations
9. VisionQAVerifier verdict rules: fail on low confidence
10. VisionQAVerifier verdict rules: fail on missing must_show
"""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import semantic_verifier as sv
from semantic_role_pipeline import Verifier


def test_fixture_verifier_pass_verdict():
    """Fixture verifier produces pass result with full verdict schema."""
    verifier = sv.FixtureVerifier()
    result = verifier.verify(
        render_unit_id="ru_test_001",
        visual_role="broll_evidence",
        frame_metadata=[],
        video_path=Path("/fake/video.mp4"),
    )
    assert result["result"] == "pass"
    assert result["reason"] is None
    details = result["details"]
    assert details["backend"] == "fixture"
    assert details["verdict"]["claim_supported"] is True
    assert details["verdict"]["must_avoid_violations"] == []
    assert details["verdict"]["confidence"] >= sv.CONFIDENCE_THRESHOLD


def test_fixture_verifier_fail_on_unit_id():
    """Fixture verifier configured to fail specific unit IDs."""
    verifier = sv.FixtureVerifier(config={"fail_on_unit_ids": ["ru_bad_001"]})
    result = verifier.verify(
        render_unit_id="ru_bad_001",
        visual_role="broll_evidence",
        frame_metadata=[],
        video_path=Path("/fake/video.mp4"),
    )
    assert result["result"] == "fail"
    assert result["reason"] == "fixture_configured_fail"
    details = result["details"]
    assert details["verdict"]["claim_supported"] is False
    assert "fixture_configured_violation" in details["verdict"]["must_avoid_violations"]


def test_fixture_verifier_fail_on_visual_role():
    """Fixture verifier configured to fail specific visual roles."""
    verifier = sv.FixtureVerifier(config={"fail_on_visual_roles": ["broll_bad"]})
    result = verifier.verify(
        render_unit_id="ru_any",
        visual_role="broll_bad",
        frame_metadata=[],
        video_path=Path("/fake/video.mp4"),
    )
    assert result["result"] == "fail"
    assert result["reason"] == "fixture_configured_fail"


def test_fixture_verifier_pass_unit_not_in_fail_list():
    """Fixture verifier passes units not in fail list."""
    verifier = sv.FixtureVerifier(config={"fail_on_unit_ids": ["ru_bad"]})
    result = verifier.verify(
        render_unit_id="ru_good",
        visual_role="broll_evidence",
        frame_metadata=[],
        video_path=Path("/fake/video.mp4"),
    )
    assert result["result"] == "pass"


def test_get_verifier_none_backend():
    """get_verifier returns None when SEMANTIC_QA_BACKEND=none."""
    os.environ["SEMANTIC_QA_BACKEND"] = "none"
    v = sv.get_verifier()
    assert v is None


def test_get_verifier_fixture_backend():
    """get_verifier returns FixtureVerifier when backend=fixture."""
    os.environ["SEMANTIC_QA_BACKEND"] = "fixture"
    v = sv.get_verifier()
    assert v is not None
    assert isinstance(v, sv.FixtureVerifier)


def test_get_verifier_vision_backend():
    """get_verifier returns VisionQAVerifier when backend=vision."""
    os.environ["SEMANTIC_QA_BACKEND"] = "vision"
    v = sv.get_verifier()
    assert v is not None
    assert isinstance(v, sv.VisionQAVerifier)


def test_get_verifier_invalid_backend():
    """get_verifier raises ValueError on invalid backend."""
    os.environ["SEMANTIC_QA_BACKEND"] = "invalid_backend"
    with pytest.raises(ValueError, match="BLOCKED_SEMANTIC_QA_BACKEND"):
        sv.get_verifier()


def test_get_verifier_default_is_none():
    """get_verifier returns None when env var is not set (default none)."""
    os.environ.pop("SEMANTIC_QA_BACKEND", None)
    v = sv.get_verifier()
    assert v is None


def test_get_verifier_case_insensitive():
    """Backend names are case-insensitive."""
    os.environ["SEMANTIC_QA_BACKEND"] = "FIXTURE"
    v = sv.get_verifier()
    assert isinstance(v, sv.FixtureVerifier)


class TestVisionQAVerifierVerdictRules:
    """Unit tests for VisionQAVerifier._apply_verdict_rules."""

    @pytest.fixture
    def v(self):
        return sv.VisionQAVerifier()

    def test_pass_all_conditions(self, v):
        status, reason = v._apply_verdict_rules(
            {"claim_supported": True, "must_show_present": ["person", "desk"],
             "must_avoid_violations": [], "described_content": "test",
             "confidence": 0.95},
            must_show=["person", "desk"],
        )
        assert status == "pass"
        assert reason is None

    def test_fail_claim_not_supported(self, v):
        status, reason = v._apply_verdict_rules(
            {"claim_supported": False, "must_show_present": [],
             "must_avoid_violations": [], "described_content": "test",
             "confidence": 0.95},
            must_show=[],
        )
        assert status == "fail"
        assert "claim_not_supported" in reason

    def test_fail_must_avoid_violations(self, v):
        status, reason = v._apply_verdict_rules(
            {"claim_supported": True, "must_show_present": [],
             "must_avoid_violations": ["readable text"],
             "described_content": "test", "confidence": 0.95},
            must_show=[],
        )
        assert status == "fail"
        assert "must_avoid_violations" in reason

    def test_fail_low_confidence(self, v):
        status, reason = v._apply_verdict_rules(
            {"claim_supported": True, "must_show_present": [],
             "must_avoid_violations": [], "described_content": "test",
             "confidence": 0.1},
            must_show=[],
        )
        assert status == "fail"
        assert "confidence" in reason
        assert "threshold" in reason

    def test_fail_missing_must_show(self, v):
        status, reason = v._apply_verdict_rules(
            {"claim_supported": True, "must_show_present": ["person"],
             "must_avoid_violations": [], "described_content": "test",
             "confidence": 0.95},
            must_show=["person", "desk", "laptop"],
        )
        assert status == "fail"
        assert "must_show_missing" in reason
        assert "desk" in reason or "laptop" in reason

    def test_pass_empty_must_show(self, v):
        status, reason = v._apply_verdict_rules(
            {"claim_supported": True, "must_show_present": [],
             "must_avoid_violations": [], "described_content": "test",
             "confidence": 0.95},
            must_show=[],
        )
        assert status == "pass"

    def test_fail_multiple_reasons(self, v):
        status, reason = v._apply_verdict_rules(
            {"claim_supported": False, "must_show_present": [],
             "must_avoid_violations": ["text"],
             "described_content": "test", "confidence": 0.05},
            must_show=["person"],
        )
        assert status == "fail"
        assert "claim_not_supported" in reason
        assert "must_avoid_violations" in reason
        assert "confidence" in reason
        assert "must_show_missing" in reason

    def test_must_show_case_insensitive_match(self, v):
        status, reason = v._apply_verdict_rules(
            {"claim_supported": True, "must_show_present": ["Person at Desk"],
             "must_avoid_violations": [], "described_content": "test",
             "confidence": 0.95},
            must_show=["person", "desk"],
        )
        assert status == "pass"

    def test_fixture_verifier_implements_abc(self):
        """FixtureVerifier is a valid Verifier subclass."""
        assert issubclass(sv.FixtureVerifier, Verifier)

    def test_vision_qa_verifier_implements_abc(self):
        """VisionQAVerifier is a valid Verifier subclass."""
        assert issubclass(sv.VisionQAVerifier, Verifier)

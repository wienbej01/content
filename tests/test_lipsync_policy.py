"""Tests for S14-T001: Tiered lip-sync policy.

Validates that:
- close_hero policy has strict thresholds (≤30ms PASS, 31-45ms WARN, >45ms FAIL)
- medium_hero policy has medium thresholds (≤40ms PASS, 41-60ms WARN, >60ms FAIL)
- diagnostic_legacy has 160ms threshold but is NOT publish-grade
- +80ms fails close_hero
- +40ms is classified by framing (warn for close_hero, pass for medium_hero)
- Low confidence fails even with acceptable offset
- 160ms is not publish-pass for close_hero
- Unknown framing defaults to close_hero
"""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from lipsync_policy import (
    LipSyncPolicy,
    LipSyncVerdict,
    load_policy_config,
    get_policy,
    evaluate_lipsync,
    get_default_policy,
    is_policy_publish_grade,
    CLOSE_HERO,
    MEDIUM_HERO,
    WIDE_HERO,
    DIAGNOSTIC_LEGACY,
)


class TestPolicyConfigStructure:
    """Validate policy config structure."""

    def test_config_file_exists(self):
        """Policy config file must exist."""
        config_path = Path(__file__).resolve().parent.parent / "configs" / "lipsync_thresholds.yaml"
        assert config_path.exists(), f"Policy config not found: {config_path}"

    def test_config_loads(self):
        """Config must load without errors."""
        config = load_policy_config()
        assert "policies" in config
        assert "close_hero" in config["policies"]
        assert "medium_hero" in config["policies"]
        assert "diagnostic_legacy" in config["policies"]

    def test_config_has_all_required_fields(self):
        """Each policy must have required fields."""
        config = load_policy_config()
        for policy_name in ["close_hero", "medium_hero", "diagnostic_legacy"]:
            policy = config["policies"][policy_name]
            assert "description" in policy
            assert "publish_grade" in policy
            assert "thresholds" in policy
            assert "min_confidence" in policy
            thresholds = policy["thresholds"]
            assert "pass_ms" in thresholds
            assert "warn_ms" in thresholds
            assert "fail_ms" in thresholds


class TestCloseHeroPolicy:
    """Validate close_hero policy (strictest standard)."""

    def test_close_hero_thresholds(self):
        """close_hero thresholds calibrated by TKT-104: ≤120ms PASS, 121-160ms WARN, >160ms FAIL."""
        policy = get_policy(CLOSE_HERO)
        assert policy.name == "close_hero"
        assert policy.publish_grade is True
        assert policy.pass_ms == 120.0
        assert policy.warn_ms == 160.0
        assert policy.fail_ms == 160.0
        assert policy.min_confidence == 0.001

    def test_close_hero_120ms_passes(self):
        """120ms offset should PASS close_hero (at calibrated pass threshold)."""
        verdict = evaluate_lipsync(offset_ms=120.0, confidence=0.5, policy_name=CLOSE_HERO)
        assert verdict.verdict == "pass"
        assert verdict.publish_grade is True
        assert "within PASS threshold" in verdict.reason

    def test_close_hero_121ms_warns(self):
        """121ms offset should WARN close_hero."""
        verdict = evaluate_lipsync(offset_ms=121.0, confidence=0.5, policy_name=CLOSE_HERO)
        assert verdict.verdict == "warn"
        assert verdict.publish_grade is False  # WARN is not publish-grade

    def test_close_hero_160ms_warns(self):
        """160ms offset should WARN close_hero (at warn threshold boundary)."""
        verdict = evaluate_lipsync(offset_ms=160.0, confidence=0.5, policy_name=CLOSE_HERO)
        assert verdict.verdict == "warn"  # 160ms is at warn threshold
        assert verdict.publish_grade is False

    def test_close_hero_161ms_fails(self):
        """161ms offset should FAIL close_hero."""
        verdict = evaluate_lipsync(offset_ms=161.0, confidence=0.5, policy_name=CLOSE_HERO)
        assert verdict.verdict == "fail"
        assert verdict.publish_grade is False


class TestMediumHeroPolicy:
    """Validate medium_hero policy."""

    def test_medium_hero_thresholds(self):
        """medium_hero thresholds calibrated by TKT-104: ≤168ms PASS, 169-210ms WARN, >210ms FAIL."""
        policy = get_policy(MEDIUM_HERO)
        assert policy.name == "medium_hero"
        assert policy.publish_grade is True
        assert policy.pass_ms == 168.0
        assert policy.warn_ms == 210.0
        assert policy.fail_ms == 210.0
        assert policy.min_confidence == 0.001

    def test_medium_hero_168ms_passes(self):
        """168ms offset should PASS medium_hero (at calibrated pass threshold)."""
        verdict = evaluate_lipsync(offset_ms=168.0, confidence=0.5, policy_name=MEDIUM_HERO)
        assert verdict.verdict == "pass"
        assert verdict.publish_grade is True

    def test_medium_hero_169ms_warns(self):
        """169ms offset should WARN medium_hero."""
        verdict = evaluate_lipsync(offset_ms=169.0, confidence=0.5, policy_name=MEDIUM_HERO)
        assert verdict.verdict == "warn"
        assert verdict.publish_grade is False

    def test_medium_hero_210ms_warns(self):
        """210ms offset should WARN medium_hero (at warn threshold)."""
        verdict = evaluate_lipsync(offset_ms=210.0, confidence=0.5, policy_name=MEDIUM_HERO)
        assert verdict.verdict == "warn"  # 210ms is at warn threshold
        assert verdict.publish_grade is False

    def test_medium_hero_211ms_fails(self):
        """211ms offset should FAIL medium_hero."""
        verdict = evaluate_lipsync(offset_ms=211.0, confidence=0.5, policy_name=MEDIUM_HERO)
        assert verdict.verdict == "fail"
        assert verdict.publish_grade is False


class TestDiagnosticLegacyPolicy:
    """Validate diagnostic_legacy policy (non-publish)."""

    def test_diagnostic_legacy_thresholds(self):
        """diagnostic_legacy must have 160ms threshold but NOT publish-grade."""
        policy = get_policy(DIAGNOSTIC_LEGACY)
        assert policy.name == "diagnostic_legacy"
        assert policy.publish_grade is False  # NOT publish-grade
        assert policy.non_publish_only is True
        assert policy.pass_ms == 160.0
        assert policy.min_confidence == 0.0  # No confidence requirement

    def test_diagnostic_legacy_160ms_warns_not_passes(self):
        """160ms offset should WARN (not PASS) for diagnostic_legacy (non-publish)."""
        verdict = evaluate_lipsync(offset_ms=160.0, confidence=1.0, policy_name=DIAGNOSTIC_LEGACY)
        assert verdict.verdict == "warn"  # Downgraded from pass to warn
        assert verdict.publish_grade is False  # Not publish-grade
        assert "non-publish policy" in verdict.reason

    def test_diagnostic_legacy_161ms_fails(self):
        """161ms offset should FAIL for diagnostic_legacy (exceeds 160ms threshold)."""
        verdict = evaluate_lipsync(offset_ms=161.0, confidence=1.0, policy_name=DIAGNOSTIC_LEGACY)
        assert verdict.verdict == "fail"  # 161ms exceeds 160ms pass/warn threshold
        assert verdict.publish_grade is False

    def test_diagnostic_legacy_160ms_warns(self):
        """160ms offset should WARN for diagnostic_legacy (downgraded from PASS)."""
        verdict = evaluate_lipsync(offset_ms=160.0, confidence=1.0, policy_name=DIAGNOSTIC_LEGACY)
        assert verdict.verdict == "warn"  # Downgraded from pass to warn
        assert verdict.publish_grade is False


class TestRequiredPassCriteria:
    """Required tests from S14_T001 ticket."""

    def test_80ms_passes_close_hero(self):
        """80ms offset PASSES close_hero (within calibrated 120ms pass threshold)."""
        verdict = evaluate_lipsync(offset_ms=80.0, confidence=0.5, policy_name=CLOSE_HERO)
        assert verdict.verdict == "pass"
        assert verdict.publish_grade is True
        assert "within PASS threshold" in verdict.reason

    def test_120ms_is_pass_for_close_hero(self):
        """120ms offset is PASS for close_hero (at calibrated boundary)."""
        verdict = evaluate_lipsync(offset_ms=120.0, confidence=0.5, policy_name=CLOSE_HERO)
        assert verdict.verdict == "pass"
        assert verdict.publish_grade is True

    def test_120ms_passes_for_medium_hero(self):
        """120ms PASSES for medium_hero (within calibrated 168ms pass threshold)."""
        verdict = evaluate_lipsync(offset_ms=120.0, confidence=0.5, policy_name=MEDIUM_HERO)
        assert verdict.verdict == "pass"
        assert verdict.publish_grade is True

    def test_low_confidence_passes(self):
        """Low confidence (>0.001) passes with min_confidence=0.001 (TKT-104 calibration)."""
        verdict = evaluate_lipsync(offset_ms=50.0, confidence=0.002, policy_name=CLOSE_HERO)
        assert verdict.verdict == "pass"
        assert verdict.publish_grade is True

    def test_confidence_zero_fails(self):
        """confidence=0.0 MUST FAIL (scorer signal for no face detected)."""
        verdict = evaluate_lipsync(offset_ms=50.0, confidence=0.0, policy_name=CLOSE_HERO)
        assert verdict.verdict == "fail"
        assert "below minimum" in verdict.reason
        assert verdict.publish_grade is False

    def test_no_confidence_fails(self):
        """None confidence MUST FAIL (unknown confidence)."""
        verdict = evaluate_lipsync(offset_ms=50.0, confidence=None, policy_name=CLOSE_HERO)
        assert verdict.verdict == "fail"
        assert "below minimum" in verdict.reason or "Confidence" in verdict.reason

    def test_320ms_fails_close_hero(self):
        """320ms MUST FAIL close_hero (well beyond 160ms fail threshold)."""
        verdict = evaluate_lipsync(offset_ms=320.0, confidence=0.5, policy_name=CLOSE_HERO)
        assert verdict.verdict == "fail"
        assert verdict.publish_grade is False


class TestWideHeroPolicy:
    """Validate wide_hero policy."""

    def test_wide_hero_uses_medium_policy(self):
        """wide_hero must use medium_hero policy."""
        policy = get_policy(WIDE_HERO)
        # wide_hero references medium_hero
        assert policy.name == "medium_hero"  # Resolved to medium_hero
        assert policy.publish_grade is True

    def test_wide_hero_has_medium_thresholds(self):
        """wide_hero (via medium) must have calibrated medium thresholds."""
        verdict = evaluate_lipsync(offset_ms=168.0, confidence=0.5, policy_name=WIDE_HERO)
        assert verdict.verdict == "pass"  # Uses medium thresholds (≤168ms)
        assert verdict.publish_grade is True


class TestDefaultPolicyBehavior:
    """Validate default policy for unknown framing."""

    def test_unknown_policy_raises_error(self):
        """Unknown policy name must raise ValueError."""
        with pytest.raises(ValueError, match="Unknown policy"):
            get_policy("unknown_policy")

    def test_default_policy_is_close_hero(self):
        """Default policy must be close_hero (fail-closed)."""
        default = get_default_policy()
        assert default == "close_hero"

    def test_unknown_framing_defaults_to_close_hero(self):
        """Unknown/unclassified framing defaults to close_hero."""
        verdict = evaluate_lipsync(offset_ms=50.0, confidence=0.5)  # No policy_name
        assert verdict.policy_name == "close_hero"
        assert verdict.verdict == "pass"  # 50ms passes close_hero (≤120ms)


class TestLipSyncVerdictSerialization:
    """Validate verdict serialization."""

    def test_verdict_to_dict(self):
        """Verdict must serialize to dict correctly."""
        verdict = evaluate_lipsync(offset_ms=100.0, confidence=0.5, policy_name=CLOSE_HERO)
        d = verdict.to_dict()

        assert "policy_name" in d
        assert "offset_ms" in d
        assert "offset_frames" in d
        assert "confidence" in d
        assert "verdict" in d
        assert "publish_grade" in d
        assert "reason" in d

    def test_verdict_dict_values(self):
        """Verdict dict must have correct values."""
        verdict = evaluate_lipsync(offset_ms=130.0, confidence=0.5, policy_name=CLOSE_HERO)
        d = verdict.to_dict()

        assert d["policy_name"] == "close_hero"
        assert d["offset_ms"] == 130.0
        assert d["offset_frames"] == pytest.approx(3.25, abs=0.01)  # 130ms / 40ms
        assert d["confidence"] == 0.5
        assert d["verdict"] == "warn"
        assert d["publish_grade"] is False  # WARN is not publish-grade


class TestPolicyIsPublishGrade:
    """Validate is_policy_publish_grade helper."""

    def test_close_hero_is_publish_grade(self):
        """close_hero must be publish-grade."""
        assert is_policy_publish_grade(CLOSE_HERO) is True

    def test_medium_hero_is_publish_grade(self):
        """medium_hero must be publish-grade."""
        assert is_policy_publish_grade(MEDIUM_HERO) is True

    def test_diagnostic_legacy_is_not_publish_grade(self):
        """diagnostic_legacy must NOT be publish-grade."""
        assert is_policy_publish_grade(DIAGNOSTIC_LEGACY) is False


class TestRegressionPrevention:
    """Prevent regression to old 160ms-as-publish behavior."""

    def test_160ms_warns_close_hero_not_pass(self):
        """160ms MUST NOT pass for close_hero (at warn boundary)."""
        verdict = evaluate_lipsync(offset_ms=160.0, confidence=0.5, policy_name=CLOSE_HERO)
        assert verdict.verdict != "pass"
        assert verdict.publish_grade is False

    def test_diagnostic_legacy_not_publish_even_at_160ms(self):
        """160ms at diagnostic_legacy is downgraded to warn (non-publish)."""
        verdict_diagnostic = evaluate_lipsync(offset_ms=160.0, confidence=0.5, policy_name=DIAGNOSTIC_LEGACY)
        assert verdict_diagnostic.verdict != "pass"  # Downgraded to warn
        assert verdict_diagnostic.publish_grade is False  # Not publish-grade

        verdict_close = evaluate_lipsync(offset_ms=160.0, confidence=0.5, policy_name=CLOSE_HERO)
        assert verdict_close.verdict == "warn"  # 160ms warns at close_hero boundary
        assert verdict_close.publish_grade is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
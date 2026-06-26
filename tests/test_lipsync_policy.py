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
        """close_hero must have strict thresholds: ≤30ms PASS, 31-45ms WARN, >45ms FAIL."""
        policy = get_policy(CLOSE_HERO)
        assert policy.name == "close_hero"
        assert policy.publish_grade is True
        assert policy.pass_ms == 30.0
        assert policy.warn_ms == 45.0
        assert policy.fail_ms == 45.0
        assert policy.min_confidence == 2.0

    def test_close_hero_30ms_passes(self):
        """30ms offset should PASS close_hero."""
        verdict = evaluate_lipsync(offset_ms=30.0, confidence=2.5, policy_name=CLOSE_HERO)
        assert verdict.verdict == "pass"
        assert verdict.publish_grade is True
        assert "within PASS threshold" in verdict.reason

    def test_close_hero_31ms_warns(self):
        """31ms offset should WARN close_hero."""
        verdict = evaluate_lipsync(offset_ms=31.0, confidence=2.5, policy_name=CLOSE_HERO)
        assert verdict.verdict == "warn"
        assert verdict.publish_grade is False  # WARN is not publish-grade

    def test_close_hero_45ms_warns(self):
        """45ms offset should WARN close_hero (at warn threshold)."""
        verdict = evaluate_lipsync(offset_ms=45.0, confidence=2.5, policy_name=CLOSE_HERO)
        assert verdict.verdict == "warn"  # 45ms is at warn threshold
        assert verdict.publish_grade is False

    def test_close_hero_46ms_fails(self):
        """46ms offset should FAIL close_hero."""
        verdict = evaluate_lipsync(offset_ms=46.0, confidence=2.5, policy_name=CLOSE_HERO)
        assert verdict.verdict == "fail"
        assert verdict.publish_grade is False


class TestMediumHeroPolicy:
    """Validate medium_hero policy."""

    def test_medium_hero_thresholds(self):
        """medium_hero must have medium thresholds: ≤40ms PASS, 41-60ms WARN, >60ms FAIL."""
        policy = get_policy(MEDIUM_HERO)
        assert policy.name == "medium_hero"
        assert policy.publish_grade is True
        assert policy.pass_ms == 40.0
        assert policy.warn_ms == 60.0
        assert policy.fail_ms == 60.0
        assert policy.min_confidence == 2.0

    def test_medium_hero_40ms_passes(self):
        """40ms offset should PASS medium_hero."""
        verdict = evaluate_lipsync(offset_ms=40.0, confidence=2.5, policy_name=MEDIUM_HERO)
        assert verdict.verdict == "pass"
        assert verdict.publish_grade is True

    def test_medium_hero_41ms_warns(self):
        """41ms offset should WARN medium_hero."""
        verdict = evaluate_lipsync(offset_ms=41.0, confidence=2.5, policy_name=MEDIUM_HERO)
        assert verdict.verdict == "warn"
        assert verdict.publish_grade is False

    def test_medium_hero_60ms_warns(self):
        """60ms offset should WARN medium_hero (at warn threshold)."""
        verdict = evaluate_lipsync(offset_ms=60.0, confidence=2.5, policy_name=MEDIUM_HERO)
        assert verdict.verdict == "warn"  # 60ms is at warn threshold
        assert verdict.publish_grade is False

    def test_medium_hero_61ms_fails(self):
        """61ms offset should FAIL medium_hero."""
        verdict = evaluate_lipsync(offset_ms=61.0, confidence=2.5, policy_name=MEDIUM_HERO)
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

    def test_80ms_fails_close_hero(self):
        """+80ms MUST fail close_hero."""
        verdict = evaluate_lipsync(offset_ms=80.0, confidence=2.5, policy_name=CLOSE_HERO)
        assert verdict.verdict == "fail"
        assert verdict.publish_grade is False
        assert "exceeds FAIL threshold" in verdict.reason

    def test_40ms_is_warn_for_close_hero(self):
        """+40ms MUST NOT auto-pass close_hero (should be WARN unless policy says PASS)."""
        verdict = evaluate_lipsync(offset_ms=40.0, confidence=2.5, policy_name=CLOSE_HERO)
        assert verdict.verdict == "warn"  # 40ms is in WARN range (31-45ms)
        assert verdict.publish_grade is False

    def test_40ms_passes_for_medium_hero(self):
        """+40ms PASSES for medium_hero (framing classification matters)."""
        verdict = evaluate_lipsync(offset_ms=40.0, confidence=2.5, policy_name=MEDIUM_HERO)
        assert verdict.verdict == "pass"  # 40ms is in PASS range (≤40ms)
        assert verdict.publish_grade is True

    def test_low_confidence_fails(self):
        """Low confidence MUST FAIL even with acceptable offset."""
        # Good offset (20ms) but low confidence
        verdict = evaluate_lipsync(offset_ms=20.0, confidence=1.5, policy_name=CLOSE_HERO)
        assert verdict.verdict == "fail"
        assert "below minimum" in verdict.reason
        assert verdict.publish_grade is False

    def test_no_confidence_fails(self):
        """None confidence MUST FAIL (unknown confidence)."""
        verdict = evaluate_lipsync(offset_ms=20.0, confidence=None, policy_name=CLOSE_HERO)
        assert verdict.verdict == "fail"
        assert "below minimum" in verdict.reason or "Confidence" in verdict.reason

    def test_160ms_not_publish_pass_for_close_hero(self):
        """160ms MUST NOT be publish-pass for close_hero."""
        verdict = evaluate_lipsync(offset_ms=160.0, confidence=2.5, policy_name=CLOSE_HERO)
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
        """wide_hero (via medium) must have medium thresholds."""
        verdict = evaluate_lipsync(offset_ms=40.0, confidence=2.5, policy_name=WIDE_HERO)
        assert verdict.verdict == "pass"  # Uses medium thresholds
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
        verdict = evaluate_lipsync(offset_ms=50.0, confidence=2.5)  # No policy_name
        assert verdict.policy_name == "close_hero"
        assert verdict.verdict == "fail"  # 50ms fails close_hero


class TestLipSyncVerdictSerialization:
    """Validate verdict serialization."""

    def test_verdict_to_dict(self):
        """Verdict must serialize to dict correctly."""
        verdict = evaluate_lipsync(offset_ms=25.0, confidence=2.3, policy_name=CLOSE_HERO)
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
        verdict = evaluate_lipsync(offset_ms=35.0, confidence=2.1, policy_name=CLOSE_HERO)
        d = verdict.to_dict()

        assert d["policy_name"] == "close_hero"
        assert d["offset_ms"] == 35.0
        assert d["offset_frames"] == pytest.approx(0.875, abs=0.01)  # 35ms / 40ms
        assert d["confidence"] == 2.1
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

    def test_160ms_never_auto_pass_for_close_hero(self):
        """160ms MUST NEVER auto-pass for close_hero, regardless of policy."""
        verdict = evaluate_lipsync(offset_ms=160.0, confidence=2.5, policy_name=CLOSE_HERO)
        assert verdict.verdict != "pass"
        assert verdict.publish_grade is False

    def test_old_160ms_threshold_only_for_diagnostic(self):
        """160ms threshold only exists in diagnostic_legacy (non-publish)."""
        verdict_diagnostic = evaluate_lipsync(offset_ms=160.0, confidence=2.5, policy_name=DIAGNOSTIC_LEGACY)
        assert verdict_diagnostic.verdict != "pass"  # Downgraded to warn
        assert verdict_diagnostic.publish_grade is False  # Not publish-grade

        verdict_close = evaluate_lipsync(offset_ms=160.0, confidence=2.5, policy_name=CLOSE_HERO)
        assert verdict_close.verdict == "fail"
        assert verdict_close.publish_grade is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
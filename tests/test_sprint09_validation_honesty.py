"""Test: PARTIAL local rehearsal cannot produce an unconditional PASS.

Sprint 09 must NOT claim unconditional PASS when full production assembly
is BLOCKED by S002.
"""
import json
from pathlib import Path


class TestPartialRehearsalHonesty:
    """The validation report must accurately reflect the partial state."""

    LOOP_DECISION = Path("reports/karpathy_loop/sprint_09/loop_decision.md")

    def test_verdict_is_not_unconditional_pass(self):
        """Verdict must NOT be 'PASS' alone."""
        text = self.LOOP_DECISION.read_text()
        # Check that the verdict is the conditional form
        assert "CONDITIONAL_PASS_COMPENSATION_PIPELINE" in text, (
            "Verdict must be CONDITIONAL_PASS_COMPENSATION_PIPELINE, not bare PASS"
        )

    def test_full_production_status_is_blocked(self):
        """FULL_PRODUCTION_STATUS must be BLOCKED."""
        text = self.LOOP_DECISION.read_text()
        assert "FULL_PRODUCTION_STATUS" in text, "Missing FULL_PRODUCTION_STATUS"
        assert "BLOCKED" in text.split("FULL_PRODUCTION_STATUS")[1][:50], (
            "FULL_PRODUCTION_STATUS must be BLOCKED"
        )

    def test_blocker_s002_documented(self):
        """S002 blocker must be documented."""
        text = self.LOOP_DECISION.read_text()
        assert "S002_HERO_SYNC_FAILED_OR_UNVERIFIED" in text, (
            "Blocker S002_HERO_SYNC_FAILED_OR_UNVERIFIED must be documented"
        )

    def test_next_required_action_is_s002_canary(self):
        """Next required action must be S002 canary render."""
        text = self.LOOP_DECISION.read_text()
        assert "CONTROLLED_S002_CANARY_RENDER" in text, (
            "Next required action must be CONTROLLED_S002_CANARY_RENDER"
        )

    def test_local_rehearsal_is_partial(self):
        """Check 4 (local production rehearsal) must be PARTIAL, not PASS."""
        text = self.LOOP_DECISION.read_text()
        assert "4. Local production rehearsal" in text
        # The status should be PARTIAL
        lines = text.split("\n")
        for line in lines:
            if "Local production rehearsal" in line:
                assert "PARTIAL" in line, f"Check 4 must be PARTIAL, got: {line.strip()}"

    def test_human_review_package_mentions_blocker(self):
        """Human review package must mention the S002 blocker."""
        hrp = Path("reports/karpathy_loop/sprint_09/human_review_package.md")
        assert hrp.exists()
        text = hrp.read_text()
        assert "S002_HERO_SYNC_FAILED_OR_UNVERIFIED" in text or "S002" in text, (
            "Human review package must mention S002 blocker"
        )
        assert "BLOCKED" in text or "BLOCKER" in text, (
            "Human review package must reference BLOCKED state"
        )

    def test_sprint_summary_has_blocker(self):
        """Sprint summary must include the blocker entry."""
        ss = Path("reports/karpathy_loop/sprint_09/sprint_summary.md")
        assert ss.exists()
        text = ss.read_text()
        assert "blocker" in text.lower(), "Sprint summary must include BLOCKER section"
        assert "S002" in text, "Sprint summary must mention S002"

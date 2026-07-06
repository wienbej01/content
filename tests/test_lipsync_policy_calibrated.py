"""TKT-104: Verify that lipsync policy thresholds match the calibration report.

Pins policy constants to the evidence in docs/plans/PPQ_SPRINT_20260704/evidence/TKT-104-calibration.md
and the JSON calibration data at /tmp/kilo/tkt104/calibration.json.
"""
import json
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from lipsync_policy import load_policy_config, get_policy, CLOSE_HERO, MEDIUM_HERO

_CALIBRATION_JSON = Path("/tmp/kilo/tkt104/calibration.json")


def _load_calibration():
    if not _CALIBRATION_JSON.exists():
        pytest.skip(f"Calibration JSON not found: {_CALIBRATION_JSON}")
    with open(_CALIBRATION_JSON) as f:
        return json.load(f)


class TestPolicyMatchesCalibrationReport:
    """Policy YAML constants must match the TKT-104 calibration report."""

    def test_calibration_json_exists(self):
        assert _CALIBRATION_JSON.exists(), (
            f"Calibration JSON required at {_CALIBRATION_JSON}. "
            "Run: python3 scripts/evals/calibrate_sync_thresholds.py --clips <dir> "
            "--json /tmp/kilo/tkt104/calibration.json"
        )

    def test_close_hero_pass_ms_matches_calibration(self):
        cal = _load_calibration()
        policy = get_policy(CLOSE_HERO)
        expected = cal["recommended_thresholds"]["close_hero"]["pass_ms"]
        assert policy.pass_ms == pytest.approx(expected, abs=0.5), (
            f"close_hero pass_ms: policy={policy.pass_ms}, calibration={expected}"
        )

    def test_close_hero_warn_ms_matches_calibration(self):
        cal = _load_calibration()
        policy = get_policy(CLOSE_HERO)
        expected = cal["recommended_thresholds"]["close_hero"]["warn_ms"]
        assert policy.warn_ms == pytest.approx(expected, abs=0.1), (
            f"close_hero warn_ms: policy={policy.warn_ms}, calibration={expected}"
        )

    def test_close_hero_fail_ms_matches_calibration(self):
        cal = _load_calibration()
        policy = get_policy(CLOSE_HERO)
        expected = cal["recommended_thresholds"]["close_hero"]["fail_ms"]
        assert policy.fail_ms == pytest.approx(expected, abs=0.1), (
            f"close_hero fail_ms: policy={policy.fail_ms}, calibration={expected}"
        )

    def test_close_hero_min_confidence_matches_calibration(self):
        cal = _load_calibration()
        policy = get_policy(CLOSE_HERO)
        expected = cal["recommended_thresholds"]["close_hero"]["min_confidence"]
        assert policy.min_confidence == pytest.approx(expected, abs=0.0001), (
            f"close_hero min_confidence: policy={policy.min_confidence}, calibration={expected}"
        )

    def test_medium_hero_pass_ms_matches_calibration(self):
        cal = _load_calibration()
        policy = get_policy(MEDIUM_HERO)
        expected = cal["recommended_thresholds"]["medium_hero"]["pass_ms"]
        assert policy.pass_ms == pytest.approx(expected, abs=0.5), (
            f"medium_hero pass_ms: policy={policy.pass_ms}, calibration={expected}"
        )

    def test_medium_hero_warn_ms_matches_calibration(self):
        cal = _load_calibration()
        policy = get_policy(MEDIUM_HERO)
        expected = cal["recommended_thresholds"]["medium_hero"]["warn_ms"]
        assert policy.warn_ms == pytest.approx(expected, abs=0.1), (
            f"medium_hero warn_ms: policy={policy.warn_ms}, calibration={expected}"
        )

    def test_medium_hero_fail_ms_matches_calibration(self):
        cal = _load_calibration()
        policy = get_policy(MEDIUM_HERO)
        expected = cal["recommended_thresholds"]["medium_hero"]["fail_ms"]
        assert policy.fail_ms == pytest.approx(expected, abs=0.1), (
            f"medium_hero fail_ms: policy={policy.fail_ms}, calibration={expected}"
        )

    def test_medium_hero_min_confidence_matches_calibration(self):
        cal = _load_calibration()
        policy = get_policy(MEDIUM_HERO)
        expected = cal["recommended_thresholds"]["medium_hero"]["min_confidence"]
        assert policy.min_confidence == pytest.approx(expected, abs=0.0001), (
            f"medium_hero min_confidence: policy={policy.min_confidence}, calibration={expected}"
        )


class TestCalibrationVerificationMetrics:
    """Verify the calibration results satisfy ticket acceptance gates."""

    def test_zero_false_pass_close(self):
        cal = _load_calibration()
        assert cal["verification"]["zero_false_pass_close"] is True, (
            f"Calibration allowed {cal['verification']['false_pass_close']} "
            "false-pass on close_hero. Must be zero."
        )

    def test_zero_false_pass_medium(self):
        cal = _load_calibration()
        assert cal["verification"]["zero_false_pass_medium"] is True, (
            f"Calibration allowed {cal['verification']['false_pass_medium']} "
            "false-pass on medium_hero. Must be zero."
        )

    def test_320ms_shifted_fails_policy(self):
        """All 320ms shifted clips must produce fail verdicts."""
        cal = _load_calibration()
        policy_close = get_policy(CLOSE_HERO)
        for r in cal["results"]:
            if r["injected_shift_ms"] == 320:
                assert abs(r["offset_ms"]) > policy_close.pass_ms or not r["face_track_found"], (
                    f"{r['clip']} at +320ms: offset={r['offset_ms']}ms <= "
                    f"pass_ms={policy_close.pass_ms}ms (false pass)"
                )

    def test_no_face_clips_recorded(self):
        """Clips without face tracking must be documented."""
        cal = _load_calibration()
        assert "no_face_clips" in cal
        # S001 has no face
        no_face = cal["no_face_clips"]
        assert len(no_face) >= 1, "Expected at least one no-face clip recorded"

    def test_calibration_report_exists(self):
        """Verification that the markdown report exists."""
        report = Path(__file__).resolve().parent.parent / "docs" / "plans" / \
            "PPQ_SPRINT_20260704" / "evidence" / "TKT-104-calibration.md"
        assert report.exists(), f"Calibration markdown report not found: {report}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

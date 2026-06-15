#!/usr/bin/env python3
"""tests/test_review.py — reviewer runner + aggregation + feedback loop (stubbed LLM)."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _load():
    spec = importlib.util.spec_from_file_location("review", ROOT / "scripts" / "review.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _stub_all_pass(name, artifact, kind):
    return {"persona": name, "status": "pass", "overall_score": 4.2,
            "recommended_fixes": [], "blocking_issues": []}


def _stub_audience_fail(name, artifact, kind):
    if name == "audience":
        return {"persona": name, "status": "fail", "overall_score": 2.0,
                "recommended_fixes": ["Open with a sharper 3s open loop"],
                "blocking_issues": ["hook does not create an open loop in 3s"]}
    return {"persona": name, "status": "pass", "overall_score": 4.0,
            "recommended_fixes": [], "blocking_issues": []}


def test_all_pass_aggregates_pass():
    R = _load()
    passed, report = R.review({"segments": [{"id": "1", "text": "x"}]}, "script", stub=_stub_all_pass)
    assert passed and report["weighted_mean"] >= R.WEIGHTED_THRESHOLD
    print("  ✓ all-pass aggregates to PASS")


def test_audience_veto_blocks():
    R = _load()
    passed, report = R.review({"segments": [{"id": "1", "text": "x"}]}, "script", stub=_stub_audience_fail)
    assert not passed and report["veto_failed"], "audience fail must veto"
    assert any("open loop" in b["issue"] for b in report["blocking_issues"])
    print("  ✓ audience reviewer vetoes regardless of other passes")


def test_storyboard_cast_used():
    R = _load()
    seen = []
    def stub(name, a, k):
        seen.append(name)
        return _stub_all_pass(name, a, k)
    R.review({"beats": [{"beat_id": "B001"}]}, "storyboard", stub=stub)
    assert set(seen) == set(R.STORYBOARD_CAST), f"storyboard cast wrong: {seen}"
    assert "audio" not in seen, "audio persona must be removed"
    print(f"  ✓ storyboard cast = {sorted(seen)} (no audio persona)")


def test_feedback_loop_revises_then_passes():
    """Loop: round0 fails → reviser applies fix → round1 passes. Author revision is exercised."""
    R = _load()
    state = {"round": 0}
    def stub(name, a, k):
        # fail audience on round 0, pass after revision
        if name == "audience" and not a.get("_revised"):
            return _stub_audience_fail(name, a, k)
        return _stub_all_pass(name, a, k)
    def reviser(artifact, fixes):
        assert fixes, "reviser must receive the recommended fixes"
        artifact = dict(artifact); artifact["_revised"] = True
        return artifact
    final, passed, rounds = R.review_loop({"segments": [{"id": "1", "text": "x"}]},
                                          "script", reviser, stub=stub)
    assert passed and final.get("_revised") and len(rounds) == 2
    print(f"  ✓ feedback loop: round0 fail → revise → round1 pass ({len(rounds)} rounds)")


def test_loop_escalates_after_max_rounds():
    R = _load()
    def stub(name, a, k):
        return _stub_audience_fail(name, a, k)  # always fails
    def reviser(a, fixes):
        return dict(a)
    final, passed, rounds = R.review_loop({"segments": [{"id": "1", "text": "x"}]},
                                          "script", reviser, stub=stub, max_rounds=2)
    assert not passed and len(rounds) == 3, "should try initial + 2 revisions then escalate"
    print("  ✓ loop escalates to human after max rounds")


def test_below_threshold_no_blockers_fails():
    """Weighted mean below WEIGHTED_THRESHOLD fails even with no blocking issues."""
    R = _load()
    def stub_low(name, a, k):
        return {"persona": name, "status": "pass", "overall_score": 1.0,  # very low
                "recommended_fixes": [], "blocking_issues": []}
    passed, report = R.review({"segments": [{"id": "1", "text": "x"}]}, "script", stub=stub_low)
    assert not passed, "below threshold must fail even without blocking issues"
    assert report["weighted_mean"] < R.WEIGHTED_THRESHOLD
    print("  ✓ below-threshold fails even without blockers")

def test_malformed_verdict_fails_closed():
    """A verdict with missing/unknown status is treated as fail-closed."""
    R = _load()
    def stub_malformed(name, a, k):
        return {"persona": name, "status": "UNKNOWN_STATUS", "overall_score": 5.0,
                "recommended_fixes": [], "blocking_issues": []}
    passed, report = R.review({"segments": [{"id": "1", "text": "x"}]}, "script", stub=stub_malformed)
    assert not passed, "malformed verdict status must fail closed"
    print("  ✓ malformed verdict fails closed")

def test_early_pass_no_revision_needed():
    """If round 0 passes cleanly, loop exits immediately without calling reviser."""
    R = _load()
    reviser_called = []
    def reviser(a, fixes):
        reviser_called.append(fixes)
        return a
    final, passed, rounds = R.review_loop(
        {"segments": [{"id": "1", "text": "x"}]}, "script", reviser,
        stub=_stub_all_pass, max_rounds=2)
    assert passed and len(reviser_called) == 0 and len(rounds) == 1
    print("  ✓ early pass: no revision called, 1 round")

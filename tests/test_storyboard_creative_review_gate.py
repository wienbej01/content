#!/usr/bin/env python3
"""tests/test_storyboard_creative_review_gate.py — S22_T011 creative review gate tests."""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
FIXTURES = ROOT / "tests" / "fixtures" / "storyboard_v2"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _pass_review(storyboard):
    return {
        "task": "storyboard_creative_review",
        "persona": "sonnet5_creative_reviewer",
        "storyboard_sha256": _load("review_storyboard_v2").compute_sha256(storyboard),
        "status": "pass",
        "visual_director": {
            "status": "pass", "scores": {"era": 5, "james_studio": 5, "broll_specificity": 4, "motion": 4, "graphic_layout": 5, "continuity": 5, "reference_lock": 5},
            "overall_score": 4.7, "blocking_issues": [], "warnings": [], "recommended_fixes": [],
        },
        "filmmaker": {
            "status": "pass", "scores": {"shot_rhythm": 4, "visual_arc": 5, "emphasis": 4, "balance": 4, "opening_shot": 5, "transitions": 4},
            "overall_score": 4.3, "blocking_issues": [], "warnings": [], "recommended_fixes": [],
        },
        "audience": {
            "status": "pass", "scores": {"hook": 5, "reason_to_stay": 4, "open_loops": 4, "save_worthy": 4, "share_worthy": 3, "payoff": 5, "cta": 4},
            "overall_score": 4.1, "predicts": {"watch_through": True, "save": True, "share": False},
            "blocking_issues": [], "warnings": [], "recommended_fixes": [],
        },
        "technical": {
            "status": "pass", "scores": {"generatability": 5, "audio_policy": 5, "references": 4, "durations": 4, "assembly": 5, "cost": 4},
            "overall_score": 4.5, "blocking_issues": [], "warnings": [], "recommended_fixes": [],
        },
        "sonnet_author_verified": True,
        "overall_score": 4.4,
        "may_proceed": True,
        "summary_findings": "Strong storyboard with good narrative alignment and visual variety.",
    }


def _broll_fail_review(storyboard):
    R = _load("review_storyboard_v2")
    return {
        "task": "storyboard_creative_review",
        "persona": "sonnet5_creative_reviewer",
        "storyboard_sha256": R.compute_sha256(storyboard),
        "status": "fail",
        "visual_director": {
            "status": "fail", "scores": {"era": 3, "james_studio": 4, "broll_specificity": 1, "motion": 3, "graphic_layout": 4, "continuity": 4, "reference_lock": 4},
            "overall_score": 2.9, "blocking_issues": ["SH002: Generic 'business people' B-roll with no source grounding — fails specificity requirement"],
            "warnings": [], "recommended_fixes": ["SH002: Replace generic office B-roll with concrete visual from source material (AI network visualization)"],
        },
        "filmmaker": {
            "status": "pass", "scores": {"shot_rhythm": 4, "visual_arc": 4, "emphasis": 4, "balance": 3, "opening_shot": 4, "transitions": 4},
            "overall_score": 3.8, "blocking_issues": [], "warnings": [], "recommended_fixes": [],
        },
        "audience": {
            "status": "pass", "scores": {"hook": 4, "reason_to_stay": 3, "open_loops": 3, "save_worthy": 4, "share_worthy": 3, "payoff": 4, "cta": 4},
            "overall_score": 3.6, "predicts": {"watch_through": True, "save": False, "share": False},
            "blocking_issues": [], "warnings": [], "recommended_fixes": [],
        },
        "technical": {
            "status": "pass", "scores": {"generatability": 4, "audio_policy": 5, "references": 4, "durations": 4, "assembly": 4, "cost": 4},
            "overall_score": 4.2, "blocking_issues": [], "warnings": [], "recommended_fixes": [],
        },
        "sonnet_author_verified": True,
        "overall_score": 3.6,
        "may_proceed": False,
        "summary_findings": "B-roll specificity fails in SH002; generic office imagery must be replaced.",
    }


def _graphic_fail_review(storyboard):
    R = _load("review_storyboard_v2")
    return {
        "task": "storyboard_creative_review",
        "persona": "sonnet5_creative_reviewer",
        "storyboard_sha256": R.compute_sha256(storyboard),
        "status": "fail",
        "visual_director": {
            "status": "fail", "scores": {"era": 4, "james_studio": 4, "broll_specificity": 3, "motion": 3, "graphic_layout": 1, "continuity": 4, "reference_lock": 3},
            "overall_score": 3.1, "blocking_issues": ["SH002: Decorative abstract shapes serve no narrative purpose — graphic lacks semantic purpose or claim support"],
            "warnings": [], "recommended_fixes": ["SH002: Replace decorative graphic with data visualization or framework that supports the AI scaling claim"],
        },
        "filmmaker": {
            "status": "pass", "scores": {"shot_rhythm": 4, "visual_arc": 3, "emphasis": 3, "balance": 3, "opening_shot": 4, "transitions": 4},
            "overall_score": 3.5, "blocking_issues": [], "warnings": [], "recommended_fixes": [],
        },
        "audience": {
            "status": "pass", "scores": {"hook": 4, "reason_to_stay": 3, "open_loops": 3, "save_worthy": 3, "share_worthy": 3, "payoff": 3, "cta": 3},
            "overall_score": 3.1, "predicts": {"watch_through": False, "save": False, "share": False},
            "blocking_issues": [], "warnings": [], "recommended_fixes": [],
        },
        "technical": {
            "status": "pass", "scores": {"generatability": 4, "audio_policy": 5, "references": 3, "durations": 4, "assembly": 4, "cost": 3},
            "overall_score": 3.8, "blocking_issues": [], "warnings": [], "recommended_fixes": [],
        },
        "sonnet_author_verified": True,
        "overall_score": 3.4,
        "may_proceed": False,
        "summary_findings": "SH002 decorative graphic lacks semantic purpose and fails to support the argument.",
    }


def _conclusion_fail_review(storyboard):
    R = _load("review_storyboard_v2")
    return {
        "task": "storyboard_creative_review",
        "persona": "sonnet5_creative_reviewer",
        "storyboard_sha256": R.compute_sha256(storyboard),
        "status": "fail",
        "visual_director": {
            "status": "fail", "scores": {"era": 3, "james_studio": 4, "broll_specificity": 2, "motion": 3, "graphic_layout": 4, "continuity": 4, "reference_lock": 3},
            "overall_score": 3.3, "blocking_issues": ["SH002: Generic landscape visual at conclusion does not reinforce the AI acceleration takeaway"],
            "warnings": [], "recommended_fixes": ["SH002: Replace with visual showing AI acceleration (speed lines, exponential curve, computing infrastructure)"],
        },
        "filmmaker": {
            "status": "fail", "scores": {"shot_rhythm": 3, "visual_arc": 2, "emphasis": 2, "balance": 3, "opening_shot": 4, "transitions": 3},
            "overall_score": 2.8, "blocking_issues": ["NB001: Conclusion visual does not build conviction — the closing energy curve drops instead of rising"],
            "warnings": [], "recommended_fixes": ["NB001: Redesign closing sequence to build rising conviction through faster cuts or push-in on James"],
        },
        "audience": {
            "status": "pass", "scores": {"hook": 4, "reason_to_stay": 3, "open_loops": 3, "save_worthy": 3, "share_worthy": 3, "payoff": 2, "cta": 3},
            "overall_score": 3.0, "predicts": {"watch_through": False, "save": False, "share": False},
            "blocking_issues": [], "warnings": [], "recommended_fixes": [],
        },
        "technical": {
            "status": "pass", "scores": {"generatability": 4, "audio_policy": 5, "references": 3, "durations": 4, "assembly": 4, "cost": 4},
            "overall_score": 4.0, "blocking_issues": [], "warnings": [], "recommended_fixes": [],
        },
        "sonnet_author_verified": True,
        "overall_score": 3.3,
        "may_proceed": False,
        "summary_findings": "Conclusion visuals in SH002 and NB001 do not align with the AI acceleration argument.",
    }


def _malformed_review(storyboard):
    return {"not_a_valid_review": True}


def test_valid_storyboard_plus_passing_stub_passes():
    """Test 1: Valid storyboard + passing stub review passes."""
    R = _load("review_storyboard_v2")
    path = FIXTURES / "valid_two_segment_storyboard.json"
    storyboard = json.loads(path.read_text())
    passed, report = R.creative_review(storyboard, stub=_pass_review)
    assert passed is True, f"Expected pass, got {report.get('status')}: {report.get('blocking_issues')}"
    assert report["may_proceed"] is True
    assert report["overall_score"] == 4.4
    assert report["sonnet_author_verified"] is True
    print(f"  ✓ Valid storyboard + passing stub = PASS (score {report['overall_score']})")


def test_python_invalid_storyboard_cannot_be_reviewed():
    """Test 2: Python-invalid storyboard cannot be reviewed as pass."""
    R = _load("review_storyboard_v2")
    path = FIXTURES / "missing_segment_work_orders.json"
    storyboard = json.loads(path.read_text())
    passed, report = R.creative_review(storyboard, stub=_pass_review)
    assert passed is False
    assert report["may_proceed"] is False
    blocked = any("BLOCKED_PYTHON_VALIDATION_FAILED" in str(b) or
                   "missing" in str(b).lower() or
                   "required field" in str(b).lower()
                   for b in report["blocking_issues"])
    assert blocked, f"Expected Python validation failure, got: {report['blocking_issues']}"
    print(f"  ✓ Python-invalid storyboard blocked with {len(report['blocking_issues'])} issues")


def test_generic_broll_fixture_gets_failing_review():
    """Test 3: Generic B-roll fixture gets failing review."""
    R = _load("review_storyboard_v2")
    path = FIXTURES / "semantic_generic_broll.json"
    storyboard = json.loads(path.read_text())
    passed, report = R.creative_review(storyboard, stub=_broll_fail_review)
    assert passed is False
    assert report["may_proceed"] is False
    has_broll_issue = any("generic" in str(b).lower() or "b-roll" in str(b).lower()
                          or "broll" in str(b).lower()
                          for b in report["blocking_issues"])
    assert has_broll_issue, f"Expected B-roll specificity issue, got: {report['blocking_issues']}"
    print(f"  ✓ Generic B-roll blocked with {len(report['blocking_issues'])} blocking issues")


def test_irrelevant_graphic_fixture_gets_failing_review():
    """Test 4: Irrelevant graphic fixture gets failing review."""
    R = _load("review_storyboard_v2")
    path = FIXTURES / "semantic_decorative_graphic.json"
    storyboard = json.loads(path.read_text())
    passed, report = R.creative_review(storyboard, stub=_graphic_fail_review)
    assert passed is False
    assert report["may_proceed"] is False
    has_graphic_issue = any("graphic" in str(b).lower() or "decorative" in str(b).lower()
                            or "purpose" in str(b).lower()
                            for b in report["blocking_issues"])
    assert has_graphic_issue, f"Expected graphic relevance issue, got: {report['blocking_issues']}"
    print(f"  ✓ Irrelevant graphic blocked with {len(report['blocking_issues'])} blocking issues")


def test_weak_conclusion_alignment_gets_failing_review():
    """Test 5: Weak conclusion alignment gets failing review."""
    R = _load("review_storyboard_v2")
    path = FIXTURES / "semantic_conclusion_unrelated_visual.json"
    storyboard = json.loads(path.read_text())
    passed, report = R.creative_review(storyboard, stub=_conclusion_fail_review)
    assert passed is False
    assert report["may_proceed"] is False
    has_conclusion_issue = any(
        "conclusion" in str(b).lower() or "closing" in str(b).lower()
        or "landscape" in str(b).lower() or "energy" in str(b).lower()
        for b in report["blocking_issues"]
    )
    assert has_conclusion_issue, f"Expected conclusion alignment issue, got: {report['blocking_issues']}"
    print(f"  ✓ Weak conclusion blocked with {len(report['blocking_issues'])} blocking issues")


def test_malformed_review_json_fails():
    """Test 6: Malformed review JSON fails."""
    R = _load("review_storyboard_v2")
    path = FIXTURES / "valid_two_segment_storyboard.json"
    storyboard = json.loads(path.read_text())
    passed, report = R.creative_review(storyboard, stub=_malformed_review)
    assert passed is False
    assert report["may_proceed"] is False
    assert any("BLOCKED_MALFORMED_REVIEW" in str(b) or "malformed" in str(b).lower()
               for b in report["blocking_issues"]), (
        f"Expected malformed review error, got: {report['blocking_issues']}")
    print("  ✓ Malformed review JSON blocked")


def test_non_sonnet_profile_fails():
    """Test 7: Non-Sonnet profile fails."""
    R = _load("review_storyboard_v2")
    path = FIXTURES / "non_sonnet_author.json"
    storyboard = json.loads(path.read_text())
    passed, report = R.creative_review(storyboard, stub=_pass_review)
    assert passed is False
    assert report["may_proceed"] is False
    assert any("BLOCKED_NON_SONNET_AUTHOR" in str(b)
               for b in report["blocking_issues"]), (
        f"Expected non-Sonnet author block, got: {report['blocking_issues']}")
    print(f"  ✓ Non-Sonnet author blocked with BLOCKED_NON_SONNET_AUTHOR")


def test_review_output_includes_actionable_entity_ids():
    """Test 8: Review output includes actionable affected entity IDs."""
    R = _load("review_storyboard_v2")
    path = FIXTURES / "semantic_generic_broll.json"
    storyboard = json.loads(path.read_text())
    passed, report = R.creative_review(storyboard, stub=_broll_fail_review)
    assert passed is False
    assert report["affected_entity_ids"], "Expected affected_entity_ids to be non-empty"
    assert any("SH002" in str(eid) for eid in report["affected_entity_ids"]), (
        f"Expected SH002 in affected entities, got: {report['affected_entity_ids']}")
    assert any("SH002" in str(b) for b in report["blocking_issues"]), (
        "Expected SH002 in blocking_issues for actionable fix")
    print(f"  ✓ Review includes entity IDs: {report['affected_entity_ids']}")


def main():
    print("Creative Review Gate Tests (S22_T011)")
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            import traceback
            print(f"  ✗ {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{'PASSED' if failed == 0 else 'FAILED'}: {passed}/{passed+failed}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()

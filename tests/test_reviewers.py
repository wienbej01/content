#!/usr/bin/env python3
"""tests/test_reviewers.py — P4-08 reviewer gate tests (no live API)."""
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


STUB_PASS = {
    "task": "script_review", "persona": "filmmaker", "status": "pass",
    "scores": {"hook": 4, "arc": 4, "pacing": 4, "transitions": 4, "payoff": 4},
    "overall_score": 4, "blocking_issues": [], "warnings": [], "may_proceed": True
}

STUB_FAIL = {
    "task": "script_review", "persona": "universe", "status": "fail",
    "scores": {"voice": 2, "forbidden": 1, "respect": 3, "originality": 3, "sourcing": 4},
    "overall_score": 2, "blocking_issues": ["Contains 'game-changer' (forbidden)"],
    "warnings": [], "may_proceed": False
}


def test_persona_prompts_exist():
    # New cast (per CREATIVE_CHAIN_SPRINT): audience(both stages), brand_voice(script),
    # filmmaker+visual_director+technical(storyboard). audio persona removed.
    for p in ["audience", "brand_voice", "filmmaker", "visual_director", "technical"]:
        path = ROOT / "docs" / "reviewer_prompts" / f"{p}.md"
        assert path.exists(), f"missing: {path}"
        content = path.read_text()
        assert "BLOCKING" in content
        assert "JSON" in content
    # audio persona must be archived/removed (speakability handled by chunk-and-stitch)
    assert not (ROOT / "docs" / "reviewer_prompts" / "audio.md").exists(), "audio persona should be removed"
    print("  ✓ new reviewer cast present (audience/brand_voice/filmmaker/visual_director/technical); audio removed")


def test_review_script_dry_run():
    rs = _load("review_script")
    script_path = ROOT / "scripts/generated/james_growth_system_teaser_02.json"
    report = rs.run_review(str(script_path), personas=["filmmaker"], dry_run=True)
    assert report["personas_run"] == ["filmmaker"]
    assert report["reviews"][0]["status"] == "dry_run"
    print("  ✓ review_script dry-run works without API")


def test_review_script_stub_pass():
    """Stub llm_call to return a passing review."""
    rs = _load("review_script")
    script_path = ROOT / "scripts/generated/james_growth_system_teaser_02.json"
    with patch("llm_call.llm_call", return_value=(STUB_PASS, "", "sonnet_creative", "claude-sonnet-4.5")):
        report = rs.run_review(str(script_path), personas=["filmmaker"])
    assert report["all_pass"] is True
    assert report["may_proceed"] is True
    print("  ✓ review_script: stubbed pass → all_pass=True, may_proceed=True")


def test_review_script_stub_fail_blocks():
    """Stub llm_call to return a failing review."""
    rs = _load("review_script")
    script_path = ROOT / "scripts/generated/james_growth_system_teaser_02.json"
    with patch("llm_call.llm_call", return_value=(STUB_FAIL, "", "sonnet_creative", "claude-sonnet-4.5")):
        report = rs.run_review(str(script_path), personas=["universe"])
    assert report["all_pass"] is False
    assert report["may_proceed"] is False
    assert "game-changer" in report["hard_blocking_issues"][0]
    print("  ✓ review_script: stubbed fail → blocks with issue reported")


def test_review_media_plan_dry_run():
    rmp = _load("review_media_plan")
    script_path = ROOT / "scripts/generated/james_growth_system_teaser_02.json"
    report = rmp.run_review(str(script_path), dry_run=True)
    assert report["status"] == "dry_run"
    print("  ✓ review_media_plan dry-run works without API")


def test_review_uses_sonnet_creative():
    """Reviewer tasks must route to sonnet_creative (creative authority)."""
    lc = _load("llm_call")
    cfg = lc.load_config()
    name, profile = lc.resolve_profile(cfg, "script_review")
    assert name == "sonnet_creative"
    assert profile["is_final_creative_authority"] is True
    print("  ✓ script_review routes to sonnet_creative (creative authority)")


def test_aggregation_across_personas():
    """Multiple personas: one fail = all_pass=False."""
    rs = _load("review_script")
    script_path = ROOT / "scripts/generated/james_growth_system_teaser_02.json"
    responses = iter([
        (STUB_PASS, "", "sonnet_creative", "claude-sonnet-4.5"),
        (STUB_FAIL, "", "sonnet_creative", "claude-sonnet-4.5"),
    ])
    with patch("llm_call.llm_call", side_effect=lambda **kwargs: next(responses)):
        report = rs.run_review(str(script_path), personas=["filmmaker", "universe"])
    assert report["all_pass"] is False
    assert len(report["hard_blocking_issues"]) >= 1
    print("  ✓ aggregation: one persona fails → whole review blocks")




def test_low_weight_persona_does_not_block_alone():
    """A low-weight persona with a low score (but no blocking_issues) doesn't stall."""
    rs = _load("review_script")
    script_path = ROOT / "scripts/generated/james_growth_system_teaser_02.json"
    # filmmaker (weight 1.5) passes with score 4; technical (weight 0.8) passes with score 2
    # Weighted avg = (4*1.5 + 2*0.8) / (1.5+0.8) = 7.6/2.3 = 3.3 → above threshold 3.0
    pass_high = {**STUB_PASS, "persona": "filmmaker", "overall_score": 4, "blocking_issues": []}
    low_tech = {"task": "script_review", "persona": "technical", "status": "pass",
                "scores": {}, "overall_score": 2, "blocking_issues": [], "warnings": ["minor nit"], "may_proceed": True}
    responses = iter([
        (pass_high, "", "sonnet_creative", "claude-sonnet-4.5"),
        (low_tech, "", "sonnet_creative", "claude-sonnet-4.5"),
    ])
    with patch("llm_call.llm_call", side_effect=lambda **kwargs: next(responses)):
        report = rs.run_review(str(script_path), personas=["filmmaker", "technical"])
    assert report["may_proceed"] is True, f"should pass: weighted avg {report.get('weighted_average_score')}"
    print(f"  ✓ low-weight technical (score 2) doesn't block when filmmaker (score 4) passes "
          f"(weighted avg: {report['weighted_average_score']})")


def test_hard_block_overrides_weighted_score():
    """A hard blocking_issue blocks even if weighted average is high."""
    rs = _load("review_script")
    script_path = ROOT / "scripts/generated/james_growth_system_teaser_02.json"
    pass_high = {**STUB_PASS, "persona": "filmmaker", "overall_score": 5, "blocking_issues": []}
    block_tech = {"task": "script_review", "persona": "technical", "status": "fail",
                  "scores": {}, "overall_score": 4, "blocking_issues": ["word count outside band"],
                  "warnings": [], "may_proceed": False}
    responses = iter([
        (pass_high, "", "sonnet_creative", "claude-sonnet-4.5"),
        (block_tech, "", "sonnet_creative", "claude-sonnet-4.5"),
    ])
    with patch("llm_call.llm_call", side_effect=lambda **kwargs: next(responses)):
        report = rs.run_review(str(script_path), personas=["filmmaker", "technical"])
    assert report["may_proceed"] is False
    assert "word count" in report["hard_blocking_issues"][0]
    print("  ✓ hard blocking issue overrides high weighted score")

def main():
    print("Reviewer Gate Tests (P4-08)")
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  ✗ {t.__name__}: {e}")
            failed += 1
    print(f"\n{'PASSED' if failed == 0 else 'FAILED'}: {passed}/{passed+failed}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()

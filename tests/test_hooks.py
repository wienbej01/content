#!/usr/bin/env python3
"""tests/test_hooks.py — P5-03 hook engineering tests (no live API)."""
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _load():
    spec = importlib.util.spec_from_file_location("generate_hooks", ROOT / "scripts" / "generate_hooks.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


STUB_HOOKS = {
    "topic": "How compounding works for careers",
    "hooks": [
        {"rank": 1, "type": "counterintuitive", "text": "Most career advice compounds to nothing.",
         "word_count": 7, "scores": {"open_loop_strength": 5, "speakability": 5, "james_voice": 4}, "total_score": 14},
        {"rank": 2, "type": "relatable_pain", "text": "You've been promoted twice and feel further behind.",
         "word_count": 10, "scores": {"open_loop_strength": 4, "speakability": 5, "james_voice": 5}, "total_score": 14},
        {"rank": 3, "type": "pattern_interrupt", "text": "Careers are not ladders — they're compound interest accounts.",
         "word_count": 9, "scores": {"open_loop_strength": 4, "speakability": 4, "james_voice": 4}, "total_score": 12},
        {"rank": 4, "type": "credibility", "text": "In thirty-five years I've watched the same pattern destroy promising careers.",
         "word_count": 12, "scores": {"open_loop_strength": 4, "speakability": 4, "james_voice": 5}, "total_score": 13},
        {"rank": 5, "type": "open_loop", "text": "What if the single thing separating compounding careers from stagnant ones is invisible?",
         "word_count": 14, "scores": {"open_loop_strength": 5, "speakability": 3, "james_voice": 4}, "total_score": 12},
    ],
    "selected": 0,
    "selection_reason": "Strongest open loop with fewest words"
}


def test_dry_run_no_api():
    gh = _load()
    result = gh.generate_hooks("test topic", dry_run=True)
    assert result["status"] == "dry_run"
    print("  ✓ dry-run works without API")


def test_stub_produces_ranked_hooks():
    gh = _load()
    with patch("llm_call.llm_call", return_value=(STUB_HOOKS, "", "sonnet_creative", "claude-sonnet-4.5")):
        result = gh.generate_hooks("How compounding works for careers", pillar="Career capital")
    assert len(result["hooks"]) == 5
    # Should be sorted by total_score descending
    scores = [h["total_score"] for h in result["hooks"]]
    assert scores == sorted(scores, reverse=True)
    assert result["selected"] == 0
    print(f"  ✓ produces 5 ranked hooks (top score: {scores[0]})")


def test_hooks_have_required_fields():
    gh = _load()
    with patch("llm_call.llm_call", return_value=(STUB_HOOKS, "", "sonnet_creative", "claude-sonnet-4.5")):
        result = gh.generate_hooks("test")
    for h in result["hooks"]:
        assert "type" in h and "text" in h and "scores" in h and "total_score" in h
        assert h["scores"].get("open_loop_strength") is not None
    print("  ✓ hooks have required fields (type, text, scores, total_score)")


def test_uses_creative_authority():
    """hook_generation must use sonnet_creative profile."""
    import llm_call
    cfg = llm_call.load_config()
    name, profile = llm_call.resolve_profile(cfg, "hook_generation")
    assert name == "sonnet_creative"
    print("  ✓ hook_generation routes to sonnet_creative")


def test_too_few_hooks_raises():
    gh = _load()
    bad = {"hooks": [{"text": "x", "total_score": 3}]}
    with patch("llm_call.llm_call", return_value=(bad, "", "sonnet_creative", "claude-sonnet-4.5")):
        try:
            gh.generate_hooks("test")
            assert False
        except RuntimeError as e:
            assert "Expected" in str(e)
    print("  ✓ fewer than 3 hooks raises RuntimeError")


def main():
    print("Hook Engineering Tests (P5-03)")
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

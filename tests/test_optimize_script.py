#!/usr/bin/env python3
"""tests/test_optimize_script.py — takeaway-emphasis optimization system tests."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _load():
    spec = importlib.util.spec_from_file_location("optimize_script", ROOT / "scripts" / "optimize_script.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _raw_script():
    return {
        "project_id": "t", "title": "Test", "narration_mode": "continuous_voiceover",
        "segments": [
            {"id": "001", "text": "Here is the setup. It frames the problem."},
            {"id": "002", "text": "Here is the evidence from a study."},
            {"id": "003", "text": "So the real lesson is simple. Protect what matters."},
        ],
    }


def test_fallback_marks_last_sentence_as_payoff():
    """With no LLM, the deterministic fallback marks the final sentence as hero_payoff."""
    O = _load()
    enriched, meta = O.optimize(_raw_script(), use_llm=False)
    kps = enriched["key_points"]
    assert kps, "fallback must produce at least one key point"
    assert kps[0]["emphasis"]["treatment"] == "hero_payoff"
    assert "Protect what matters" in kps[0]["text"]
    print("  ✓ fallback marks final sentence as hero_payoff")


def test_only_one_hero_payoff_enforced():
    """Even if the LLM returns multiple hero_payoffs, only ONE is kept."""
    O = _load()
    # Monkeypatch llm_call to return two hero_payoffs
    import llm_call
    orig = llm_call.llm_call
    def fake(task, prompt, **kw):
        return ({"key_points": [
            {"text": "First takeaway.", "treatment": "hero_payoff", "overlay": {"kind": "key_line", "text": "First"}},
            {"text": "Second takeaway.", "treatment": "hero_payoff", "overlay": {"kind": "key_line", "text": "Second"}},
        ], "segments": []}, "", "sonnet_creative", "model")
    llm_call.llm_call = fake
    try:
        enriched, meta = O.optimize(_raw_script(), use_llm=True)
    finally:
        llm_call.llm_call = orig
    heroes = [k for k in enriched["key_points"] if k["emphasis"]["treatment"] == "hero_payoff"]
    assert len(heroes) == 1, f"only one hero_payoff allowed, got {len(heroes)}"
    print("  ✓ exactly one hero_payoff enforced")


def test_tts_pacing_sanitized():
    """All break tags are removed (they distort prosody); pacing falls to punctuation."""
    O = _load()
    # Stacked breaks → no breaks remain
    out1 = O._sanitize_tts('a <break time="0.5s" /><break time="0.5s" /> b')
    assert "<break" not in out1
    # A break after a sentence becomes an ellipsis beat
    out2 = O._sanitize_tts('It is dangerous. <break time="0.6s" /> You burn the fuel.')
    assert "<break" not in out2 and "..." in out2
    print("  ✓ all break tags stripped; sentence-boundary breaks → ellipsis")


def test_llm_tts_text_merged():
    """LLM-provided tts_text is merged onto the matching segment."""
    O = _load()
    import llm_call
    orig = llm_call.llm_call
    def fake(task, prompt, **kw):
        return ({"key_points": [
            {"text": "Protect what matters.", "treatment": "hero_payoff",
             "hero_gesture": "open hand", "overlay": {"kind": "key_line", "text": "Protect what matters"}}],
            "segments": [{"id": "003", "tts_text": "So the real lesson is simple — protect what matters."}]},
            "", "sonnet_creative", "model")
    llm_call.llm_call = fake
    try:
        enriched, meta = O.optimize(_raw_script(), use_llm=True)
    finally:
        llm_call.llm_call = orig
    seg3 = [s for s in enriched["segments"] if s["id"] == "003"][0]
    assert "tts_text" in seg3 and "—" in seg3["tts_text"]
    assert enriched["key_points"][0]["emphasis"]["hero_gesture"] == "open hand"
    print("  ✓ LLM tts_text + gesture merged onto segment/key_point")


def test_storyboard_consumes_key_points():
    """The storyboard router applies emphasis from optimizer-produced key_points
    (proves downstream alignment is general, not video-specific)."""
    spec = importlib.util.spec_from_file_location("storyboard", ROOT / "scripts" / "storyboard.py")
    S = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(S)
    O = _load()
    script = _raw_script()
    script["video_type"] = "short"
    enriched, _ = O.optimize(script, use_llm=False)
    sb = S.route(enriched, S.load_constraints())
    kp_beats = [b for b in sb["beats"] if b.get("key_point")]
    assert kp_beats, "storyboard must mark at least one key_point beat from optimizer output"
    print(f"  ✓ storyboard consumed key_points → {len(kp_beats)} emphasis beat(s)")

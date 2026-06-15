#!/usr/bin/env python3
"""tests/test_direct_storyboard.py — Storyboard Director tests (validators + context, no LLM)."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _load():
    spec = importlib.util.spec_from_file_location("direct_storyboard", ROOT / "scripts" / "direct_storyboard.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_anachronism_rejected():
    D = _load()
    beats = [{"beat_id": "B003", "shot_type": "broll_specific", "duration_target_sec": 5,
              "subject": "a clerk", "setting": "a mid-century wooden desk with manuscript pages",
              "visual_brief": "a clerk sorting manuscript pages at a mid-century desk"}]
    errors, warnings = D.validate_director_output(beats, source_text="a 2008 computer study")
    assert any("anachronism" in e for e in errors), f"should reject anachronism, got {errors}"
    print("  ✓ anachronism (mid-century/manuscript) rejected for a modern-era video")


def test_anachronism_allowed_if_source_historical():
    D = _load()
    beats = [{"beat_id": "B003", "shot_type": "broll_specific", "duration_target_sec": 5,
              "subject": "Ebbinghaus", "setting": "an 1885 study",
              "visual_brief": "an 1885 laboratory scene"}]
    # source explicitly historical
    errors, _ = D.validate_director_output(beats, source_text="In 1885 Ebbinghaus ran his study")
    assert not any("anachronism" in e for e in errors), "historical source should permit the era"
    print("  ✓ historical era allowed when source justifies it")


def test_broll_length_capped():
    D = _load()
    beats = [{"beat_id": "B005", "shot_type": "broll_environment", "duration_target_sec": 13,
              "visual_brief": "office", "setting": "modern office"}]
    errors, _ = D.validate_director_output(beats, "")
    assert any("exceeds 6s" in e for e in errors), "long b-roll must be flagged to split"
    print("  ✓ b-roll >6s flagged to split into multiple shots")


def test_graphic_requires_layout():
    D = _load()
    beats = [{"beat_id": "B008", "shot_type": "graphic", "duration_target_sec": 5,
              "visual_brief": "cta", "graphic": {"required": True, "layout": None}}]
    errors, _ = D.validate_director_output(beats, "")
    assert any("no layout" in e for e in errors)
    print("  ✓ required graphic without a layout rejected")


def test_bibles_loaded():
    """The director context includes the key bibles + constraints (the core fix)."""
    D = _load()
    bibles = D.load_bibles()
    for must in ["UNIVERSE_BIBLE", "JAMES_CHARACTER_BIBLE", "FORBIDDEN_PATTERNS", "constraints.json"]:
        assert must in bibles, f"director context missing {must}"
    print("  ✓ director is fed the bibles + constraints (anachronism root-cause fix)")


def test_prompt_includes_source_and_script():
    D = _load()
    script = {"title": "T", "segments": [{"id": "001", "text": "hello world"}], "key_points": []}
    prompt = D.build_director_prompt(script, "SOURCE_MARKER_TEXT", D.load_bibles())
    assert "SOURCE_MARKER_TEXT" in prompt
    assert "hello world" in prompt
    assert "MODERN ERA ONLY" in prompt
    print("  ✓ director prompt includes source text + script + era rule")

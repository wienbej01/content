#!/usr/bin/env python3
"""tests/test_anachronism_guard.py — Regression tests for anachronism guard word-boundary fix."""
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


def _beat(visual_brief, setting="modern office", subject="a user"):
    return {"beat_id": "B006", "shot_type": "broll_specific", "duration_target_sec": 5,
            "visual_brief": visual_brief, "setting": setting, "subject": subject}


def test_modern_scroll_not_flagged():
    D = _load()
    beats = [_beat("user scrolls through AI options on a laptop")]
    errors, _ = D.validate_director_output(beats, source_text="an article about AI tools")
    assert not any("anachronism" in e for e in errors), f"false positive on 'scrolls': {errors}"


def test_scrolling_not_flagged():
    D = _load()
    beats = [_beat("scrolling feed on a phone screen")]
    errors, _ = D.validate_director_output(beats, source_text="social media usage study")
    assert not any("anachronism" in e for e in errors), f"false positive on 'scrolling': {errors}"


def test_candlestick_chart_not_flagged():
    D = _load()
    beats = [_beat("candlestick chart on a trading screen")]
    errors, _ = D.validate_director_output(beats, source_text="stock market analysis")
    assert not any("anachronism" in e for e in errors), f"false positive on 'candlestick': {errors}"


def test_real_anachronism_still_caught():
    D = _load()
    beats = [_beat("victorian study with a quill and parchment", setting="victorian study")]
    errors, _ = D.validate_director_output(beats, source_text="a 2024 productivity framework")
    anachronism_errors = [e for e in errors if "anachronism" in e]
    assert len(anachronism_errors) >= 1, f"should catch victorian/quill/parchment, got {errors}"


def test_anachronism_justified_by_source_passes():
    D = _load()
    beats = [_beat("ancient parchment document on display")]
    errors, _ = D.validate_director_output(beats, source_text="the parchment manuscripts of the Dead Sea")
    assert not any("anachronism" in e and "parchment" in e for e in errors), \
        f"source-justified 'parchment' should not be flagged: {errors}"


def test_negation_still_skipped():
    D = _load()
    beats = [_beat("no typewriter, modern desk with dual monitors")]
    errors, _ = D.validate_director_output(beats, source_text="remote work study 2025")
    assert not any("typewriter" in e for e in errors), f"negated 'typewriter' should not flag: {errors}"

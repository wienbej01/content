"""TKT-303: Word-anchored graphic timing tests.

Tests verify:
1. Anchor phrase present in word_timing resolves to correct start_ms.
2. Anchor phrase absent from word_timing raises ValueError naming phrase.
3. No anchor (None/empty) is a no-op (unchanged behavior).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def _fixture_word_timing(words, durations_ms, gaps_ms, start_offset_ms=0):
    segments = []
    cursor = float(start_offset_ms)
    for i, word in enumerate(words):
        end = cursor + durations_ms[i]
        segments.append({
            "word": word,
            "start_ms": round(cursor, 3),
            "end_ms": round(end, 3),
            "confidence": 0.5,
            "segment_id": f"fixture_{i:04d}",
        })
        cursor = round(end + (gaps_ms[i] if i < len(gaps_ms) else 0), 3)

    total_ms = round(cursor, 3)
    return {
        "metadata": {
            "audio_sha": "abcdef123456",
            "script_sha": "123456abcdef",
            "backend": "fixture",
            "total_duration_ms": total_ms,
            "coverage": 1.0,
            "total_words": len(words),
            "aligned_words": len(words),
        },
        "words": segments,
    }


class TestGraphicAnchorResolution:
    """Anchor phrase matching against word_timing."""

    def test_anchor_phrase_present_resolves_start_ms(self):
        words = ["This", "is", "a", "KEY", "INSIGHT", "for", "today"]
        durations = [100.0] * 7
        gaps = [30.0] * 6
        wt = _fixture_word_timing(words, durations, gaps)
        word_list = wt["words"]

        from produce_db import _resolve_graphic_anchor

        result_ms = _resolve_graphic_anchor("KEY INSIGHT", word_list)

        assert result_ms == pytest.approx(word_list[3]["start_ms"], abs=0.01)

    def test_anchor_phrase_single_word_resolves(self):
        words = ["Hello", "world", "focus", "here"]
        durations = [120.0, 150.0, 100.0, 130.0]
        gaps = [20.0] * 3
        wt = _fixture_word_timing(words, durations, gaps)
        word_list = wt["words"]

        from produce_db import _resolve_graphic_anchor

        result_ms = _resolve_graphic_anchor("focus", word_list)
        assert result_ms == pytest.approx(word_list[2]["start_ms"], abs=0.01)

    def test_anchor_case_insensitive_match(self):
        words = ["the", "Quick", "Brown", "fox"]
        durations = [100.0] * 4
        gaps = [20.0] * 3
        wt = _fixture_word_timing(words, durations, gaps)
        word_list = wt["words"]

        from produce_db import _resolve_graphic_anchor

        result_ms = _resolve_graphic_anchor("quick brown", word_list)
        assert result_ms == pytest.approx(word_list[1]["start_ms"], abs=0.01)

    def test_anchor_punctuation_normalized(self):
        words = ["Its", "a", "key", "insight", "period"]
        durations = [100.0] * 5
        gaps = [20.0] * 4
        wt = _fixture_word_timing(words, durations, gaps)
        word_list = wt["words"]

        from produce_db import _resolve_graphic_anchor

        result_ms = _resolve_graphic_anchor("key insight!", word_list)
        assert result_ms == pytest.approx(word_list[2]["start_ms"], abs=0.01)

    def test_first_occurrence_within_beat_span(self):
        words = ["the", "point", "is", "the", "point", "again"]
        durations = [80.0] * 6
        gaps = [15.0] * 5
        wt = _fixture_word_timing(words, durations, gaps)
        word_list = wt["words"]

        from produce_db import _resolve_graphic_anchor

        result_ms = _resolve_graphic_anchor("the point", word_list, beat_word_span=[2, 6])
        assert result_ms == pytest.approx(word_list[3]["start_ms"], abs=0.01)

    def test_anchor_phrase_absent_raises(self):
        words = ["One", "two", "three", "four"]
        durations = [100.0] * 4
        gaps = [20.0] * 3
        wt = _fixture_word_timing(words, durations, gaps)
        word_list = wt["words"]

        from produce_db import _resolve_graphic_anchor

        with pytest.raises(ValueError) as exc:
            _resolve_graphic_anchor("missing phrase", word_list)
        assert "missing phrase" in str(exc.value)

    def test_no_anchor_is_noop(self):
        from produce_db import _resolve_graphic_anchor

        result = _resolve_graphic_anchor("", [])
        assert result is None

        result = _resolve_graphic_anchor(None, [])
        assert result is None


class TestGraphicAnchorResolveAtCompile:
    """End-to-end anchor resolution at compile time via invoke_compile_media."""

    def test_no_anchor_does_not_raise(self, tmp_path):
        from produce_db import _resolve_graphic_anchor

        result = _resolve_graphic_anchor(None, [])
        assert result is None

        result = _resolve_graphic_anchor("", [])
        assert result is None

    def test_unresolvable_anchor_compile_error_names_phrase_and_beat(self):
        from produce_db import _resolve_graphic_anchor

        words = [{"word": "hello", "start_ms": 0}, {"word": "world", "start_ms": 200}]
        phrase = "missing phrase"
        beat_label = "B3_BEAT"

        with pytest.raises(RuntimeError) as exc:
            try:
                _resolve_graphic_anchor(phrase, words)
            except ValueError:
                raise RuntimeError(
                    f"Graphic anchor phrase {phrase!r} for beat {beat_label!r} "
                    f"not found in word_timing words."
                )

        msg = str(exc.value)
        assert phrase in msg
        assert beat_label in msg
        assert "not found in word_timing words" in msg

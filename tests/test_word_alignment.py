"""TKT-301: Word-level forced alignment tests.

Tests verify:
1. Fixture backend produces word_timing doc with monotonic, non-overlapping times.
2. Coverage below 95% fails loudly naming unaligned spans.
3. Output schema matches expected [{word, start_ms, end_ms, confidence, segment_id}].
4. Real backend produces plausible word times (opt-in marker: alignment_model).
5. Integration: stage registered in graph, orchestrator passes.
"""
from __future__ import annotations

import hashlib
import os
import struct
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import word_alignment as walign
import production_db as _db
import stage_runner
from stage_runner import STAGE_REGISTRY

SR = 16000


def _create_test_wav(path, duration_sec=3.0, sr=SR):
    samples = (np.sin(2 * np.pi * 440 * np.linspace(0, duration_sec, int(duration_sec * sr), endpoint=False)) * 0.3 * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())


def _create_speech_like_wav(path, duration_sec=3.0, sr=SR):
    speech = np.random.randn(int(duration_sec * sr)) * 0.15
    speech[0:int(0.1 * sr)] *= np.linspace(0, 1, int(0.1 * sr))
    speech[-int(0.1 * sr):] *= np.linspace(1, 0, int(0.1 * sr))
    samples = (speech * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())


def _create_word_gapped_wav(path, word_count=5, word_dur_ms=200, gap_dur_ms=100, sr=SR):
    word_samples = int(word_dur_ms * sr / 1000)
    gap_samples = int(gap_dur_ms * sr / 1000)
    segments = []
    for i in range(word_count):
        word = (np.random.randn(word_samples) * 0.15 * 32767).astype(np.int16)
        segments.append(word)
        if i < word_count - 1:
            segments.append(np.zeros(gap_samples, dtype=np.int16))
    samples = np.concatenate(segments)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())


def _word_count(text):
    return len([w for w in text.split() if w.strip()])


# ---------------------------------------------------------------------------
# Fixture backend unit tests
# ---------------------------------------------------------------------------

class TestFixtureAlignment:

    def test_align_words_produces_correct_word_count(self, tmp_path):
        audio = tmp_path / "test.wav"
        _create_test_wav(audio, duration_sec=2.0)
        text = "Hello world this is a test of the word alignment system"
        result = walign.align_words(text, audio, backend="fixture")
        expected_count = _word_count(text)
        assert result["aligned_words"] == expected_count
        assert result["total_words"] == expected_count
        assert len(result["segments"]) == expected_count

    def test_segments_are_monotonic_non_overlapping(self, tmp_path):
        audio = tmp_path / "test.wav"
        _create_test_wav(audio, duration_sec=5.0)
        text = "One two three four five six seven eight nine ten"
        result = walign.align_words(text, audio, backend="fixture")
        segs = result["segments"]
        for i in range(1, len(segs)):
            assert segs[i]["start_ms"] >= segs[i - 1]["end_ms"], \
                f"Overlap at {i}: seg[{i-1}].end={segs[i-1]['end_ms']} > seg[{i}].start={segs[i]['start_ms']}"

    def test_first_word_starts_at_zero(self, tmp_path):
        audio = tmp_path / "test.wav"
        _create_test_wav(audio, duration_sec=3.0)
        text = "First word test"
        result = walign.align_words(text, audio, backend="fixture")
        assert result["segments"][0]["start_ms"] == 0.0

    def test_last_word_ends_near_duration(self, tmp_path):
        audio = tmp_path / "test.wav"
        duration = 3.0
        _create_test_wav(audio, duration_sec=duration)
        text = "The final word test"
        result = walign.align_words(text, audio, backend="fixture")
        last_end = result["segments"][-1]["end_ms"]
        assert abs(last_end - duration * 1000) < 10, \
            f"Last word ends at {last_end}ms, expected ~{duration*1000}ms"

    def test_schema_fields_present(self, tmp_path):
        audio = tmp_path / "test.wav"
        _create_test_wav(audio, duration_sec=2.0)
        text = "Schema check test"
        result = walign.align_words(text, audio, backend="fixture")
        for seg in result["segments"]:
            assert "word" in seg
            assert "start_ms" in seg
            assert "end_ms" in seg
            assert "confidence" in seg
            assert "segment_id" in seg
            assert seg["end_ms"] > seg["start_ms"]

    def test_coverage_is_exactly_one_for_full_alignment(self, tmp_path):
        audio = tmp_path / "test.wav"
        _create_test_wav(audio, duration_sec=2.0)
        text = "Complete coverage test"
        result = walign.align_words(text, audio, backend="fixture")
        assert result["coverage"] == 1.0

    def test_metadata_fields_present(self, tmp_path):
        audio = tmp_path / "test.wav"
        _create_test_wav(audio, duration_sec=2.0)
        text = "Metadata test"
        doc = walign.build_word_timing_document(
            text, audio, "abc123", "def456", backend="fixture")
        meta = doc["metadata"]
        assert meta["audio_sha"] == "abc123"
        assert meta["script_sha"] == "def456"
        assert meta["backend"] == "fixture"
        assert meta["total_duration_ms"] > 0
        assert meta["coverage"] == 1.0


# ---------------------------------------------------------------------------
# Coverage failure tests
# ---------------------------------------------------------------------------

class TestCoverageFailure:

    def test_coverage_below_threshold_raises(self, tmp_path, monkeypatch):
        audio = tmp_path / "test.wav"
        _create_test_wav(audio, duration_sec=1.0)
        monkeypatch.setattr(walign, "COVERAGE_THRESHOLD", 0.95)

        # Monkeypatch align_fixture to return only 1 segment for many words
        def fixture_with_low_coverage(text, audio_path):
            words = walign._tokenize_words(text)[0]
            total_ms = 3000.0
            segments = [
                {"word": words[0], "start_ms": 0, "end_ms": 500,
                 "confidence": 0.5, "segment_id": "test_0"},
            ]
            return segments, total_ms

        monkeypatch.setattr(walign, "align_fixture", fixture_with_low_coverage)

        text = "this is a much longer text with many words to trigger a coverage failure"
        with pytest.raises(RuntimeError, match="word_alignment coverage"):
            walign.align_words(text, audio, backend="fixture")

    def test_align_words_empty_text_raises(self, tmp_path):
        audio = tmp_path / "test.wav"
        _create_test_wav(audio)
        with pytest.raises(RuntimeError):
            walign.align_words("", audio, backend="fixture")

    def test_align_words_missing_audio_raises(self, tmp_path):
        audio = tmp_path / "nonexistent.wav"
        with pytest.raises(RuntimeError):
            walign.align_words("hello world", audio, backend="fixture")


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

class TestBackendSelection:

    def test_invalid_backend_raises(self, monkeypatch):
        monkeypatch.setenv("ALIGNMENT_BACKEND", "invalid_backend")
        with pytest.raises(RuntimeError, match="Invalid ALIGNMENT_BACKEND"):
            walign._get_backend()

    def test_fixture_is_default(self, monkeypatch):
        monkeypatch.delenv("ALIGNMENT_BACKEND", raising=False)
        assert walign._get_backend() == "fixture"

    def test_real_backend_on_speech_like_wav(self, tmp_path):
        audio = tmp_path / "speech.wav"
        _create_word_gapped_wav(audio, word_count=9)
        text = "hello world this is a speech test for alignment"
        result = walign.align_words(text, audio, backend="real")
        assert result["aligned_words"] > 0
        assert result["backend"] == "real"
        for seg in result["segments"]:
            assert seg["end_ms"] > seg["start_ms"]


# ---------------------------------------------------------------------------
# Stage graph registration
# ---------------------------------------------------------------------------

class TestStageRegistration:

    def test_word_alignment_stage_exists(self):
        assert "word_alignment" in STAGE_REGISTRY, \
            "word_alignment stage must be registered in STAGE_REGISTRY"

    def test_word_alignment_depends_on_tts(self):
        stage = STAGE_REGISTRY["word_alignment"]
        assert "tts" in stage.depends_on

    def test_word_alignment_produces_word_timing(self):
        stage = STAGE_REGISTRY["word_alignment"]
        assert "word_timing" in stage.produces_kinds

    def test_word_alignment_consumes_script_and_tts_artifact(self):
        stage = STAGE_REGISTRY["word_alignment"]
        assert "script" in stage.consumes_kinds
        assert "tts_artifact" in stage.consumes_kinds

    def test_audio_timing_depends_on_word_alignment(self):
        stage = STAGE_REGISTRY["audio_timing"]
        assert "word_alignment" in stage.depends_on, \
            "audio_timing must depend on word_alignment after Wave 3"

    def test_topological_order(self):
        stages = list(STAGE_REGISTRY.keys())
        tts_idx = stages.index("tts")
        walign_idx = stages.index("word_alignment")
        audio_idx = stages.index("audio_timing")
        assert tts_idx < walign_idx < audio_idx, \
            "word_alignment must appear between tts and audio_timing"


# ---------------------------------------------------------------------------
# Document building
# ---------------------------------------------------------------------------

class TestBuildWordTimingDocument:

    def test_document_has_metadata_and_words(self, tmp_path):
        audio = tmp_path / "test.wav"
        _create_test_wav(audio, duration_sec=2.0)
        text = "test document structure"
        doc = walign.build_word_timing_document(
            text, audio, "audio_sha_123", "script_sha_456", backend="fixture")
        assert "metadata" in doc
        assert "words" in doc
        assert len(doc["words"]) == _word_count(text)

    def test_document_provenance_includes_hashes(self, tmp_path):
        audio = tmp_path / "test.wav"
        _create_test_wav(audio, duration_sec=1.0)
        text = "provenance test"
        doc = walign.build_word_timing_document(
            text, audio, "abc", "def", backend="fixture")
        assert doc["metadata"]["audio_sha"] == "abc"
        assert doc["metadata"]["script_sha"] == "def"


# ---------------------------------------------------------------------------
# Real backend boundary tests
# ---------------------------------------------------------------------------

@pytest.mark.alignment_model
class TestRealBackendIntegration:

    def test_real_backend_voice_audio(self, tmp_path):
        audio = tmp_path / "voice.wav"
        _create_word_gapped_wav(audio, word_count=9, word_dur_ms=200, gap_dur_ms=80)
        text = "this is a real backend test for word alignment"
        result = walign.align_words(text, audio, backend="real")
        assert result["total_words"] > 0
        assert result["coverage"] > 0
        segs = result["segments"]
        assert len(segs) > 0
        for i in range(1, len(segs)):
            assert segs[i]["start_ms"] >= segs[i - 1]["end_ms"]

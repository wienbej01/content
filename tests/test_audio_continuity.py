"""Tests for S13-T004: Audio seam QA.

Three honest checks, each proven end-to-end against AAC-encoded fixtures:

1. **Gaps** — silent gap between speech regions fails at >500ms; passes below.
2. **Overlaps** — overlapping segment-timeline intervals fail (deterministic).
3. **Clicks** — a full-scale impulse at a segment seam fails; a clean seam passes.

Overlap and click checks consume segment timeline metadata. Fixtures that
exercise them carry the timeline that produces (or avoids) the defect, so the
test proves a real defect is caught — not that "the logic merely exists".
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from evals.eval_audio_continuity import (
    evaluate_audio_continuity,
    detect_timeline_overlaps,
    detect_seam_clicks,
    _seam_positions,
    CLICK_THRESHOLD_DB,
)
from audio_test_fixtures import (
    create_clean_audio_video,
    create_audio_with_gap,
    create_timeline_with_overlap,
    create_audio_with_seam_click,
    generate_speech_like,
    SR,
)


# ---------------------------------------------------------------------------
# Pure-unit checks on the deterministic detectors (no audio I/O)
# ---------------------------------------------------------------------------
class TestOverlapDetectorUnit:
    """Overlap detection is deterministic over segment-timeline metadata."""

    def test_sequential_timeline_has_no_overlap(self):
        segs = [{"start": 0.0, "end": 2.0}, {"start": 2.0, "end": 4.0}]
        assert detect_timeline_overlaps(segs) == []

    def test_overlapping_timeline_detected(self):
        segs = [{"start": 0.0, "end": 2.0}, {"start": 1.8, "end": 4.0}]
        overlaps = detect_timeline_overlaps(segs)
        assert len(overlaps) == 1
        assert overlaps[0]["duration_ms"] == pytest.approx(200.0, abs=1.0)
        assert overlaps[0]["segments"] == [0, 1]

    def test_overlap_threshold_respected(self):
        # 50ms overlap, threshold 100ms -> not flagged
        segs = [{"start": 0.0, "end": 2.0}, {"start": 1.95, "end": 4.0}]
        assert detect_timeline_overlaps(segs, threshold_ms=100.0) == []
        # same overlap, threshold 0ms -> flagged
        assert len(detect_timeline_overlaps(segs, threshold_ms=0.0)) == 1

    def test_duration_form_segments(self):
        # segments given as {duration: ...} are sequenced end-to-end
        segs = [{"duration": 2.0}, {"duration": 2.0}]
        assert detect_timeline_overlaps(segs) == []
        assert _seam_positions(segs) == [2.0]


class TestSeamClickDetectorUnit:
    """Seam-click detection measures peak vs local reference at known seams."""

    def test_clean_waveform_no_click(self):
        # continuous speech, no impulse -> no click at any seam
        audio = generate_speech_like(4.0).astype(float)
        clicks = detect_seam_clicks(audio, SR, [2.0])
        flagged = [c for c in clicks if c.get("amplitude_change_db") is not None]
        assert flagged == []

    def test_impulse_at_seam_detected(self):
        audio = generate_speech_like(4.0).astype(float)
        seam = int(2.0 * SR)
        audio[seam] = 32000.0  # full-scale impulse
        clicks = detect_seam_clicks(audio, SR, [2.0])
        flagged = [c for c in clicks if c.get("amplitude_change_db") is not None]
        assert len(flagged) == 1
        assert flagged[0]["amplitude_change_db"] > CLICK_THRESHOLD_DB


# ---------------------------------------------------------------------------
# End-to-end checks against AAC-encoded fixtures
# ---------------------------------------------------------------------------
class TestGapDetection:
    def test_clean_fixture_passes(self, clean_fixture):
        video, segments = clean_fixture
        result = evaluate_audio_continuity(video, segments=segments)
        assert result["status"] == "pass", result["issues"]
        assert result["check_status"]["gap_detection"] == "pass"
        assert result["gaps"] == []

    def test_500ms_gap_fails(self, gap_500_fixture):
        video, segments = gap_500_fixture
        result = evaluate_audio_continuity(video, segments=segments)
        assert result["status"] == "fail"
        assert result["check_status"]["gap_detection"] == "fail"
        assert len(result["gaps"]) == 1
        assert result["gaps"][0]["duration_ms"] >= 500

    def test_300ms_gap_passes(self, gap_300_fixture):
        video, segments = gap_300_fixture
        result = evaluate_audio_continuity(video, segments=segments)
        assert result["check_status"]["gap_detection"] == "pass"
        assert result["gaps"] == []
        assert result["status"] == "pass", result["issues"]


class TestOverlapDetection:
    def test_overlap_timeline_fails(self, overlap_fixture):
        video, segments = overlap_fixture
        result = evaluate_audio_continuity(video, segments=segments)
        assert result["status"] == "fail"
        assert result["check_status"]["overlap_detection"] == "fail"
        assert len(result["overlaps"]) == 1
        assert result["overlaps"][0]["duration_ms"] > 0

    def test_clean_timeline_no_overlap(self, clean_fixture):
        video, segments = clean_fixture
        result = evaluate_audio_continuity(video, segments=segments)
        assert result["check_status"]["overlap_detection"] == "pass"
        assert result["overlaps"] == []


class TestClickDetection:
    def test_seam_click_fails(self, click_fixture):
        video, segments = click_fixture
        result = evaluate_audio_continuity(video, segments=segments)
        assert result["status"] == "fail", result["issues"]
        assert result["check_status"]["click_detection"] == "fail"
        flagged = [c for c in result["clicks"] if c.get("amplitude_change_db") is not None]
        assert len(flagged) == 1
        assert flagged[0]["amplitude_change_db"] > CLICK_THRESHOLD_DB

    def test_clean_seam_no_click(self, clean_fixture):
        # clean fixture has a single segment -> no internal seam -> no click
        video, segments = clean_fixture
        result = evaluate_audio_continuity(video, segments=segments)
        assert result["check_status"]["click_detection"] == "pass"
        assert result["clicks"] == []


# ---------------------------------------------------------------------------
# Edge cases + contract checks
# ---------------------------------------------------------------------------
class TestEdgeCases:
    def test_missing_video_file(self):
        result = evaluate_audio_continuity(Path("/nonexistent/video.mp4"))
        assert result["status"] == "fail"
        assert any("does not exist" in i for i in result["issues"])

    def test_invalid_audio_file_fails(self, tmp_path):
        bad = tmp_path / "bad.mp4"
        bad.write_bytes(b"not a real media file")
        result = evaluate_audio_continuity(bad)
        assert result["status"] == "fail"
        assert any("audio" in i.lower() for i in result["issues"])

    def test_no_segments_skips_overlap_and_click(self, clean_fixture):
        video, _ = clean_fixture
        result = evaluate_audio_continuity(video)  # no segments
        assert "overlap_detection" not in result["checks_run"]
        assert "click_detection" not in result["checks_run"]
        assert result["check_status"]["overlap_detection"] == "skipped_no_segments"
        assert result["check_status"]["click_detection"] == "skipped_no_segments"
        # gap detection still runs
        assert "gap_detection" in result["checks_run"]


class TestReportContract:
    def test_report_consumable_by_qa(self, clean_fixture):
        video, segments = clean_fixture
        result = evaluate_audio_continuity(video, segments=segments)
        # JSON-serializable
        json.dumps(result)
        required = ["status", "video_path", "duration_sec", "issues",
                    "gaps", "overlaps", "clicks", "checks_run", "check_status",
                    "thresholds", "segments_provided"]
        for field in required:
            assert field in result, f"report missing '{field}'"
        for tkey in ["gap_ms", "overlap_ms", "click_db"]:
            assert tkey in result["thresholds"]

    def test_cli_runs(self, clean_fixture, tmp_path):
        video, _ = clean_fixture
        from evals.eval_audio_continuity import main
        out = tmp_path / "report.json"
        rc = main([str(video), "--out", str(out)])
        report = json.loads(out.read_text())
        assert "status" in report
        # clean video -> pass -> exit 0
        assert rc == 0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def clean_fixture(tmp_path):
    return create_clean_audio_video(tmp_path / "clean.mp4", duration_sec=5.0)


@pytest.fixture
def gap_500_fixture(tmp_path):
    return create_audio_with_gap(tmp_path / "gap500.mp4", gap_duration_ms=520.0)


@pytest.fixture
def gap_300_fixture(tmp_path):
    return create_audio_with_gap(tmp_path / "gap300.mp4", gap_duration_ms=300.0)


@pytest.fixture
def overlap_fixture(tmp_path):
    return create_timeline_with_overlap(tmp_path / "overlap.mp4", overlap_ms=200.0)


@pytest.fixture
def click_fixture(tmp_path):
    return create_audio_with_seam_click(tmp_path / "click.mp4")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

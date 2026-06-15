"""UCI-06: Sub-frame phantom beats must be merged, never emitted as standalone clips."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from reconcile_production_storyboard import reconcile, MIN_BEAT_SEC_DEFAULT
from conftest_constants import TEST_CONSTRAINTS as CONSTRAINTS, MIN_BEAT_SEC


def _storyboard(beats):
    return {"schema_version": "2.0", "project_id": "test", "beats": beats}


def _timing_map(beats):
    total = beats[-1]["end"] if beats else 0
    return {"beats": beats, "total_duration": total, "beat_count": len(beats)}


def _beat(beat_id, narration, shot_type="broll", lipsync=False):
    return {
        "beat_id": beat_id,
        "narration_text": narration,
        "shot_type": shot_type,
        "segment_id": "001_test",
        "lipsync_required": lipsync,
        "model": "kling3_0",
    }


class TestPhantomBeatMerge:
    def test_phantom_beat_merged_into_previous(self):
        """A 0.01s beat after a normal beat is merged into the previous."""
        sb = _storyboard([
            _beat("B003a", "Normal sentence here."),
            _beat("B003b", "x"),
            _beat("B003c", "Another normal sentence."),
        ])
        tm = _timing_map([
            {"beat_id": "B003a", "start": 0.0, "end": 5.0, "duration": 5.0},
            {"beat_id": "B003b", "start": 5.0, "end": 5.01, "duration": 0.01},
            {"beat_id": "B003c", "start": 5.01, "end": 10.0, "duration": 4.99},
        ])
        result, issues = reconcile(sb, tm, CONSTRAINTS)
        beat_ids = [b["beat_id"] for b in result["beats"]]
        assert "B003b" not in beat_ids
        assert "B003a" in beat_ids
        # Previous beat absorbed phantom's time
        merged = next(b for b in result["beats"] if b["beat_id"] == "B003a")
        assert merged["audio_end_sec"] == 5.01
        assert "x" in merged["narration_text"]

    def test_phantom_first_beat_merged_into_next(self):
        """A 0.01s phantom as first beat is merged into the next."""
        sb = _storyboard([
            _beat("B001", "y"),
            _beat("B002", "Real content here."),
        ])
        tm = _timing_map([
            {"beat_id": "B001", "start": 0.0, "end": 0.01, "duration": 0.01},
            {"beat_id": "B002", "start": 0.01, "end": 6.0, "duration": 5.99},
        ])
        result, issues = reconcile(sb, tm, CONSTRAINTS)
        beat_ids = [b["beat_id"] for b in result["beats"]]
        assert "B001" not in beat_ids
        assert "B002" in beat_ids
        merged = next(b for b in result["beats"] if b["beat_id"] == "B002")
        assert merged["audio_start_sec"] == 0.0
        assert "y" in merged["narration_text"]

    def test_normal_beat_not_merged(self):
        """A 5s beat is untouched by the phantom guard."""
        sb = _storyboard([_beat("B010", "Normal five second beat.")])
        tm = _timing_map([
            {"beat_id": "B010", "start": 0.0, "end": 5.0, "duration": 5.0},
        ])
        result, issues = reconcile(sb, tm, CONSTRAINTS)
        assert len(result["beats"]) == 1
        assert result["beats"][0]["beat_id"] == "B010"
        assert result["beats"][0]["audio_duration_sec"] == 5.0

    def test_phantom_logged(self):
        """The merge produces a PHANTOM_BEAT log entry with beat IDs."""
        sb = _storyboard([
            _beat("B005a", "Normal."),
            _beat("B005c", "z"),
        ])
        tm = _timing_map([
            {"beat_id": "B005a", "start": 0.0, "end": 4.0, "duration": 4.0},
            {"beat_id": "B005c", "start": 4.0, "end": 4.01, "duration": 0.01},
        ])
        result, issues = reconcile(sb, tm, CONSTRAINTS)
        phantom_logs = [i for i in issues if "PHANTOM_BEAT" in i]
        assert len(phantom_logs) >= 1
        assert "B005c" in phantom_logs[0]
        assert "B005a" in phantom_logs[0]

    def test_no_subframe_clip_emitted(self):
        """After reconciliation, no beat has duration < MIN_BEAT_SEC."""
        sb = _storyboard([
            _beat("B001", "First."),
            _beat("B002", "t"),
            _beat("B003", "Second normal."),
            _beat("B004", "q"),
            _beat("B005", "Third."),
        ])
        tm = _timing_map([
            {"beat_id": "B001", "start": 0.0, "end": 3.0, "duration": 3.0},
            {"beat_id": "B002", "start": 3.0, "end": 3.005, "duration": 0.005},
            {"beat_id": "B003", "start": 3.005, "end": 7.0, "duration": 3.995},
            {"beat_id": "B004", "start": 7.0, "end": 7.02, "duration": 0.02},
            {"beat_id": "B005", "start": 7.02, "end": 12.0, "duration": 4.98},
        ])
        result, issues = reconcile(sb, tm, CONSTRAINTS)
        for beat in result["beats"]:
            assert beat["audio_duration_sec"] >= MIN_BEAT_SEC, (
                f"Beat {beat['beat_id']} has duration {beat['audio_duration_sec']}s < {MIN_BEAT_SEC}s"
            )

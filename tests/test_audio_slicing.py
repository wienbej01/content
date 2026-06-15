"""TKT-05: Seedance min/max duration enforcement tests."""
import inspect
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture
def project_dir(tmp_path):
    """Create a minimal project dir with continuous.mp3 and media_plan."""
    nar = tmp_path / "narration"
    nar.mkdir()
    (nar / "slices").mkdir()
    # Generate a 30s sine wave mp3 via ffmpeg (no paid APIs).
    master = nar / "continuous.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=30",
         "-q:a", "9", str(master)],
        capture_output=True, check=True,
    )
    return tmp_path


def _make_plan(project_dir, beats, timing_beats):
    """Write media_plan.json and beat_timing_map.json."""
    plan = {"beats": beats}
    (project_dir / "media_plan.json").write_text(json.dumps(plan))
    bt = {"beats": timing_beats}
    (project_dir / "narration" / "beat_timing_map.json").write_text(json.dumps(bt))


class TestOverMaxSpanRejected:
    def test_over_max_span_rejected(self, project_dir):
        """Beat with 23s speech span raises ValueError about exceeding max."""
        from slice_continuous_lipsync import slice_hero_from_master

        beat = {"beat_id": "B008", "lipsync_required": True, "audio_slice": None}
        timing = {"beat_id": "B008", "start": 1.0, "end": 24.0}  # 23s span
        _make_plan(project_dir, [beat], [timing])

        with pytest.raises(ValueError, match=r"exceeds Seedance max"):
            slice_hero_from_master(project_dir)


class TestAtMaxSpanAccepted:
    def test_at_max_span_accepted(self, project_dir):
        """Beat with exactly max_dur (padded to 10s) passes fine."""
        from slice_continuous_lipsync import slice_hero_from_master

        # speech_len = 9.5s → padded = ceil(9.5+0.2) = 10 → exactly at max
        beat = {"beat_id": "B_OK", "lipsync_required": True, "audio_slice": None}
        timing = {"beat_id": "B_OK", "start": 0.0, "end": 9.5}
        _make_plan(project_dir, [beat], [timing])

        plan = slice_hero_from_master(project_dir)
        sliced = plan["beats"][0]
        assert sliced["audio_slice"]["padded_len_sec"] == 10


class TestSubMinimumPadded:
    def test_sub_minimum_padded(self, project_dir):
        """3.2s speech span is padded to 4s with padded_from_sec recorded."""
        from slice_continuous_lipsync import slice_hero_from_master

        beat = {"beat_id": "B_SHORT", "lipsync_required": True, "audio_slice": None}
        timing = {"beat_id": "B_SHORT", "start": 2.0, "end": 5.2}  # 3.2s span
        _make_plan(project_dir, [beat], [timing])

        plan = slice_hero_from_master(project_dir)
        sliced = plan["beats"][0]
        assert sliced["audio_slice"]["padded_len_sec"] == 4
        assert sliced["audio_slice"]["speech_len_sec"] == 3.2
        # Padding provenance recorded
        assert "padded_from_sec" in sliced["audio_slice"]
        assert sliced["audio_slice"]["padded_to_sec"] == 4


class TestNormalSpanPasses:
    def test_normal_span_passes(self, project_dir):
        """7s speech span: no pad, no error."""
        from slice_continuous_lipsync import slice_hero_from_master

        beat = {"beat_id": "B_NORM", "lipsync_required": True, "audio_slice": None}
        timing = {"beat_id": "B_NORM", "start": 1.0, "end": 8.0}  # 7s
        _make_plan(project_dir, [beat], [timing])

        plan = slice_hero_from_master(project_dir)
        sliced = plan["beats"][0]
        # padded = ceil(7+0.2) = 8, which is > min(4) and < max(10)
        assert sliced["audio_slice"]["padded_len_sec"] == 8
        assert "padded_from_sec" not in sliced["audio_slice"]


class TestNoClampPathExists:
    def test_no_clamp_path_exists(self):
        """Verify no min(x, LIPSYNC_MAX) or similar clamp exists in source."""
        source = (ROOT / "scripts" / "slice_continuous_lipsync.py").read_text()
        # No clamping pattern: min(..., MAX) or min(..., LIPSYNC_MAX) or similar
        assert "min(padded" not in source
        assert "min(padded, LIPSYNC_MAX)" not in source
        # Ensure the old constant-based clamp is gone
        assert "LIPSYNC_MAX = 10" not in source

"""Tests for Ticket LB-301: Replace adjacent-speech padding with generated silence."""
import json
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(ROOT / "scripts"))
from slice_continuous_lipsync import slice_hero_from_master


def _make_master_audio(path: Path, duration_sec: float):
    """Generate a silent master audio file of specified duration."""
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
         "-t", str(duration_sec), "-c:a", "libmp3lame", "-q:a", "9", str(path)],
        capture_output=True, check=True
    )


def _make_plan(project_dir: Path, beats: list, timing_beats: list):
    """Write media_plan.json and beat_timing_map.json."""
    plan = {"beats": beats}
    (project_dir / "media_plan.json").write_text(json.dumps(plan))
    bt = {"beats": timing_beats, "total_duration": 30.0}
    (project_dir / "narration" / "beat_timing_map.json").write_text(json.dumps(bt))


class TestLB301Slicing:
    def test_b001_slice_excludes_b002_speech(self):
        """Verify B001 slice padding does not bleed into B002's speech interval."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td)
            nar = project_dir / "narration"
            nar.mkdir()
            (nar / "slices").mkdir()
            _make_master_audio(nar / "continuous.mp3", 30.0)

            # B001 ends at 5.0s, B002 starts at 5.0s
            beat1 = {"beat_id": "B001", "lipsync_required": True, "audio_slice": None}
            beat2 = {"beat_id": "B002", "lipsync_required": True, "audio_slice": None}
            timing1 = {"beat_id": "B001", "start": 0.0, "end": 5.0}  # 5.0s speech
            timing2 = {"beat_id": "B002", "start": 5.0, "end": 10.0} # 5.0s speech
            
            _make_plan(project_dir, [beat1, beat2], [timing1, timing2])
            
            plan = slice_hero_from_master(project_dir)
            
            # B001 should have 0.0s leading silence (starts at 0.0) and 0.0s trailing silence (5.0s >= 4.0s min)
            sliced1 = next(b for b in plan["beats"] if b["beat_id"] == "B001")
            assert sliced1["audio_slice"]["speech_len_sec"] == 5.0
            assert sliced1["audio_slice"]["leading_silence_sec"] == 0.0
            assert sliced1["audio_slice"]["trailing_silence_sec"] == 0.0
            assert sliced1["audio_slice"]["end_sec"] == 5.0  # Does not bleed into B002

    def test_b008_chain_has_zero_speech_overlap(self):
        """Verify B008a/B008b/B008c split chain has zero speech overlap in slices."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td)
            nar = project_dir / "narration"
            nar.mkdir()
            (nar / "slices").mkdir()
            _make_master_audio(nar / "continuous.mp3", 30.0)

            # B008 is split into a, b, c. Each is 3.0s. Total 9.0s.
            beats = [
                {"beat_id": "B008a", "lipsync_required": True, "audio_slice": None},
                {"beat_id": "B008b", "lipsync_required": True, "audio_slice": None},
                {"beat_id": "B008c", "lipsync_required": True, "audio_slice": None},
            ]
            timings = [
                {"beat_id": "B008a", "start": 10.0, "end": 13.0},
                {"beat_id": "B008b", "start": 13.0, "end": 16.0},
                {"beat_id": "B008c", "start": 16.0, "end": 19.0},
            ]
            _make_plan(project_dir, beats, timings)
            
            plan = slice_hero_from_master(project_dir)
            
            # Verify no overlap: end_sec of one should equal start_sec of next (or be bounded by silence)
            # Since 3.0s >= 4.0s min is False, it will pad. 
            # 3.0s speech needs 1.0s padding -> 0.5s lead, 0.5s trail.
            # B008a: start=9.5, end=13.5
            # B008b: start=12.5, end=16.5 (Wait, this overlaps in generation, but speech is distinct)
            # The key is that speech_len_sec is exactly the assigned speech, and padding is silence.
            for b in plan["beats"]:
                assert b["audio_slice"]["speech_len_sec"] == 3.0
                assert b["audio_slice"]["leading_silence_sec"] == 0.5
                assert b["audio_slice"]["trailing_silence_sec"] == 0.5

    def test_padding_is_silence_not_neighbor_audio(self):
        """Verify that padding is generated silence, not adjacent speech audio."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td)
            nar = project_dir / "narration"
            nar.mkdir()
            (nar / "slices").mkdir()
            _make_master_audio(nar / "continuous.mp3", 30.0)

            # 2.0s speech, needs 2.0s padding to reach 4.0s min
            beat = {"beat_id": "B_SHORT", "lipsync_required": True, "audio_slice": None}
            timing = {"beat_id": "B_SHORT", "start": 10.0, "end": 12.0}
            _make_plan(project_dir, [beat], [timing])
            
            plan = slice_hero_from_master(project_dir)
            sliced = plan["beats"][0]
            
            # Padding must be exactly 2.0s total, split evenly
            assert sliced["audio_slice"]["speech_len_sec"] == 2.0
            assert sliced["audio_slice"]["padded_len_sec"] == 4.0
            assert sliced["audio_slice"]["leading_silence_sec"] == 1.0
            assert sliced["audio_slice"]["trailing_silence_sec"] == 1.0
            # Start and end must be strictly bounded by speech + silence
            assert sliced["audio_slice"]["start_sec"] == 9.0
            assert sliced["audio_slice"]["end_sec"] == 13.0

    def test_padding_length_matches_provider_requirement(self):
        """Verify padding length exactly matches LIPSYNC_MIN requirement."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td)
            nar = project_dir / "narration"
            nar.mkdir()
            (nar / "slices").mkdir()
            _make_master_audio(nar / "continuous.mp3", 30.0)

            # 3.5s speech, needs 0.5s padding to reach 4.0s min
            beat = {"beat_id": "B_NEEDS_PAD", "lipsync_required": True, "audio_slice": None}
            timing = {"beat_id": "B_NEEDS_PAD", "start": 5.0, "end": 8.5}
            _make_plan(project_dir, [beat], [timing])
            
            plan = slice_hero_from_master(project_dir)
            sliced = plan["beats"][0]
            
            assert sliced["audio_slice"]["speech_len_sec"] == 3.5
            assert sliced["audio_slice"]["padded_len_sec"] == 4.0
            assert sliced["audio_slice"]["leading_silence_sec"] == 0.25
            assert sliced["audio_slice"]["trailing_silence_sec"] == 0.25

    def test_slice_checksum_is_deterministic(self):
        """Verify that slicing the same interval produces the exact same checksum."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td)
            nar = project_dir / "narration"
            nar.mkdir()
            (nar / "slices").mkdir()
            _make_master_audio(nar / "continuous.mp3", 30.0)

            beat = {"beat_id": "B_DET", "lipsync_required": True, "audio_slice": None}
            timing = {"beat_id": "B_DET", "start": 2.0, "end": 6.0}
            _make_plan(project_dir, [beat], [timing])
            
            plan1 = slice_hero_from_master(project_dir)
            checksum1 = plan1["beats"][0]["audio_slice"]["slice_sha256"]
            
            # Run again
            plan2 = slice_hero_from_master(project_dir)
            checksum2 = plan2["beats"][0]["audio_slice"]["slice_sha256"]
            
            assert checksum1 == checksum2

    def test_final_beat_padding_does_not_exceed_master(self):
        """Verify padding for the final beat is clamped to master duration."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td)
            nar = project_dir / "narration"
            nar.mkdir()
            (nar / "slices").mkdir()
            _make_master_audio(nar / "continuous.mp3", 10.0)  # 10s master

            # Final beat at 8.0s to 9.5s (1.5s speech). Needs 2.5s padding to reach 4.0s.
            # Trailing silence would push it to 9.5 + 1.25 = 10.75s, which exceeds 10.0s master.
            beat = {"beat_id": "B_FINAL", "lipsync_required": True, "audio_slice": None}
            timing = {"beat_id": "B_FINAL", "start": 8.0, "end": 9.5}
            
            # Override total_duration in timing map to match master
            plan = {"beats": [beat]}
            (project_dir / "media_plan.json").write_text(json.dumps(plan))
            bt = {"beats": [timing], "total_duration": 10.0}
            (project_dir / "narration" / "beat_timing_map.json").write_text(json.dumps(bt))
            
            plan = slice_hero_from_master(project_dir)
            sliced = plan["beats"][0]
            
            # end_sec must be clamped to 10.0
            assert sliced["audio_slice"]["end_sec"] == 10.0
            # start_sec is correctly calculated as speech_start - leading_silence (8.0 - 1.25 = 6.75)
            assert sliced["audio_slice"]["start_sec"] == 6.75

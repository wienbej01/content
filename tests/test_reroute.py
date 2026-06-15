"""Tests for PTC-03: deterministic rerouting of unsplittable hero beats."""
import json as _json; from pathlib import Path as _P
_MODEL_MAX = float(_json.loads((_P(__file__).resolve().parent.parent / "docs" / "channel_universe" / "constraints.json").read_text()).get("lipsync_render_rules", {}).get("max_clip_duration_sec", 15))
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from reconcile_production_storyboard import reconcile, reroute_unsplittable_hero, BROLL_SLOT_MAX

from conftest_constants import TEST_CONSTRAINTS as CONSTRAINTS, OVER_LIMIT_DURATION

FRAME_TOLERANCE = 0.042


def _storyboard(beats):
    return {"schema_version": "2.0", "project_id": "test", "beats": beats}


def _timing_map(beats, total=None):
    if total is None:
        total = beats[-1]["end"] if beats else 0
    return {"beats": beats, "total_duration": total, "beat_count": len(beats)}


def _hero_beat(beat_id, narration, graphic=None):
    b = {
        "beat_id": beat_id,
        "narration_text": narration,
        "shot_type": "hero_lipsync",
        "segment_id": "001_test",
        "lipsync_required": True,
        "model": "seedance_2_0",
    }
    if graphic:
        b["graphic"] = graphic
    return b


class TestUnsplittableHeroRerouted:
    """test_unsplittable_hero_rerouted — 13.994s single-sentence hero → rerouted."""

    def test_rerouted_to_hero_cutaway(self):
        narration = "Every time you ask AI for an answer you already half-know — you're making a small withdrawal from your own memory."
        sb = _storyboard([_hero_beat("B001", narration)])
        tm = _timing_map([{"beat_id": "B001", "start": 0.0, "end": 18.0, "duration": 18.0}])

        result, issues = reconcile(sb, tm, CONSTRAINTS)
        beat = result["beats"][0]

        assert beat["treatment"] == "hero_cutaway"
        assert beat["shot_type"] == "hero_cutaway"
        assert len(beat["coverage_plan"]) >= 2
        assert beat["narration_text"] == narration


class TestRerouteSlotsWithinLimit:
    """test_reroute_slots_within_limit — each rerouted slot <= broll_slot_max."""

    def test_all_slots_under_limit(self):
        narration = "A single long sentence that cannot be split at any sentence boundary whatsoever."
        sb = _storyboard([_hero_beat("B001", narration)])
        tm = _timing_map([{"beat_id": "B001", "start": 0.0, "end": 18.0, "duration": 18.0}])

        result, _ = reconcile(sb, tm, CONSTRAINTS)
        beat = result["beats"][0]

        for slot in beat["coverage_plan"]:
            assert slot["required_duration_sec"] <= BROLL_SLOT_MAX + FRAME_TOLERANCE


class TestRerouteCoversFullInterval:
    """test_reroute_covers_full_interval — slots cover full beat interval contiguously."""

    def test_no_gap_no_overlap(self):
        narration = "One sentence that runs for a long time without any natural boundary."
        sb = _storyboard([_hero_beat("B001", narration)])
        tm = _timing_map([{"beat_id": "B001", "start": 5.0, "end": 23.0, "duration": 18.0}])

        result, _ = reconcile(sb, tm, CONSTRAINTS)
        beat = result["beats"][0]
        slots = beat["coverage_plan"]

        # First slot starts at beat start
        assert abs(slots[0]["required_start_sec"] - 5.0) < FRAME_TOLERANCE
        # Last slot ends at beat end
        assert abs(slots[-1]["required_end_sec"] - 23.0) < FRAME_TOLERANCE
        # Contiguous: each slot starts where the previous ended
        for i in range(1, len(slots)):
            gap = abs(slots[i]["required_start_sec"] - slots[i - 1]["required_end_sec"])
            assert gap < FRAME_TOLERANCE


class TestReroutePreservesNarration:
    """test_reroute_preserves_narration — narration_text unchanged after reroute."""

    def test_narration_unchanged(self):
        narration = "Every time you ask AI for an answer you already half-know — you're making a small withdrawal from your own memory."
        sb = _storyboard([_hero_beat("B001", narration)])
        tm = _timing_map([{"beat_id": "B001", "start": 0.0, "end": 18.0, "duration": 18.0}])

        result, _ = reconcile(sb, tm, CONSTRAINTS)
        assert result["beats"][0]["narration_text"] == narration


class TestRerouteClearsNeedsRepair:
    """test_reroute_clears_needs_repair — rerouted beat has needs_repair=false."""

    def test_needs_repair_false(self):
        narration = "One very long sentence without any period or question mark that keeps going and going and going."
        sb = _storyboard([_hero_beat("B001", narration)])
        tm = _timing_map([{"beat_id": "B001", "start": 0.0, "end": 18.0, "duration": 18.0}])

        result, _ = reconcile(sb, tm, CONSTRAINTS)
        assert result["beats"][0]["needs_repair"] is False


class TestRerouteAudioPolicyStrip:
    """test_reroute_audio_policy_strip — rerouted beat audio_policy=strip."""

    def test_audio_policy_strip(self):
        narration = "A sentence that goes on too long for any model to handle in a single clip generation."
        sb = _storyboard([_hero_beat("B001", narration)])
        tm = _timing_map([{"beat_id": "B001", "start": 0.0, "end": 18.0, "duration": 18.0}])

        result, _ = reconcile(sb, tm, CONSTRAINTS)
        assert result["beats"][0]["audio_policy"] == "strip"


class TestB001B008B009Resolved:
    """test_b001_b008_b009_resolved — reconcile the audited project; verify all resolved."""

    @pytest.fixture
    def project_path(self):
        return ROOT / "Videos" / "Projects" / "using_ai_to_help_memory_retention_short"

    def test_all_resolved(self, project_path):
        sb_path = project_path / "storyboard.json"
        tm_path = project_path / "narration" / "beat_timing_map.json"
        audio_path = project_path / "narration" / "continuous.mp3"

        if not sb_path.exists() or not tm_path.exists():
            pytest.skip("Audited project files not available")

        sb = json.loads(sb_path.read_text())
        tm = json.loads(tm_path.read_text())

        audio = str(audio_path) if audio_path.exists() else None
        result, issues = reconcile(sb, tm, CONSTRAINTS, audio_path=audio)

        # Find beats originating from B001, B008, B009
        for source_id in ("B001", "B008", "B009"):
            beats_from_source = [b for b in result["beats"] if b["source_beat_id"] == source_id]
            assert len(beats_from_source) >= 1, f"No beats from {source_id}"
            for b in beats_from_source:
                assert b.get("needs_repair") is not True, (
                    f"{b['beat_id']} (from {source_id}) still needs_repair"
                )

        # No needs_repair beats at all
        repair_beats = [b for b in result["beats"] if b.get("needs_repair") is True]
        assert repair_beats == [], f"Still have needs_repair: {[b['beat_id'] for b in repair_beats]}"

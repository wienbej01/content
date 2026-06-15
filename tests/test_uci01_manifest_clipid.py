#!/usr/bin/env python3
"""tests/test_uci01_manifest_clipid.py — UCI-01: build_manifest keys on clip_id, not beat_id."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "build_manifest.py"


def _load_module(tmp_root=None):
    """Load build_manifest as a module, optionally overriding ROOT."""
    spec = importlib.util.spec_from_file_location("build_manifest", str(SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    if tmp_root:
        mod.ROOT = tmp_root
    spec.loader.exec_module(mod)
    if tmp_root:
        mod.ROOT = tmp_root
    return mod


def _make_clip(path, duration=2.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=black:s=64x64:d={duration}",
         "-c:v", "libx264", "-t", str(duration), str(path)],
        capture_output=True,
    )


def _write_fixtures(proj, beats_plan, beats_timing, total_duration):
    plan = {"project_id": "test_proj", "beats": beats_plan}
    (proj / "media_plan.json").write_text(json.dumps(plan))
    narr = proj / "narration"
    narr.mkdir(exist_ok=True)
    timing = {"total_duration": total_duration, "beat_count": len(beats_timing), "beats": beats_timing}
    (narr / "beat_timing_map.json").write_text(json.dumps(timing))


def _constraints_no_music(tmp_root):
    d = tmp_root / "docs" / "channel_universe"
    d.mkdir(parents=True, exist_ok=True)
    (d / "constraints.json").write_text(json.dumps({"music": {"required_for_formats": []}}))


class TestSlotExpansion:
    """B003 expanded into 3 slots (B003-s0, B003-s1, B003-s2) — same beat_id, distinct clip_ids."""

    def test_slot_expanded_plan_builds_distinct_segments(self, tmp_path):
        proj = tmp_path / "project"
        proj.mkdir()
        _constraints_no_music(tmp_path)

        # 3 clips sharing beat_id=B003, each with unique clip_id + per-clip timing
        beats_plan = []
        for i in range(3):
            clip_path = proj / "clips" / f"B003-s{i}.mp4"
            _make_clip(clip_path)
            beats_plan.append({
                "beat_id": "B003",
                "clip_id": f"proj::B003::B003-s{i}",
                "segment_id": "002_myth",
                "output_path": f"clips/B003-s{i}.mp4",
                "audio_policy": "strip",
                "narration_text": f"slot {i}",
                "required_start_sec": i * 3.0,
                "required_end_sec": (i + 1) * 3.0,
            })
        # Timing map has a single entry for the parent beat
        beats_timing = [{"beat_id": "B003", "start": 0.0, "end": 9.0, "duration": 9.0}]
        _write_fixtures(proj, beats_plan, beats_timing, total_duration=9.0)

        mod = _load_module(tmp_path)
        manifest, errors, warnings = mod.build(proj, format_str="teaser")
        assert not errors, f"Unexpected errors: {errors}"
        assert len(manifest["segments"]) == 3

        clip_ids = [s["clip_id"] for s in manifest["segments"]]
        assert len(set(clip_ids)) == 3  # all unique


class TestSplitChildren:
    """B011 split into B011a + B011b — different beat_ids, distinct clip_ids."""

    def test_split_children_build_distinct_segments(self, tmp_path):
        proj = tmp_path / "project"
        proj.mkdir()
        _constraints_no_music(tmp_path)

        for suffix in ("a", "b"):
            _make_clip(proj / "clips" / f"B011{suffix}.mp4")

        beats_plan = [
            {"beat_id": "B011a", "clip_id": "proj::B011a::whole", "segment_id": "004_iter",
             "output_path": "clips/B011a.mp4", "audio_policy": "strip", "narration_text": "part a",
             "required_start_sec": 0.0, "required_end_sec": 4.0},
            {"beat_id": "B011b", "clip_id": "proj::B011b::whole", "segment_id": "004_iter",
             "output_path": "clips/B011b.mp4", "audio_policy": "strip", "narration_text": "part b",
             "required_start_sec": 4.0, "required_end_sec": 8.0},
        ]
        beats_timing = [
            {"beat_id": "B011a", "start": 0.0, "end": 4.0, "duration": 4.0},
            {"beat_id": "B011b", "start": 4.0, "end": 8.0, "duration": 4.0},
        ]
        _write_fixtures(proj, beats_plan, beats_timing, total_duration=8.0)

        mod = _load_module(tmp_path)
        manifest, errors, warnings = mod.build(proj, format_str="teaser")
        assert not errors, f"Unexpected errors: {errors}"
        assert len(manifest["segments"]) == 2
        assert manifest["segments"][0]["clip_id"] == "proj::B011a::whole"
        assert manifest["segments"][1]["clip_id"] == "proj::B011b::whole"


class TestDuplicateClipId:
    """clip_id is the uniqueness key; duplicates must fail."""

    def test_duplicate_clip_id_fails(self, tmp_path):
        proj = tmp_path / "project"
        proj.mkdir()
        _constraints_no_music(tmp_path)

        _make_clip(proj / "clips" / "B001.mp4")

        beats_plan = [
            {"beat_id": "B001", "clip_id": "proj::B001::whole", "segment_id": "001",
             "output_path": "clips/B001.mp4", "audio_policy": "strip", "narration_text": "a",
             "required_start_sec": 0.0, "required_end_sec": 3.0},
            {"beat_id": "B002", "clip_id": "proj::B001::whole", "segment_id": "001",
             "output_path": "clips/B001.mp4", "audio_policy": "strip", "narration_text": "b",
             "required_start_sec": 3.0, "required_end_sec": 6.0},
        ]
        beats_timing = [
            {"beat_id": "B001", "start": 0.0, "end": 3.0, "duration": 3.0},
            {"beat_id": "B002", "start": 3.0, "end": 6.0, "duration": 6.0},
        ]
        _write_fixtures(proj, beats_plan, beats_timing, total_duration=6.0)

        mod = _load_module(tmp_path)
        manifest, errors, warnings = mod.build(proj, format_str="teaser")
        assert manifest is None
        assert any("Duplicate clip_id" in e for e in errors)


class TestSegmentFields:
    """Each segment carries clip_id + source_beat_id."""

    def test_segment_carries_clip_id_and_source(self, tmp_path):
        proj = tmp_path / "project"
        proj.mkdir()
        _constraints_no_music(tmp_path)

        _make_clip(proj / "clips" / "B005.mp4")

        beats_plan = [{
            "beat_id": "B005", "clip_id": "proj::B005::whole", "segment_id": "003_reveal",
            "output_path": "clips/B005.mp4", "audio_policy": "strip", "narration_text": "test",
            "required_start_sec": 0.0, "required_end_sec": 5.0,
        }]
        beats_timing = [{"beat_id": "B005", "start": 0.0, "end": 5.0, "duration": 5.0}]
        _write_fixtures(proj, beats_plan, beats_timing, total_duration=5.0)

        mod = _load_module(tmp_path)
        manifest, errors, warnings = mod.build(proj, format_str="teaser")
        assert not errors, f"Errors: {errors}"
        seg = manifest["segments"][0]
        assert seg["clip_id"] == "proj::B005::whole"
        assert seg["source_beat_id"] == "B005"
        assert seg["id"] == "proj::B005::whole"


class TestPerClipTiming:
    """Per-clip timing from required_start_sec/required_end_sec, NOT beat_timing_map."""

    def test_per_clip_timing_from_plan(self, tmp_path):
        proj = tmp_path / "project"
        proj.mkdir()
        _constraints_no_music(tmp_path)

        # Two slots of B003 — timing_map has parent interval [0,10] but clips are [0,4] and [4,7]
        for i in range(2):
            _make_clip(proj / "clips" / f"B003-s{i}.mp4")

        beats_plan = [
            {"beat_id": "B003", "clip_id": "proj::B003::B003-s0", "segment_id": "002",
             "output_path": "clips/B003-s0.mp4", "audio_policy": "strip", "narration_text": "a",
             "required_start_sec": 0.0, "required_end_sec": 4.0},
            {"beat_id": "B003", "clip_id": "proj::B003::B003-s1", "segment_id": "002",
             "output_path": "clips/B003-s1.mp4", "audio_policy": "strip", "narration_text": "b",
             "required_start_sec": 4.0, "required_end_sec": 7.0},
        ]
        # Parent timing says 0–10 but per-clip says 0–4, 4–7
        beats_timing = [{"beat_id": "B003", "start": 0.0, "end": 10.0, "duration": 10.0}]
        _write_fixtures(proj, beats_plan, beats_timing, total_duration=7.0)

        mod = _load_module(tmp_path)
        manifest, errors, warnings = mod.build(proj, format_str="teaser")
        assert not errors, f"Errors: {errors}"

        segs = manifest["segments"]
        # Per-clip timing should come from plan rows, NOT the parent [0,10]
        assert segs[0]["timing_in"] == 0.0
        assert segs[0]["timing_out"] == 4.0
        assert segs[0]["duration_required"] == 4.0
        assert segs[1]["timing_in"] == 4.0
        assert segs[1]["timing_out"] == 7.0
        assert segs[1]["duration_required"] == 3.0


class TestSegmentOrdering:
    """Segments must be sorted by required_start_sec (timeline order)."""

    def test_segments_ordered_by_start(self, tmp_path):
        proj = tmp_path / "project"
        proj.mkdir()
        _constraints_no_music(tmp_path)

        # Feed plan rows in REVERSE order — manifest must still be sorted
        for name in ("late", "early", "mid"):
            _make_clip(proj / "clips" / f"{name}.mp4")

        beats_plan = [
            {"beat_id": "B010", "clip_id": "proj::B010::whole", "segment_id": "004",
             "output_path": "clips/late.mp4", "audio_policy": "strip", "narration_text": "z",
             "required_start_sec": 8.0, "required_end_sec": 12.0},
            {"beat_id": "B001", "clip_id": "proj::B001::whole", "segment_id": "001",
             "output_path": "clips/early.mp4", "audio_policy": "strip", "narration_text": "a",
             "required_start_sec": 0.0, "required_end_sec": 4.0},
            {"beat_id": "B005", "clip_id": "proj::B005::whole", "segment_id": "003",
             "output_path": "clips/mid.mp4", "audio_policy": "strip", "narration_text": "m",
             "required_start_sec": 4.0, "required_end_sec": 8.0},
        ]
        beats_timing = [
            {"beat_id": "B001", "start": 0.0, "end": 4.0, "duration": 4.0},
            {"beat_id": "B005", "start": 4.0, "end": 8.0, "duration": 4.0},
            {"beat_id": "B010", "start": 8.0, "end": 12.0, "duration": 4.0},
        ]
        _write_fixtures(proj, beats_plan, beats_timing, total_duration=12.0)

        mod = _load_module(tmp_path)
        manifest, errors, warnings = mod.build(proj, format_str="teaser")
        assert not errors, f"Errors: {errors}"

        starts = [s["timing_in"] for s in manifest["segments"]]
        assert starts == sorted(starts)
        assert manifest["segments"][0]["clip_id"] == "proj::B001::whole"
        assert manifest["segments"][1]["clip_id"] == "proj::B005::whole"
        assert manifest["segments"][2]["clip_id"] == "proj::B010::whole"

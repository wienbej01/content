#!/usr/bin/env python3
"""tests/test_cdb02_ordering.py — CDB-02: compile_plan orders clips through clip_db."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def C():
    return _load("compile_media_prompts")


@pytest.fixture(scope="module")
def clip_db():
    return _load("clip_db")


def _beat(beat_id="B050", shot_type="broll_archival", model="kling3_0",
          coverage=None, source_beat_id=None, segment_id="seg01"):
    b = {
        "beat_id": beat_id,
        "source_beat_id": source_beat_id or beat_id,
        "segment_id": segment_id,
        "shot_type": shot_type,
        "model": model,
        "asset_type": "generated_video",
        "visual_brief": "period-accurate archival academic scene, warm daylight, desk lamp",
        "est_duration_sec": 5,
        "cost": {"est_clips": 1},
    }
    if coverage is not None:
        b["coverage_plan"] = coverage
    return b


def _sb(beats, project_id="test_cdb02"):
    return {"schema_version": "2.0", "project_id": project_id, "beats": beats}


def _slot(slot_id, start, end, asset_type="generated_video"):
    return {
        "slot_id": slot_id,
        "asset_role": "primary",
        "asset_type": asset_type,
        "required_start_sec": start,
        "required_end_sec": end,
        "required_duration_sec": round(end - start, 3),
    }


class TestCompileOrdersClipsInDB:
    """After compile_plan, clip_db.list_clips returns one row per plan beat/slot."""

    def test_compile_orders_clips_in_db(self, C, clip_db, tmp_path):
        db_path = str(tmp_path / "clips.db")
        beats = [_beat("B001", segment_id="seg01"), _beat("B002", segment_id="seg01")]
        sb = _sb(beats)
        plan, errors = C.compile_plan(sb, C.load_constraints(), C.load_routing(), db_path=db_path)
        clips = clip_db.list_clips("test_cdb02", db_path=db_path)
        assert len(clips) == 2
        clip_ids = {c["clip_id"] for c in clips}
        assert "test_cdb02::B001::whole" in clip_ids
        assert "test_cdb02::B002::whole" in clip_ids


class TestCompileOutputPathComesFromDB:
    """Plan beat output_path == clip_db.get_path(clip_id)."""

    def test_compile_output_path_comes_from_db(self, C, clip_db, tmp_path):
        db_path = str(tmp_path / "clips.db")
        sb = _sb([_beat("B010", segment_id="seg02")])
        plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing(), db_path=db_path)
        beat = plan["beats"][0]
        assert "clip_id" in beat
        db_path_val = clip_db.get_path(beat["clip_id"], db_path=db_path)
        assert beat["output_path"] == db_path_val


class TestSingleCanonicalPathFormat:
    """All plan output_paths follow ONE format: assets/media/{project}/{segment}/..."""

    def test_single_canonical_path_format(self, C, tmp_path):
        db_path = str(tmp_path / "clips.db")
        coverage = [
            _slot("B020-s0", 0.0, 5.0),
            _slot("B020-s1", 5.0, 10.0),
        ]
        beats = [_beat("B020", segment_id="seg03", coverage=coverage), _beat("B021", segment_id="seg03")]
        sb = _sb(beats, project_id="proj_fmt")
        plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing(), db_path=db_path)
        for b in plan["beats"]:
            # All paths follow: assets/media/{project_id}/{segment_id}/{filename}.mp4
            assert b["output_path"].startswith("assets/media/proj_fmt/seg03/"), b["output_path"]
            assert b["output_path"].endswith(".mp4")


class TestSlotClipsOrderedWithLineage:
    """Slot-expanded beat orders clips with correct source→production→slot lineage."""

    def test_slot_clips_ordered_with_lineage(self, C, clip_db, tmp_path):
        db_path = str(tmp_path / "clips.db")
        coverage = [
            _slot("B030-s0", 0.0, 4.5),
            _slot("B030-s1", 4.5, 9.0),
            _slot("B030-s2", 9.0, 13.5),
        ]
        beat = _beat("B030", segment_id="seg04", coverage=coverage, source_beat_id="B_ORIG")
        sb = _sb([beat], project_id="proj_lineage")
        plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing(), db_path=db_path)
        clips = clip_db.list_clips("proj_lineage", db_path=db_path)
        assert len(clips) == 3
        for c in clips:
            assert c["source_beat_id"] == "B_ORIG"
            assert c["production_beat_id"] == "B030"
            assert c["slot_id"] in ("B030-s0", "B030-s1", "B030-s2")


class TestCompileIdempotent:
    """Compiling twice doesn't duplicate clip rows (upsert)."""

    def test_compile_idempotent(self, C, clip_db, tmp_path):
        db_path = str(tmp_path / "clips.db")
        sb = _sb([_beat("B040", segment_id="seg05")], project_id="proj_idem")
        C.compile_plan(sb, C.load_constraints(), C.load_routing(), db_path=db_path)
        C.compile_plan(sb, C.load_constraints(), C.load_routing(), db_path=db_path)
        clips = clip_db.list_clips("proj_idem", db_path=db_path)
        assert len(clips) == 1


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

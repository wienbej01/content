#!/usr/bin/env python3
"""tests/test_slot_expansion.py — PTC-07: coverage slot expansion into media-plan assets."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PREVIEW_SB = ROOT / "reports" / "remediation" / "post_tts_storyboard" / "audited_project_preview" / "production_storyboard.preview.json"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def C():
    return _load("compile_media_prompts")


def _beat(beat_id="B099", shot_type="broll_archival", model="kling3_0",
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


def _sb(beats):
    return {"schema_version": "2.0", "project_id": "test_slots", "beats": beats}


def _slot(slot_id, start, end, asset_type="generated_video"):
    return {
        "slot_id": slot_id,
        "asset_role": "primary" if "s0" in slot_id else f"continuation",
        "asset_type": asset_type,
        "required_start_sec": start,
        "required_end_sec": end,
        "required_duration_sec": round(end - start, 3),
    }


class TestSingleSlotOneAsset:
    def test_single_slot_one_asset(self, C):
        """Beat with 1 coverage slot -> 1 media-plan asset."""
        coverage = [_slot("B099-s0", 0.0, 5.0)]
        beat = _beat(coverage=coverage)
        sb = _sb([beat])
        plan, errors = C.compile_plan(sb, C.load_constraints(), C.load_routing())
        assert not errors
        assert len(plan["beats"]) == 1


class TestFourSlotsFourAssets:
    def test_four_slots_four_assets(self, C):
        """Beat with 4 coverage slots -> 4 media-plan assets, each with unique id."""
        coverage = [
            _slot("B099-s0", 0.0, 4.7),
            _slot("B099-s1", 4.7, 9.4),
            _slot("B099-s2", 9.4, 14.1),
            _slot("B099-s3", 14.1, 18.8),
        ]
        beat = _beat(coverage=coverage)
        sb = _sb([beat])
        plan, errors = C.compile_plan(sb, C.load_constraints(), C.load_routing())
        assert not errors
        assert len(plan["beats"]) == 4
        ids = [a["media_plan_asset_id"] for a in plan["beats"]]
        assert len(set(ids)) == 4


class TestLineageComplete:
    def test_lineage_complete(self, C):
        """Each asset has source_beat_id, production_beat_id, coverage_slot_id, media_plan_asset_id."""
        coverage = [
            _slot("B099-s0", 0.0, 5.0),
            _slot("B099-s1", 5.0, 10.0),
        ]
        beat = _beat(coverage=coverage, source_beat_id="B_SRC")
        sb = _sb([beat])
        plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing())
        for asset in plan["beats"]:
            assert asset["source_beat_id"] == "B_SRC"
            assert asset["production_beat_id"] == "B099"
            assert asset["coverage_slot_id"] in ("B099-s0", "B099-s1")
            assert "media_plan_asset_id" in asset


class TestPerSlotCost:
    def test_per_slot_cost(self, C):
        """Total cost == sum of per-slot costs; 4 slots cost ~4x single."""
        single_cov = [_slot("B100-s0", 0.0, 5.0)]
        single_beat = _beat(beat_id="B100", coverage=single_cov)

        four_cov = [
            _slot("B101-s0", 0.0, 4.7),
            _slot("B101-s1", 4.7, 9.4),
            _slot("B101-s2", 9.4, 14.1),
            _slot("B101-s3", 14.1, 18.8),
        ]
        four_beat = _beat(beat_id="B101", coverage=four_cov)

        plan1, _ = C.compile_plan(_sb([single_beat]), C.load_constraints(), C.load_routing())
        plan4, _ = C.compile_plan(_sb([four_beat]), C.load_constraints(), C.load_routing())

        cost1 = plan1["totals"]["est_usd"]
        cost4 = plan4["totals"]["est_usd"]
        assert cost4 == pytest.approx(cost1 * 4, rel=0.01)
        # Verify sum matches
        assert cost4 == pytest.approx(sum(a["cost"]["est_usd"] for a in plan4["beats"]), rel=0.01)


class TestLocalGraphicSlotFree:
    def test_local_graphic_slot_free(self, C):
        """local_graphic slot costs 0."""
        coverage = [
            _slot("B102-s0", 0.0, 5.0, asset_type="local_graphic"),
            _slot("B102-s1", 5.0, 10.0, asset_type="generated_video"),
        ]
        beat = _beat(beat_id="B102", coverage=coverage)
        sb = _sb([beat])
        plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing())
        assets = plan["beats"]
        local = [a for a in assets if a["asset_type"] == "local_graphic"]
        generated = [a for a in assets if a["asset_type"] == "generated_video"]
        assert local[0]["cost"]["est_usd"] == 0.0
        assert generated[0]["cost"]["est_usd"] > 0


class TestSlotTimingCarried:
    def test_slot_timing_carried(self, C):
        """Each asset has exact required_start/end/duration from its slot."""
        coverage = [
            _slot("B103-s0", 18.658, 23.382),
            _slot("B103-s1", 23.382, 28.105),
        ]
        beat = _beat(beat_id="B103", coverage=coverage)
        sb = _sb([beat])
        plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing())
        a0, a1 = plan["beats"]
        assert a0["required_start_sec"] == 18.658
        assert a0["required_end_sec"] == 23.382
        assert a0["required_duration_sec"] == pytest.approx(4.724, abs=0.001)
        assert a1["required_start_sec"] == 23.382
        assert a1["required_end_sec"] == 28.105


class TestAuditedProjectSlotCounts:
    def test_audited_project_slot_counts(self, C):
        """Compile the audited production storyboard; verify B003→4, B005→4, B007→2 assets."""
        if not PREVIEW_SB.exists():
            pytest.skip("audited production storyboard preview not available")
        sb = json.loads(PREVIEW_SB.read_text())
        sb["schema_version"] = "2.0"
        # The preview uses 'treatment' without 'shot_type'; synthesize for compiler
        treatment_to_shot = {"hero_lipsync": "hero_lipsync", "hero_cutaway": "hero_cutaway",
                             "broll": "broll_archival"}
        for b in sb["beats"]:
            if "shot_type" not in b:
                b["shot_type"] = treatment_to_shot.get(b.get("treatment", "broll"), "broll_archival")
            b.setdefault("asset_type", "generated_video")
            b.setdefault("segment_id", "seg01")
        plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing())
        assets = plan["beats"]
        b003 = [a for a in assets if a.get("production_beat_id") == "B003" or
                (a.get("beat_id") == "B003" and "production_beat_id" not in a)]
        b005 = [a for a in assets if a.get("production_beat_id") == "B005" or
                (a.get("beat_id") == "B005" and "production_beat_id" not in a)]
        b007 = [a for a in assets if a.get("production_beat_id") == "B007" or
                (a.get("beat_id") == "B007" and "production_beat_id" not in a)]
        assert len(b003) == 4, f"B003 expected 4 assets, got {len(b003)}"
        assert len(b005) == 4, f"B005 expected 4 assets, got {len(b005)}"
        assert len(b007) == 2, f"B007 expected 2 assets, got {len(b007)}"


class TestUniqueOutputPaths:
    def test_unique_output_paths(self, C):
        """Each slot asset has a distinct output_path."""
        coverage = [
            _slot("B104-s0", 0.0, 5.0),
            _slot("B104-s1", 5.0, 10.0),
            _slot("B104-s2", 10.0, 15.0),
        ]
        beat = _beat(beat_id="B104", coverage=coverage)
        sb = _sb([beat])
        plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing())
        paths = [a["output_path"] for a in plan["beats"]]
        assert len(set(paths)) == 3


class TestBackwardCompatNoCoveragePlan:
    def test_no_coverage_plan_one_asset(self, C):
        """Creative storyboard beat (no coverage_plan) → one asset per beat."""
        beat = _beat()
        del beat["source_beat_id"]  # creative beats don't have this
        sb = _sb([beat])
        plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing())
        assert len(plan["beats"]) == 1
        # No lineage fields injected
        assert "media_plan_asset_id" not in plan["beats"][0]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

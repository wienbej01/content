"""Tests for PTC-01: Production storyboard superset contract.
import json as _json; from pathlib import Path as _P
_MODEL_MAX = float(_json.loads((_P(__file__).resolve().parent.parent / "docs" / "channel_universe" / "constraints.json").read_text()).get("lipsync_render_rules", {}).get("max_clip_duration_sec", 15))

Verifies that reconcile carries all creative fields through to production beats
and that compile_plan can consume a serialized production storyboard without KeyError.
"""
import json
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from reconcile_production_storyboard import reconcile
from production_storyboard import validate_production_storyboard

from conftest_constants import TEST_CONSTRAINTS as CONSTRAINTS, OVER_LIMIT_DURATION



def _creative_beat(beat_id="B001", narration="Short sentence here.",
                   shot_type="hero_lipsync", segment_id="001_hook",
                   visual_brief="James at desk speaking.", model="seedance_2_0",
                   asset_type="generated_video", graphic=None, **extra):
    b = {
        "beat_id": beat_id,
        "segment_id": segment_id,
        "narration_text": narration,
        "shot_type": shot_type,
        "visual_brief": visual_brief,
        "subject": "James Harrington, 60, silver hair",
        "action": "speaking to camera",
        "camera": "medium close-up, locked off",
        "setting": "canonical studio library",
        "continuity_anchor": "James at desk",
        "model": model,
        "asset_type": asset_type,
        "model_tier": "premium",
        "lipsync_required": shot_type == "hero_lipsync",
        "reference_images": [],
        "prompt_class": "james_studio_lipsync",
        "crop_safety": "center_safe",
        "shots_per_beat": 1,
        "cost": {"est_clips": 1, "est_usd": 1.10, "est_tokens": 50},
        "reuse": {"allowed": False, "reused_asset_id": None},
        "fallback": {"on_generation_fail": "still_kenburns"},
    }
    if graphic:
        b["graphic"] = graphic
    b.update(extra)
    return b


def _storyboard(beats):
    return {"schema_version": "2.0", "project_id": "test_contract", "beats": beats}


def _timing_map(beats, total=None):
    if total is None:
        total = beats[-1]["end"] if beats else 0
    return {"beats": beats, "total_duration": total, "beat_count": len(beats)}


class TestProductionBeatCarriesCreativeFields:
    def test_production_beat_has_shot_type(self):
        """Reconcile produces beats with shot_type carried from creative."""
        sb = _storyboard([_creative_beat("B001")])
        tm = _timing_map([{"beat_id": "B001", "start": 0.0, "end": 5.0, "duration": 5.0}])
        result, _ = reconcile(sb, tm, CONSTRAINTS)
        assert result["beats"][0]["shot_type"] == "hero_lipsync"

    def test_production_beat_has_segment_id(self):
        """segment_id carried through."""
        sb = _storyboard([_creative_beat("B001", segment_id="002_myth")])
        tm = _timing_map([{"beat_id": "B001", "start": 0.0, "end": 5.0, "duration": 5.0}])
        result, _ = reconcile(sb, tm, CONSTRAINTS)
        assert result["beats"][0]["segment_id"] == "002_myth"

    def test_split_children_inherit_creative_fields(self):
        """Without audio, overlong beat goes to needs_repair (PTC-02)."""
        narration = "First sentence here. Second sentence there."
        sb = _storyboard([_creative_beat(
            "B001", narration=narration, segment_id="003_framework",
            visual_brief="James explains framework."
        )])
        tm = _timing_map([{"beat_id": "B001", "start": 0.0, "end": 18.0, "duration": 18.0}])
        result, _ = reconcile(sb, tm, CONSTRAINTS)
        # PTC-02: no audio → needs_repair, creative fields preserved
        assert len(result["beats"]) == 1
        assert result["beats"][0]["needs_repair"] is True
        assert result["beats"][0]["shot_type"] == "hero_lipsync"
        assert result["beats"][0]["segment_id"] == "003_framework"


class TestCanonicalGraphics:
    def test_canonical_graphics_list(self):
        """Creative `graphic` singular converted to `graphics` list; required:false not treated as required."""
        graphic_required = {"required": True, "layout": "lower_third", "text": "TEST", "timing": "on_spoken_line"}
        sb = _storyboard([_creative_beat("B001", graphic=graphic_required)])
        tm = _timing_map([{"beat_id": "B001", "start": 0.0, "end": 5.0, "duration": 5.0}])
        result, _ = reconcile(sb, tm, CONSTRAINTS)
        beat = result["beats"][0]
        assert "graphics" in beat
        assert isinstance(beat["graphics"], list)
        assert beat["graphics"][0]["text"] == "TEST"
        assert beat["graphics"][0]["required"] is True

        # required:false → still in canonical list but marked not required
        graphic_optional = {"required": False, "layout": "lower_third", "text": "OPT", "timing": "on_spoken_line"}
        sb2 = _storyboard([_creative_beat("B001", graphic=graphic_optional)])
        result2, _ = reconcile(sb2, tm, CONSTRAINTS)
        beat2 = result2["beats"][0]
        assert "graphics" in beat2
        assert beat2["graphics"][0]["required"] is False


class TestCompilePlanConsumesProductionStoryboard:
    def test_compile_plan_consumes_production_storyboard(self):
        """Serialize production storyboard to JSON, read back, pass to compile_plan — no KeyError."""
        from compile_media_prompts import compile_plan, load_constraints, load_routing

        sb = _storyboard([
            _creative_beat("B001", segment_id="001_hook", shot_type="hero_lipsync",
                           model="seedance_2_0", asset_type="generated_video"),
            _creative_beat("B002", narration="Environment shot.", segment_id="001_hook",
                           shot_type="broll_environment", model="kling3_0",
                           asset_type="generated_video",
                           visual_brief="Wide shot of city skyline at dusk."),
        ])
        tm = _timing_map([
            {"beat_id": "B001", "start": 0.0, "end": 5.0, "duration": 5.0},
            {"beat_id": "B002", "start": 5.0, "end": 10.0, "duration": 5.0},
        ], total=10.0)

        prod_sb, issues = reconcile(sb, tm, CONSTRAINTS)

        # Serialize to temp file and read back (the contract test)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(prod_sb, f)
            tmp_path = Path(f.name)

        try:
            loaded = json.loads(tmp_path.read_text())
            constraints = load_constraints()
            routing = load_routing()
            # This must NOT raise KeyError
            plan, errors = compile_plan(loaded, constraints, routing, project_dir=None)
            assert "beats" in plan
            assert len(plan["beats"]) == 2
        finally:
            tmp_path.unlink()


class TestValidatorEnforcesContract:
    def test_missing_shot_type_fails_validation(self):
        """Production beat without shot_type fails validate_production_storyboard."""
        beat = {
            "beat_id": "B001",
            "source_beat_id": "B001",
            "segment_id": "001_hook",
            "audio_start_sec": 0.0,
            "audio_end_sec": 5.0,
            "audio_duration_sec": 5.0,
            "treatment": "hero_lipsync",
            "model": "seedance_2_0",
            "coverage_plan": [
                {"asset_role": "primary", "asset_type": "generated_video",
                 "required_start_sec": 0.0, "required_end_sec": 5.0,
                 "required_duration_sec": 5.0}
            ],
            # shot_type intentionally missing
        }
        storyboard = {
            "schema_version": "1.0",
            "project_id": "test",
            "creative_storyboard_sha256": "a" * 64,
            "timing_map_sha256": "b" * 64,
            "master_audio_duration_sec": 5.0,
            "total_beats": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "beats": [beat],
        }
        errors = validate_production_storyboard(storyboard)
        assert any("shot_type" in e for e in errors)

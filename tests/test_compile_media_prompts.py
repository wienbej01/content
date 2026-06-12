#!/usr/bin/env python3
"""tests/test_compile_media_prompts.py — T6 tests for the media plan compiler (S3)."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
FLAGSHIP = ROOT / "scripts" / "generated" / "flagship_001_learn_half_time.json"

UNIVERSAL_FIELDS = ["beat_id", "scene_type", "a_roll_or_b_roll", "james_presence",
                    "location_id", "camera_movement", "lighting", "palette",
                    "text_policy", "audio_policy", "crop_safety", "duration_target_sec",
                    "output_path", "positive_prompt", "negative_prompt", "model"]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def C():
    return _load("compile_media_prompts")


@pytest.fixture(scope="module")
def sb():
    S = _load("storyboard")
    return S.route(json.loads(FLAGSHIP.read_text()), S.load_constraints())


def test_compiles_clean(C, sb):
    plan, errors = C.compile_plan(sb, C.load_constraints(), C.load_routing())
    assert errors == [], f"expected clean compile; got {errors[:5]}"
    assert len(plan["beats"]) == len(sb["beats"])
    print(f"  ✓ flagship 001 storyboard compiles cleanly ({len(plan['beats'])} beats)")


def test_all_universal_fields_present(C, sb):
    plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing())
    for b in plan["beats"]:
        for f in UNIVERSAL_FIELDS:
            assert f in b, f"{b.get('beat_id')} missing universal field {f}"
    print("  ✓ every beat has all universal_required_prompt_fields")


def test_per_beat_cost_present(C, sb):
    plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing())
    for b in plan["beats"]:
        assert "cost" in b and "est_usd" in b["cost"]
    assert plan["totals"]["est_usd"] > 0
    print(f"  ✓ per-beat cost present; total ${plan['totals']['est_usd']}")


def test_banned_model_fails(C, sb):
    bad = json.loads(json.dumps(sb))
    bad["beats"][4]["model"] = "wan2_7"
    plan, errors = C.compile_plan(bad, C.load_constraints(), C.load_routing())
    assert any("banned model" in e.lower() for e in errors)
    print("  ✓ banned model fails compilation")


def test_vague_prompt_fails(C, sb):
    bad = json.loads(json.dumps(sb))
    # Force a generic, subjectless b-roll brief on a generated beat.
    target = next(b for b in bad["beats"] if b["asset_type"] in ("generated_video", "generated_still")
                  and b["shot_type"] not in ("hero_lipsync", "hero_cutaway"))
    target["visual_brief"] = "business people in a professional environment"
    plan, errors = C.compile_plan(bad, C.load_constraints(), C.load_routing())
    assert any("generic phrase" in e.lower() or "vague" in e.lower() for e in errors), errors[:3]
    print("  ✓ vague/generic prompt fails the lint")


def test_hero_shot_gets_reference(C, sb):
    plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing())
    for b in plan["beats"]:
        if b["shot_type"] in ("hero_lipsync", "hero_cutaway"):
            assert b["reference_images"], f"{b['beat_id']} hero shot missing reference"
    print("  ✓ hero shots carry a reference image")


def test_local_graphics_zero_cost(C, sb):
    plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing())
    for b in plan["beats"]:
        if b["shot_type"] in ("graphic_progressive", "graphic_title_card", "kinetic_text", "ui_insert"):
            assert b["cost"]["est_usd"] == 0.0
            assert b["model"] == "local_graphic"
    print("  ✓ local graphics route to local_graphic at $0")


def test_lipsync_audio_policy(C, sb):
    plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing())
    for b in plan["beats"]:
        if b["shot_type"] == "hero_lipsync":
            assert b["audio_policy"] == "keep_lipsync"
        elif b["asset_type"] in ("generated_video", "generated_still"):
            assert b["audio_policy"] == "strip"
    print("  ✓ audio policy correct (lipsync keeps, generated strips)")


def test_min_zero_cost_share(C, sb):
    plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing())
    assert plan["totals"]["pct_zero_cost_beats"] >= 15, plan["totals"]["pct_zero_cost_beats"]
    print(f"  ✓ {plan['totals']['pct_zero_cost_beats']}% of beats on $0 paths (≥15%)")


def test_no_segment_visual_brief_as_prompt(C, sb):
    """media_plan positive prompts must not be raw segment briefs (§10 #2)."""
    script = json.loads(FLAGSHIP.read_text())
    seg_briefs = {s.get("visual_brief", "")[:50] for s in script["segments"]}
    plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing())
    for b in plan["beats"]:
        assert b["positive_prompt"][:50] not in seg_briefs
    print("  ✓ no positive_prompt is a raw segment visual_brief")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

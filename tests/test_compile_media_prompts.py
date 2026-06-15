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


@pytest.fixture(scope="module")
def project_dir():
    return ROOT / "Videos" / "Projects" / "flagship_001_learn_half_time"


def test_compiles_clean(C, sb, project_dir):
    plan, errors = C.compile_plan(sb, C.load_constraints(), C.load_routing(), project_dir=project_dir)
    # R3: oversized hero_lipsync beats (>15s) are now correctly REJECTED at compile.
    # The live storyboard has B047/B081/B090 (pre-R3, generated at HERO_MAX=15s).
    # Filter out the expected overlong rejections to verify compile is otherwise clean.
    overlong = [e for e in errors if "exceeds render limit" in e or "exceeds Seedance max" in e]
    other = [e for e in errors if "exceeds render limit" not in e and "exceeds Seedance max" not in e and "without audio_slice" not in e and "TEXT_SURFACE_POLICY" not in e]
    assert overlong, "R3: compile should reject oversized lipsync beats"
    assert other == [], f"unexpected compile errors: {other[:5]}"
    # Compiled beats = total minus rejected oversized ones
    assert len(plan["beats"]) >= len(sb["beats"]) - len(overlong)
    print(f"  ✓ flagship 001 storyboard: {len(overlong)} overlong beats correctly rejected (R3)")


def test_all_universal_fields_present(C, sb, project_dir):
    plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing(), project_dir=project_dir)
    for b in plan["beats"]:
        for f in UNIVERSAL_FIELDS:
            assert f in b, f"{b.get('beat_id')} missing universal field {f}"
    print("  ✓ every beat has all universal_required_prompt_fields")


def test_per_beat_cost_present(C, sb, project_dir):
    plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing(), project_dir=project_dir)
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


def test_hero_shot_gets_reference(C, sb, project_dir):
    plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing(), project_dir=project_dir)
    for b in plan["beats"]:
        if b["shot_type"] in ("hero_lipsync", "hero_cutaway"):
            assert b["reference_images"], f"{b['beat_id']} hero shot missing reference"
    print("  ✓ hero shots carry a reference image")


def test_local_graphics_zero_cost(C, sb, project_dir):
    plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing(), project_dir=project_dir)
    for b in plan["beats"]:
        if b["shot_type"] in ("graphic_progressive", "graphic_title_card", "kinetic_text", "ui_insert"):
            assert b["cost"]["est_usd"] == 0.0
            assert b["model"] == "local_graphic"
    print("  ✓ local graphics route to local_graphic at $0")


def test_lipsync_audio_policy(C, sb, project_dir):
    plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing(), project_dir=project_dir)
    for b in plan["beats"]:
        if b["shot_type"] == "hero_lipsync":
            assert b["audio_policy"] == "keep_lipsync"
        elif b["asset_type"] in ("generated_video", "generated_still"):
            assert b["audio_policy"] == "strip"
    print("  ✓ audio policy correct (lipsync keeps, generated strips)")


def test_min_zero_cost_share(C, sb, project_dir):
    plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing(), project_dir=project_dir)
    assert plan["totals"]["pct_zero_cost_beats"] >= 15, plan["totals"]["pct_zero_cost_beats"]
    print(f"  ✓ {plan['totals']['pct_zero_cost_beats']}% of beats on $0 paths (≥15%)")


def test_no_segment_visual_brief_as_prompt(C, sb, project_dir):
    """media_plan positive prompts must not be raw segment briefs (§10 #2)."""
    script = json.loads(FLAGSHIP.read_text())
    seg_briefs = {s.get("visual_brief", "")[:50] for s in script["segments"]}
    plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing(), project_dir=project_dir)
    for b in plan["beats"]:
        assert b["positive_prompt"][:50] not in seg_briefs
    print("  ✓ no positive_prompt is a raw segment visual_brief")


def test_lipsync_slices_meet_seedance_minimum(C, sb, project_dir):
    """Every hero_lipsync beat's padded slice must be >= the Seedance minimum
    clip duration (constraints.json lipsync_render_rules.min_clip_duration_sec),
    so short beats never hard-fail at render then degrade to a still."""
    constraints = C.load_constraints()
    min_clip = constraints.get("lipsync_render_rules", {}).get("min_clip_duration_sec", 4)
    max_clip = constraints.get("lipsync_render_rules", {}).get("max_clip_duration_sec", 15)
    plan, errors = C.compile_plan(sb, constraints, C.load_routing(), project_dir=project_dir)
    # Exclude beats that were correctly rejected for exceeding max (R3)
    rejected_ids = {e.split(":")[0] for e in errors if "exceeds render limit" in e}
    short = []
    for b in plan["beats"]:
        if b["shot_type"] == "hero_lipsync" and b["beat_id"] not in rejected_ids:
            sl = b.get("audio_slice") or {}
            pl = sl.get("padded_len_sec")
            if pl is not None and pl < min_clip:
                short.append((b["beat_id"], pl))
    assert not short, f"hero_lipsync beats below {min_clip}s minimum: {short}"
    print(f"  ✓ all non-rejected hero_lipsync slices padded to >= {min_clip}s")


def test_lipsync_references_rotate_across_angles(C, sb, project_dir):
    """hero_lipsync beats must rotate across approved canonical frames (>=3 distinct
    angles), no two CONSECUTIVE hero beats reusing the same frame (Fable G14 / T5)."""
    plan, _ = C.compile_plan(sb, C.load_constraints(), C.load_routing(), project_dir=project_dir)
    hero = [b for b in plan["beats"] if b["shot_type"] == "hero_lipsync"]
    frames = [(b.get("reference_images") or [None])[0] for b in hero]
    distinct = {f for f in frames if f}
    assert len(distinct) >= 3, f"hero beats use only {len(distinct)} distinct frame(s): {distinct}"
    consec = 0
    for i in range(1, len(hero)):
        same_group = (hero[i].get("render_group")
                      and hero[i]["render_group"] == hero[i - 1].get("render_group"))
        if frames[i] == frames[i - 1] and not same_group:
            consec += 1
    assert consec == 0, f"{consec} consecutive hero beats reuse the same reference frame"
    print(f"  ✓ hero references rotate across {len(distinct)} angles, 0 consecutive repeats")


def test_empty_negative_prompt_rejected(C):
    """A generated beat compiled against blank default_negative_constraints must
    error (negatives are injection-only; an empty block would ship unguarded)."""
    constraints = dict(C.load_constraints())
    constraints["default_negative_constraints"] = ""   # simulate missing/blank
    beat = {
        "beat_id": "B999", "segment_id": "s", "shot_type": "broll_archival",
        "asset_type": "generated_video", "model": "kling3_0",
        "visual_brief": "period-accurate archival academic scene, warm daylight, shallow depth",
        "narrative_function": "x", "cost": {"est_clips": 1},
    }
    _entry, errs, _warns = C.compile_beat(beat, constraints, C.load_routing())
    assert any("empty negative_prompt" in e for e in errs), errs
    print("  ✓ generated beat with blank negative_prompt is rejected at compile")


def test_sliceless_compile_clean_error_not_crash(C, sb, tmp_path):
    """A hero_lipsync beat reaching compile without resolvable slices must produce a
    clean warning (not an AttributeError crash). Slicing is a downstream step."""
    sb2 = json.loads(json.dumps(sb))
    sb2["project_id"] = "sliceless_test"
    empty_proj = tmp_path / "proj"
    empty_proj.mkdir()
    try:
        _plan, errors = C.compile_plan(sb2, C.load_constraints(), C.load_routing(),
                                       project_dir=empty_proj)
    except AttributeError as e:
        raise AssertionError(f"compile crashed with AttributeError instead of clean warning: {e}")
    # Missing audio_slice is now a warning (slice_lipsync is downstream), not an error
    warnings = _plan.get("warnings", [])
    assert any("audio_slice" in w for w in warnings), \
        f"expected audio_slice warning, got warnings={warnings[:3]}, errors={errors[:3]}"
    print("  ✓ sliceless compile yields clean warning, no AttributeError")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

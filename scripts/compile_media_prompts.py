#!/usr/bin/env python3
"""compile_media_prompts.py — Compile constrained media prompts from storyboard + bibles.

Reads a storyboard and constraints.json to produce a media_prompt_plan.json where
every prompt includes universe/technical constraints. No raw visual_brief.

Usage:
  python3 scripts/compile_media_prompts.py storyboard.json --output prompt_plan.json
  python3 scripts/compile_media_prompts.py storyboard.json --dry-run
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONSTRAINTS_PATH = ROOT / "docs" / "channel_universe" / "constraints.json"


def load_constraints():
    return json.loads(CONSTRAINTS_PATH.read_text()) if CONSTRAINTS_PATH.exists() else {}


def compile_prompt(beat, constraints):
    """Compile one storyboard beat into a constrained media prompt entry."""
    scene = beat.get("scene_type", "B_ROLL_SUPPORTING_VISUAL")
    is_studio = beat.get("location_id", "").startswith("ENV_STUDIO") or beat.get("location_id", "").startswith("ENV_PRIVATE")
    is_aroll = beat.get("a_roll_or_b_roll") == "a_roll"
    james = beat.get("james_presence", "absent")

    # Model selection
    if james in ("present_speaking",) and scene == "A_ROLL_TALKING_HEAD":
        model = constraints.get("model_routing_policy", {}).get("a_roll_lipsync", "seedance_2_0")
        audio_policy = "keep_lipsync"
    elif james != "absent":
        model = constraints.get("model_routing_policy", {}).get("james_present_voiceover", "seedance_2_0")
        audio_policy = "strip"
    else:
        model = constraints.get("model_routing_policy", {}).get("grounded_broll", "wan2_7")
        audio_policy = "strip"

    neg = constraints.get("default_negative_constraints", "")
    extra_forbidden = beat.get("forbidden_elements", [])
    if extra_forbidden:
        neg += ", " + ", ".join(extra_forbidden)

    # Build positive prompt from beat fields
    parts = []
    if beat.get("narration_text"):
        parts.append(f"Scene illustrating: {beat['narration_text'][:100]}")
    parts.append(f"Location: {beat.get('location_id', 'unspecified')}")
    parts.append(f"Lighting: {beat.get('lighting', 'warm desk lamp')}")
    parts.append(f"Camera: {beat.get('movement', 'locked-off medium shot')}")
    parts.append(f"Palette: {beat.get('palette', 'warm neutrals')}")
    if james != "absent":
        parts.append("James Harrington present (60yo British man, silver-grey hair, navy sweater, white Oxford)")
    parts.append("Hyperrealistic, 16:9, 4K")

    entry = {
        "beat_id": beat["beat_id"],
        "scene_type": scene,
        "a_roll_or_b_roll": beat.get("a_roll_or_b_roll", "b_roll"),
        "james_presence": james,
        "location_id": beat.get("location_id"),
        "camera_movement": beat.get("movement", "locked-off medium shot"),
        "lighting": beat.get("lighting", "warm desk lamp"),
        "palette": beat.get("palette", "warm neutrals"),
        "text_policy": beat.get("text_policy", "none"),
        "audio_policy": audio_policy,
        "crop_safety": beat.get("crop_safety", "center_safe"),
        "duration_target_sec": beat.get("duration_target_sec", 8),
        "output_path": f"media/{beat['beat_id']}.mp4",
        "positive_prompt": ". ".join(parts),
        "negative_prompt": neg,
        "model": model,
        "reference_assets": beat.get("reference_assets", []),
        "draft": True,
    }

    if is_studio:
        entry["camera_angle_id"] = beat.get("camera")

    return entry


def compile_plan(storyboard, constraints):
    beats = storyboard.get("beats", [])
    prompts = [compile_prompt(b, constraints) for b in beats]
    return {
        "project_id": storyboard.get("project_id"),
        "source_storyboard": "provided",
        "draft": True,
        "prompts": prompts,
    }


def main():
    ap = argparse.ArgumentParser(description="Compile media prompts from storyboard + constraints.")
    ap.add_argument("storyboard", help="Storyboard JSON path")
    ap.add_argument("--output", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    path = Path(args.storyboard).resolve()
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)

    sb = json.load(open(path))
    constraints = load_constraints()
    plan = compile_plan(sb, constraints)

    if args.dry_run:
        print(f"DRY RUN: {len(plan['prompts'])} prompts compiled")
        for p in plan["prompts"]:
            print(f"  {p['beat_id']:25s} {p['scene_type']:35s} model={p['model']}")
        return

    out_path = Path(args.output) if args.output else (path.parent / f"{sb.get('project_id', 'plan')}_prompt_plan.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(plan, f, indent=2)
    print(f"  prompt plan: {out_path} ({len(plan['prompts'])} prompts)")


if __name__ == "__main__":
    main()

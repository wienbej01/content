#!/usr/bin/env python3
"""storyboard.py — Generate and validate storyboard JSON from a reviewed script.

Produces a structured storyboard with typed beats, scene classifications, and
production constraints derived from the channel universe bibles. No LLM calls —
uses deterministic rule-based defaults for now. Output is a draft storyboard.

Usage:
  python3 scripts/storyboard.py script.json --dry-run
  python3 scripts/storyboard.py script.json --validate-only
  python3 scripts/storyboard.py script.json --output path/to/storyboard.json
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONSTRAINTS_PATH = ROOT / "docs" / "channel_universe" / "constraints.json"

VALID_SCENE_TYPES = [
    "A_ROLL_TALKING_HEAD", "A_ROLL_CHARACTER_PRESENT_VOICEOVER",
    "B_ROLL_SUPPORTING_VISUAL", "B_ROLL_SYMBOLIC_VISUAL",
    "INSERT_HANDS_WRITING", "INSERT_OBJECT_DETAIL",
    "TEXT_OVERLAY_POST_ONLY", "TRANSITION", "TITLE_CARD",
]

VALID_AUDIO_MODES = ("generated_tts", "baked_in", "silent")


def load_constraints():
    if CONSTRAINTS_PATH.exists():
        return json.loads(CONSTRAINTS_PATH.read_text())
    return {}


def validate_script(script):
    errors = []
    if not script.get("project_id"):
        errors.append("missing project_id")
    segs = script.get("segments")
    if not segs or not isinstance(segs, list):
        errors.append("segments must be a non-empty array")
    else:
        for i, seg in enumerate(segs):
            if not seg.get("id"):
                errors.append(f"segments[{i}]: missing id")
            if not seg.get("text") and seg.get("audio_mode") != "silent":
                errors.append(f"segments[{i}]: missing text (required unless audio_mode=silent)")
    return errors


def classify_beat(seg, idx, total, constraints):
    """Deterministic rule-based classification for a script segment."""
    audio_mode = seg.get("audio_mode", "generated_tts")

    # First and last segments default to A-roll talking head for host-led
    if idx == 0 or idx == total - 1:
        scene_type = "A_ROLL_TALKING_HEAD"
        james_presence = "present_speaking"
        a_or_b = "a_roll"
        location = "ENV_STUDIO_LIBRARY"
        camera = "STUDIO_LIBRARY_MEDIUM_DESK_001"
    elif audio_mode == "baked_in":
        scene_type = "A_ROLL_TALKING_HEAD"
        james_presence = "present_speaking"
        a_or_b = "a_roll"
        location = "ENV_STUDIO_LIBRARY"
        camera = "STUDIO_LIBRARY_MEDIUM_DESK_001"
    elif idx % 3 == 0:
        # Every 3rd middle segment is James-present voiceover
        scene_type = "A_ROLL_CHARACTER_PRESENT_VOICEOVER"
        james_presence = "present_silent"
        a_or_b = "a_roll"
        location = "ENV_STUDIO_LIBRARY"
        camera = "STUDIO_LIBRARY_OVER_SHOULDER_001"
    else:
        scene_type = "B_ROLL_SUPPORTING_VISUAL"
        james_presence = "absent"
        a_or_b = "b_roll"
        location = "ENV_PROFESSIONAL_COMMON"
        camera = None

    words = len(seg.get("text", "").split())
    # Estimate 2.4 wps
    dur = max(3.0, round(words / 2.4, 1))

    ref_assets = []
    if james_presence != "absent":
        ref_assets = ["JAMES_FRONT_DESK_001"]

    return {
        "beat_id": f"beat_{seg['id']}",
        "source_script_segment_id": seg["id"],
        "narration_text": seg.get("text", ""),
        "narrative_function": "hook" if idx == 0 else ("cta" if idx == total - 1 else "argument"),
        "scene_type": scene_type,
        "a_roll_or_b_roll": a_or_b,
        "james_presence": james_presence,
        "location_id": location,
        "reference_assets": ref_assets,
        "audio_source": "continuous_narration",
        "audio_continuity_group": "main_narration",
        "duration_target_sec": dur,
        "camera": camera,
        "lighting": "warm desk lamp, soft side-key",
        "palette": "warm neutrals, navy, cream, dark wood",
        "movement": "locked-off medium shot" if a_or_b == "a_roll" else "subtle parallax",
        "props": [],
        "text_policy": "none",
        "crop_safety": "center_safe",
        "forbidden_elements": [],
        "transition_in": "cut",
        "transition_out": "cut",
        "qa_notes": "draft_storyboard — deterministic default, not LLM-reviewed",
    }


def generate_storyboard(script, constraints):
    segs = script["segments"]
    beats = [classify_beat(seg, i, len(segs), constraints) for i, seg in enumerate(segs)]
    total_dur = sum(b["duration_target_sec"] for b in beats)

    return {
        "project_id": script["project_id"],
        "episode_title": script.get("title", "Untitled"),
        "target_audience": "mid-career professionals, founders, executives (30-50)",
        "narrative_promise": f"Structured framework from {script.get('title', 'this episode')}",
        "total_target_duration": round(total_dur, 1),
        "narration_mode": "continuous_voiceover",
        "allow_all_broll": False,
        "draft": True,
        "beats": beats,
    }


def validate_storyboard(storyboard, constraints):
    """Validate a storyboard JSON. Returns (errors, warnings)."""
    errors, warnings = [], []

    if not storyboard.get("project_id"):
        errors.append("missing project_id")
    if not storyboard.get("beats"):
        errors.append("no beats")
        return errors, warnings

    beats = storyboard["beats"]
    for i, b in enumerate(beats):
        prefix = f"beats[{i}]"
        if not b.get("beat_id"):
            errors.append(f"{prefix}: missing beat_id")
        if b.get("scene_type") not in VALID_SCENE_TYPES:
            errors.append(f"{prefix}: invalid scene_type '{b.get('scene_type')}'")
        if not b.get("narration_text") and b.get("scene_type") not in ("TRANSITION", "TITLE_CARD"):
            warnings.append(f"{prefix}: missing narration_text")

    # James-presence check (beat-count)
    excluded = {"TRANSITION", "TITLE_CARD"}
    content_beats = [b for b in beats if b.get("scene_type") not in excluded]
    present = [b for b in content_beats if b.get("james_presence") in ("present_speaking", "present_silent")]

    if not storyboard.get("allow_all_broll", False):
        if len(content_beats) > 0 and len(present) == 0:
            errors.append("BLOCKING: 0% James presence in host-led episode")
        elif len(content_beats) > 0:
            pct = round(100 * len(present) / len(content_beats))
            min_pct = constraints.get("a_roll_rules", {}).get("min_presence_teaser_pct", 40)
            if pct < min_pct:
                warnings.append(f"James presence {pct}% is below minimum {min_pct}% for this episode type")

    # Scene evolution
    min_angles = constraints.get("storyboard_rules", {}).get("min_distinct_angles_or_locations", 3)
    locations = set(b.get("location_id") or b.get("camera") for b in beats if b.get("scene_type") not in excluded)
    if len(locations) < min_angles:
        warnings.append(f"Only {len(locations)} distinct locations/angles (minimum {min_angles})")

    return errors, warnings


def main():
    ap = argparse.ArgumentParser(description="Generate/validate storyboard from script.")
    ap.add_argument("script", help="Path to reviewed script JSON")
    ap.add_argument("--dry-run", action="store_true", help="Print plan, write nothing")
    ap.add_argument("--validate-only", action="store_true", help="Validate script for storyboard readiness")
    ap.add_argument("--output", default=None, help="Output path for storyboard JSON")
    args = ap.parse_args()

    script_path = Path(args.script).resolve()
    if not script_path.exists():
        print(f"ERROR: script not found: {script_path}", file=sys.stderr)
        sys.exit(1)

    with open(script_path) as f:
        script = json.load(f)

    errors = validate_script(script)
    if errors:
        print(f"ERROR: script validation failed:\n  " + "\n  ".join(errors), file=sys.stderr)
        sys.exit(1)

    constraints = load_constraints()

    if args.validate_only:
        print(f"VALID: {len(script['segments'])} segments, ready for storyboard generation")
        return

    storyboard = generate_storyboard(script, constraints)

    # Validate the generated storyboard
    sb_errors, sb_warnings = validate_storyboard(storyboard, constraints)
    for w in sb_warnings:
        print(f"  ⚠ {w}")
    if sb_errors:
        print(f"  ERRORS: " + "; ".join(sb_errors), file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print(f"DRY RUN: would generate {len(storyboard['beats'])} beats")
        for b in storyboard["beats"]:
            print(f"  {b['beat_id']:20s} {b['scene_type']:40s} james={b['james_presence']}")
        print(f"  total_target_duration: {storyboard['total_target_duration']}s")
        return

    out_path = Path(args.output) if args.output else (script_path.parent / f"{script['project_id']}_storyboard.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(storyboard, f, indent=2)
    print(f"  storyboard: {out_path} ({len(storyboard['beats'])} beats, {storyboard['total_target_duration']}s)")


if __name__ == "__main__":
    main()

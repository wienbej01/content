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


def generate_storyboard(script, constraints, optimize=False):
    """Generate storyboard. If optimize=True, runs LLM beat-optimization pass."""
    segs = script["segments"]
    beats = [classify_beat(seg, i, len(segs), constraints) for i, seg in enumerate(segs)]
    total_dur = sum(b["duration_target_sec"] for b in beats)

    storyboard = {
        "project_id": script["project_id"],
        "episode_title": script.get("title", "Untitled"),
        "target_audience": "mid-career professionals, founders, executives (30-50)",
        "narrative_promise": f"Structured framework from {script.get('title', 'this episode')}",
        "total_target_duration": round(total_dur, 1),
        "narration_mode": "continuous_voiceover",
        "allow_all_broll": False,
        "draft": not optimize,
        "beats": beats,
    }

    if optimize:
        storyboard = _llm_optimize_beats(storyboard, script, constraints)
        storyboard["draft"] = False

    return storyboard


def _llm_optimize_beats(storyboard, script, constraints):
    """LLM pass: optimize beat placement for retention while keeping compliance."""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    from llm_call import llm_call

    prompt = f"""You are optimizing a video storyboard for audience retention.

The rule-based generator produced a compliant storyboard, but beat placement is mechanical.
Your job: rearrange scene_types and james_presence values to maximize retention.

RETENTION PRINCIPLES:
- James should appear (present_speaking) at trust moments: hook, key insight reveals, CTA
- B-roll should follow high-energy James moments as a "visual rest" before the next build
- Use scene-type variation: never 3+ identical scene_types in a row
- The first beat MUST be James present_speaking (hook must be personal/direct)
- The final beat SHOULD be James present_speaking (CTA is personal)
- Slow push-in (camera: medium_close) at the most important idea

CONSTRAINTS (hard, cannot violate):
- James presence must be ≥{constraints.get('a_roll_rules', {}).get('min_presence_teaser_pct', 40)}% of content beats
- First beat must have james_presence = present_speaking
- scene_type must be one of: JAMES_SPEAKING, JAMES_PRESENT_VOICEOVER, B_ROLL_SUPPORTING, TRANSITION, TITLE_CARD

Current storyboard beats:
{json.dumps([{{'beat_id': b['beat_id'], 'scene_type': b['scene_type'], 'james_presence': b['james_presence'], 'narration_text': b.get('narration_text','')[:60]}} for b in storyboard['beats']], indent=2)}

Return the SAME beats with optimized scene_type and james_presence values.
Respond ONLY with valid JSON — an array of objects with beat_id, scene_type, james_presence, and a brief "retention_note" explaining why.
"""
    data, raw, profile, model = llm_call(
        task="storyboard_generation", prompt=prompt, expect_json=True)

    if data is None:
        return storyboard  # fallback to rule-based if LLM fails

    # Apply LLM suggestions back to beats (only scene_type + james_presence)
    optimized = data if isinstance(data, list) else data.get("beats", [])
    opt_map = {b["beat_id"]: b for b in optimized if isinstance(b, dict) and "beat_id" in b}

    for beat in storyboard["beats"]:
        if beat["beat_id"] in opt_map:
            opt = opt_map[beat["beat_id"]]
            if opt.get("scene_type") in VALID_SCENE_TYPES:
                beat["scene_type"] = opt["scene_type"]
            if opt.get("james_presence"):
                beat["james_presence"] = opt["james_presence"]
            if opt.get("retention_note"):
                beat["retention_note"] = opt["retention_note"]

    # Re-validate after LLM changes
    errors, warnings = validate_storyboard(storyboard, constraints)
    if errors:
        # LLM broke compliance — revert to original rule-based
        storyboard["draft"] = True
        storyboard["_llm_reverted"] = True
        storyboard["_revert_reason"] = errors

    return storyboard


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
    ap.add_argument("--optimize", action="store_true", help="Run LLM retention-optimization pass")
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

    storyboard = generate_storyboard(script, constraints, optimize=args.optimize)

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

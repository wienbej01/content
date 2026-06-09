#!/usr/bin/env python3
"""review_storyboard.py — Rule-based QA review of a storyboard JSON. No LLM calls.

Usage:
  python3 scripts/review_storyboard.py storyboard.json
  python3 scripts/review_storyboard.py storyboard.json --output-json review.json
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONSTRAINTS_PATH = ROOT / "docs" / "channel_universe" / "constraints.json"


def load_constraints():
    return json.loads(CONSTRAINTS_PATH.read_text()) if CONSTRAINTS_PATH.exists() else {}


def review(storyboard, constraints):
    blocking, warnings, fixes = [], [], []
    beats = storyboard.get("beats", [])
    if not beats:
        blocking.append("No beats in storyboard")
        return blocking, warnings, fixes

    excluded = set(constraints.get("excluded_from_presence_count", ["TRANSITION", "TITLE_CARD"]))
    content_beats = [b for b in beats if b.get("scene_type") not in excluded]
    present = [b for b in content_beats if b.get("james_presence") in ("present_speaking", "present_silent")]

    # Host-led presence check
    if not storyboard.get("allow_all_broll", False):
        if content_beats and len(present) == 0:
            blocking.append("0% James presence in host-led episode")
        elif content_beats:
            pct = round(100 * len(present) / len(content_beats))
            rules = constraints.get("a_roll_rules", {})
            min_pct = rules.get("min_presence_teaser_pct", 40)
            if pct < min_pct:
                warnings.append(f"James presence {pct}% below minimum {min_pct}%")

    # Scene evolution
    min_angles = constraints.get("storyboard_rules", {}).get("min_distinct_angles_or_locations", 3)
    locs = set()
    for b in content_beats:
        locs.add(b.get("location_id") or b.get("camera") or "unknown")
    if len(locs) < min_angles:
        warnings.append(f"Only {len(locs)} distinct locations/angles (min {min_angles})")

    # Per-beat checks
    valid_types = set(constraints.get("allowed_scene_types", []))
    for i, b in enumerate(beats):
        if b.get("scene_type") and valid_types and b["scene_type"] not in valid_types:
            blocking.append(f"beats[{i}]: invalid scene_type '{b['scene_type']}'")
        if not b.get("crop_safety"):
            warnings.append(f"beats[{i}]: missing crop_safety")
        if not b.get("audio_continuity_group") and b.get("scene_type") not in excluded:
            warnings.append(f"beats[{i}]: missing audio_continuity_group")
        if b.get("text_policy") == "post_overlay" and b.get("scene_type") == "B_ROLL_SUPPORTING_VISUAL":
            warnings.append(f"beats[{i}]: text_policy=post_overlay on b-roll — verify intent")

    # All-b-roll check
    a_roll = [b for b in content_beats if b.get("a_roll_or_b_roll") == "a_roll"]
    if not storyboard.get("allow_all_broll") and content_beats and len(a_roll) == 0:
        blocking.append("All-b-roll host-led video — no A-roll beats")

    return blocking, warnings, fixes


def main():
    ap = argparse.ArgumentParser(description="Rule-based storyboard QA review.")
    ap.add_argument("storyboard", help="Path to storyboard JSON")
    ap.add_argument("--output-json", default=None)
    ap.add_argument("--warn-only", action="store_true", help="Exit 0 even on blocking issues")
    args = ap.parse_args()

    path = Path(args.storyboard).resolve()
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)

    sb = json.load(open(path))
    constraints = load_constraints()
    blocking, warnings, fixes = review(sb, constraints)

    result = {
        "task": "storyboard_review",
        "model_profile": "rule_based",
        "status": "fail" if blocking else "pass",
        "score": 1 if blocking else (3 if warnings else 5),
        "blocking_issues": blocking,
        "warnings": warnings,
        "recommended_fixes": fixes,
        "may_proceed": len(blocking) == 0,
    }

    if args.output_json:
        Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output_json, "w") as f:
            json.dump(result, f, indent=2)

    for w in warnings:
        print(f"  ⚠ {w}")
    if blocking:
        for b in blocking:
            print(f"  ✗ BLOCKING: {b}")
        if not args.warn_only:
            sys.exit(1)
    else:
        print(f"  ✓ PASS (score {result['score']}/5, {len(warnings)} warnings)")


if __name__ == "__main__":
    main()

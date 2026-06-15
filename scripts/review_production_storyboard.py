#!/usr/bin/env python3
"""review_production_storyboard.py — PST-05 Production Storyboard Review Gate.

Two-part review:
  1. Deterministic structural validation (Python, always runs, non-overridable)
  2. Optional focused LLM creative review (--llm-review flag, advisory only)

Structural failures ALWAYS block production. Creative notes never block.

Usage:
    python3 scripts/review_production_storyboard.py \
        --production-storyboard production_storyboard.json \
        --creative-storyboard storyboard.json \
        --output review_report.json \
        [--llm-review]
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from production_storyboard import validate_production_storyboard

FRAME_TOLERANCE = 0.042
CONSTRAINTS_PATH = ROOT / "docs" / "channel_universe" / "constraints.json"
MODEL_ROUTING_PATH = ROOT / "configs" / "james" / "model_routing.yaml"

KNOWN_MODELS = {
    "seedance_2_0", "kling3_0", "cinematic_studio_3_0",
    "still_kenburns", "local_graphic",
}


def _load_text_surface_banned_terms():
    """Load banned terms from constraints.json text_surface_policy."""
    if CONSTRAINTS_PATH.exists():
        constraints = json.loads(CONSTRAINTS_PATH.read_text())
        return constraints.get("text_surface_policy", {}).get("banned_terms", [])
    return []


def structural_review(production_sb, creative_sb):
    """Run deterministic structural validation. Returns (errors, warnings)."""
    errors = []
    warnings = []

    # Part A: PST-01 validate_production_storyboard (non-overridable)
    schema_errors = validate_production_storyboard(production_sb)
    errors.extend(schema_errors)

    beats = production_sb.get("beats", [])
    master = production_sb.get("master_audio_duration_sec", 0)
    creative_beats = creative_sb.get("beats", [])

    # Audio coverage completeness
    if beats:
        total_duration = sum(b["audio_duration_sec"] for b in beats)
        if abs(total_duration - master) > FRAME_TOLERANCE:
            errors.append(
                f"AUDIO_COVERAGE: sum of beat durations ({total_duration:.3f}s) != "
                f"master_audio_duration_sec ({master:.3f}s), diff={abs(total_duration - master):.3f}s"
            )

    # Hero lipsync proportion (advisory — creative was already approved at storyboard stage)
    hero_beats = [b for b in beats if b.get("treatment") == "hero_lipsync"]
    if beats:
        hero_ratio = len(hero_beats) / len(beats)
        if hero_ratio > 0.60:
            warnings.append(
                f"HERO_PROPORTION: hero_lipsync is {hero_ratio*100:.1f}% of beats (high — verify creative approval)"
            )
        elif hero_ratio > 0.25:
            warnings.append(
                f"HERO_PROPORTION: hero_lipsync is {hero_ratio*100:.1f}% of beats (recommended ≤25%)"
            )

    # Narration mutation check (group-level: concat split children)
    creative_narrations = {}
    for cb in creative_beats:
        bid = cb.get("beat_id", "")
        if cb.get("narration_text"):
            creative_narrations[bid] = cb["narration_text"]

    # Group production beats by source_beat_id
    source_groups = defaultdict(list)
    for b in beats:
        source_id = b.get("source_beat_id", "")
        if source_id in creative_narrations:
            source_groups[source_id].append(b)

    def _canonical_words(text):
        """Normalize text to word sequence for comparison."""
        return text.split()

    for source_id, group in source_groups.items():
        # Order by split_index (default 0 for non-split beats)
        group.sort(key=lambda b: b.get("split_index", 0))
        concat = " ".join(b.get("narration_text", "") for b in group)
        if _canonical_words(concat) != _canonical_words(creative_narrations[source_id]):
            beat_ids = [b.get("beat_id") for b in group]
            errors.append(
                f"NARRATION_MUTATION: beats {beat_ids} (source {source_id}) "
                f"concatenated narration differs from creative source"
            )

    # Required graphics check (respect required:false, check at source-group level)
    creative_required_graphics = {}
    for cb in creative_beats:
        g = cb.get("graphic")
        if g and g.get("required", True) is not False:
            creative_required_graphics[cb.get("beat_id", "")] = g

    for source_id, graphic in creative_required_graphics.items():
        children = [b for b in beats if b.get("source_beat_id") == source_id]
        if not any(b.get("graphic") or b.get("graphics") for b in children):
            errors.append(
                f"MISSING_GRAPHIC: source {source_id} "
                f"requires graphic from creative storyboard but none of its production beats have it"
            )

    # Text-heavy b-roll check (only for rerouted beats — original broll was approved at creative stage)
    banned_terms = _load_text_surface_banned_terms()
    for b in beats:
        if b.get("reroute") and b.get("visual_brief"):
            brief_lower = b["visual_brief"].lower()
            for term in banned_terms:
                if term.lower() in brief_lower:
                    warnings.append(
                        f"TEXT_SURFACE_BROLL: beat {b.get('beat_id')} has banned term "
                        f"'{term}' in visual_brief (rerouted — may need brief update)"
                    )
                    break

    # Model assignments check
    for b in beats:
        model = b.get("model")
        if model and model not in KNOWN_MODELS:
            errors.append(
                f"INVALID_MODEL: beat {b.get('beat_id')} has unknown model '{model}'"
            )

    return errors, warnings


def creative_review(production_sb):
    """Run LLM creative review. Returns (passed, score, notes).
    This is a stub — actual LLM call would go here."""
    # In production this calls llm_call.py with reviewer prompts
    # For now returns advisory pass
    return True, None, ["LLM creative review not yet implemented"]


def run_review(production_sb, creative_sb, llm_review=False):
    """Run full review and return report dict."""
    errors, warnings = structural_review(production_sb, creative_sb)
    structural_passed = len(errors) == 0

    creative_passed = True
    creative_score = None
    creative_notes = []

    if llm_review:
        creative_passed, creative_score, creative_notes = creative_review(production_sb)

    # Structural failures ALWAYS block. Creative never blocks.
    blocks_production = not structural_passed

    status = "PASS" if not blocks_production else "FAIL"

    return {
        "status": status,
        "structural": {
            "passed": structural_passed,
            "errors": errors,
            "warnings": warnings,
        },
        "creative": {
            "passed": creative_passed,
            "score": creative_score,
            "notes": creative_notes,
        },
        "blocks_production": blocks_production,
    }


def main():
    parser = argparse.ArgumentParser(description="PST-05: Production Storyboard Review Gate")
    parser.add_argument("--production-storyboard", required=True, type=Path,
                        help="Path to production_storyboard.json")
    parser.add_argument("--creative-storyboard", required=True, type=Path,
                        help="Path to creative storyboard JSON")
    parser.add_argument("--output", required=True, type=Path,
                        help="Path to write review_report.json")
    parser.add_argument("--llm-review", action="store_true", default=False,
                        help="Enable optional LLM creative review")
    args = parser.parse_args()

    production_sb = json.loads(args.production_storyboard.read_text())
    creative_sb = json.loads(args.creative_storyboard.read_text())

    report = run_review(production_sb, creative_sb, llm_review=args.llm_review)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))

    if report["blocks_production"]:
        print(f"FAIL — {len(report['structural']['errors'])} structural error(s):", file=sys.stderr)
        for e in report["structural"]["errors"]:
            print(f"  • {e}", file=sys.stderr)
        sys.exit(1)
    else:
        print("PASS — production storyboard review passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()

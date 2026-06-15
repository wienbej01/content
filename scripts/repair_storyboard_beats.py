#!/usr/bin/env python3
"""PST-04 — Targeted storyboard LLM repair for beats that can't be mechanically split.

Takes a production storyboard with beats marked needs_repair=True, sends them
to an LLM for creative repair (choosing a visual treatment that fits model limits),
then validates LLM output against immutable invariants before acceptance.

Usage:
    python3 scripts/repair_storyboard_beats.py \
      --production-storyboard production_storyboard.json \
      --creative-storyboard storyboard.json \
      --beats B001 B008 B009 \
      --output production_storyboard.json \
      [--dry-run]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from production_storyboard import validate_production_storyboard

FRAME_TOLERANCE = 0.042

# Fields the LLM may NOT alter
IMMUTABLE_FIELDS = ("narration_text", "audio_start_sec", "audio_end_sec", "source_beat_id")


def build_repair_prompt(beat: dict, creative_beat: dict | None,
                        prev_beat: dict | None, next_beat: dict | None) -> str:
    """Build the LLM prompt for repairing a single beat."""
    lines = [
        "You are repairing a production storyboard beat that exceeds model duration limits.",
        "Your job: choose a visual treatment that fits within the constraints.",
        "",
        "## IMMUTABLE FIELDS (you MUST preserve these exactly):",
        f"  narration_text: {json.dumps(beat['narration_text'])}",
        f"  audio_start_sec: {beat['audio_start_sec']}",
        f"  audio_end_sec: {beat['audio_end_sec']}",
        f"  source_beat_id: {beat['source_beat_id']}",
        "",
        f"## Beat timing:",
        f"  duration: {beat['audio_duration_sec']}s",
        f"  model_max_duration_sec: {beat.get('model_max_duration_sec', 10.0)}",
        "",
        "## Available treatments:",
        "  - hero_lipsync (model: seedance_2_0, max 10s)",
        "  - broll (model: kling3_0, max 6s per slot)",
        "  - local_graphic (no model limit)",
        "",
        "## Shot-mix constraints:",
        "  - Hero (lipsync + cutaway): 25-40%",
        "  - Specific/archival b-roll: >=25%",
        "  - Graphics/UI: >=10%",
        "",
    ]

    if beat.get("graphics"):
        lines.append("## REQUIRED GRAPHICS (must be preserved in output):")
        lines.append(f"  {json.dumps(beat['graphics'])}")
        lines.append("")

    if creative_beat:
        lines.append("## Creative intent (from creative storyboard):")
        lines.append(f"  shot_type: {creative_beat.get('shot_type', 'unknown')}")
        lines.append(f"  visual_prompt: {creative_beat.get('visual_prompt', 'N/A')}")
        lines.append("")

    if prev_beat:
        lines.append(f"## Previous beat: {prev_beat.get('beat_id')} "
                     f"(treatment: {prev_beat.get('treatment', 'unknown')})")
    if next_beat:
        lines.append(f"## Next beat: {next_beat.get('beat_id')} "
                     f"(treatment: {next_beat.get('treatment', 'unknown')})")

    lines.extend([
        "",
        "## Output format: Return a JSON array of beat objects. Each must have:",
        "  beat_id, source_beat_id, audio_start_sec, audio_end_sec, audio_duration_sec,",
        "  narration_text, treatment, model, model_max_duration_sec, coverage_plan, graphics,",
        "  split_index, split_total",
        "",
        "If you split into multiple beats, ensure their timing is contiguous and covers the full range.",
        "If you cannot split (single long sentence), change treatment to broll or local_graphic.",
    ])
    return "\n".join(lines)


def validate_repair(original_beat: dict, repaired_beats: list[dict]) -> list[str]:
    """Validate LLM repair output against immutable invariants. Returns errors."""
    errors = []
    if not repaired_beats:
        errors.append("REPAIR_FAILED: LLM returned empty result")
        return errors

    orig_start = original_beat["audio_start_sec"]
    orig_end = original_beat["audio_end_sec"]
    orig_narration = original_beat["narration_text"]
    orig_source = original_beat["source_beat_id"]
    orig_graphics = original_beat.get("graphics", [])
    required_graphics = [g for g in orig_graphics if g.get("required", True)]

    # Check immutable fields across all repaired beats
    combined_narration_parts = []
    for rb in repaired_beats:
        # source_beat_id must match
        if rb.get("source_beat_id") != orig_source:
            errors.append(
                f"IMMUTABLE_FIELD: source_beat_id changed from "
                f"{orig_source!r} to {rb.get('source_beat_id')!r}"
            )

        if rb.get("narration_text"):
            combined_narration_parts.append(rb["narration_text"])

        # model limit check
        model_max = rb.get("model_max_duration_sec")
        if model_max and rb.get("audio_duration_sec", 0) > model_max + FRAME_TOLERANCE:
            errors.append(
                f"REPAIR_FAILED: beat {rb.get('beat_id')} audio_duration_sec "
                f"{rb['audio_duration_sec']:.3f} exceeds model_max {model_max}"
            )

    # If single beat, narration must be byte-for-byte identical
    if len(repaired_beats) == 1:
        if repaired_beats[0].get("narration_text") != orig_narration:
            errors.append(
                f"IMMUTABLE_FIELD: narration_text changed"
            )
        if abs(repaired_beats[0].get("audio_start_sec", 0) - orig_start) > FRAME_TOLERANCE:
            errors.append(
                f"IMMUTABLE_FIELD: audio_start_sec changed from "
                f"{orig_start} to {repaired_beats[0].get('audio_start_sec')}"
            )
        if abs(repaired_beats[0].get("audio_end_sec", 0) - orig_end) > FRAME_TOLERANCE:
            errors.append(
                f"IMMUTABLE_FIELD: audio_end_sec changed from "
                f"{orig_end} to {repaired_beats[0].get('audio_end_sec')}"
            )
    else:
        # Multi-beat split: combined narration must equal original
        combined = " ".join(combined_narration_parts)
        if combined != orig_narration:
            errors.append("IMMUTABLE_FIELD: narration_text changed (combined split mismatch)")

        # Audio boundaries: first start must match, last end must match
        if abs(repaired_beats[0].get("audio_start_sec", 0) - orig_start) > FRAME_TOLERANCE:
            errors.append(
                f"IMMUTABLE_FIELD: audio_start_sec changed from "
                f"{orig_start} to {repaired_beats[0].get('audio_start_sec')}"
            )
        if abs(repaired_beats[-1].get("audio_end_sec", 0) - orig_end) > FRAME_TOLERANCE:
            errors.append(
                f"IMMUTABLE_FIELD: audio_end_sec changed from "
                f"{orig_end} to {repaired_beats[-1].get('audio_end_sec')}"
            )

    # Required graphics must survive
    if required_graphics:
        for rb in repaired_beats:
            rb_graphics = rb.get("graphics", [])
            for rg in required_graphics:
                if rg not in rb_graphics:
                    errors.append(
                        f"MISSING_GRAPHIC: required graphic {rg.get('type', 'unknown')} "
                        f"missing from repaired beat {rb.get('beat_id')}"
                    )
                    break  # one error per beat is enough

    return errors


def repair_beats(production_sb: dict, creative_sb: dict, beat_ids: list[str],
                 llm_fn=None, dry_run: bool = False) -> tuple[dict, list[dict]]:
    """Repair specified beats. Returns (updated_storyboard, repair_log).

    llm_fn: callable(prompt) -> list[dict] (repaired beat defs).
             If None, uses scripts/llm_call.py.
    """
    beats = production_sb["beats"]
    creative_by_id = {b["beat_id"]: b for b in creative_sb.get("beats", [])}

    # Index beats
    beat_index = {b["beat_id"]: (i, b) for i, b in enumerate(beats)}
    repair_log = []

    for bid in beat_ids:
        if bid not in beat_index:
            repair_log.append({"beat_id": bid, "status": "NOT_FOUND"})
            continue

        idx, beat = beat_index[bid]
        creative_beat = creative_by_id.get(beat.get("source_beat_id", bid))
        prev_beat = beats[idx - 1] if idx > 0 else None
        next_beat = beats[idx + 1] if idx < len(beats) - 1 else None

        prompt = build_repair_prompt(beat, creative_beat, prev_beat, next_beat)

        if dry_run:
            repair_log.append({
                "beat_id": bid,
                "status": "DRY_RUN",
                "prompt_preview": prompt[:500],
            })
            continue

        # Call LLM
        try:
            repaired = llm_fn(prompt) if llm_fn else _default_llm_call(prompt)
        except Exception as e:
            repair_log.append({"beat_id": bid, "status": "LLM_ERROR", "error": str(e)})
            continue

        # Validate
        errors = validate_repair(beat, repaired)
        if errors:
            repair_log.append({
                "beat_id": bid,
                "status": "REPAIR_FAILED",
                "errors": errors,
            })
            # Mark the beat as failed rather than silently accepting
            beat["repair_status"] = "REPAIR_FAILED"
            beat["repair_errors"] = errors
            continue

        # Replace beat(s) in production storyboard
        for rb in repaired:
            rb.pop("needs_repair", None)

        production_sb["beats"] = beats[:idx] + repaired + beats[idx + 1:]
        beats = production_sb["beats"]
        # Rebuild index after replacement
        beat_index = {b["beat_id"]: (i, b) for i, b in enumerate(beats)}
        production_sb["total_beats"] = len(beats)

        repair_log.append({
            "beat_id": bid,
            "status": "REPAIRED",
            "replacement_count": len(repaired),
        })

    return production_sb, repair_log


def _default_llm_call(prompt: str) -> list[dict]:
    """Call LLM via llm_call.py for real repair."""
    from llm_call import llm_call
    data, _raw, _prof, _model = llm_call(
        task="storyboard_repair",
        prompt=prompt,
        model_profile="sonnet_creative",
        expect_json=True,
    )
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "beats" in data:
        return data["beats"]
    raise RuntimeError(f"Unexpected LLM response format: {type(data)}")


def main():
    parser = argparse.ArgumentParser(description="PST-04: Targeted storyboard LLM repair")
    parser.add_argument("--production-storyboard", type=Path, required=True)
    parser.add_argument("--creative-storyboard", type=Path, required=True)
    parser.add_argument("--beats", nargs="+", required=True, help="Beat IDs to repair")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    for p in (args.production_storyboard, args.creative_storyboard):
        if not p.exists():
            print(f"ERROR: File not found: {p}", file=sys.stderr)
            sys.exit(1)

    production_sb = json.loads(args.production_storyboard.read_text())
    creative_sb = json.loads(args.creative_storyboard.read_text())

    result, log = repair_beats(production_sb, creative_sb, args.beats, dry_run=args.dry_run)

    # Print summary
    for entry in log:
        status = entry["status"]
        bid = entry["beat_id"]
        if status == "REPAIRED":
            print(f"  ✓ {bid}: repaired ({entry['replacement_count']} beats)")
        elif status == "DRY_RUN":
            print(f"  ○ {bid}: [dry-run] prompt built ({len(entry['prompt_preview'])} chars preview)")
        else:
            print(f"  ✗ {bid}: {status}", file=sys.stderr)
            if "errors" in entry:
                for e in entry["errors"]:
                    print(f"      {e}", file=sys.stderr)

    # Check for failed repairs
    has_failures = any(entry["status"] == "REPAIR_FAILED" for entry in log)
    has_malformed = any(entry["status"] == "MALFORMED" for entry in log)

    if not args.dry_run:
        # Validate final storyboard
        errors = validate_production_storyboard(result)
        still_needs_repair = [b for b in result.get("beats", []) if b.get("needs_repair")]
        is_invalid = bool(errors) or has_failures or has_malformed or bool(still_needs_repair)

        if errors:
            print(f"\nERROR: Final storyboard has {len(errors)} validation errors:",
                  file=sys.stderr)
            for e in errors:
                print(f"  • {e}", file=sys.stderr)
        if still_needs_repair:
            print(f"\nERROR: {len(still_needs_repair)} beats still need repair", file=sys.stderr)

        # Don't overwrite valid existing file with invalid output
        if is_invalid and args.output.exists():
            diag_path = args.output.with_suffix(".repair_failed.json")
            diag_path.write_text(json.dumps(result, indent=2))
            print(f"\n  ⚠ Invalid repair output written to: {diag_path}", file=sys.stderr)
            sys.exit(1)

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2))
        print(f"\n  Output: {args.output}")
        sys.exit(1 if is_invalid else 0)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2))
        print(f"\n  Output: {args.output}")
        sys.exit(0)


if __name__ == "__main__":
    main()

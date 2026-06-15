#!/usr/bin/env python3
"""Production storyboard validator.

Validates a production storyboard JSON against structural invariants
that guarantee contiguous timeline, model-legal durations, and full
visual coverage for every beat.

Usage:
    python3 scripts/production_storyboard.py validate <production_storyboard.json>
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

FRAME_TOLERANCE = 0.042  # one frame at 24fps
DURATION_TOLERANCE = 0.001

LEGAL_ASSET_TYPES = {"generated_video", "generated_still", "local_graphic", "archive_clip"}
LEGAL_MODELS = {"seedance_2_0", "kling3_0", "local_graphic"}
LEGAL_AUDIO_POLICIES = {"keep_lipsync", "strip", "post_overlay"}


def validate_coverage_geometry(beat) -> list[str]:
    """Validate coverage slot boundary geometry for a beat.

    Checks ordered continuity (no gaps/overlaps), alignment with beat
    boundaries, internal duration consistency, unique IDs, and legal values.
    """
    errors = []
    bid = beat.get("beat_id", "unknown")
    coverage = beat.get("coverage_plan")
    if not coverage:
        return errors

    beat_start = beat["audio_start_sec"]
    beat_end = beat["audio_end_sec"]

    # Sort by required_start_sec
    slots = sorted(coverage, key=lambda s: s.get("required_start_sec", 0))

    # Check unique slot IDs
    seen_ids = set()
    for slot in slots:
        sid = slot.get("slot_id") or slot.get("coverage_slot")
        if sid:
            if sid in seen_ids:
                errors.append(f"Beat {bid}: duplicate slot_id '{sid}'")
            seen_ids.add(sid)

    for i, slot in enumerate(slots):
        s_start = slot.get("required_start_sec", 0)
        s_end = slot.get("required_end_sec", 0)
        s_dur = slot.get("required_duration_sec", 0)

        # Reversed boundaries
        if s_end < s_start:
            errors.append(
                f"Beat {bid}: slot {i} has reversed boundaries "
                f"(start={s_start:.3f} > end={s_end:.3f})"
            )
            continue

        # Internal duration consistency
        if abs(s_dur - (s_end - s_start)) > DURATION_TOLERANCE:
            errors.append(
                f"Beat {bid}: slot {i} required_duration_sec {s_dur:.3f} != "
                f"end-start {s_end - s_start:.3f}"
            )

        # Visual asset_type required
        asset_type = slot.get("asset_type")
        if not asset_type:
            errors.append(f"Beat {bid}: slot {i} missing visual asset_type")
        elif asset_type not in LEGAL_ASSET_TYPES:
            errors.append(f"Beat {bid}: slot {i} illegal asset_type '{asset_type}'")

        # Legal model (if present)
        model = slot.get("model")
        if model and model not in LEGAL_MODELS:
            errors.append(f"Beat {bid}: slot {i} illegal model '{model}'")

        # Legal audio_policy (if present)
        audio_policy = slot.get("audio_policy")
        if audio_policy and audio_policy not in LEGAL_AUDIO_POLICIES:
            errors.append(f"Beat {bid}: slot {i} illegal audio_policy '{audio_policy}'")

    # First slot must start at beat start
    if abs(slots[0].get("required_start_sec", 0) - beat_start) > FRAME_TOLERANCE:
        errors.append(
            f"Beat {bid}: first slot starts at {slots[0]['required_start_sec']:.3f}s, "
            f"beat starts at {beat_start:.3f}s"
        )

    # Last slot must end at beat end
    if abs(slots[-1].get("required_end_sec", 0) - beat_end) > FRAME_TOLERANCE:
        errors.append(
            f"Beat {bid}: last slot ends at {slots[-1]['required_end_sec']:.3f}s, "
            f"beat ends at {beat_end:.3f}s"
        )

    # Consecutive slot continuity (no gaps, no overlaps)
    for i in range(len(slots) - 1):
        end_i = slots[i].get("required_end_sec", 0)
        start_next = slots[i + 1].get("required_start_sec", 0)
        diff = start_next - end_i
        if diff > FRAME_TOLERANCE:
            errors.append(
                f"Beat {bid}: gap of {diff:.3f}s between slot {i} and slot {i+1}"
            )
        elif diff < -FRAME_TOLERANCE:
            errors.append(
                f"Beat {bid}: overlap of {abs(diff):.3f}s between slot {i} and slot {i+1}"
            )

    return errors


def validate_production_storyboard(storyboard: dict) -> list[str]:
    """Returns list of error strings. Empty = valid."""
    errors = []
    beats = storyboard.get("beats", [])
    master = storyboard.get("master_audio_duration_sec", 0)

    if not beats:
        errors.append("No beats found")
        return errors

    # Invariant 3: timeline start
    if beats[0]["audio_start_sec"] > FRAME_TOLERANCE:
        errors.append(
            f"Timeline start: first beat starts at {beats[0]['audio_start_sec']:.3f}s, expected 0.0"
        )

    # Invariant 4: timeline end
    if abs(beats[-1]["audio_end_sec"] - master) > FRAME_TOLERANCE:
        errors.append(
            f"Timeline end: last beat ends at {beats[-1]['audio_end_sec']:.3f}s, "
            f"master_audio_duration_sec is {master:.3f}s"
        )

    # Per-beat checks
    for i, beat in enumerate(beats):
        bid = beat.get("beat_id", f"index_{i}")

        # Invariant: compiler-required fields
        if not beat.get("shot_type"):
            errors.append(f"Beat {bid}: missing shot_type (required by compiler)")
        if not beat.get("segment_id"):
            errors.append(f"Beat {bid}: missing segment_id (required by compiler)")

        # Invariant 5: duration mismatch
        computed = beat["audio_end_sec"] - beat["audio_start_sec"]
        if abs(computed - beat["audio_duration_sec"]) > DURATION_TOLERANCE:
            errors.append(
                f"Beat {bid}: audio_duration_sec {beat['audio_duration_sec']:.3f} != "
                f"end-start {computed:.3f}"
            )

        # Invariant 6: missing provenance
        if not beat.get("source_beat_id"):
            errors.append(f"Beat {bid}: missing source_beat_id")

        # Invariant 7: missing coverage
        coverage = beat.get("coverage_plan")
        if not coverage:
            errors.append(f"Beat {bid}: empty or missing coverage_plan")

        # Invariant 8: model limit exceeded
        model_max = beat.get("model_max_duration_sec")
        if model_max is not None:
            if beat["audio_duration_sec"] > model_max + FRAME_TOLERANCE:
                errors.append(
                    f"Beat {bid}: audio_duration_sec {beat['audio_duration_sec']:.3f} "
                    f"exceeds model_max_duration_sec {model_max}"
                )

        # Invariant 9: coverage geometry (boundary continuity)
        if coverage:
            errors.extend(validate_coverage_geometry(beat))

        # Invariant 10: narration text with zero/negative duration
        if beat.get("narration_text") and beat["audio_duration_sec"] <= 0:
            errors.append(
                f"Beat {bid}: has narration_text but audio_duration_sec is "
                f"{beat['audio_duration_sec']:.3f}"
            )

        # Invariants 1 & 2: timeline continuity (gap/overlap with next beat)
        if i < len(beats) - 1:
            gap = beats[i + 1]["audio_start_sec"] - beat["audio_end_sec"]
            if gap > FRAME_TOLERANCE:
                errors.append(
                    f"Timeline gap between {bid} and {beats[i+1].get('beat_id', f'index_{i+1}')}: "
                    f"{gap:.3f}s"
                )
            elif gap < -DURATION_TOLERANCE:
                errors.append(
                    f"Timeline overlap between {bid} and {beats[i+1].get('beat_id', f'index_{i+1}')}: "
                    f"{abs(gap):.3f}s"
                )

    # Invariant 11: split integrity
    splits = defaultdict(list)
    for beat in beats:
        if beat.get("split_total", 1) > 1:
            splits[beat["source_beat_id"]].append(beat.get("split_index", 0))

    for source_id, indices in splits.items():
        expected_total = None
        for beat in beats:
            if beat.get("source_beat_id") == source_id and beat.get("split_total", 1) > 1:
                expected_total = beat["split_total"]
                break
        if expected_total:
            expected = list(range(expected_total))
            if sorted(indices) != expected:
                errors.append(
                    f"Split integrity for {source_id}: expected indices {expected}, "
                    f"got {sorted(indices)}"
                )

    return errors


def main():
    parser = argparse.ArgumentParser(description="Production storyboard validator")
    sub = parser.add_subparsers(dest="command")
    val = sub.add_parser("validate", help="Validate a production storyboard JSON")
    val.add_argument("file", type=Path, help="Path to production_storyboard.json")
    args = parser.parse_args()

    if args.command != "validate":
        parser.print_help()
        sys.exit(1)

    data = json.loads(args.file.read_text())
    errors = validate_production_storyboard(data)

    if errors:
        print(f"FAILED — {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  • {e}", file=sys.stderr)
        sys.exit(1)
    else:
        print("PASS — production storyboard is valid.")
        sys.exit(0)


if __name__ == "__main__":
    main()

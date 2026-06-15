#!/usr/bin/env python3
"""Post-TTS reconciliation engine.

Reconciles a creative storyboard with exact beat timing from TTS,
splitting over-limit beats at sentence boundaries and generating
coverage plans for all beats.

Usage:
    python3 scripts/reconcile_production_storyboard.py \
      --storyboard storyboard.json \
      --timing-map narration/beat_timing_map.json \
      --output production_storyboard.json \
      [--audio narration/continuous.mp3] \
      [--dry-run]
"""
import argparse
import hashlib
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from artifact_fingerprint import write_fingerprint
from audio_alignment import find_legal_split_points
from production_storyboard import validate_production_storyboard

CONSTRAINTS_PATH = ROOT / "docs" / "channel_universe" / "constraints.json"
FRAME_TOLERANCE = 0.042
BROLL_SLOT_MAX = 6.0


def _load_constraints():
    """Load lipsync render rules from constraints.json."""
    data = json.loads(CONSTRAINTS_PATH.read_text())
    rules = data.get("lipsync_render_rules", {})
    reroute = data.get("reroute_policy", {})
    return {
        "max_clip_sec": rules.get("max_clip_duration_sec", 15.0),
        "min_clip_sec": rules.get("min_clip_duration_sec", 4.0),
        "reroute_target": reroute.get("unsplittable_hero_target", "hero_cutaway"),
        "broll_slot_max": reroute.get("broll_slot_max_sec", BROLL_SLOT_MAX),
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _split_sentences(text: str) -> list[str]:
    """Split text at sentence boundaries (.!? followed by space)."""
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p for p in parts if p.strip()]


def _word_count(text: str) -> int:
    return len(text.split())


def _word_proportional_times(sentences: list[str], start: float, end: float) -> list[tuple[float, float]]:
    """Assign start/end times proportional to word count. ADVISORY ONLY — not authoritative."""
    total_words = sum(_word_count(s) for s in sentences)
    if total_words == 0:
        return [(start, end)]
    duration = end - start
    times = []
    cursor = start
    for s in sentences:
        frac = _word_count(s) / total_words
        seg_dur = duration * frac
        times.append((cursor, cursor + seg_dur))
        cursor += seg_dur
    # Snap last end to actual end
    if times:
        times[-1] = (times[-1][0], end)
    return times


def _select_split_points(split_points, beat_start, beat_end, max_clip):
    """Select minimum split points that produce all sub-intervals <= max_clip.

    Returns list of chosen points or None if impossible.
    """
    if not split_points:
        return None

    # Greedy: pick earliest split point that keeps current interval <= max_clip
    sorted_pts = sorted(split_points)
    chosen = []
    cursor = beat_start

    while beat_end - cursor > max_clip + FRAME_TOLERANCE:
        # Find candidates: points in (cursor, beat_end) that make interval <= max_clip
        candidates = [p for p in sorted_pts if cursor < p <= cursor + max_clip]
        if not candidates:
            return None
        # Pick the latest valid candidate (maximise interval usage)
        pick = candidates[-1]
        chosen.append(pick)
        cursor = pick

    return chosen if chosen else None


def _assign_sentences_to_intervals(sentences, advisory_times, boundaries):
    """Assign sentences to measured intervals based on advisory midpoint proximity.

    boundaries: [start, split1, split2, ..., end]
    Returns list of dicts with {sentences, start, end}.
    """
    n_intervals = len(boundaries) - 1
    groups = [{"sentences": [], "start": boundaries[i], "end": boundaries[i + 1]}
              for i in range(n_intervals)]

    for sent, (adv_start, adv_end) in zip(sentences, advisory_times):
        mid = (adv_start + adv_end) / 2
        # Find which interval this midpoint falls into
        assigned = n_intervals - 1  # default to last
        for i in range(n_intervals):
            if mid <= boundaries[i + 1]:
                assigned = i
                break
        groups[assigned]["sentences"].append(sent)

    # Ensure no empty groups — redistribute from adjacent if needed
    for i in range(n_intervals):
        if not groups[i]["sentences"] and i + 1 < n_intervals and len(groups[i + 1]["sentences"]) > 1:
            groups[i]["sentences"].append(groups[i + 1]["sentences"].pop(0))

    return groups


def reroute_unsplittable_hero(beat, max_clip_sec, broll_slot_max=6.0, target_treatment="hero_cutaway"):
    """For an over-limit hero beat that can't be split:
    transform to continuous-voiceover b-roll coverage.
    Narration is preserved (continuous VO over the whole interval).
    Visual becomes a sequence of b-roll/cutaway slots each <= broll_slot_max.
    Returns the rerouted beat (treatment changed, coverage_plan = multiple slots).
    """
    beat_start = beat["audio_start_sec"]
    beat_end = beat["audio_end_sec"]
    duration = beat["audio_duration_sec"]

    # Generate coverage slots
    n_slots = math.ceil(duration / broll_slot_max)
    slot_dur = duration / n_slots
    coverage = []
    cursor = beat_start
    for i in range(n_slots):
        slot_end = cursor + slot_dur if i < n_slots - 1 else beat_end
        r_start = round(cursor, 3)
        r_end = round(slot_end, 3)
        coverage.append({
            "slot_id": f"{beat['beat_id']}-s{i}",
            "asset_role": "primary" if i == 0 else f"continuation_{i}",
            "asset_type": "generated_video",
            "required_start_sec": r_start,
            "required_end_sec": r_end,
            "required_duration_sec": round(r_end - r_start, 3),
        })
        cursor = slot_end

    from_treatment = beat.get("treatment", "hero_lipsync")
    beat["treatment"] = target_treatment
    beat["shot_type"] = target_treatment
    beat["audio_policy"] = "strip"
    beat["lipsync_required"] = False
    beat["needs_repair"] = False
    beat["model_max_duration_sec"] = None
    beat["coverage_plan"] = coverage
    beat["reroute"] = {
        "from_treatment": from_treatment,
        "to_treatment": target_treatment,
        "reason": "unsplittable single-sentence over model limit",
    }
    return beat


def _make_coverage_plan(beat_start: float, beat_end: float, duration: float,
                        treatment: str, model: str, max_clip_sec: float) -> list[dict]:
    """Generate coverage plan entries for a beat."""
    is_lipsync = treatment in ("hero_lipsync", "keep_lipsync")
    if is_lipsync:
        return [{
            "asset_role": "primary",
            "asset_type": "generated_video",
            "required_start_sec": beat_start,
            "required_end_sec": beat_end,
            "required_duration_sec": round(duration, 3),
        }]

    if treatment == "local_graphic":
        return [{
            "asset_role": "primary",
            "asset_type": "local_graphic",
            "required_start_sec": beat_start,
            "required_end_sec": beat_end,
            "required_duration_sec": round(duration, 3),
        }]

    # broll / generated_video — split into slots if > BROLL_SLOT_MAX
    if duration <= BROLL_SLOT_MAX:
        return [{
            "asset_role": "primary",
            "asset_type": "generated_video",
            "required_start_sec": beat_start,
            "required_end_sec": beat_end,
            "required_duration_sec": round(duration, 3),
        }]

    slots = []
    n_slots = math.ceil(duration / BROLL_SLOT_MAX)
    slot_dur = duration / n_slots
    cursor = beat_start
    for i in range(n_slots):
        slot_end = cursor + slot_dur if i < n_slots - 1 else beat_end
        r_start = round(cursor, 3)
        r_end = round(slot_end, 3)
        slots.append({
            "asset_role": "primary" if i == 0 else f"continuation_{i}",
            "asset_type": "generated_video",
            "required_start_sec": r_start,
            "required_end_sec": r_end,
            "required_duration_sec": round(r_end - r_start, 3),
        })
        cursor = slot_end
    return slots


def _get_treatment(beat: dict) -> str:
    """Determine treatment from creative storyboard beat."""
    shot_type = beat.get("shot_type", "")
    if beat.get("lipsync_required") or shot_type == "hero_lipsync":
        return "hero_lipsync"
    if "broll" in shot_type or shot_type in ("broll_environment", "broll_tactical"):
        return "broll"
    return beat.get("shot_type", "broll")


# Fields from the creative storyboard that must be carried through to production beats.
_CREATIVE_CARRY_FIELDS = (
    "shot_type", "segment_id", "visual_brief", "subject", "action", "camera",
    "setting", "continuity_anchor", "asset_type", "model_tier", "lipsync_required",
    "reference_required", "reference_images", "prompt_class", "audio_mode",
    "crop_safety", "shots_per_beat", "visual_function", "narrative_function",
    "era", "cost", "reuse", "fallback", "justification", "music_duck",
    "duration_target_sec", "narration_word_span", "est_duration_sec",
)


def _normalize_graphics(beat: dict) -> list[dict]:
    """Convert creative beat graphic (singular dict) to canonical graphics list."""
    graphics_list = beat.get("graphics")
    if isinstance(graphics_list, list):
        return graphics_list
    graphic = beat.get("graphic")
    if graphic and isinstance(graphic, dict):
        return [graphic]
    return []


def _base_from_creative(beat: dict) -> dict:
    """Build a production beat base by copying creative carry fields."""
    base = {}
    for field in _CREATIVE_CARRY_FIELDS:
        if field in beat:
            base[field] = beat[field]
    return base


def reconcile(storyboard: dict, timing_map: dict, constraints: dict,
              audio_path: str = None) -> tuple[dict, list[str]]:
    """
    Returns (production_storyboard, issues).
    issues is a list of strings describing problems that need LLM repair.
    """
    issues = []
    max_clip = constraints["max_clip_sec"]
    min_clip = constraints["min_clip_sec"]

    # Index timing by beat_id
    timing_by_id = {b["beat_id"]: b for b in timing_map.get("beats", [])}
    master_duration = timing_map.get("total_duration", 0)

    production_beats = []

    for beat in storyboard.get("beats", []):
        bid = beat["beat_id"]

        # Step 1: Match timing
        if bid not in timing_by_id:
            issues.append(f"ERROR: Beat {bid} has no timing entry — cannot reconcile")
            continue

        timing = timing_by_id[bid]
        audio_start = timing["start"]
        audio_end = timing["end"]
        audio_duration = timing["duration"]
        treatment = _get_treatment(beat)
        model = beat.get("model", "kling3_0")

        # Determine model max for this beat
        is_lipsync = treatment in ("hero_lipsync", "keep_lipsync")
        model_max = max_clip if is_lipsync else None

        # Step 2: Check against model limits
        needs_split = is_lipsync and audio_duration > max_clip + FRAME_TOLERANCE

        # Extract canonical graphics list
        graphics = _normalize_graphics(beat)

        if needs_split:
            # Step 3: Split at sentence boundaries
            narration = beat.get("narration_text", "")
            sentences = _split_sentences(narration)

            if len(sentences) < 2:
                # Single sentence — cannot split; reroute to b-roll coverage
                reroute_target = constraints.get("reroute_target", "hero_cutaway")
                slot_max = constraints.get("broll_slot_max", BROLL_SLOT_MAX)
                prod_beat = _base_from_creative(beat)
                prod_beat.update({
                    "beat_id": bid,
                    "source_beat_id": bid,
                    "audio_start_sec": audio_start,
                    "audio_end_sec": audio_end,
                    "audio_duration_sec": round(audio_duration, 3),
                    "narration_text": narration,
                    "treatment": treatment,
                    "model": model,
                    "model_max_duration_sec": model_max,
                    "needs_repair": True,
                    "coverage_plan": _make_coverage_plan(
                        audio_start, audio_end, audio_duration, treatment, model, max_clip
                    ),
                })
                if graphics:
                    prod_beat["graphics"] = graphics
                reroute_unsplittable_hero(prod_beat, max_clip, slot_max, reroute_target)
                production_beats.append(prod_beat)
                continue

            # --- Measured silence boundary split (PTC-02) ---
            # Word-proportional is advisory only; actual split uses silence detection
            advisory_times = _word_proportional_times(sentences, audio_start, audio_end)

            if audio_path is None:
                # No audio → cannot measure boundaries → mark needs_repair
                issues.append(
                    f"NEEDS_REPAIR: Beat {bid} ({audio_duration:.3f}s) needs split but "
                    f"no --audio provided for measured boundaries"
                )
                prod_beat = _base_from_creative(beat)
                prod_beat.update({
                    "beat_id": bid,
                    "source_beat_id": bid,
                    "audio_start_sec": audio_start,
                    "audio_end_sec": audio_end,
                    "audio_duration_sec": round(audio_duration, 3),
                    "narration_text": narration,
                    "treatment": treatment,
                    "model": model,
                    "model_max_duration_sec": model_max,
                    "needs_repair": True,
                    "estimated_split_advisory": [
                        {"start": round(s, 3), "end": round(e, 3)} for s, e in advisory_times
                    ],
                    "coverage_plan": _make_coverage_plan(
                        audio_start, audio_end, audio_duration, treatment, model, max_clip
                    ),
                })
                if graphics:
                    prod_beat["graphics"] = graphics
                production_beats.append(prod_beat)
                continue

            # Detect measured silence split points within beat
            alignment = find_legal_split_points(
                audio_path, audio_start, audio_end,
                min_silence_dur=0.20, noise_db=-35
            )
            split_points = alignment["split_points"]

            # Select split points that produce all sub-intervals <= max_clip
            chosen = _select_split_points(split_points, audio_start, audio_end, max_clip)

            if chosen is None:
                # No measured boundaries produce legal sub-intervals — reroute
                reroute_target = constraints.get("reroute_target", "hero_cutaway")
                slot_max = constraints.get("broll_slot_max", BROLL_SLOT_MAX)
                prod_beat = _base_from_creative(beat)
                prod_beat.update({
                    "beat_id": bid,
                    "source_beat_id": bid,
                    "audio_start_sec": audio_start,
                    "audio_end_sec": audio_end,
                    "audio_duration_sec": round(audio_duration, 3),
                    "narration_text": narration,
                    "treatment": treatment,
                    "model": model,
                    "model_max_duration_sec": model_max,
                    "needs_repair": True,
                    "coverage_plan": _make_coverage_plan(
                        audio_start, audio_end, audio_duration, treatment, model, max_clip
                    ),
                })
                if graphics:
                    prod_beat["graphics"] = graphics
                reroute_unsplittable_hero(prod_beat, max_clip, slot_max, reroute_target)
                production_beats.append(prod_beat)
                continue

            # Build sub-intervals from chosen split points
            boundaries = [audio_start] + chosen + [audio_end]
            # Map narration sentences to sub-intervals by nearest split point
            sentence_groups = _assign_sentences_to_intervals(sentences, advisory_times, boundaries)

            timing_provenance = {
                "method": alignment["method"],
                "confidence": alignment["confidence"],
                "audio_sha256": alignment["audio_sha256"],
                "boundary_evidence": chosen,
            }

            # Produce child beats
            suffixes = "abcdefghijklmnopqrstuvwxyz"
            split_total = len(sentence_groups)
            for idx, group in enumerate(sentence_groups):
                child_narration = " ".join(group["sentences"])
                child_start = group["start"]
                child_end = group["end"]
                child_dur = child_end - child_start

                child_beat = _base_from_creative(beat)
                child_beat.update({
                    "beat_id": f"{bid}{suffixes[idx]}",
                    "source_beat_id": bid,
                    "split_index": idx,
                    "split_total": split_total,
                    "audio_start_sec": round(child_start, 3),
                    "audio_end_sec": round(child_end, 3),
                    "audio_duration_sec": round(child_dur, 3),
                    "narration_text": child_narration,
                    "treatment": treatment,
                    "model": model,
                    "model_max_duration_sec": model_max,
                    "timing_provenance": timing_provenance,
                    "coverage_plan": _make_coverage_plan(
                        round(child_start, 3), round(child_end, 3),
                        child_dur, treatment, model, max_clip
                    ),
                })
                if graphics:
                    child_beat["graphics"] = graphics
                production_beats.append(child_beat)
        else:
            # Step 4: Attach timing, generate coverage
            narration = beat.get("narration_text", "")
            prod_beat = _base_from_creative(beat)
            prod_beat.update({
                "beat_id": bid,
                "source_beat_id": bid,
                "audio_start_sec": audio_start,
                "audio_end_sec": audio_end,
                "audio_duration_sec": round(audio_duration, 3),
                "narration_text": narration,
                "treatment": treatment,
                "model": model,
                "model_max_duration_sec": model_max,
                "coverage_plan": _make_coverage_plan(
                    audio_start, audio_end, audio_duration, treatment, model, max_clip
                ),
            })
            graphics = _normalize_graphics(beat)
            if graphics:
                prod_beat["graphics"] = graphics
            # Flag long broll as a note
            if not is_lipsync and audio_duration > BROLL_SLOT_MAX:
                prod_beat["note"] = (
                    f"Long broll ({audio_duration:.3f}s) — "
                    f"coverage_plan has {len(prod_beat['coverage_plan'])} slots"
                )
            production_beats.append(prod_beat)

    # Build production storyboard
    production_storyboard = {
        "schema_version": "1.0",
        "project_id": storyboard.get("project_id", "unknown"),
        "creative_storyboard_sha256": "dry_run_no_hash",
        "timing_map_sha256": "dry_run_no_hash",
        "master_audio_duration_sec": master_duration,
        "total_beats": len(production_beats),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "beats": production_beats,
    }

    # Step 5: Validate
    errors = validate_production_storyboard(production_storyboard)
    if errors:
        for e in errors:
            issues.append(f"VALIDATION: {e}")

    return production_storyboard, issues


def _group_sentences(sentences: list[str], times: list[tuple[float, float]],
                     max_dur: float, min_dur: float) -> list[dict] | None:
    """Group sentences into chunks each <= max_dur using greedy approach."""
    groups = []
    current_sentences = []
    current_start = times[0][0]
    current_end = times[0][0]

    for i, (sent, (t_start, t_end)) in enumerate(zip(sentences, times)):
        seg_dur = t_end - current_start
        if seg_dur <= max_dur:
            current_sentences.append(sent)
            current_end = t_end
        else:
            # Close current group if non-empty
            if current_sentences:
                groups.append({
                    "sentences": current_sentences,
                    "start": current_start,
                    "end": current_end,
                })
                current_sentences = [sent]
                current_start = current_end
                current_end = t_end
            else:
                # Single sentence exceeds max — fail
                return None

    # Close final group
    if current_sentences:
        groups.append({
            "sentences": current_sentences,
            "start": current_start,
            "end": current_end,
        })

    # Verify all groups are <= max_dur
    for g in groups:
        if g["end"] - g["start"] > max_dur + FRAME_TOLERANCE:
            return None

    return groups if groups else None


def reconcile_with_hashes(storyboard_path: Path, timing_map_path: Path,
                          storyboard: dict, timing_map: dict, constraints: dict,
                          audio_path: str = None) -> tuple[dict, list[str]]:
    """Reconcile and attach real SHA-256 hashes."""
    result, issues = reconcile(storyboard, timing_map, constraints, audio_path)
    result["creative_storyboard_sha256"] = _sha256(storyboard_path)
    result["timing_map_sha256"] = _sha256(timing_map_path)
    return result, issues


def main():
    parser = argparse.ArgumentParser(description="Post-TTS reconciliation engine")
    parser.add_argument("--storyboard", type=Path, required=True,
                        help="Path to creative storyboard JSON")
    parser.add_argument("--timing-map", type=Path, required=True,
                        help="Path to beat_timing_map.json from TTS")
    parser.add_argument("--output", type=Path, required=True,
                        help="Output path for production_storyboard.json")
    parser.add_argument("--audio", type=Path, default=None,
                        help="Optional continuous narration audio for silence detection")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate and preview without writing final output")
    args = parser.parse_args()

    if not args.storyboard.exists():
        print(f"ERROR: Storyboard not found: {args.storyboard}", file=sys.stderr)
        sys.exit(1)
    if not args.timing_map.exists():
        print(f"ERROR: Timing map not found: {args.timing_map}", file=sys.stderr)
        sys.exit(1)

    storyboard = json.loads(args.storyboard.read_text())
    timing_map = json.loads(args.timing_map.read_text())
    constraints = _load_constraints()

    result, issues = reconcile_with_hashes(
        args.storyboard, args.timing_map,
        storyboard, timing_map, constraints,
        str(args.audio) if args.audio else None
    )

    # Print summary
    print(f"Reconciliation complete: {result['total_beats']} production beats")
    print(f"  Master audio: {result['master_audio_duration_sec']:.3f}s")

    split_beats = [b for b in result["beats"] if b.get("split_total", 1) > 1]
    repair_beats = [b for b in result["beats"] if b.get("needs_repair")]
    multi_slot = [b for b in result["beats"] if len(b.get("coverage_plan", [])) > 1]

    if split_beats:
        print(f"  Split beats: {len(split_beats)} (from {len(set(b['source_beat_id'] for b in split_beats))} parents)")
    if repair_beats:
        print(f"  Needs LLM repair: {len(repair_beats)}")
    if multi_slot:
        print(f"  Multi-slot coverage: {len(multi_slot)} beats")

    if issues:
        print(f"\n  Issues ({len(issues)}):")
        for issue in issues:
            print(f"    • {issue}")

    # Fail-closed: check for unresolved needs_repair beats and validation errors
    has_unresolved = bool(repair_beats)
    validation_errors = validate_production_storyboard(result)
    has_errors = any(i.startswith("ERROR") for i in issues)
    is_invalid = has_unresolved or bool(validation_errors) or has_errors

    if validation_errors:
        print(f"\n  Validation errors ({len(validation_errors)}):")
        for e in validation_errors:
            print(f"    • {e}")

    if args.dry_run:
        print("\n[DRY-RUN] Writing preview output...")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2))
        print(f"  → {args.output}")
        sys.exit(1 if is_invalid else 0)
    else:
        # Atomic write: don't overwrite valid existing output with invalid result
        if is_invalid and args.output.exists():
            diag_path = args.output.with_suffix(".invalid.json")
            diag_path.write_text(json.dumps(result, indent=2))
            print(f"\n  ⚠ Invalid output written to diagnostic: {diag_path}")
            print(f"  Existing valid production_storyboard.json preserved.")
            sys.exit(1)

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2))
        write_fingerprint(
            args.output,
            producer="reconcile_production_storyboard",
            producer_version="1.0",
            upstream_hashes=[_sha256(args.storyboard), _sha256(args.timing_map)],
            project_id=result.get("project_id", ""),
        )
        print(f"\n  Output: {args.output}")
        sys.exit(1 if is_invalid else 0)


if __name__ == "__main__":
    main()

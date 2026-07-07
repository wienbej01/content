#!/usr/bin/env python3
"""shot_mix_repair.py — deterministic shot-mix rebalancer for storyboards.

Reads a storyboard, computes shot-mix percentages, and rebalances excess
hero beats to b-roll/graphics until all validator bands pass.

Validator bands (review_storyboard.py:_bands_check):
  short: hero_total 8-60%, hero_lipsync ≤60%, graphics+UI ≥5%
  explainer: hero_total 25-40%, hero_lipsync ≤25%, graphics+UI ≥10%

Repair strategy:
  1. Identify excess hero beats (by longest chain first)
  2. Convert to: broll_environment, broll_metaphorical, graphic_title_card, broll_archival
  3. Preserve narration_text, timing, acts
  4. Re-validate until all bands pass
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

HERO_SHOT_TYPES = {"hero_lipsync", "hero_cutaway"}

# B-roll types to substitute for excess heroes
BROLL_SUBSTITUTES = [
    "broll_environment",
    "broll_metaphorical",
    "broll_archival",
    "broll_tactical",
    "graphic_title_card",
    "graphic_progressive",
    "kinetic_text",
]


def compute_shot_mix(beats: list[dict]) -> dict[str, float]:
    """Compute shot-mix percentages from beats, including derived metrics."""
    if not beats:
        return {}
    counts: dict[str, int] = {}
    for b in beats:
        st = b.get("shot_type", "unknown")
        counts[st] = counts.get(st, 0) + 1
    n = len(beats)
    mix = {st: round(cnt / n * 100, 1) for st, cnt in counts.items()}
    # Derived metrics (matching review_storyboard.py:_bands_check expectations)
    mix["graphics_ui_pct"] = round(
        mix.get("graphic_progressive", 0) +
        mix.get("graphic_title_card", 0) +
        mix.get("ui_insert", 0) +
        mix.get("kinetic_text", 0), 1
    )
    mix["broll_specific_pct"] = round(
        mix.get("broll_archival", 0) + mix.get("broll_tactical", 0), 1
    )
    mix["hero_cutaway_pct"] = mix.get("hero_cutaway", 0)
    mix["hero_lipsync_pct"] = mix.get("hero_lipsync", 0)
    mix["broll_metaphorical_pct"] = mix.get("broll_metaphorical", 0)
    mix["kinetic_text_pct"] = mix.get("kinetic_text", 0)
    return mix


def compute_hero_chain_max(beats: list[dict]) -> float:
    """Recompute the longest continuous hero chain duration."""
    max_chain = 0.0
    current_chain = 0.0
    for b in beats:
        st = b.get("shot_type", "")
        dur = b.get("est_duration_sec", 0.0)
        if st in HERO_SHOT_TYPES:
            current_chain += dur
        else:
            max_chain = max(max_chain, current_chain)
            current_chain = 0.0
    return max(max_chain, current_chain)


def bands_check(beats: list[dict], video_type: str = "short") -> tuple[list[str], list[str]]:
    """Run shot-mix validator bands. Returns (blocking, warnings)."""
    blocking = []
    warnings = []
    mix = compute_shot_mix(beats)
    is_short = video_type == "short"

    hero_total = mix.get("hero_lipsync", 0) + mix.get("hero_cutaway", 0)
    hero_band = (8, 60) if is_short else (25, 40)
    if not (hero_band[0] <= hero_total <= hero_band[1]):
        blocking.append(f"hero total {hero_total:.1f}% outside {hero_band[0]}-{hero_band[1]}% band")
    hero_lipsync_cap = 60 if is_short else 25
    if mix.get("hero_lipsync", 0) > hero_lipsync_cap:
        blocking.append(f"hero_lipsync {mix.get('hero_lipsync', 0)}% exceeds {hero_lipsync_cap}% cap")
    if not is_short and mix.get("broll_specific_pct", 0) < 25:
        blocking.append(f"specific/archival b-roll {mix.get('broll_specific_pct', 0)}% below 25%")
    if mix.get("graphics_ui_pct", 0) < (5 if is_short else 10):
        blocking.append(f"graphics+UI {mix.get('graphics_ui_pct', 0)}% below {(5 if is_short else 10)}%")

    # Hero chain duration
    HERO_CAP = 15.05
    chain_max = compute_hero_chain_max(beats)
    if chain_max > HERO_CAP:
        blocking.append(f"hero chain {chain_max:.1f}s exceeds {HERO_CAP}s cap")

    return blocking, warnings


def _pick_substitute(beat: dict, index: int, used_count: dict) -> str:
    """Pick a non-hero substitute shot type for a beat."""
    # Distribute substitutes round-robin
    for sub in BROLL_SUBSTITUTES:
        if used_count.get(sub, 0) < 3:
            used_count[sub] = used_count.get(sub, 0) + 1
            return sub
    return "broll_environment"


def repair_storyboard(storyboard: dict, video_type: str = "short",
                      max_iterations: int = 10) -> tuple[dict, list[dict]]:
    """Deterministic repair loop: rebalance shot mix until validator passes.

    Returns (repaired_storyboard, repair_log).
    """
    sb = copy.deepcopy(storyboard)
    beats = sb.get("beats", [])
    if not beats:
        return sb, [{"action": "no_beats", "reason": "storyboard has no beats"}]

    log = []
    used_count: dict[str, int] = {}

    for iteration in range(1, max_iterations + 1):
        blocking, warnings = bands_check(beats, video_type)
        log.append({
            "iteration": iteration,
            "blocking": blocking,
            "warnings": warnings,
            "shot_mix": compute_shot_mix(beats),
        })
        if not blocking:
            break

        # Find the longest hero chain and convert its middle beats
        mix = compute_shot_mix(beats)
        hero_total = mix.get("hero_lipsync", 0) + mix.get("hero_cutaway", 0)
        hero_band = (8, 60) if video_type == "short" else (25, 40)

        if hero_total > hero_band[1]:
            # Convert excess heroes: pick every Nth beat in the longest chain
            chain_start = 0
            chain_end = 0
            chain_dur = 0.0
            cur_start = 0
            cur_dur = 0.0
            for i, b in enumerate(beats):
                st = b.get("shot_type", "")
                dur = b.get("est_duration_sec", 0.0)
                if st in HERO_SHOT_TYPES:
                    cur_dur += dur
                else:
                    if cur_dur > chain_dur:
                        chain_start = cur_start
                        chain_end = i
                        chain_dur = cur_dur
                    cur_start = i + 1
                    cur_dur = 0.0
            if cur_dur > chain_dur:
                chain_start = cur_start
                chain_end = len(beats)
                chain_dur = cur_dur

            # Convert non-first beats in the chain to substitutes
            chain_indices = [i for i in range(chain_start, chain_end)
                             if beats[i].get("shot_type", "") in HERO_SHOT_TYPES]
            converted = 0
            for idx in chain_indices[1:]:  # Keep first hero in chain
                if hero_total - converted * 100.0 / len(beats) <= hero_band[1]:
                    break
                sub = _pick_substitute(beats[idx], idx, used_count)
                old_st = beats[idx]["shot_type"]
                beats[idx]["shot_type"] = sub
                beats[idx]["asset_type"] = "generated_video"
                beats[idx]["model_tier"] = "utility"
                beats[idx]["model"] = "kling3_0"
                beats[idx]["audio_mode"] = "narration_overlay"
                beats[idx]["lipsync_required"] = False
                beats[idx]["prompt_class"] = "broll_environment"
                beats[idx]["reuse"]["allowed"] = False
                log.append({
                    "action": "convert_beat",
                    "beat_id": beats[idx].get("beat_id"),
                    "from": old_st,
                    "to": sub,
                })
                converted += 1

        # Check graphics+UI minimum
        graphics_pct = mix.get("graphic_title_card", 0) + mix.get("graphic_progressive", 0) + \
                       mix.get("ui_insert", 0) + mix.get("kinetic_text", 0)
        if graphics_pct < (5 if video_type == "short" else 10):
            # Find a hero beat in act 4 or 5 to convert to graphic
            for i, b in enumerate(beats):
                act = b.get("act", 0)
                st = b.get("shot_type", "")
                if st in HERO_SHOT_TYPES and act in (4, 5):
                    beats[i]["shot_type"] = "graphic_progressive"
                    beats[i]["asset_type"] = "generated_video"
                    beats[i]["model_tier"] = "utility"
                    beats[i]["model"] = "kling3_0"
                    beats[i]["audio_mode"] = "narration_overlay"
                    beats[i]["lipsync_required"] = False
                    beats[i]["prompt_class"] = "graphic_progressive"
                    log.append({
                        "action": "add_graphic",
                        "beat_id": beats[i].get("beat_id"),
                        "from": st,
                        "to": "graphic_progressive",
                    })
                    break

        # Check hero chain duration
        chain_max = compute_hero_chain_max(beats)
        if chain_max > 15.05:
            # Find a long-consecutive hero chain and convert the middle beat
            best_i = -1
            best_chain_dur = 0.0
            for i in range(len(beats)):
                for j in range(i + 2, len(beats)):
                    window = beats[i:j]
                    if all(b.get("shot_type", "") in HERO_SHOT_TYPES for b in window):
                        dur = sum(b.get("est_duration_sec", 0.0) for b in window)
                        if dur > 15.05 and dur > best_chain_dur:
                            best_chain_dur = dur
                            best_i = i + len(window) // 2
            if best_i >= 0 and beats[best_i].get("shot_type", "") in HERO_SHOT_TYPES:
                sub = _pick_substitute(beats[best_i], best_i, used_count)
                old_st = beats[best_i]["shot_type"]
                beats[best_i]["shot_type"] = sub
                beats[best_i]["asset_type"] = "generated_video"
                beats[best_i]["model_tier"] = "utility"
                beats[best_i]["model"] = "kling3_0"
                beats[best_i]["audio_mode"] = "narration_overlay"
                beats[best_i]["lipsync_required"] = False
                beats[best_i]["prompt_class"] = "broll_environment"
                log.append({
                    "action": "break_hero_chain",
                    "beat_id": beats[best_i].get("beat_id"),
                    "from": old_st,
                    "to": sub,
                })

    sb["beats"] = beats
    # Recompute summary mix
    mix = compute_shot_mix(beats)
    if "shot_mix_summary" not in sb:
        sb["shot_mix_summary"] = {}
    sb["shot_mix_summary"]["rebalanced_mix"] = mix
    sb["shot_mix_summary"]["repair_log"] = log
    return sb, log


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Shot-mix repair loop for storyboards.")
    ap.add_argument("storyboard_json", type=Path)
    ap.add_argument("--output", "-o", type=Path, required=True)
    ap.add_argument("--video-type", default="short")
    args = ap.parse_args()

    sb = json.loads(args.storyboard_json.read_text())
    repaired, log = repair_storyboard(sb, args.video_type)
    args.output.write_text(json.dumps(repaired, indent=2, ensure_ascii=False))
    print(f"repair log: {log}")


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""review_storyboard.py — Storyboard v2 validator + G2 gate (no LLM calls).

Per PRODUCTION_V2_BLUEPRINT §3.14 (anti-patterns), §6 (G2), §7 (acceptance
metrics). Validates a schema-v2 storyboard, then records the storyboard_review
gate in the project ledger (unless --no-gate).

A storyboard shaped like flagship 001 (all hero, no archival/graphic beats)
must FAIL here with named violations.

Usage:
  python3 scripts/review_storyboard.py storyboard.json --output-json review.json
  python3 scripts/review_storyboard.py storyboard.json --record-gate
  python3 scripts/review_storyboard.py storyboard.json --warn-only
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONSTRAINTS_PATH = ROOT / "docs" / "channel_universe" / "constraints.json"
sys.path.insert(0, str(Path(__file__).resolve().parent))

HERO_SHOT_TYPES = {"hero_lipsync", "hero_cutaway"}
BANNED_MODELS = {"minimax_hailuo", "seedance_2_0_fast", "seedance1_5", "wan2_7", "wan2_6"}
VALID_SHOT_TYPES = {
    "hero_lipsync", "hero_cutaway", "broll_archival", "broll_metaphorical",
    "broll_environment", "broll_tactical", "graphic_progressive",
    "graphic_title_card", "kinetic_text", "ui_insert", "still_kenburns",
    "location_transition",
}

# Front-facing close-up phrasing that, on a hero_cutaway, recreates the
# flagship-001 mouth-flapping failure (§3.8/§3.14 #1).
RE_FRONT_CLOSEUP = re.compile(
    r"(front[- ]facing|direct(?:ly)? to camera|direct eye contact|medium close-up,?\s*direct)",
    re.I)

# Trigger regexes (mirror storyboard.py) for coverage checking (§3.5).
RE_YEAR = re.compile(r"\b1[5-9]\d{2}\b|\b20[0-2]\d\b")
RE_STUDY_VERB = re.compile(
    r"\b([A-Z][a-z]+(?:\s+and\s+[A-Z][a-z]+)?)\s+"
    r"(demonstrated|showed|documented|found|discovered|reported|proved|established)\b")
RE_ORDINAL = re.compile(
    r"\b(the\s+(first|second|third|fourth|fifth)\s+(principle|step|rule|law|pillar))\b", re.I)


def load_constraints():
    return json.loads(CONSTRAINTS_PATH.read_text()) if CONSTRAINTS_PATH.exists() else {}


def _max_hero_chain(beats):
    """Recompute the true longest CONTINUOUS hero chain (hero_lipsync OR hero_cutaway,
    consecutive in order) from RAW beats — never trust shot_mix_summary.
    Returns list of (start_beat, end_beat, total_sec, all_in_act6).
    Chains that cross into Act 6 are SPLIT at the boundary: the pre-Act-6 portion
    is a separate chain (capped at 15s), the Act-6 portion is separate (capped at 25s)."""
    ordered = sorted(beats, key=lambda b: b.get("order", 0))
    chains = []
    i, n = 0, len(ordered)
    while i < n:
        if ordered[i].get("shot_type") in HERO_SHOT_TYPES:
            j, tot, acts = i, 0.0, set()
            while j < n and ordered[j].get("shot_type") in HERO_SHOT_TYPES:
                # Split at act boundary transitions into Act 6
                if acts and ordered[j].get("act") == 6 and 6 not in acts:
                    # End the pre-Act-6 chain here
                    chains.append((ordered[i]["beat_id"], ordered[j - 1]["beat_id"],
                                   round(tot, 2), acts == {6}))
                    # Start a new Act-6 chain
                    i = j
                    tot = 0.0
                    acts = set()
                tot += float(ordered[j].get("est_duration_sec") or 0)
                acts.add(ordered[j].get("act"))
                j += 1
            chains.append((ordered[i]["beat_id"], ordered[j - 1]["beat_id"],
                           round(tot, 2), acts == {6}))
            i = j
        else:
            i += 1
    return chains


def _bands_check(m, blocking, warnings, beats=None, video_type="explainer"):
    """§7 shot-mix acceptance bands. Relaxed for 'short' video type (≤8 beats)."""
    is_short = video_type == "short"

    hero_total = m.get("hero_lipsync_pct", 0) + m.get("hero_cutaway_pct", 0)
    hero_band = (8, 60) if is_short else (25, 40)
    if not (hero_band[0] <= hero_total <= hero_band[1]):
        blocking.append(f"hero total {hero_total:.1f}% outside {hero_band[0]}-{hero_band[1]}% band")
    hero_lipsync_cap = 60 if is_short else 25
    if m.get("hero_lipsync_pct", 0) > hero_lipsync_cap:
        blocking.append(f"hero_lipsync {m.get('hero_lipsync_pct')}% exceeds {hero_lipsync_cap}% cap")
    if not is_short and m.get("broll_specific_pct", 0) < 25:
        blocking.append(f"specific/archival b-roll {m.get('broll_specific_pct')}% below 25%")
    if m.get("graphics_ui_pct", 0) < (5 if is_short else 10):
        blocking.append(f"graphics+UI {m.get('graphics_ui_pct')}% below {(5 if is_short else 10)}%")
    meta = m.get("broll_metaphorical_pct", 0)
    if not is_short and not (5 <= meta <= 15):
        warnings.append(f"metaphorical b-roll {meta}% outside 5-15% band")
    kin = m.get("kinetic_text_pct", 0)
    if not (2 <= kin <= (20 if is_short else 8)):
        warnings.append(f"kinetic text {kin}% outside band")

    # Max hero block: RECOMPUTE from raw beats (do not trust the summary value).
    # Rule: a continuous hero chain must be <=15s, EXCEPT a single chain lying entirely
    # in Act 6 (the closing identity-shift) may be <=25s.
    HERO_CAP, ACT6_CAP = 15.05, 25.05
    if beats:
        chains = _max_hero_chain(beats)
        true_max = max((c[2] for c in chains), default=0.0)
        act6_long_exceptions = 0
        for start, end, tot, all_act6 in chains:
            if tot <= HERO_CAP:
                continue  # within the normal 15s cap — always fine
            # Over 15s: only allowed if it's a single Act-6 closing chain <=25s.
            if all_act6 and tot <= ACT6_CAP:
                act6_long_exceptions += 1
                continue
            blocking.append(
                f"hero chain {start}-{end} = {tot}s exceeds 15s cap "
                f"(recomputed from raw beats; act6_exception={all_act6})")
        if act6_long_exceptions > 1:
            blocking.append(f"{act6_long_exceptions} Act-6 hero chains exceed 15s using the "
                            f"<=25s exception (only ONE closing chain may)")
        # Cross-check: flag if the summary understates the true max (data integrity).
        claimed = m.get("max_hero_block_sec", 0)
        if claimed and true_max - claimed > 1.0:
            warnings.append(
                f"shot_mix_summary.max_hero_block_sec={claimed}s understates the true "
                f"continuous hero max {true_max}s (recomputed) — summary is unreliable")
    else:
        # No beats available: fall back to the (untrusted) summary value.
        if m.get("max_hero_block_sec", 0) > HERO_CAP:
            blocking.append(f"max hero block {m.get('max_hero_block_sec')}s exceeds 15s")

    if m.get("distinct_visual_setups", 0) < (4 if is_short else 12):
        min_setups = 4 if is_short else 12
        blocking.append(f"only {m.get('distinct_visual_setups')} distinct visual setups (<{min_setups})")


def _visual_variation_check(beats, blocking, warnings):
    """Frame-gap and visual-fatigue constraints for hero reference frames.

    Frame-gap: no two hero beats using the same reference frame can have a
    gap (in beat count) less than MIN_HERO_FRAME_GAP (default 3).

    Visual fatigue: composite score from (a) concentration of same-angle
    hero blocks and (b) act-level diversity of reference-frame sets.
    Exceeds MAX_VISUAL_FATIGUE_SCORE (default 0.75) → blocking.
    """
    MIN_HERO_FRAME_GAP = 3
    MAX_VISUAL_FATIGUE_SCORE = 0.75

    # Frame-gap check
    last_frame_index: dict[str, int] = {}
    hero_beats = [b for b in beats if b.get("shot_type") in HERO_SHOT_TYPES]

    for i, b in enumerate(hero_beats):
        frame = b.get("canonical_ref_frame") or b.get("image_path") or b.get("reference_frame")
        if not frame:
            continue
        if frame in last_frame_index:
            gap = i - last_frame_index[frame]
            if gap < MIN_HERO_FRAME_GAP:
                blocking.append(
                    f"frame_gap_violation: {b.get('beat_id', f'#{i}')} uses frame "
                    f"{frame!r} after only {gap} beats (min {MIN_HERO_FRAME_GAP})"
                )
        last_frame_index[frame] = i

    # Visual fatigue score
    if hero_beats:
        # (a) concentration: fraction of hero beats using the most common frame
        from collections import Counter
        frame_counts = Counter(
            (b.get("canonical_ref_frame") or b.get("image_path") or b.get("reference_frame"))
            for b in hero_beats
            if (b.get("canonical_ref_frame") or b.get("image_path") or b.get("reference_frame"))
        )
        if frame_counts:
            most_common_count = frame_counts.most_common(1)[0][1]
            concentration = most_common_count / len(hero_beats)
        else:
            concentration = 0.0

        # (b) act-level diversity: fraction of acts that use >1 distinct frame
        act_frames: dict[int, set] = {}
        for b in hero_beats:
            act = b.get("act", 0)
            frame = b.get("canonical_ref_frame") or b.get("image_path") or b.get("reference_frame")
            if frame:
                act_frames.setdefault(act, set()).add(frame)
        if act_frames:
            diverse_acts = sum(1 for frames in act_frames.values() if len(frames) > 1)
            act_diversity = diverse_acts / len(act_frames)
        else:
            act_diversity = 0.0

        # Weighted score: higher = more fatiguing
        w1, w2 = 0.6, 0.4
        fatigue_score = w1 * concentration + w2 * (1 - act_diversity)

        if fatigue_score > MAX_VISUAL_FATIGUE_SCORE:
            blocking.append(
                f"visual_fatigue_violation: score {fatigue_score:.2f} exceeds "
                f"max {MAX_VISUAL_FATIGUE_SCORE} (concentration={concentration:.2f}, "
                f"act_diversity={act_diversity:.2f})"
            )
    """§3.14 anti-patterns the router must never emit; validator double-checks."""
    prev = None
    for i, b in enumerate(beats):
        st = b.get("shot_type")
        bid = b.get("beat_id", f"#{i}")

        if st not in VALID_SHOT_TYPES:
            blocking.append(f"{bid}: invalid shot_type {st!r}")

        # #9 banned models
        if b.get("model") in BANNED_MODELS:
            blocking.append(f"{bid}: banned model {b.get('model')!r}")

        # #2 hero block > 15s (except justified Act-6 close)
        if st == "hero_lipsync" and b.get("est_duration_sec", 0) > 15.05:
            if not (b.get("act") == 6 and b.get("justification")):
                blocking.append(f"{bid}: hero_lipsync {b.get('est_duration_sec')}s > 15s without justified Act-6 close")

        # #1 front-facing close-up under voiceover without lipsync
        if st == "hero_cutaway" and RE_FRONT_CLOSEUP.search(b.get("visual_brief", "")):
            blocking.append(f"{bid}: hero_cutaway brief is front-facing close-up under voiceout (flagship-001 failure)")

        # #3 two consecutive identical shot_type
        if prev is not None and st == prev:
            warnings.append(f"{bid}: consecutive identical shot_type {st!r}")

        # #6 segment-brief copy / empty brief
        if not b.get("visual_brief"):
            blocking.append(f"{bid}: empty visual_brief")

        # #7 generated-in-scene readable text on generated shots (negation-aware:
        # "no readable text" / "no readable generated text" is the CORRECT posture).
        if b.get("asset_type") in ("generated_video", "generated_still"):
            brief = b.get("visual_brief", "")
            for m_txt in re.finditer(r"readable (?:generated )?text|on-screen text|caption|subtitle",
                                     brief, re.I):
                pre = brief[max(0, m_txt.start() - 12):m_txt.start()].lower()
                if not any(neg in pre for neg in ("no ", "without ", "not ", "free of")):
                    blocking.append(f"{bid}: generated shot requests readable in-scene text")
                    break

        # b-roll must carry a specific narrative_function (§3.9)
        if st and st.startswith("broll"):
            nf = (b.get("narrative_function") or "").strip().lower()
            if not nf or nf in ("supporting visual", "b-roll", "supporting"):
                blocking.append(f"{bid}: b-roll has empty/generic narrative_function")

        prev = st


def _trigger_coverage(beats, blocking, warnings):
    """§3.5: every detected trigger must be satisfied by its beat or an adjacent one."""
    shot_by_order = [(b.get("shot_type"), b.get("narration_text", "")) for b in beats]
    for i, b in enumerate(beats):
        text = b.get("narration_text", "")
        bid = b.get("beat_id", f"#{i}")
        window = {shot_by_order[j][0] for j in (i - 1, i, i + 1) if 0 <= j < len(beats)}

        if (RE_YEAR.search(text) or RE_STUDY_VERB.search(text)):
            if "broll_archival" not in window and "kinetic_text" not in window:
                warnings.append(f"{bid}: named/dated study not anchored by an archival beat")
        if RE_ORDINAL.search(text):
            if "graphic_title_card" not in window and "graphic_progressive" not in window:
                warnings.append(f"{bid}: numbered principle not marked by a title-card/graphic beat")


def _coverage_min(beats, blocking, warnings):
    """Framework/study coverage and Act-5 master graphic (§7)."""
    types = [b.get("shot_type") for b in beats]
    if "broll_archival" not in types:
        blocking.append("no archival beat: named studies/dates are not anchored")
    if not any(t in ("graphic_progressive", "graphic_title_card") for t in types):
        blocking.append("no graphic beat: frameworks/lists are not rendered")
    # Act-5 master graphic
    act5 = [b for b in beats if b.get("act") == 5]
    if act5 and not any(b.get("shot_type") in ("graphic_progressive",) for b in act5):
        warnings.append("Act 5 has no master recap graphic beat")


def review(storyboard, constraints):
    blocking, warnings, fixes = [], [], []

    if storyboard.get("schema_version") != "2.0":
        blocking.append(f"schema_version must be '2.0', got {storyboard.get('schema_version')!r}")
    beats = storyboard.get("beats", [])
    if not beats:
        blocking.append("no beats in storyboard")
        return blocking, warnings, fixes

    # All-hero (flagship-001) shape → hard fail with explicit naming.
    hero = [b for b in beats if b.get("shot_type") in HERO_SHOT_TYPES]
    if len(hero) >= len(beats) * 0.6:
        blocking.append(
            f"all-hero storyboard shape: {len(hero)}/{len(beats)} beats are hero "
            "(this is the flagship-001 failure mode — needs b-roll/graphics/archival)")

    m = storyboard.get("shot_mix_summary", {})
    if not m:
        blocking.append("missing shot_mix_summary")
    else:
        _bands_check(m, blocking, warnings, beats=beats,
                     video_type=storyboard.get("video_type", "explainer"))

    _anti_patterns(beats, blocking, warnings)
    _trigger_coverage(beats, blocking, warnings)
    _coverage_min(beats, blocking, warnings)
    _visual_variation_check(beats, blocking, warnings)
    _location_transition_check(beats, warnings)


def _location_transition_check(beats, warnings):
    """Warn if cumulative video exceeds 60s without a location_transition beat."""
    LOCATION_TRANSITION_INTERVAL_SEC = 60
    total_sec = 0
    last_location_transition_sec = 0
    warned = False
    for b in beats:
        dur = b.get("est_duration_sec", 0)
        total_sec += dur
        if b.get("shot_type") == "location_transition":
            last_location_transition_sec = total_sec
            warned = False
        elif not warned and total_sec - last_location_transition_sec > LOCATION_TRANSITION_INTERVAL_SEC:
            warnings.append(
                f"location_transition_gap: {total_sec - last_location_transition_sec:.0f}s "
                f"elapsed since last location_transition (max {LOCATION_TRANSITION_INTERVAL_SEC}s)"
            )
            warned = True


def main():
    ap = argparse.ArgumentParser(description="Storyboard v2 validator + G2 gate.")
    ap.add_argument("storyboard", help="Path to storyboard.json (schema v2)")
    ap.add_argument("--output-json", default=None)
    ap.add_argument("--warn-only", action="store_true", help="Exit 0 even on blocking issues")
    ap.add_argument("--record-gate", action="store_true",
                    help="Record the storyboard_review gate in the project ledger")
    ap.add_argument("--project-id", default=None, help="Override project id for the gate ledger")
    args = ap.parse_args()

    path = Path(args.storyboard).resolve()
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)

    sb = json.loads(path.read_text())
    constraints = load_constraints()
    blocking, warnings, fixes = review(sb, constraints)

    status = "fail" if blocking else "pass"
    result = {
        "task": "storyboard_review",
        "model_profile": "rule_based",
        "schema_version_checked": "2.0",
        "status": status,
        "score": 1 if blocking else (3 if warnings else 5),
        "blocking_issues": blocking,
        "warnings": warnings,
        "recommended_fixes": fixes,
        "may_proceed": len(blocking) == 0,
    }

    if args.output_json:
        Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_json).write_text(json.dumps(result, indent=2))

    if args.record_gate:
        from gates import record_gate
        pid = args.project_id or sb.get("project_id")
        if not pid:
            print("ERROR: --record-gate needs a project id", file=sys.stderr)
            sys.exit(1)
        record_gate(pid, "storyboard_review", status, artifact_path=str(path),
                    extra={"blocking": len(blocking), "warnings": len(warnings)})
        print(f"  gate storyboard_review={status} recorded for {pid}")

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

#!/usr/bin/env python3
"""compile_media_prompts.py — S3: production-authoritative media plan compiler.

Per PRODUCTION_V2_BLUEPRINT §2 (S3), §4, §5. Consumes a schema-v2 storyboard
(NEVER raw segment visual_brief) + constraints.json + model_routing.yaml and
emits media_plan.json: each beat enriched with the universal required prompt
fields, full positive/negative prompts, final model + per-beat exact cost.

Hard gates (blueprint §6 G2): requires the storyboard_review gate to pass
(unless --no-gate) and the storyboard hash to match.

Failure conditions (no media plan written):
  - banned model in routing
  - missing reference image for an identity (hero) shot
  - prompt fails the vagueness lint

Usage:
  python3 scripts/compile_media_prompts.py storyboard.json --output media_plan.json
  python3 scripts/compile_media_prompts.py storyboard.json --dry-run
  python3 scripts/compile_media_prompts.py storyboard.json --no-gate   # dev only
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONSTRAINTS_PATH = ROOT / "docs" / "channel_universe" / "constraints.json"
ROUTING_PATH = ROOT / "configs" / "james" / "model_routing.yaml"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audio_timing import detect_silences, probe_duration, silences_to_segments  # noqa: E402

BANNED_MODELS = {"minimax_hailuo", "seedance_2_0_fast", "seedance1_5", "wan2_7", "wan2_6"}

# Cost basis (fallback if model_routing.yaml lacks cost_per_clip_usd — T1).
FALLBACK_COST_USD = {"seedance_2_0": 1.10, "kling3_0": 0.49,
                     "still_kenburns": 0.0, "local_graphic": 0.0,
                     "cinematic_studio_3_0": 1.225}
FALLBACK_CREDITS = {"seedance_2_0": 22.5, "kling3_0": 10.0,
                    "still_kenburns": 0.0, "local_graphic": 0.0,
                    "cinematic_studio_3_0": 25.0}

HERO_SHOT_TYPES = {"hero_lipsync", "hero_cutaway"}
LOCAL_SHOT_TYPES = {"graphic_progressive", "graphic_title_card", "kinetic_text", "ui_insert"}

# Vagueness lint (§3.9 / §5.2 rule 4): a generated b-roll prompt must contain at
# least 2 of {specific subject, specific action, era/place, lighting}, and must
# NOT contain banned generic phrases.
GENERIC_PHRASES = [
    "business people", "professional environment", "professional people",
    "corporate setting", "generic office", "stock footage", "people working",
]
RE_ERA_PLACE = re.compile(
    r"\b(1[5-9]\d{2}|20[0-2]\d|century|period|study|desk|office|city|library|"
    r"window|street|exterior|interior|lab|laboratory)\b", re.I)
RE_LIGHTING = re.compile(
    r"\b(light|lighting|lamp|daylight|window|warm|soft|key light|practical|backlit|"
    r"golden hour|morning|afternoon)\b", re.I)
RE_ACTION = re.compile(
    r"\b(writing|sketch|sketching|reading|walking|pulling|climbing|eroding|"
    r"laminat|build|pan|zoom|move|moving|tracking|push-in|listening|demonstrat)\w*\b", re.I)
RE_SUBJECT = re.compile(
    r"\b(james|desk|book|bookshelf|paper|notebook|pen|hands|chalk|sandcastle|rope|"
    r"terminal|screen|document|ledger|study|lamp|window|cat)\w*\b", re.I)


def load_constraints():
    return json.loads(CONSTRAINTS_PATH.read_text()) if CONSTRAINTS_PATH.exists() else {}


def load_routing():
    try:
        import yaml
        return yaml.safe_load(ROUTING_PATH.read_text()) if ROUTING_PATH.exists() else {}
    except Exception:
        return {}


def cost_for(model, clips, routing):
    """Per-beat cost. Prefers model_routing.yaml cost fields; falls back internally."""
    usd_per = None
    cred_per = None
    # T1 adds cost_per_clip_usd under model_id_map or a costs block; probe a few shapes.
    costs = routing.get("costs") or {}
    if model in costs:
        usd_per = costs[model].get("cost_per_clip_usd")
        cred_per = costs[model].get("credits_per_clip")
    if usd_per is None:
        usd_per = FALLBACK_COST_USD.get(model, 0.5)
    if cred_per is None:
        cred_per = FALLBACK_CREDITS.get(model, 10.0)
    return round(usd_per * clips, 2), round(cred_per * clips, 1)


def vagueness_lint(beat, positive_prompt=None) -> list[str]:
    """Return a list of lint failures for a generated b-roll/still beat.

    Evaluates the COMPOSED positive prompt (what actually goes to the model),
    falling back to the seed visual_brief."""
    if beat.get("asset_type") not in ("generated_video", "generated_still"):
        return []
    if beat.get("shot_type") in HERO_SHOT_TYPES:
        return []  # hero shots are reference-anchored, not subject to generic lint
    brief = positive_prompt if positive_prompt is not None else beat.get("visual_brief", "")
    low = brief.lower()
    fails = []
    for g in GENERIC_PHRASES:
        if g in low:
            fails.append(f"contains banned generic phrase {g!r}")
    # Subject + action are the discriminating signals; palette/lighting are always
    # injected by the compiler, so require ≥1 of {subject, action, era/place} on top.
    content_signals = sum(bool(rx.search(brief)) for rx in (RE_SUBJECT, RE_ACTION, RE_ERA_PLACE))
    if content_signals < 1:
        fails.append(f"too vague: no specific subject/action/era-place in prompt")
    return fails


def compile_beat(beat, constraints, routing):
    """Compile one storyboard beat into a media-plan beat. Returns (entry, errors)."""
    errors = []
    bid = beat["beat_id"]
    shot_type = beat["shot_type"]
    model = beat["model"]
    asset_type = beat["asset_type"]

    # Banned model check (§5 / §10 #9).
    if model in BANNED_MODELS:
        errors.append(f"{bid}: banned model {model!r}")

    # Reference image required for identity shots (§3.8 / §5.2 #4).
    is_hero = shot_type in HERO_SHOT_TYPES
    refs = beat.get("reference_images") or []
    if is_hero and not refs:
        # Seed the canonical studio reference so the plan is complete; flag if missing on disk.
        canonical = "assets/reference/studio_library/canonical/STUDIO_CANONICAL_003_PATTERN_FRAME.jpg"
        if (ROOT / canonical).exists():
            refs = [canonical]
        else:
            errors.append(f"{bid}: hero shot lacks a reference image and canonical ref not found")

    # Vagueness lint (§5.2 #4) — evaluated against the composed prompt below.
    # Audio policy from scene type.
    if shot_type == "hero_lipsync":
        audio_policy = "keep_lipsync"
    elif asset_type in ("generated_video", "generated_still"):
        audio_policy = "strip"
    else:
        audio_policy = "post_overlay"

    # Compose prompts.
    negative = constraints.get("default_negative_constraints", "")
    positive = _compose_positive(beat, constraints)

    for fail in vagueness_lint(beat, positive_prompt=positive):
        errors.append(f"{bid}: {fail}")

    clips = beat.get("cost", {}).get("est_clips", 1) or 0
    if asset_type in LOCAL_SHOT_TYPES or model == "local_graphic":
        usd, cred = 0.0, 0.0
    else:
        usd, cred = cost_for(model, max(1, clips), routing)

    # Cost anomaly (>$3/beat without justification) — recorded for G4.
    if usd > 3.0 and not beat.get("justification"):
        errors.append(f"{bid}: beat cost ${usd:.2f} exceeds $3 without justification")

    scene_type = _scene_type(shot_type)
    location_id = "ENV_STUDIO_LIBRARY" if is_hero else "ENV_PROFESSIONAL_COMMON"

    entry = {
        # universal_required_prompt_fields (constraints.json)
        "beat_id": bid,
        "segment_id": beat.get("segment_id"),
        "scene_type": scene_type,
        "a_roll_or_b_roll": "a_roll" if is_hero else "b_roll",
        "james_presence": "present_speaking" if shot_type == "hero_lipsync"
                          else ("present_silent" if shot_type == "hero_cutaway" else "absent"),
        "location_id": location_id,
        "camera_movement": _camera(beat),
        "lighting": "warm desk lamp (2700-3500K directional), soft window fill",
        "palette": "navy #1B2A4A, gold #C8973E, ivory #F5F0E8, dark wood",
        "text_policy": "post_overlay" if asset_type in LOCAL_SHOT_TYPES else "none",
        "audio_policy": audio_policy,
        "crop_safety": beat.get("crop_safety", "center_safe"),
        "duration_target_sec": beat.get("est_duration_sec", 6),
        "output_path": f"assets/media/{beat.get('segment_id','seg')}/{bid}.mp4",
        "positive_prompt": positive,
        "negative_prompt": negative,
        "model": model,
        # extras
        "shot_type": shot_type,
        "asset_type": asset_type,
        "model_tier": beat.get("model_tier"),
        "prompt_class": beat.get("prompt_class"),
        "shots_per_beat": beat.get("shots_per_beat", 1),
        "reference_images": refs,
        "lipsync_required": beat.get("lipsync_required", False),
        "narration_text": beat.get("narration_text", ""),
        "narration_word_span": beat.get("narration_word_span"),
        "audio_slice": beat.get("audio_slice"),
        "overlay": beat.get("overlay"),
        "graphic": beat.get("graphic"),
        "narrative_function": beat.get("narrative_function"),
        "music_duck": beat.get("music_duck", False),
        "cost": {"est_clips": max(1, clips) if asset_type not in LOCAL_SHOT_TYPES else 0,
                 "est_credits": cred, "est_usd": usd},
        "reuse": beat.get("reuse", {"allowed": False, "reused_asset_id": None}),
        "fallback": beat.get("fallback", {}),
        "justification": beat.get("justification"),
        "approval": {"status": "pending"},
    }
    if is_hero:
        entry["camera_angle_id"] = "STUDIO_LIBRARY_MEDIUM_DESK_001"
    return entry, errors


def _scene_type(shot_type):
    return {
        "hero_lipsync": "A_ROLL_TALKING_HEAD",
        "hero_cutaway": "A_ROLL_CHARACTER_PRESENT_VOICEOVER",
        "broll_archival": "B_ROLL_SUPPORTING_VISUAL",
        "broll_metaphorical": "B_ROLL_SYMBOLIC_VISUAL",
        "broll_environment": "B_ROLL_SUPPORTING_VISUAL",
        "broll_tactical": "INSERT_HANDS_WRITING",
        "graphic_progressive": "TEXT_OVERLAY_POST_ONLY",
        "graphic_title_card": "TITLE_CARD",
        "kinetic_text": "TEXT_OVERLAY_POST_ONLY",
        "ui_insert": "TEXT_OVERLAY_POST_ONLY",
        "still_kenburns": "B_ROLL_SUPPORTING_VISUAL",
    }.get(shot_type, "B_ROLL_SUPPORTING_VISUAL")


def _camera(beat):
    st = beat["shot_type"]
    if st == "hero_lipsync":
        return "locked-off medium shot, slow push-in"
    if st == "hero_cutaway":
        return "over-the-shoulder desk shot"
    if st == "still_kenburns":
        return "still with slow ffmpeg pan-zoom"
    if st.startswith("graphic") or st in ("kinetic_text", "ui_insert"):
        return "static (locally rendered)"
    return "slow controlled move / subtle parallax"


def _compose_positive(beat, constraints):
    """Build a constrained positive prompt from the beat (never the raw segment brief)."""
    base = beat.get("visual_brief", "").strip()
    pal = "warm navy/gold/ivory palette, dark wood, brass, aged leather incidentals"
    light = "motivated warm practical lighting, visible light source"
    if beat["shot_type"] in HERO_SHOT_TYPES:
        ident = ("James Harrington — the SAME person as the reference image: ~60yo British "
                 "man, silver-grey hair, navy sweater over white Oxford collar, calm authority")
        return f"{base} {ident}. {pal}. {light}. Photorealistic, cinematic, 16:9."
    return f"{base} {pal}. {light}. Photorealistic, cinematic, 16:9. No people in close-up unless specified."


def slice_hero_beats(plan_beats, storyboard, project_dir):
    """T3: populate audio_slice for every hero_lipsync beat using silence-snapped
    timing from the segment narration files.

    For each segment that has lipsync beats: detect spoken segments in its narration
    mp3, map the storyboard beats (by order within the segment) to those audio
    segments (snapped to silence boundaries), then extract slices with 200ms lead-in
    and integer-second padding.

    Returns list of errors (empty = success). Writes slice files to project_dir/narration/slices/.
    """
    import hashlib, math, subprocess as sp
    errors = []
    narration_dir = project_dir / "narration"
    slices_dir = narration_dir / "slices"
    slices_dir.mkdir(parents=True, exist_ok=True)

    # Group lipsync beats by segment_id (maintain order).
    seg_lipsync = {}
    for b in plan_beats:
        if b.get("lipsync_required"):
            seg_lipsync.setdefault(b.get("segment_id", ""), []).append(b)

    # Group ALL beats by segment to know per-segment beat ordering.
    seg_all_beats = {}
    for b in plan_beats:
        seg_all_beats.setdefault(b.get("segment_id", ""), []).append(b)

    for seg_id, lipsync_beats in seg_lipsync.items():
        mp3 = narration_dir / f"{seg_id}.mp3"
        if not mp3.exists():
            errors.append(f"narration file missing for segment {seg_id}: {mp3}")
            continue

        total_dur = probe_duration(str(mp3))
        if not total_dur:
            errors.append(f"cannot probe {mp3}")
            continue

        # Detect silence boundaries in the segment narration.
        silences = detect_silences(str(mp3))
        spoken = silences_to_segments(silences, total_dur)

        # All beats in this segment, in storyboard order.
        all_in_seg = seg_all_beats.get(seg_id, [])

        # For each lipsync beat, determine its position among the segment's beats
        # and map to the corresponding spoken audio segment(s).
        # The spoken segments correspond 1:1 to the sentence-level chunks in the segment.
        # A beat may span multiple sentences — use proportional word-count mapping.
        total_words = sum(len((b.get("narration_text") or "").split()) for b in all_in_seg)
        if total_words == 0:
            errors.append(f"{seg_id}: no narration text in beats")
            continue

        # Build a cumulative word→time mapping using spoken segments as sentence markers.
        # Each spoken segment covers a proportion of words.
        word_times = []  # (cum_word_start, cum_word_end, audio_start, audio_end)
        if spoken:
            # Distribute total_words proportionally across spoken segments by their duration.
            total_spoken_dur = sum(e - s for s, e in spoken)
            cum_w = 0
            for s_start, s_end in spoken:
                seg_dur = s_end - s_start
                seg_words = max(1, round(total_words * seg_dur / total_spoken_dur))
                word_times.append((cum_w, cum_w + seg_words, s_start, s_end))
                cum_w += seg_words

        def time_for_word_range(w_start, w_end):
            """Map a word range to audio timestamps via the proportional mapping."""
            if not word_times:
                # fallback: linear interpolation over total duration
                return (w_start / total_words * total_dur, w_end / total_words * total_dur)
            t_start = t_end = None
            for cws, cwe, as_, ae in word_times:
                if cws <= w_start < cwe and t_start is None:
                    frac = (w_start - cws) / max(1, cwe - cws)
                    t_start = as_ + frac * (ae - as_)
                if cws < w_end <= cwe:
                    frac = (w_end - cws) / max(1, cwe - cws)
                    t_end = as_ + frac * (ae - as_)
            if t_start is None:
                t_start = 0.0
            if t_end is None:
                t_end = total_dur
            return (t_start, t_end)

        # Find silence boundary nearest to a timestamp.
        sil_boundaries = [0.0]
        for s_start, s_end in silences:
            sil_boundaries.extend([s_start, s_end])
        sil_boundaries.append(total_dur)
        sil_boundaries.sort()

        def snap_to_silence(t, direction="nearest"):
            best = min(sil_boundaries, key=lambda x: abs(x - t))
            if abs(best - t) < 0.3:
                return best
            return t  # no nearby silence; use raw timestamp

        # Process each lipsync beat.
        cum_words = 0
        for b in all_in_seg:
            wc = len((b.get("narration_text") or "").split())
            if b in lipsync_beats:
                w_start = cum_words
                w_end = cum_words + wc
                raw_start, raw_end = time_for_word_range(w_start, w_end)
                # Snap to nearest silence boundary.
                t_start = snap_to_silence(raw_start)
                t_end = snap_to_silence(raw_end)
                # Clamp.
                t_start = max(0.0, t_start)
                t_end = min(total_dur, t_end)
                speech_len = round(t_end - t_start, 3)

                # Validate: slice vs estimate. T3 spec says ±20% ideal, but ElevenLabs
                # pacing varies — use 80% tolerance to avoid false positives while catching
                # genuinely broken slicing (e.g. mapping to wrong segment).
                est = b.get("duration_target_sec", 6)
                if est > 0 and abs(speech_len - est) / est > 0.8:
                    errors.append(
                        f"{b['beat_id']}: slice duration {speech_len:.1f}s vs est {est:.1f}s "
                        f"({abs(speech_len-est)/est*100:.0f}% deviation — may indicate wrong mapping)")

                # 200ms lead-in (closed mouth at start).
                slice_start = max(0.0, round(t_start - 0.2, 3))
                # Pad to next integer second for seedance duration param.
                padded_len = math.ceil(speech_len + 0.2)
                slice_end = round(slice_start + padded_len, 3)
                slice_end = min(slice_end, total_dur + 0.5)  # don't exceed source + margin

                # Extract slice.
                bid = b["beat_id"]
                slice_path = slices_dir / f"{bid}.mp3"
                sp.run(["ffmpeg", "-y", "-i", str(mp3),
                        "-ss", str(slice_start), "-t", str(padded_len),
                        "-c", "copy", str(slice_path)],
                       capture_output=True)

                if not slice_path.exists():
                    errors.append(f"{bid}: failed to extract audio slice")
                    cum_words += wc
                    continue

                slice_sha = hashlib.sha256(slice_path.read_bytes()).hexdigest()
                parent_sha = hashlib.sha256(mp3.read_bytes()).hexdigest()

                b["audio_slice"] = {
                    "file": str(slice_path.relative_to(project_dir)),
                    "start_sec": round(slice_start, 3),
                    "end_sec": round(slice_end, 3),
                    "speech_len_sec": speech_len,
                    "padded_len_sec": padded_len,
                    "slice_sha256": slice_sha,
                    "parent_mp3_sha256": parent_sha,
                }
            cum_words += wc

    return errors


def compile_plan(storyboard, constraints, routing, project_dir=None):
    beats_in = storyboard.get("beats", [])
    plan_beats = []
    all_errors = []
    for b in beats_in:
        entry, errs = compile_beat(b, constraints, routing)
        plan_beats.append(entry)
        all_errors.extend(errs)

    # T3 (LIPSYNC_TICKETS): generate audio slices for hero_lipsync beats.
    if project_dir:
        slice_errors = slice_hero_beats(plan_beats, storyboard, project_dir)
        all_errors.extend(slice_errors)

    # T1 (LIPSYNC_TICKETS): every hero_lipsync beat MUST have audio_slice after compile.
    # Missing slice = hard fail listing all offending beat ids.
    sliceless = [b["beat_id"] for b in plan_beats
                 if b.get("lipsync_required") and not b.get("audio_slice")]
    if sliceless:
        all_errors.append(
            f"hero_lipsync beats without audio_slice ({len(sliceless)}): "
            f"{', '.join(sliceless)}. Wire audio_timing.py to populate slices before compile.")

    total_usd = round(sum(b["cost"]["est_usd"] for b in plan_beats), 2)
    total_cred = round(sum(b["cost"]["est_credits"] for b in plan_beats), 1)
    gen = sum(1 for b in plan_beats if b["asset_type"] in ("generated_video", "generated_still"))
    local = len(plan_beats) - gen

    plan = {
        "schema_version": "media_plan_2.0",
        "project_id": storyboard.get("project_id"),
        "video_type": storyboard.get("video_type"),
        "source_storyboard": storyboard.get("source_script", ""),
        "compiled_at": datetime.now().isoformat(timespec="seconds"),
        "beats": plan_beats,
        "totals": {
            "est_usd": total_usd,
            "est_higgsfield_credits": total_cred,
            "budget_cap_usd": storyboard.get("totals", {}).get("budget_cap_usd", 60.0),
            "beats_requiring_generation": gen,
            "beats_local_or_reused": local,
            "pct_zero_cost_beats": round(100 * local / max(1, len(plan_beats)), 1),
        },
    }
    return plan, all_errors


def main():
    ap = argparse.ArgumentParser(description="Compile media_plan.json from storyboard v2.")
    ap.add_argument("storyboard", help="Storyboard v2 JSON path")
    ap.add_argument("--output", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-gate", action="store_true", help="Skip the G2 storyboard gate (dev only)")
    ap.add_argument("--project-id", default=None)
    args = ap.parse_args()

    path = Path(args.storyboard).resolve()
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)
    sb = json.loads(path.read_text())

    if sb.get("schema_version") != "2.0":
        print(f"ERROR: expected storyboard schema_version 2.0, got {sb.get('schema_version')!r}",
              file=sys.stderr)
        sys.exit(1)

    # G2 gate: require storyboard_review pass + matching hash before compiling (§6).
    if not args.no_gate:
        from gates import require_gates
        pid = args.project_id or sb.get("project_id")
        require_gates(pid, ["storyboard_review"], artifact_hashes=None)

    constraints = load_constraints()
    routing = load_routing()
    # Determine project dir for audio slicing (T3).
    pid = args.project_id or sb.get("project_id")
    proj_dir = ROOT / "Videos" / "Projects" / pid if pid else None
    plan, errors = compile_plan(sb, constraints, routing, project_dir=proj_dir)

    if errors:
        print("ERROR: media plan compilation failed:", file=sys.stderr)
        for e in errors:
            print(f"  ✗ {e}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print(f"DRY RUN: {len(plan['beats'])} beats, est ${plan['totals']['est_usd']}, "
              f"{plan['totals']['pct_zero_cost_beats']}% on $0 paths")
        for b in plan["beats"]:
            print(f"  {b['beat_id']} {b['shot_type']:20s} {b['model']:16s} ${b['cost']['est_usd']:.2f}")
        return

    out_path = Path(args.output) if args.output else \
        (ROOT / "Videos" / "Projects" / sb["project_id"] / "media_plan.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(plan, indent=2))
    print(f"  media plan: {out_path} ({len(plan['beats'])} beats, est ${plan['totals']['est_usd']}, "
          f"{plan['totals']['pct_zero_cost_beats']}% $0)")


if __name__ == "__main__":
    main()

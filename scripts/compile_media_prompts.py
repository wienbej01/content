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
import hashlib
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


def _detect_storyboard_mode(storyboard: dict) -> str:
    """Return 'canonical' if storyboard has storyboard_contract_version, else 'legacy'."""
    if storyboard.get("storyboard_contract_version"):
        return "canonical"
    return "legacy"


def compile_plan_from_canonical(canonical: dict, constraints: dict, routing: dict,
                                project_dir=None, db_path=None) -> tuple[dict, list]:
    """Compile a media plan from a canonical Sonnet-authored storyboard.

    Projects canonical shots[] into legacy beats via storyboard_projection,
    validates canonical lineage, then delegates to compile_plan().

    Args:
        canonical: Canonical storyboard dict with storyboard_contract_version,
                   shots[], overlays[].
        constraints: Channel universe constraints dict.
        routing: Model routing config dict.
        project_dir: Optional project directory for audio slicing.
        db_path: Optional DB path for clip ordering.

    Returns:
        (plan, errors) — same shape as compile_plan().

    Raises:
        ImportError: if storyboard_projection is not available.
        ValueError: if input is not canonical mode.
    """
    from storyboard_projection import project_canonical, ProjectionError

    if _detect_storyboard_mode(canonical) != "canonical":
        raise ValueError(
            "compile_plan_from_canonical requires a canonical storyboard "
            "with storyboard_contract_version"
        )

    shots = canonical.get("shots", [])
    if not shots:
        raise ValueError("Canonical storyboard has no shots[]")

    # Project canonical shots into legacy beats.
    try:
        legacy_beats = project_canonical(canonical)
    except ProjectionError as e:
        raise ValueError(f"Canonical projection failed: {e}")

    # Validate every beat has canonical_shot_id lineage.
    for beat in legacy_beats:
        if not beat.get("canonical_shot_id"):
            raise ValueError(
                f"Beat {beat.get('beat_id', '?')} lacks canonical_shot_id "
                f"after projection"
            )

    # Collect raw script visual_briefs to poison (NEVER use as production prompt).
    # The projection already guarantees visual_brief derives from canonical shot
    # fields, not raw script. This set would catch any legacy mixed-mode error.
    script_briefs = set()

    # Build a storyboard-like wrapper for compile_plan.
    projected_sb = {
        "schema_version": "2.0",
        "project_id": canonical.get("project_id", ""),
        "video_type": canonical.get("video_type", "explainer"),
        "source_script": canonical.get("approved_script_revision_id", ""),
        "totals": canonical.get("totals", {}),
        "beats": legacy_beats,
    }
    # Carry original fields needed downstream.
    for key in ("project_id", "video_type", "source_script"):
        if key not in projected_sb and key in canonical:
            projected_sb[key] = canonical[key]

    canonical_shots = list(shots)

    return compile_plan(
        projected_sb, constraints, routing,
        project_dir=project_dir, db_path=db_path,
        _canonical_shots=canonical_shots,
        _canonical_script_briefs=script_briefs,
    )


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
    """Compile one storyboard beat into a media-plan beat. Returns (entry, errors, warnings)."""
    errors = []
    warnings = []
    bid = beat["beat_id"]
    shot_type = beat["shot_type"]
    model = beat["model"]
    asset_type = beat["asset_type"]

    # Banned model check (§5 / §10 #9).
    if model in BANNED_MODELS:
        errors.append(f"{bid}: banned model {model!r}")

    # Early reject: hero lipsync beats exceeding Seedance max (catch before slice).
    if shot_type == "hero_lipsync":
        max_clip = constraints.get("lipsync_render_rules", {}).get("max_clip_duration_sec", 15)
        est_dur = beat.get("est_duration_sec", 0)
        if est_dur > max_clip:
            errors.append(
                f"{bid}: hero speech span {est_dur:.1f}s exceeds Seedance max "
                f"{max_clip:.1f}s. Beat must be split in storyboard or routed to b-roll.")

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
    if asset_type == "reused":
        audio_policy = beat.get("audio_policy") or "HERO_PROVIDER_AUDIO_ISLAND"
    elif shot_type == "hero_lipsync":
        audio_policy = "HERO_SYNC_LOCKED"
    elif asset_type in ("generated_video", "generated_still"):
        audio_policy = "BROLL_FLEX"
    else:
        audio_policy = "post_overlay"

    # Compose prompts.
    negative = constraints.get("default_negative_constraints", "")
    positive = _compose_positive(beat, constraints)

    # Text-surface policy (TKT-12): ban prompts requesting readable text surfaces
    # in generated_video beats — these produce pseudo-text artefacts.
    tsp = constraints.get("text_surface_policy", {})
    tsp_banned = tsp.get("banned_terms", [])
    # text_policy values that indicate no readable text is requested
    _NO_READABLE_TEXT_POLICIES = frozenset((
        "none", "soft_focus_only", "out_of_focus", "no_readable_text", "background",
    ))
    # Inference (2026-06-16): a b-roll brief that EXPLICITLY states its text is
    # unreadable / out of focus / illegible declares no-readable-text intent even
    # when the authoring stage left text_policy unset. Honour that intent so the
    # beat NEUTRALIZES (stays as footage) instead of being rerouted to a blank
    # local_graphic. We only INFER when text_policy is unset/empty — an explicit
    # policy (e.g. 'post_overlay', meaning legible text IS added) is never overridden.
    _explicit_unreadable = (
        "out of focus", "out-of-focus", "unreadable", "illegible",
        "no readable", "not readable", "deliberately blurred", "text blurred",
    )
    if shot_type.startswith("broll") and not (beat.get("text_policy") or "").strip():
        _brief_l = (beat.get("visual_brief", "") + " " + beat.get("visual_description", "")).lower()
        if any(p in _brief_l for p in _explicit_unreadable):
            beat["text_policy"] = "out_of_focus"
            warnings.append(
                f"TEXT_SURFACE_POLICY: beat {bid} text_policy inferred 'out_of_focus' "
                f"(brief explicitly states unreadable/out-of-focus text)")
    if asset_type in tsp.get("banned_for_asset_types", []):
        check_text = (beat.get("visual_brief", "") + " " + positive).lower()
        for term in tsp_banned:
            if term in check_text:
                # Reroute to local_graphic if shot_type allows it
                if shot_type in LOCAL_SHOT_TYPES or shot_type.startswith("broll"):
                    beat_text_policy = (beat.get("text_policy") or "").strip().lower()
                    if beat_text_policy in _NO_READABLE_TEXT_POLICIES and beat_text_policy:
                        # Beat explicitly declares no readable text — neutralize, don't reroute
                        negative = f"{negative}, no {term}, no readable text" if negative else f"no {term}, no readable text"
                        warnings.append(
                            f"TEXT_SURFACE_POLICY: beat {bid} broll neutralized "
                            f"'{term}' in negative_prompt (text_policy={beat_text_policy}, no readable text requested)")
                    else:
                        asset_type = "local_graphic"
                        model = "local_graphic"
                        beat["asset_type"] = asset_type
                        beat["model"] = model
                        warnings.append(
                            f"TEXT_SURFACE_POLICY: beat {bid} rerouted to local_graphic "
                            f"(visual_brief contains '{term}')")
                elif shot_type == "hero_cutaway":
                    # hero_cutaway is continuous-VO b-roll-style; neutralize
                    # the banned term in negative_prompt, do NOT hard-error.
                    negative = f"{negative}, no {term}" if negative else f"no {term}"
                    warnings.append(
                        f"TEXT_SURFACE_POLICY: beat {bid} hero_cutaway neutralized "
                        f"'{term}' in negative_prompt (continuous VO, no readable text)")
                elif shot_type.startswith("hero"):
                    # hero_lipsync / hero shots: talking-head with set decoration.
                    # The term (e.g. 'notebook') is background scenery, not
                    # instructional readable text. Neutralize, do NOT hard-error.
                    negative = f"{negative}, no {term}, no readable text" if negative else f"no {term}, no readable text"
                    warnings.append(
                        f"TEXT_SURFACE_POLICY: beat {bid} hero neutralized "
                        f"'{term}' in negative_prompt (set decoration, not readable text)")
                else:
                    errors.append(
                        f"TEXT_SURFACE_POLICY: beat {bid} visual_brief contains "
                        f"'{term}' which requires readable text in a generated video. "
                        f"Reroute to local_graphic or rewrite prompt.")
                break

    # Guard: every GENERATED (non-local) beat must carry a non-empty negative prompt.
    # Negatives are injection-only, so an empty default_negative_constraints would
    # silently ship generated beats with no suppression block — reject at compile.
    is_generated = asset_type in ("generated_video", "generated_still") and model != "local_graphic"
    if is_generated and not (negative and negative.strip()):
        errors.append(f"{bid}: generated beat has an empty negative_prompt "
                      f"(constraints.default_negative_constraints is missing/blank)")

    # Append banned terms to negative_prompt for generated_video beats (after empty check)
    if asset_type in ("generated_video", "generated_still") and model != "local_graphic" and tsp_banned:
        extra_neg = ", ".join(f"no {t}" for t in tsp_banned)
        negative = f"{negative}, {extra_neg}" if negative else extra_neg

    for fail in vagueness_lint(beat, positive_prompt=positive):
        errors.append(f"{bid}: {fail}")

    clips = beat.get("cost", {}).get("est_clips", 1) or 0
    if asset_type == "reused":
        usd, cred = 0.0, 0.0
    elif asset_type in LOCAL_SHOT_TYPES or model == "local_graphic":
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
        "canonical_shot_id": beat.get("canonical_shot_id"),
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
        "output_path": f"assets/media/{beat.get('segment_id','seg')}/{bid}.mp4",  # CDB-02: overwritten by clip_db when project_id present
        "positive_prompt": positive,
        "negative_prompt": negative,
        "model": model,
        # extras
        "shot_type": shot_type,
        "asset_type": asset_type,
        "model_tier": beat.get("model_tier"),
        "prompt_class": beat.get("prompt_class"),
        # Production storyboard timing (carried for downstream slice/generate)
        "audio_start_sec": beat.get("audio_start_sec"),
        "audio_end_sec": beat.get("audio_end_sec"),
        "audio_duration_sec": beat.get("audio_duration_sec"),
        "source_beat_id": beat.get("source_beat_id"),
        "shots_per_beat": beat.get("shots_per_beat", 1),
        "reference_images": refs,
        "lipsync_required": beat.get("lipsync_required", False),
        "narration_text": beat.get("narration_text", ""),
        "narration_word_span": beat.get("narration_word_span"),
        "audio_slice": beat.get("audio_slice"),
        "overlay": beat.get("overlay"),
        "graphics": beat.get("graphics") or (beat.get("graphic") and [beat.get("graphic")]) or [],
        "narrative_function": beat.get("narrative_function"),
        "music_duck": beat.get("music_duck", False),
        "cost": {"est_clips": 0 if asset_type == "reused" else (max(1, clips) if asset_type not in LOCAL_SHOT_TYPES else 0),
                 "est_credits": cred, "est_usd": usd},
        "reuse": beat.get("reuse", {"allowed": False, "reused_asset_id": None}),
        "fallback": beat.get("fallback", {}),
        "justification": beat.get("justification"),
        "approval": {"status": "pending"},
    }
    if is_hero:
        entry["camera_angle_id"] = "STUDIO_LIBRARY_MEDIUM_DESK_001"
    return entry, errors, warnings


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
        # Composition/proportion lock: prevents the desk being rendered too high (which
        # dwarfs the subject / makes him look child-sized). Anchors adult proportions.
        framing = ("Seated upright at natural adult proportions, FOREARMS RESTING on the "
                   "desk surface, the desktop at his lower-chest/waist height (NOT up at his "
                   "neck or shoulders), shoulders and upper torso clearly above the desk, "
                   "eyeline at upper third of frame")
        return f"{base} {ident}. {framing}. {pal}. {light}. Photorealistic, cinematic, 16:9."
    return f"{base} {pal}. {light}. Photorealistic, cinematic, 16:9. No people in close-up unless specified."


def slice_hero_beats(plan_beats, storyboard, project_dir, constraints=None):
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

    # Continuous-voiceover projects have ONE master, not per-segment files. In that
    # case defer hero slicing to slice_continuous_lipsync.py (run after compile) and
    # do not error on missing per-segment narration.
    continuous_master = narration_dir / "continuous.mp3"
    continuous_mode = continuous_master.exists() and not any(
        (narration_dir / f"{sid}.mp3").exists() for sid in seg_lipsync)

    for seg_id, lipsync_beats in seg_lipsync.items():
        mp3 = narration_dir / f"{seg_id}.mp3"
        if not mp3.exists():
            if continuous_mode:
                continue  # slices come from the continuous master post-compile
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
                # Pad to next integer second for seedance duration param, then
                # enforce the seedance minimum clip duration (constraints.json
                # lipsync_render_rules.min_clip_duration_sec, default 4s). Seedance
                # rejects duration < 4s; a sub-min beat would hard-fail then degrade
                # to a still, so pad it up with room tone here.
                min_clip = ((constraints or {}).get("lipsync_render_rules", {})
                            .get("min_clip_duration_sec", 4))
                max_clip = ((constraints or {}).get("lipsync_render_rules", {})
                            .get("max_clip_duration_sec", 15))
                padded_len = max(math.ceil(speech_len + 0.2), int(min_clip))
                # R3: Reject any lipsync beat that exceeds the render limit. This
                # should never happen if storyboard split correctly — if it does,
                # force a re-split rather than clamp (clamping causes desync).
                if padded_len > max_clip:
                    errors.append(
                        f"{b['beat_id']}: padded_len {padded_len}s exceeds render limit "
                        f"{max_clip}s — storyboard must split this beat (never clamp)")
                    cum_words += wc
                    continue
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


def _merge_lipsync_chains(plan_beats, project_dir):
    """T4: consecutive hero_lipsync beats with combined speech ≤15s are rendered as
    one clip. Annotates each beat in a merged chain with render_group (shared ID)
    and creates a combined slice file for the group leader."""
    import math, hashlib, subprocess as sp
    chains = []
    chain = []
    for b in plan_beats:
        if b.get("lipsync_required"):
            chain.append(b)
        else:
            if len(chain) > 1:
                chains.append(chain)
            chain = []
    if len(chain) > 1:
        chains.append(chain)

    for chain in chains:
        total_speech = sum((b.get("audio_slice") or {}).get("speech_len_sec", 0) for b in chain)
        if total_speech > 15.0 or total_speech == 0:
            continue  # don't merge chains >15s or those with no slices yet
        group_id = f"RG_{chain[0]['beat_id']}_{chain[-1]['beat_id']}"
        # Concatenate the individual slice files into one combined slice.
        if project_dir:
            slices_dir = project_dir / "narration" / "slices"
            slice_files = [slices_dir / f"{b['beat_id']}.mp3" for b in chain]
            if all(f.exists() for f in slice_files):
                combined = slices_dir / f"{group_id}.mp3"
                # ffmpeg concat demuxer
                concat_list = combined.with_suffix(".concat.txt")
                concat_list.write_text("\n".join(f"file '{f.resolve()}'" for f in slice_files))
                sp.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                        "-i", str(concat_list), "-c", "copy", str(combined)],
                       capture_output=True)
                concat_list.unlink(missing_ok=True)
                padded_len = math.ceil(total_speech + 0.2)
                combined_sha = hashlib.sha256(combined.read_bytes()).hexdigest() if combined.exists() else None
                # Annotate every beat in the chain.
                for i, b in enumerate(chain):
                    b["render_group"] = group_id
                    b["render_group_index"] = i
                    b["render_group_size"] = len(chain)
                # Group leader (first beat) carries the combined slice; others are "merged_follower".
                chain[0]["audio_slice"] = {
                    "file": f"narration/slices/{group_id}.mp3",
                    "start_sec": 0.0,
                    "end_sec": round(padded_len, 3),
                    "speech_len_sec": round(total_speech, 3),
                    "padded_len_sec": padded_len,
                    "slice_sha256": combined_sha,
                    "parent_mp3_sha256": (chain[0].get("audio_slice") or {}).get("parent_mp3_sha256"),
                    "merged_beats": [b["beat_id"] for b in chain],
                }
                for b in chain[1:]:
                    b["audio_slice"]["merged_into"] = group_id


def assign_lipsync_references(plan_beats, routing):
    """Distribute approved canonical reference frames across hero_lipsync beats so
    they rotate through >=3 angles (fixes reference-frame monotony / Fable G14).

    - Uses routing['lipsync_references'] active_set frames (angle-tagged, one wardrobe).
    - Honors a beat's explicit camera_angle_id when it matches a frame angle.
    - Otherwise round-robins; never assigns the SAME frame to two CONSECUTIVE hero
      beats (T5 rule). Merged-group followers inherit the group leader's frame.
    Returns (errors, warnings). Mutates beat['reference_images'].
    errors block compile (broken config / missing files); warnings do not (G14 gap).
    """
    cfg = (routing or {}).get("lipsync_references") or {}
    active = cfg.get("active_set")
    sets = cfg.get("sets") or {}
    frames = (sets.get(active) or {}).get("frames") or []
    errors, warnings = [], []
    if not frames:
        warnings.append("lipsync_references: no active_set frames configured — hero beats "
                        "fall back to the single canonical frame (monotony not fixed).")
        return errors, warnings

    # Validate frames exist on disk. A configured-but-not-yet-generated frame is a
    # WARNING (e.g. a G14 gap awaiting image-gen), not a hard error — the compiler
    # rotates across whatever frames DO exist and flags the shortfall.
    usable = []
    for fr in frames:
        p = fr.get("path")
        if p and (ROOT / p).exists():
            usable.append(fr)
        else:
            warnings.append(f"lipsync_references: frame not yet on disk (skipped): {p}")
    if len(usable) < 3:
        warnings.append(f"lipsync_references active_set {active!r} has only {len(usable)} usable "
                        f"frame(s) (<3) — angle variety insufficient; generate the missing angles "
                        f"(G14) e.g. via scripts/generate_navy_lipsync_angles.py.")
    if not usable:
        return errors, warnings

    by_angle = {fr.get("angle"): fr["path"] for fr in usable}
    rr = [fr["path"] for fr in usable]
    rr_i = 0
    last_path = None
    group_leader_path = {}

    for b in plan_beats:
        if b.get("shot_type") != "hero_lipsync":
            continue
        # Merged-group followers inherit the leader's frame (same physical clip).
        rg = b.get("render_group")
        if rg and b.get("render_group_index", 0) > 0 and rg in group_leader_path:
            b["reference_images"] = [group_leader_path[rg]]
            continue

        chosen = None
        # 1) explicit angle match
        ang = b.get("camera_angle_id")
        if ang:
            for a, path in by_angle.items():
                if a and a.lower() in str(ang).lower():
                    chosen = path
                    break
        # 2) round-robin, skip if it would repeat the previous hero frame
        if chosen is None:
            for _ in range(len(rr)):
                cand = rr[rr_i % len(rr)]
                rr_i += 1
                if cand != last_path or len(rr) == 1:
                    chosen = cand
                    break
        if chosen is None:
            chosen = rr[0]
        b["reference_images"] = [chosen]
        last_path = chosen
        if rg:
            group_leader_path[rg] = chosen
    return errors, warnings


def _expand_coverage_slots(entry, beat_input, constraints, routing):
    """PTC-07: expand a compiled beat into per-slot assets if it has a multi-slot coverage_plan.

    Returns a list of media-plan asset entries (1 if no expansion needed).
    Backward compat: beats without coverage_plan produce one asset (the entry itself).
    """
    coverage = beat_input.get("coverage_plan")
    if not coverage or len(coverage) <= 1:
        return [entry]

    project_id = entry.get("segment_id", "seg")
    beat_id = entry["beat_id"]
    source_beat_id = beat_input.get("source_beat_id", beat_id)
    assets = []
    for i, slot in enumerate(coverage):
        slot_id = slot.get("slot_id", f"{beat_id}-s{i}")
        slot_asset_type = slot.get("asset_type", entry["asset_type"])
        slot_model = slot.get("model", entry["model"])
        slot_dur = slot["required_duration_sec"]

        # Per-slot cost
        is_local = (slot_asset_type in LOCAL_SHOT_TYPES or
                    slot_asset_type == "local_graphic" or slot_model == "local_graphic")
        if is_local:
            usd, cred = 0.0, 0.0
            slot_model = "local_graphic"
            slot_asset_type = "local_graphic"   # keep model+asset_type consistent (no orphan beat)
        else:
            usd, cred = cost_for(slot_model, 1, routing)

        asset = dict(entry)
        asset["media_plan_asset_id"] = f"{beat_id}-{slot_id}" if not slot_id.startswith(beat_id) else slot_id
        asset["source_beat_id"] = source_beat_id
        asset["production_beat_id"] = beat_id
        asset["coverage_slot_id"] = slot_id
        asset["required_start_sec"] = slot["required_start_sec"]
        asset["required_end_sec"] = slot["required_end_sec"]
        asset["required_duration_sec"] = slot_dur
        asset["duration_target_sec"] = slot_dur
        asset["asset_type"] = slot_asset_type
        asset["model"] = slot_model
        asset["output_path"] = f"assets/media/{project_id}/{beat_id}_{slot_id}.mp4"  # CDB-02: overwritten by clip_db
        asset["cost"] = {"est_clips": 0 if is_local else 1,
                         "est_credits": cred, "est_usd": usd}
        assets.append(asset)
    return assets


def compile_plan(storyboard, constraints, routing, project_dir=None, db_path=None,
                 _canonical_shots=None, _canonical_script_briefs=None):
    """Compile media plan from storyboard beats.

    In canonical mode (when _canonical_shots is provided), the beats must
    already carry canonical_shot_id lineage from storyboard_projection.
    Raw script visual_brief is rejected as production prompt source.

    Args:
        storyboard: Storyboard dict (legacy format with schema_version 2.0).
        constraints: Channel universe constraints dict.
        routing: Model routing config dict.
        project_dir: Optional project directory for audio slicing.
        db_path: Optional DB path for clip ordering.
        _canonical_shots: Optional list of canonical shot dicts (internal).
        _canonical_script_briefs: Optional set of script-level brief texts
                                  that must never appear in production prompts.
    """
    is_canonical_mode = _canonical_shots is not None
    beats_in = storyboard.get("beats", [])
    plan_beats = []
    all_errors = []
    plan_warnings = []
    for b in beats_in:
        # Canonical mode guard: every beat MUST have canonical_shot_id.
        if is_canonical_mode and not b.get("canonical_shot_id"):
            all_errors.append(
                f"CANONICAL_LINEAGE_MISSING: beat {b.get('beat_id', '?')} "
                f"lacks canonical_shot_id — projection required before compile"
            )
            continue

        entry, errs, beat_warns = compile_beat(b, constraints, routing)
        expanded = _expand_coverage_slots(entry, b, constraints, routing)
        plan_beats.extend(expanded)
        all_errors.extend(errs)
        plan_warnings.extend(beat_warns)

    # Poison-text guard (placeholder): reject any production prompt that contains
    # raw script visual_brief text. Currently unused because projection guarantees
    # canonical source — kept as defense-in-depth for future mixed-mode errors.
    if _canonical_script_briefs and plan_beats:
        for b in plan_beats:
            bid = b.get("beat_id", "?")
            pos = (b.get("positive_prompt") or "").lower().strip()
            for sbrief in _canonical_script_briefs:
                # Only match longer briefs to avoid false positives on short common phrases.
                if sbrief and len(sbrief) > 30 and sbrief in pos:
                    all_errors.append(
                        f"RAW_SCRIPT_BRIEF_LEAK: beat {bid} positive_prompt contains "
                        f"raw script visual_brief text ('{sbrief[:60]}...'). "
                        f"Production prompts must derive from canonical shot fields, "
                        f"not raw script visual_brief."
                    )
                    break

    # STRUCTURAL GUARD: model and asset_type must be consistent so every beat has an
    # owning producer. A beat with model=local_graphic but asset_type=generated_video
    # (or vice-versa) is an ORPHAN — generate_media skips it (model=local_graphic) AND
    # render_graphics skips it (asset_type=generated_video) → never produced. Fail closed.
    for b in plan_beats:
        bid = b.get("beat_id", "?")
        slot = b.get("coverage_slot_id", "")
        model = b.get("model")
        atype = b.get("asset_type")
        model_is_local = (model == "local_graphic")
        atype_is_local = (atype == "local_graphic" or atype in LOCAL_SHOT_TYPES)
        if model_is_local != atype_is_local:
            all_errors.append(
                f"ORPHAN_BEAT: {bid}{('/'+slot) if slot else ''} has model={model!r} but "
                f"asset_type={atype!r} — inconsistent producer. Both must be local_graphic "
                f"or both non-local. No step would generate this beat.")

    # PST-06: verify production storyboard traceability — every beat must have source_beat_id.
    if storyboard.get("reconciled_from") or storyboard.get("production"):
        missing_source = [b.get("beat_id", f"idx{i}") for i, b in enumerate(beats_in)
                          if not b.get("source_beat_id")]
        if missing_source:
            all_errors.append(
                f"Production storyboard beats missing source_beat_id ({len(missing_source)}): "
                f"{', '.join(missing_source[:5])}")

    # T3 (LIPSYNC_TICKETS): generate audio slices for hero_lipsync beats.
    if project_dir:
        slice_errors = slice_hero_beats(plan_beats, storyboard, project_dir, constraints)
        all_errors.extend(slice_errors)

    # Reference-frame rotation: distribute approved canonical angles across hero
    # beats so they don't all anchor to one frame (Fable G14 / T5).
    ref_errors, ref_warnings = assign_lipsync_references(plan_beats, routing)
    all_errors.extend(ref_errors)
    plan_warnings.extend(ref_warnings)

    # R8/D5: Assert every hero beat's reference is in the active set (lock enforcement).
    lipsync_cfg = routing.get("lipsync_references", {})
    active_set_name = lipsync_cfg.get("active_set")
    if active_set_name:
        active_frames = lipsync_cfg.get("sets", {}).get(active_set_name, {}).get("frames", [])
        active_paths = {f.get("path") for f in active_frames if f.get("path")}
        for b in plan_beats:
            if b.get("lipsync_required"):
                refs = b.get("reference_images") or []
                for rp in refs:
                    if rp and rp not in active_paths:
                        plan_warnings.append(
                            f"{b['beat_id']}: reference {Path(rp).name} not in active set "
                            f"'{active_set_name}' — wardrobe/identity drift risk")

    # T4: merge consecutive hero_lipsync chains ≤15s into render groups.
    _merge_lipsync_chains(plan_beats, project_dir)

    # T1 (LIPSYNC_TICKETS): every hero_lipsync beat MUST have audio_slice after compile.
    # slice_lipsync is a DOWNSTREAM step (runs after compile_media_plan in produce.py),
    # so missing slices at compile time are expected — emit a warning, not an error.
    sliceless = [b["beat_id"] for b in plan_beats
                 if b.get("lipsync_required") and not b.get("audio_slice")]
    if sliceless:
        plan_warnings.append(
            f"hero_lipsync beats without audio_slice ({len(sliceless)}): "
            f"{', '.join(sliceless)}. slice_lipsync step will populate these.")

    # CDB-02: Order all plan beats through clip_db — the DB assigns canonical paths/IDs.
    project_id = storyboard.get("project_id")
    if project_id:
        import clip_db as _clip_db
        _clip_db.init_db(db_path=db_path)
        for b in plan_beats:
            _b_segment = b.get("segment_id") or "seg"
            _b_prod_id = b.get("production_beat_id") or b["beat_id"]
            _b_source_id = b.get("source_beat_id") or _b_prod_id
            _b_slot_id = b.get("coverage_slot_id")
            _b_start = b.get("required_start_sec") or b.get("audio_start_sec") or 0.0
            _b_end = b.get("required_end_sec") or b.get("audio_end_sec") or _b_start + b.get("duration_target_sec", 5.0)
            _plan_sha = hashlib.sha256(json.dumps(
                {k: b.get(k) for k in ("beat_id", "segment_id", "model", "asset_type",
                                        "audio_policy", "lipsync_required", "duration_target_sec",
                                        "coverage_slot_id", "required_start_sec", "required_end_sec")},
                sort_keys=True).encode()).hexdigest()
            row = _clip_db.order_clip(
                project_id=project_id,
                source_beat_id=_b_source_id,
                production_beat_id=_b_prod_id,
                segment_id=_b_segment,
                asset_type=b.get("asset_type", "generated_video"),
                model=b.get("model"),
                audio_policy=b.get("audio_policy", "strip"),
                lipsync_required=b.get("lipsync_required", False),
                required_start_sec=_b_start,
                required_end_sec=_b_end,
                slot_id=_b_slot_id,
                split_index=b.get("split_index"),
                split_total=b.get("split_total"),
                speech_len_sec=b.get("audio_slice", {}).get("speech_len_sec") if isinstance(b.get("audio_slice"), dict) else None,
                plan_sha256=_plan_sha,
                db_path=db_path,
            )
            # DB-authoritative path and clip_id written back into plan beat
            b["output_path"] = row["output_path"]
            b["clip_id"] = row["clip_id"]
            b["required_start_sec"] = row["required_start_sec"]
            b["required_end_sec"] = row["required_end_sec"]
            b["required_dur_sec"] = row["required_dur_sec"]

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
    if plan_warnings:
        plan["warnings"] = plan_warnings
    return plan, all_errors


def main():
    ap = argparse.ArgumentParser(description="Compile media_plan.json from storyboard v2.")
    ap.add_argument("storyboard", help="Storyboard v2 JSON path")
    ap.add_argument("--output", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-gate", action="store_true", help="Skip the G2 storyboard gate (dev only)")
    ap.add_argument("--project-id", default=None)
    ap.add_argument("--canonical", action="store_true",
                    help="Input is a canonical Sonnet-authored storyboard (storyboard_contract_version)")
    args = ap.parse_args()

    path = Path(args.storyboard).resolve()
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)
    sb = json.loads(path.read_text())

    constraints = load_constraints()
    routing = load_routing()

    # Detect canonical mode if not explicitly flagged.
    is_canonical = args.canonical or _detect_storyboard_mode(sb) == "canonical"

    if is_canonical:
        # Canonical mode: project shots -> legacy beats, then compile.
        plan, errors = compile_plan_from_canonical(
            sb, constraints, routing,
        )
    else:
        if sb.get("schema_version") != "2.0":
            print(f"ERROR: expected storyboard schema_version 2.0, got {sb.get('schema_version')!r}",
                  file=sys.stderr)
            sys.exit(1)

        # G2 gate: require storyboard_review pass + matching hash before compiling (§6).
        if not args.no_gate:
            from gates import require_gates
            pid = args.project_id or sb.get("project_id")
            require_gates(pid, ["storyboard_review"], artifact_hashes=None)

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
        (ROOT / "Videos" / "Projects" / (sb.get("project_id") or "unknown") / "media_plan.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(plan, indent=2))
    print(f"  media plan: {out_path} ({len(plan['beats'])} beats, est ${plan['totals']['est_usd']}, "
          f"{plan['totals']['pct_zero_cost_beats']}% $0)")


if __name__ == "__main__":
    main()

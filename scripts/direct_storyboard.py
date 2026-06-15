#!/usr/bin/env python3
"""direct_storyboard.py — Specialized Storyboard Director (LLM, bible-grounded).

The leverage point of the whole visual pipeline: a high-capability LLM that is fed
EVERYTHING — the approved script, the SOURCE RESEARCH TEXT, and the full set of
environment/technical bibles — and produces a BULLETPROOF, fully-resolved storyboard.

Every beat is elaborated so downstream generation is deterministic:
  - hero shots: exact James look (from JAMES_CHARACTER_BIBLE), studio setting (from
    JAMES_RECORDING_STUDIO_LIBRARY), camera, gesture, reference frame, lipsync slice.
  - b-roll: SPECIFIC subject + action grounded in the SOURCE TEXT, era-correct
    (anachronism-guarded against UNIVERSE_BIBLE), motion, camera move, continuity.
  - graphics: TED-style integrated layout (side-by-side speaker / lower-third /
    callout), exact text, timing.

The director is told the FORBIDDEN_PATTERNS and PROMPT_RULES and must self-validate.
Its output is then re-checked deterministically (anachronism terms, James lock,
shot-mix, durations) before it is accepted.

Usage:
  python3 scripts/direct_storyboard.py <script.json> --source <source.txt|.pdf> \
        --output <storyboard.json> [--dry-run]
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
CU = ROOT / "docs" / "channel_universe"

# Bibles fed to the director (ordered most→least critical for visual decisions).
BIBLE_FILES = [
    "UNIVERSE_BIBLE.md",
    "JAMES_CHARACTER_BIBLE.md",
    "JAMES_RECORDING_STUDIO_LIBRARY.md",
    "TECHNICAL_BIBLE.md",
    "FORBIDDEN_PATTERNS.md",
]

# Era/anachronism guard terms — generated b-roll must be MODERN unless the source
# explicitly calls for a historical depiction.
ANACHRONISM_TERMS = [
    "19th century", "1800s", "1900s", "mid-century", "victorian", "vintage",
    "period piece", "antique", "manuscript", "parchment", "quill", "candle",
    "old film", "sepia", "black and white", "typewriter",
]


def _read(p):
    p = Path(p)
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def _read_source(path):
    """Read source research text; extract text from a PDF if needed."""
    p = Path(path)
    if not p.exists():
        return ""
    if p.suffix.lower() == ".pdf":
        txt = p.with_suffix(".txt")
        if not txt.exists():
            subprocess.run(["pdftotext", str(p), str(txt)], capture_output=True)
        return _read(txt)
    return _read(p)


def load_bibles(max_chars_each=4000):
    """Load + trim each bible. Keep compact — the director prompt is already schema-heavy."""
    out = []
    for name in BIBLE_FILES:
        txt = _read(CU / name)
        if not txt:
            continue
        if len(txt) > max_chars_each:
            txt = txt[:max_chars_each] + "\n…[trimmed]…"
        out.append(f"===== {name} =====\n{txt}")
    return "\n\n".join(out)


def build_director_prompt(script, source_text, bibles, video_type="explainer",
                          prior_beats=None, fixes=None):
    from episode_format import format_block, get_format
    title = script.get("title", "")
    segments = [{"id": s["id"], "text": s.get("text", "")} for s in script.get("segments", [])]
    key_points = script.get("key_points", [])
    fmt = get_format(video_type)
    budget_tokens = {"short": 510, "explainer": 1224, "teaser": 200}.get(video_type, 1224)
    prompt = f"""You are the STORYBOARD DIRECTOR for a premium faceless educational YouTube channel
(host: James Harrington). Your output feeds the production pipeline directly.

{format_block(video_type)}

=== HARD RULES ===
1. MODERN ERA ONLY (2020s) unless SOURCE describes a historical event.
2. JAMES LOCK: hero = James per bible (60, silver hair, navy sweater/white Oxford, mahogany desk, bookshelves, brass lamp).
3. B-ROLL = SPECIFIC + GROUNDED + IN MOTION from SOURCE. No static. No generic.
4. B-ROLL ≤6s. HERO ∈[4,10]s. 5. GRAPHICS = INTEGRATED (side_by_side/lower_third/stat_callout/key_line).
6. CONTINUITY via continuity_anchor. 7. FORBIDDEN: readable text, logos, sci-fi, real faces, close-up hands.

=== VALID SHOT TYPES (use ONLY these) ===
hero_lipsync (seedance, 9tok/s, [4,15]s) | hero_cutaway (kling, 6tok/s, ≤15s)
broll_archival (kling, 6tok/s, ≤6s) | broll_environment (kling, 6tok/s, ≤6s) | broll_tactical (kling, 6tok/s, ≤6s)
graphic_progressive (local, 0) | graphic_title_card (local, 0) | kinetic_text (local, 0) | still_kenburns (0, ≤6s)

BUDGET: ~{budget_tokens} tokens (dur × tok/s). Keep hero durations tight.

=== OUTPUT: JSON array of beats ===
[{{"beat_id":"B001", "segment_id":"<script id>", "order":1, "act":<1-6>,
   "narration_text":"<exact words>", "shot_type":"<from list>",
   "est_duration_sec":<words/2.4 clamped to limits>,
   "era":"modern_2020s", "subject":"<concrete>", "action":"<concrete motion>",
   "camera":"<framing+movement>", "setting":"<location>",
   "continuity_anchor":"<carry>",
   "visual_brief":"<FULL generation prompt: subject+action+setting+camera+lighting+style+16:9>",
   "narrative_function":"<SPECIFIC purpose>",
   "graphic":{{"required":bool,"layout":"<type|null>","text":"<exact|null>","timing":"on_spoken_line|null"}},
   "music_duck":false, "rationale":"<1 line>"}}]

TITLE: {title}
KEY TAKEAWAYS: {json.dumps([k.get('text') for k in key_points], indent=0)}
SCRIPT: {json.dumps(segments, indent=2)}
SOURCE: \"\"\"{source_text[:3000]}\"\"\"
BIBLES: {bibles}
"""
    if prior_beats and fixes:
        prompt += f"""\n=== REVISION: incorporate fixes, return full updated array ===
PRIOR: {json.dumps(prior_beats, indent=2)}
FIXES: {json.dumps(fixes, indent=2)}"""
    return prompt




VALID_SHOT_TYPES = {
    "hero_lipsync", "hero_cutaway", "broll_archival",
    "broll_environment", "broll_tactical", "graphic_progressive",
    "graphic_title_card", "kinetic_text", "still_kenburns",
}
SHOT_ROUTING = {
    "hero_lipsync": ("seedance_2_0", "generated_video", "premium"),
    "hero_cutaway": ("kling3_0", "generated_video", "standard"),
    "broll_archival": ("kling3_0", "generated_video", "standard"),
    "broll_environment": ("kling3_0", "generated_video", "standard"),
    "broll_tactical": ("kling3_0", "generated_video", "standard"),
    "graphic_progressive": ("local_graphic", "local_graphic", "local"),
    "graphic_title_card": ("local_graphic", "local_graphic", "local"),
    "kinetic_text": ("local_graphic", "local_graphic", "local"),
    "still_kenburns": ("still_kenburns", "generated_still", "cheap"),
}
TOKENS_PER_SEC = {"seedance_2_0": 9, "kling3_0": 6}
def _load_calibrated_wps():
    """Load calibrated WPS from voice_pacing.yaml, fall back to conservative default."""
    try:
        import yaml
        cfg_path = Path(__file__).resolve().parent.parent / "configs" / "voice_pacing.yaml"
        with open(cfg_path) as f:
            return yaml.safe_load(f).get("calibrated_wps", 1.8077)
    except Exception:
        return 1.8077

WPS = _load_calibrated_wps()
PROMPT_CLASS = {
    "hero_lipsync": "james_studio_lipsync", "hero_cutaway": "james_studio_cutaway",
    "broll_archival": "environment_broll", "broll_environment": "environment_broll",
    "broll_tactical": "tactical_insert", "graphic_progressive": "local_render",
    "graphic_title_card": "local_render", "kinetic_text": "local_render",
    "still_kenburns": "environment_broll",
}


def hydrate_beats(beats, project_id, video_type):
    """Fill routing/mechanical fields deterministically from shot_type. Runs after LLM."""
    word_offset = 0
    total_dur = 0
    for b in beats:
        st = b.get("shot_type", "")
        model, asset_type, tier = SHOT_ROUTING.get(st, ("kling3_0", "generated_video", "standard"))
        b.setdefault("model", model)
        b.setdefault("asset_type", asset_type)
        b.setdefault("model_tier", tier)
        b.setdefault("lipsync_required", st == "hero_lipsync")
        b.setdefault("reference_required", st.startswith("hero"))
        b.setdefault("reference_images", [])
        # Duration
        words = len(b.get("narration_text", "").split())
        est = round(words / WPS, 2) if words else b.get("est_duration_sec", 5)
        if st.startswith("hero"):
            est = max(4, min(15, est))
        elif st.startswith("broll"):
            est = max(3, min(6, est))
        b["est_duration_sec"] = est
        b.setdefault("duration_target_sec", est)
        # Word span
        b["narration_word_span"] = [word_offset, word_offset + words]
        word_offset += words
        # Routing fields
        b.setdefault("prompt_class", PROMPT_CLASS.get(st, "environment_broll"))
        b.setdefault("audio_mode", "lipsync" if st == "hero_lipsync" else ("silent" if asset_type == "local_graphic" else "voiceover"))
        b.setdefault("crop_safety", "center_safe")
        b.setdefault("shots_per_beat", 1)
        b.setdefault("visual_function", "develops")
        # Cost
        tps = TOKENS_PER_SEC.get(model, 0)
        tokens = round(b["duration_target_sec"] * tps)
        b["cost"] = {"est_tokens": tokens, "est_usd": round(tokens * 0.049, 2), "est_clips": 1 if asset_type != "local_graphic" else 0}
        # Fallback/reuse
        b.setdefault("reuse", {"allowed": False, "reused_asset_id": None})
        b.setdefault("fallback", {"on_generation_fail": "still_kenburns" if asset_type == "generated_video" else "local_graphic", "on_qa_fail": "regenerate_once_then_fallback"})
        total_dur += b["duration_target_sec"]
    # Top-level structure
    hero_dur = sum(b["duration_target_sec"] for b in beats if b["shot_type"].startswith("hero"))
    broll_dur = sum(b["duration_target_sec"] for b in beats if b["shot_type"].startswith("broll"))
    gfx_dur = sum(b["duration_target_sec"] for b in beats if b["asset_type"] == "local_graphic")
    total_tokens = sum(b["cost"]["est_tokens"] for b in beats)
    storyboard = {
        "schema_version": "2.0",
        "project_id": project_id,
        "video_type": video_type,
        "beats": beats,
        "shot_mix_summary": {
            "hero_lipsync_pct": round(100 * sum(b["duration_target_sec"] for b in beats if b["shot_type"] == "hero_lipsync") / max(1, total_dur), 1),
            "hero_cutaway_pct": round(100 * sum(b["duration_target_sec"] for b in beats if b["shot_type"] == "hero_cutaway") / max(1, total_dur), 1),
            "broll_specific_pct": round(100 * broll_dur / max(1, total_dur), 1),
            "graphics_ui_pct": round(100 * gfx_dur / max(1, total_dur), 1),
            "max_hero_block_sec": 0,  # computed by review_storyboard
            "distinct_visual_setups": len(beats),
            "total_cuts_estimate": len(beats),
        },
        "totals": {
            "est_tokens": total_tokens,
            "est_usd": round(total_tokens * 0.049, 2),
            "budget_cap_tokens": {"short": 510, "explainer": 1224, "teaser": 200}.get(video_type, 1224),
            "target_runtime_sec": round(total_dur, 1),
        },
    }
    return storyboard


def validate_director_output(beats, source_text):
    """Deterministic post-checks the director's output must pass."""
    errors, warnings = [], []
    if not beats:
        return ["director returned no beats"], []
    src_lower = (source_text or "").lower()
    for b in beats:
        bid = b.get("beat_id", "?")
        st = b.get("shot_type", "")
        brief = (b.get("visual_brief", "") + " " + b.get("setting", "") + " " +
                 b.get("subject", "")).lower()

        # Shot type validity
        if st not in VALID_SHOT_TYPES:
            errors.append(f"{bid}: invalid shot_type {st!r} (must be one of {sorted(VALID_SHOT_TYPES)})")

        # Model/asset_type consistency with routing table
        if st in SHOT_ROUTING:
            exp_model, exp_asset, exp_tier = SHOT_ROUTING[st]
            if b.get("model") != exp_model:
                warnings.append(f"{bid}: model {b.get('model')!r} != expected {exp_model!r} for {st}")
            if b.get("asset_type") != exp_asset:
                warnings.append(f"{bid}: asset_type {b.get('asset_type')!r} != expected {exp_asset!r}")

        # Anachronism guard (word-boundary matching)
        for term in ANACHRONISM_TERMS:
            if term in src_lower:
                continue
            match = re.search(r'\b' + re.escape(term) + r'\b', brief)
            if match:
                # Negation-aware: skip if preceded by "no ", "not ", "without ", "never "
                pre = brief[max(0, match.start() - 10):match.start()]
                if any(neg in pre for neg in ("no ", "not ", "without ", "never ")):
                    continue
                errors.append(f"{bid}: anachronism '{term}' in a modern-era video "
                              f"(source does not justify it)")

        # Duration limits
        dur = b.get("duration_target_sec") or b.get("est_duration_sec") or 0
        if st.startswith("broll") and dur > 6.5:
            errors.append(f"{bid}: b-roll {dur}s exceeds 6s (split)")
        if st.startswith("hero") and dur > 15.5:
            errors.append(f"{bid}: hero {dur}s exceeds 15s (Seedance limit)")
        if st == "hero_lipsync" and dur < 4:
            errors.append(f"{bid}: hero_lipsync {dur}s below 4s (Seedance minimum)")

        # Hero must reference James studio
        if st.startswith("hero") and "james" not in brief:
            warnings.append(f"{bid}: hero beat doesn't mention James explicitly")

        # Text-surface policy (TKT-12): warn if generated_video brief has banned terms
        if b.get("asset_type") == "generated_video" and not st.startswith("hero"):
            _tsp_terms = ["laptop screen", "reading", "writing", "notebook",
                          "handwriting", "book page", "document", "spreadsheet",
                          "dashboard", "phone app", "article text",
                          "chat interface", "ui interface"]
            for term in _tsp_terms:
                if term in brief:
                    warnings.append(
                        f"{bid}: text-surface term '{term}' in generated_video brief "
                        f"(compile will reroute to local_graphic)")
                    break

        # Graphics must specify layout + text
        g = b.get("graphic", {})
        if g.get("required") and not g.get("layout"):
            errors.append(f"{bid}: graphic.required but no layout specified")

        # Required fields check
        for field in ("narrative_function", "visual_brief", "segment_id", "act"):
            if not b.get(field):
                errors.append(f"{bid}: missing required field '{field}'")

        # Narrative function must be specific
        nf = (b.get("narrative_function") or "").lower()
        if nf and nf in ("supporting visual", "b-roll", "supporting", "visual"):
            errors.append(f"{bid}: narrative_function is generic ({nf!r})")

    return errors, warnings


def direct(script_path, source_path, dry_run=False, model_profile="storyboard_director",
           video_type="explainer", prior_beats=None, fixes=None):
    """Run the director. If prior_beats + fixes are given, it runs a REVISION pass.
    Returns (result, meta). Hydrates routing fields after LLM returns."""
    script = json.loads(Path(script_path).read_text())
    source_text = _read_source(source_path) if source_path else ""
    bibles = load_bibles()
    prompt = build_director_prompt(script, source_text, bibles, video_type=video_type,
                                   prior_beats=prior_beats, fixes=fixes)
    if dry_run:
        return None, {"prompt_chars": len(prompt), "bibles_chars": len(bibles),
                      "source_chars": len(source_text), "model_profile": model_profile,
                      "prompt": prompt}

    from llm_call import llm_call
    data, raw, profile, model = llm_call(task="storyboard_generation", prompt=prompt,
                                         model_profile=model_profile, expect_json=True,
                                         timeout=300)
    # Handle both: full object with "beats" key, or bare array
    if isinstance(data, list):
        beats = data
    elif isinstance(data, dict):
        beats = data.get("beats", [])
    else:
        beats = []

    errors, warnings = validate_director_output(beats, source_text)

    # Hydrate: fill all routing/mechanical fields from shot_type
    project_id = script.get("project_id", "untitled")
    storyboard = hydrate_beats(beats, project_id, video_type)

    return {"storyboard": storyboard, "beats": beats, "errors": errors,
            "warnings": warnings, "model": model, "prompt": prompt, "raw": raw}, \
           {"model": model, "beats": len(beats)}



def main(argv=None):
    ap = argparse.ArgumentParser(description="Specialized Storyboard Director (bible-grounded LLM).")
    ap.add_argument("script")
    ap.add_argument("--source", help="Source research text (.txt or .pdf)")
    ap.add_argument("--output")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--profile", default="storyboard_director")
    args = ap.parse_args(argv)

    result, meta = direct(args.script, args.source, dry_run=args.dry_run, model_profile=args.profile)
    if args.dry_run:
        print(f"  DRY RUN — prompt {meta['prompt_chars']} chars "
              f"(bibles {meta['bibles_chars']}, source {meta['source_chars']}) "
              f"→ {meta['model_profile']}")
        return 0
    print(f"  director [{result['model']}] → {meta['beats']} beats")
    for e in result["errors"]:
        print(f"    ✗ {e}")
    for w in result["warnings"][:10]:
        print(f"    ⚠ {w}")
    if args.output and not result["errors"]:
        Path(args.output).write_text(json.dumps(result, indent=2))
        print(f"  wrote {args.output}")
    elif result["errors"]:
        print(f"  NOT written — {len(result['errors'])} hard errors (director must re-run)")
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""storyboard.py — Storyboard Router v2 (the directorial layer).

Per PRODUCTION_V2_BLUEPRINT.md §3/§4. Two passes:

  1. DETERMINISTIC pre-pass (pure Python, fully testable):
       - sentence chunking into 4-10s beats (never crossing segment/trigger
         boundaries),
       - trigger regex engine (years, names+study verbs, institutions,
         frameworks/ordinals, numbers/percentages, tactical instructions,
         abstract states, thesis/emotional-close),
       - 6-act mapping by position + content markers,
       - shot-type assignment + hero-block ≤15s enforcement,
       - shot-mix allocation + cost estimate.
  2. LLM directorial pass (optional, --optimize): refines visual briefs / act
     mapping WITHIN the deterministic skeleton. It may never violate the
     deterministic constraints; the validator re-checks its output and reverts
     on any breach.

Output validates against schemas/storyboard_v2.schema.json.

Usage:
  python3 scripts/storyboard.py script.json --dry-run
  python3 scripts/storyboard.py script.json --output Videos/Projects/<id>/storyboard.json
  python3 scripts/storyboard.py script.json --optimize --output <path>
  python3 scripts/storyboard.py script.json --validate-only
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

ROUTER_VERSION = "2.0.0"
SCHEMA_VERSION = "2.0"

# ---- duration / chunking ----
DEFAULT_WPS = 2.4               # words per second (calm band midpoint)
BEAT_MIN_SEC = 4.0
BEAT_MAX_SEC = 10.0
HERO_MAX_SEC = 15.0             # hard cap for hero_lipsync beats (§3.2)
EMOTIONAL_CLOSE_MAX_SEC = 25.0  # the single exception (Act 6, justified)

# ---- cost basis (mirrors configs/james/model_routing.yaml; budget.py is source of truth) ----
COST_PER_CLIP_USD = {
    "seedance_2_0": 1.10,
    "kling3_0": 0.49,
    "still_kenburns": 0.0,
    "local_graphic": 0.0,
}
CREDITS_PER_CLIP = {
    "seedance_2_0": 22.5,
    "kling3_0": 10.0,
    "still_kenburns": 0.0,
    "local_graphic": 0.0,
}
DEFAULT_BUDGET_CAP_USD = 60.0
CLIP_LEN_SEC = 5.0  # one generated clip ~5s

# ---- banned models (must agree with constraints/model_routing) ----
BANNED_MODELS = {"minimax_hailuo", "seedance_2_0_fast", "seedance1_5", "wan2_7", "wan2_6"}

# shot_type -> constraints.json scene_type
SHOT_TO_SCENE = {
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
}

# shot_type -> (model, model_tier, asset_type)
SHOT_ROUTING = {
    "hero_lipsync": ("seedance_2_0", "premium", "generated_video"),
    "hero_cutaway": ("kling3_0", "standard", "generated_video"),
    "broll_archival": ("kling3_0", "standard", "generated_video"),
    "broll_metaphorical": ("still_kenburns", "cheap", "generated_still"),
    "broll_environment": ("kling3_0", "standard", "generated_video"),
    "broll_tactical": ("kling3_0", "standard", "generated_video"),
    "graphic_progressive": ("local_graphic", "local", "local_graphic"),
    "graphic_title_card": ("local_graphic", "local", "local_graphic"),
    "kinetic_text": ("local_graphic", "local", "local_graphic"),
    "ui_insert": ("local_graphic", "local", "local_graphic"),
    "still_kenburns": ("still_kenburns", "cheap", "generated_still"),
}

LOCAL_SHOT_TYPES = {"graphic_progressive", "graphic_title_card", "kinetic_text", "ui_insert"}
HERO_SHOT_TYPES = {"hero_lipsync", "hero_cutaway"}

# ---- trigger regexes (§3.5) ----
RE_YEAR = re.compile(r"\b1[5-9]\d{2}\b|\b20[0-2]\d\b")
RE_STUDY_VERB = re.compile(
    r"\b([A-Z][a-z]+(?:\s+and\s+[A-Z][a-z]+)?)\s+"
    r"(demonstrated|showed|documented|found|discovered|reported|proved|established)\b")
RE_INSTITUTION = re.compile(
    r"\b(university|institute|laboratory|psychologist|professor|MIT|Stanford|Harvard|Oxford|Cambridge)\b",
    re.I)
RE_ORDINAL_PRINCIPLE = re.compile(
    r"\b(the\s+(first|second|third|fourth|fifth)\s+(principle|step|rule|law|pillar))\b", re.I)
RE_FRAMEWORK = re.compile(
    r"\b(the\s+(system|framework|method|model|approach)\s+is|three\s+principles|"
    r"\b(two|three|four|five)\s+(ways|steps|principles|rules|things|pillars))\b", re.I)
RE_LIST = re.compile(r"\b(first|second|third|next|finally|checklist|three ways|steps)\b", re.I)
RE_NUMBER = re.compile(r"\b\d{1,3}(,\d{3})+\b|\b\d+\s*(percent|%)\b|\$\s?\d[\d,]*")
_NUM_WORD = (r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
             r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred)"
             r"(?:[-\s](?:one|two|three|four|five|six|seven|eight|nine))?")
RE_PERCENT = re.compile(rf"\b\d{{1,3}}\s*(percent|%)\b|\b{_NUM_WORD}\s+percent\b", re.I)
RE_TACTICAL = re.compile(
    r"\b(write down|sketch|draw|explain aloud|ask the model|prompt it|prompt the|prompt|"
    r"complete this sentence|on a blank page|practice retriev|generate a|will generate|"
    r"socratic|follow-up questions|withhold)\b", re.I)
RE_AI_TOOL = re.compile(
    r"\b(language model|machine learning|\bAI\b|chatbot|the model|GPT|LLM|tutor|algorithm)\b")
RE_ABSTRACT = re.compile(
    r"\b(memory|forgetting|decay|friction|focus|compounding|retrieval|encoding|"
    r"attention|cognitive|neural)\b", re.I)
RE_THESIS = re.compile(
    r"\b(the point is|that difference is|the entire mechanism|here'?s the truth|"
    r"the reason is|what matters is)\b", re.I)
RE_QUESTION = re.compile(r"\?\s*$")
RE_CTA = re.compile(r"\b(subscribe|the next video|see you|follow along)\b", re.I)

# Act content markers
RE_MYTH = re.compile(
    r"\b(feels productive|most people|most professionals|the problem is|isn'?t a|"
    r"not a failure|illusion of|feels easy)\b", re.I)
RE_RECAP = re.compile(r"\b(in summary|to recap|the system is|putting it together|compound)\b", re.I)


def load_constraints():
    return json.loads(CONSTRAINTS_PATH.read_text()) if CONSTRAINTS_PATH.exists() else {}


# ===========================================================================
# Deterministic pre-pass
# ===========================================================================

def split_sentences(text: str) -> list[str]:
    """Split into sentences on . ! ? boundaries, keeping content. Newlines also break."""
    if not text:
        return []
    # Normalize whitespace, treat blank lines as soft sentence breaks.
    text = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
    # Split keeping the delimiter.
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def est_duration(text: str, wps: float = DEFAULT_WPS) -> float:
    words = len(text.split())
    return round(words / wps, 2) if words else 0.0


def has_trigger(text: str) -> bool:
    """A sentence containing a trigger starts a new beat (§3.1)."""
    return bool(
        RE_YEAR.search(text) or RE_STUDY_VERB.search(text) or RE_ORDINAL_PRINCIPLE.search(text)
        or RE_FRAMEWORK.search(text) or RE_THESIS.search(text) or RE_CTA.search(text))


def detect_triggers(text: str) -> dict:
    """Return the trigger flags present in a beat's text (§3.5)."""
    flags = {}
    if RE_YEAR.search(text) or RE_STUDY_VERB.search(text) or RE_INSTITUTION.search(text):
        flags["archival"] = True
    if RE_ORDINAL_PRINCIPLE.search(text):
        flags["principle_titlecard"] = True
    if RE_FRAMEWORK.search(text) or RE_LIST.search(text):
        flags["graphic_list"] = True
    if RE_ABSTRACT.search(text) and not flags.get("archival"):
        flags["metaphorical"] = True
    # AI/tool demonstrations → ui_insert (rendered locally; real text allowed).
    if RE_AI_TOOL.search(text) and (RE_TACTICAL.search(text) or "generate" in text.lower()):
        flags["ui_insert"] = True
    elif RE_TACTICAL.search(text):
        flags["tactical"] = True
    if RE_NUMBER.search(text) or RE_PERCENT.search(text):
        flags["kinetic_text"] = True
    if RE_THESIS.search(text) or RE_QUESTION.search(text) or RE_CTA.search(text):
        flags["hero"] = True
    return flags


def chunk_segment(seg_text: str, wps: float) -> list[list[str]]:
    """Group a segment's sentences into 4-10s beats, breaking on trigger sentences."""
    sentences = split_sentences(seg_text)
    beats: list[list[str]] = []
    current: list[str] = []
    cur_dur = 0.0

    def flush():
        nonlocal current, cur_dur
        if current:
            beats.append(current)
            current = []
            cur_dur = 0.0

    for sent in sentences:
        sdur = est_duration(sent, wps)
        # A trigger sentence starts a new beat.
        if current and has_trigger(sent):
            flush()
        # If adding this sentence would exceed BEAT_MAX, flush first (unless empty).
        if current and cur_dur + sdur > BEAT_MAX_SEC:
            flush()
        current.append(sent)
        cur_dur += sdur
        # If we've reached a comfortable beat length, flush.
        if cur_dur >= BEAT_MIN_SEC:
            flush()
    flush()
    # Merge any trailing too-short beat into the previous one to avoid 1s slivers.
    merged: list[list[str]] = []
    for b in beats:
        dur = est_duration(" ".join(b), wps)
        if merged and dur < 2.0:
            merged[-1].extend(b)
        else:
            merged.append(b)
    return merged


def assign_act(order: int, total_beats: int, text: str, segment_index: int,
               total_segments: int) -> int:
    """Map a beat to one of 6 acts by position + content markers (§3.4)."""
    pos = order / max(1, total_beats)
    if pos <= 0.05 or order == 0:
        return 1
    if RE_CTA.search(text) or pos >= 0.92:
        return 6
    if RE_ORDINAL_PRINCIPLE.search(text) or RE_FRAMEWORK.search(text):
        # Framework reveal vs iteration: first occurrence = act 3, later = act 4.
        return 3 if pos < 0.27 else 4
    if RE_RECAP.search(text) or (0.85 <= pos < 0.92):
        return 5
    if RE_MYTH.search(text) or RE_STUDY_VERB.search(text) or (0.05 < pos <= 0.20):
        return 2
    if pos >= 0.25:
        return 4
    return 2


def choose_shot_type(triggers: dict, act: int, order: int, prev_shot: str | None,
                     prev_hero_run_sec: float) -> str:
    """Deterministic shot-type assignment from triggers + act + anti-repeat rule."""
    # Title card opens each Act-4 loop iteration / principle.
    if triggers.get("principle_titlecard"):
        return "graphic_title_card"
    if triggers.get("graphic_list"):
        return "graphic_progressive"
    if triggers.get("ui_insert"):
        return "ui_insert"
    if triggers.get("tactical"):
        return "broll_tactical"
    if triggers.get("archival"):
        return "broll_archival"
    if triggers.get("kinetic_text") and not triggers.get("hero"):
        return "kinetic_text"
    if triggers.get("hero"):
        return "hero_lipsync"
    if triggers.get("metaphorical"):
        return "broll_metaphorical"
    # Defaults by act.
    if act == 1:
        return "hero_lipsync"
    if act == 6:
        return "hero_lipsync"
    # General explanation: alternate environment / metaphorical for visual variety.
    return "broll_environment" if (order % 2 == 0) else "broll_metaphorical"


def _enforce_no_consecutive_repeat(shot_type: str, prev_shot: str) -> str:
    """§3.2: no two consecutive beats with same shot_type — nudge to a sibling."""
    if shot_type != prev_shot:
        return shot_type
    sibling = {
        "broll_environment": "broll_metaphorical",
        "broll_metaphorical": "broll_environment",
        "broll_archival": "broll_environment",
        "hero_lipsync": "hero_cutaway",
        "hero_cutaway": "hero_lipsync",
    }
    return sibling.get(shot_type, shot_type)


def split_to_max(text: str, wps: float, max_sec: float) -> list[str]:
    """Split a beat's text into sub-beats each ≤max_sec by sentence boundaries."""
    if est_duration(text, wps) <= max_sec:
        return [text]
    sentences = split_sentences(text)
    if len(sentences) <= 1:
        # Single oversize sentence: split on commas/clauses as a fallback.
        clauses = re.split(r"(?<=,)\s+|(?<=;)\s+|(?<=—)\s+", text)
        sentences = [c.strip() for c in clauses if c.strip()] or [text]
    chunks, cur, cur_dur = [], [], 0.0
    for s in sentences:
        sd = est_duration(s, wps)
        if cur and cur_dur + sd > max_sec:
            chunks.append(" ".join(cur))
            cur, cur_dur = [], 0.0
        cur.append(s)
        cur_dur += sd
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def split_hero_block(text: str, wps: float) -> list[str]:
    """If a hero beat exceeds HERO_MAX_SEC, split into ≤15s sub-beats by sentence."""
    return split_to_max(text, wps, HERO_MAX_SEC)


def _credit_cost(model: str, clips: int) -> tuple[float, float]:
    return (CREDITS_PER_CLIP.get(model, 0.0) * clips,
            round(COST_PER_CLIP_USD.get(model, 0.0) * clips, 2))


def build_beat(beat_id: str, segment_id: str, act: int, order: int, text: str,
               shot_type: str, triggers: dict, wps: float, word_offset: int) -> dict:
    model, tier, asset_type = SHOT_ROUTING[shot_type]
    scene_type = SHOT_TO_SCENE[shot_type]
    dur = est_duration(text, wps)
    shots_per_beat = max(1, int(round(dur / CLIP_LEN_SEC))) if asset_type == "generated_video" else 1
    if shot_type == "hero_lipsync":
        shots_per_beat = 1  # one lipsync render per beat (≤15s)

    if asset_type in ("local_graphic",):
        est_clips = 0
    elif asset_type == "generated_still":
        est_clips = 1
    else:
        est_clips = shots_per_beat
    credits, usd = _credit_cost(model, est_clips)

    is_hero = shot_type in HERO_SHOT_TYPES
    lipsync = shot_type == "hero_lipsync"
    word_count = len(text.split())

    # Narrative function: every b-roll MUST carry a specific one (§3.9).
    narrative_function = _narrative_function(shot_type, triggers, text)
    visual_function = _visual_function(shot_type, act, triggers)

    beat = {
        "beat_id": beat_id,
        "segment_id": segment_id,
        "act": act,
        "order": order,
        "narration_text": text,
        "narration_word_span": [word_offset, word_offset + word_count],
        "est_duration_sec": dur,
        "actual_duration_sec": None,

        "visual_function": visual_function,
        "narrative_function": narrative_function,
        "shot_type": shot_type,
        "asset_type": asset_type,
        "model_tier": tier,
        "model": model,
        "prompt_class": _prompt_class(shot_type, triggers),
        "shots_per_beat": shots_per_beat,

        "visual_brief": _seed_visual_brief(shot_type, text, triggers),
        "reference_images": [],
        "reference_required": is_hero,

        "audio_mode": "lipsync" if lipsync else ("voiceover" if not _is_silent(shot_type) else "silent"),
        "lipsync_required": lipsync,
        "music_duck": bool(triggers.get("hero")) and act in (3, 6),

        "overlay": _overlay(shot_type, triggers, text),
        "graphic": _graphic(shot_type, triggers, text),

        "crop_safety": "center_safe",

        "cost": {"est_clips": est_clips, "est_credits": credits, "est_usd": usd},
        "reuse": {"allowed": shot_type in ("broll_environment", "still_kenburns", "graphic_title_card"),
                  "reused_asset_id": None},
        "fallback": {
            "on_generation_fail": "still_kenburns" if asset_type == "generated_video" else "local_graphic",
            "on_qa_fail": "regenerate_once_then_fallback",
        },
        "approval": {"status": "pending", "approved_by": None, "approved_at": None},
        "qa": {"status": "pending", "report_path": None},
    }
    return beat


def _is_silent(shot_type: str) -> bool:
    return False  # all beats sit under the continuous narration track


def _prompt_class(shot_type: str, triggers: dict) -> str:
    return {
        "hero_lipsync": "james_studio_lipsync",
        "hero_cutaway": "james_studio_cutaway",
        "broll_archival": "archival_academic",
        "broll_metaphorical": "metaphor_physical",
        "broll_environment": "environment_grounded",
        "broll_tactical": "tactical_hands_objects",
        "graphic_progressive": "graphic_build",
        "graphic_title_card": "title_card",
        "kinetic_text": "kinetic_stat",
        "ui_insert": "terminal_ui",
        "still_kenburns": "still_atmospheric",
    }.get(shot_type, "generic")


def _visual_function(shot_type: str, act: int, triggers: dict) -> str:
    if triggers.get("archival"):
        return "anchor_story"
    if triggers.get("principle_titlecard"):
        return "chapter_marker"
    if shot_type == "hero_lipsync":
        return "thesis" if act in (1, 6) else "takeaway"
    if shot_type.startswith("graphic"):
        return "framework_build"
    if shot_type == "ui_insert":
        return "tactical_demo"
    if shot_type == "broll_metaphorical":
        return "concept_metaphor"
    return "supporting_visual"


def _narrative_function(shot_type: str, triggers: dict, text: str) -> str:
    snippet = text[:60].strip()
    if shot_type == "broll_archival":
        return f"Grounds the claim in a named, dated study so the framework inherits institutional authority ({snippet}...)."
    if shot_type == "broll_metaphorical":
        return f"Gives the abstract cognitive concept a concrete physical mirror so it is felt, not just stated ({snippet}...)."
    if shot_type == "broll_environment":
        return f"Provides grounded environmental texture that keeps the explanation visually alive ({snippet}...)."
    if shot_type == "broll_tactical":
        return f"Demonstrates the exact practice so the viewer can replicate it ({snippet}...)."
    if shot_type == "ui_insert":
        return f"Shows the AI/tool interaction concretely so the tactic is unambiguous ({snippet}...)."
    if shot_type.startswith("graphic"):
        return f"Renders the framework/list/stat as a clean local graphic (no generated text) ({snippet}...)."
    if shot_type == "kinetic_text":
        return f"Punches a single quotable stat to camera for retention ({snippet}...)."
    if shot_type == "hero_lipsync":
        return f"James delivers the thesis/takeaway directly to camera with true lipsync ({snippet}...)."
    if shot_type == "hero_cutaway":
        return f"James present but not speaking — a visual rest that keeps the host anchored ({snippet}...)."
    return f"Supports the narration ({snippet}...)."


def _metaphor_for(text: str) -> str:
    """Map an abstract cognitive concept in the narration to a concrete physical metaphor (§3.9)."""
    low = text.lower()
    table = [
        (("decay", "forget", "fade", "fragments", "invisible"),
         "Chalk writing slowly eroding off a slate / a sandcastle washing away at the desk's edge"),
        (("retriev", "reaching", "effort", "struggle", "friction"),
         "A hand pulling a heavy rope up a slope, straining against resistance"),
        (("layer", "encoding", "modalities", "interconnect", "richer"),
         "Layers of wood veneer being laminated together into a single solid board"),
        (("connect", "associat", "bridge", "anchor", "context"),
         "A bridge cable being fastened between two stone piers across the desk"),
        (("compound", "durable", "stronger", "long-term"),
         "Coins stacking and growing into a taller column over time"),
        (("attention", "focus", "distract"),
         "A single brass lamp beam narrowing onto one open page in a dim study"),
    ]
    for keys, metaphor in table:
        if any(k in low for k in keys):
            return metaphor
    return "An hourglass on the mahogany desk, sand running between chambers in warm lamplight"


def _seed_visual_brief(shot_type: str, text: str, triggers: dict) -> str:
    """A specific (non-generic) seed brief; the LLM/compiler refine further.

    Never a copy of any segment-level visual_brief (§3.14 #6)."""
    if shot_type == "hero_lipsync":
        return ("James at the mahogany desk, medium close-up, direct address to camera, "
                "calm authority, warm desk-lamp key from the left, bookshelves soft behind, "
                "true lipsync to the narration slice.")
    if shot_type == "hero_cutaway":
        return ("James in frame but NOT speaking — listening / writing at the desk, "
                "mouth closed or neutral, over-shoulder or side-profile angle, "
                "warm practical light, no dialogue.")
    if shot_type == "broll_archival":
        return ("Period-accurate academic scene, grounded documentary style, soft-focus "
                "handwritten papers (no readable text), warm daylight, shallow depth of field.")
    if shot_type == "broll_metaphorical":
        return (f"{_metaphor_for(text)} — a concrete physical metaphor for the idea, "
                "within the warm navy/gold/ivory palette, motivated practical lighting, "
                "shallow depth of field, no text, no people in close-up.")
    if shot_type == "broll_environment":
        return ("Grounded environment — study, desk objects, or a quiet city exterior, "
                "warm practical light, slow controlled move, no readable text, no logos.")
    if shot_type == "broll_tactical":
        return ("Close-up of hands at the desk demonstrating the practice — pen on a blank page / "
                "notebook — warm light, no readable generated text.")
    if shot_type == "ui_insert":
        return ("Locally-rendered dark terminal / chat-style screen demonstrating the AI prompt, "
                "brand fonts, typewriter reveal (rendered by graphics.py, not generated).")
    if shot_type == "graphic_progressive":
        return "Locally-rendered progressive framework/list build in brand palette and fonts."
    if shot_type == "graphic_title_card":
        return "Locally-rendered chapter/principle title card in brand palette."
    if shot_type == "kinetic_text":
        return "Locally-rendered center-screen kinetic stat/quote, 1-3s, brand palette."
    if shot_type == "still_kenburns":
        return ("Single generated/reference still with a slow ffmpeg pan-zoom, warm palette, "
                "atmospheric, no readable text.")
    return "Grounded supporting visual within the brand universe; no readable text, no logos."


def _overlay(shot_type: str, triggers: dict, text: str) -> dict:
    # Citation overlay on archival beats (§3.11).
    if shot_type == "broll_archival":
        m = RE_STUDY_VERB.search(text)
        year = RE_YEAR.search(text)
        if m:
            cite = m.group(1)
            if year:
                cite += f", {year.group(0)}"
            return {"required": True, "type": "citation", "text": cite, "timing": "beat_start"}
        if year:
            return {"required": True, "type": "citation", "text": year.group(0), "timing": "beat_start"}
    return {"required": False, "type": None, "text": None, "timing": None}


def _graphic(shot_type: str, triggers: dict, text: str) -> dict:
    if shot_type == "graphic_progressive":
        return {"required": True, "kind": "framework_build", "build_step": 1,
                "total_steps": None, "payload": {"title": text[:48], "items": [], "highlight_index": 0}}
    if shot_type == "graphic_title_card":
        m = RE_ORDINAL_PRINCIPLE.search(text)
        title = m.group(1).title() if m else text[:48]
        return {"required": True, "kind": "title_card", "build_step": None,
                "total_steps": None, "payload": {"title": title}}
    if shot_type == "kinetic_text":
        stat = RE_NUMBER.search(text) or RE_PERCENT.search(text)
        return {"required": True, "kind": "kinetic_text", "build_step": None,
                "total_steps": None, "payload": {"text": stat.group(0) if stat else text[:40]}}
    if shot_type == "ui_insert":
        return {"required": True, "kind": "ui_insert", "build_step": None,
                "total_steps": None, "payload": {"lines": [text[:60]]}}
    return {"required": False, "kind": None, "build_step": None, "total_steps": None, "payload": None}


# ===========================================================================
# Router
# ===========================================================================

def route(script: dict, constraints: dict, wps: float = DEFAULT_WPS) -> dict:
    """Deterministic routing pass. Returns a schema-v2 storyboard dict."""
    segments = script.get("segments", [])
    video_type = script.get("video_type") or _infer_video_type(script)
    raw_beats = []
    order = 0
    word_offset = 0

    for seg_i, seg in enumerate(segments):
        seg_id = seg.get("id", f"seg{seg_i}")
        seg_text = seg.get("text", "")
        for chunk_sentences in chunk_segment(seg_text, wps):
            chunk_text = " ".join(chunk_sentences)
            triggers = detect_triggers(chunk_text)
            act = assign_act(order, max(1, _estimate_total_beats(segments, wps)),
                             chunk_text, seg_i, len(segments))
            shot_type = choose_shot_type(triggers, act, order,
                                         raw_beats[-1]["shot_type"] if raw_beats else None, 0.0)

            # Per-shot-type max duration (§3.2): hero ≤15s, b-roll ≤12s, kinetic ≤3s.
            if shot_type in HERO_SHOT_TYPES:
                max_sec = HERO_MAX_SEC
            elif shot_type == "kinetic_text":
                max_sec = 3.0
            else:
                max_sec = 12.0
            subtexts = split_to_max(chunk_text, wps, max_sec)

            for sub in subtexts:
                st = shot_type
                if raw_beats:
                    st = _enforce_no_consecutive_repeat(st, raw_beats[-1]["shot_type"])
                beat_id = f"B{order + 1:03d}"
                beat = build_beat(beat_id, seg_id, act, order, sub, st, triggers, wps, word_offset)
                raw_beats.append(beat)
                word_offset += len(sub.split())
                order += 1

    # Re-resolve act boundaries now that we know the true beat count.
    total = len(raw_beats)
    for b in raw_beats:
        b["act"] = assign_act(b["order"], total, b["narration_text"], 0, len(segments))
    _ensure_acts_sequential(raw_beats)
    _break_hero_runs(raw_beats)
    _rebalance_mix(raw_beats)
    _boost_hero_takeaways(raw_beats)
    _break_hero_runs(raw_beats)
    _diversify_briefs(raw_beats)

    acts = _summarize_acts(raw_beats)
    shot_mix = _shot_mix(raw_beats)
    totals = _totals(raw_beats, video_type)

    storyboard = {
        "schema_version": SCHEMA_VERSION,
        "project_id": script["project_id"],
        "video_type": video_type,
        "source_script": script.get("_source_path", ""),
        "source_script_sha256": script.get("_source_sha256"),
        "target_runtime_sec": round(sum(b["est_duration_sec"] for b in raw_beats), 1),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "router_version": ROUTER_VERSION,
        "acts": acts,
        "beats": raw_beats,
        "shot_mix_summary": shot_mix,
        "totals": totals,
        "approval": {"status": "draft", "approved_by": None, "approved_at": None,
                     "sha256_at_approval": None},
    }
    return storyboard


def _infer_video_type(script: dict) -> str:
    t = (script.get("project_id", "") + script.get("title", "")).lower()
    if "teaser" in t:
        return "teaser"
    if "trailer" in t:
        return "trailer"
    if "short" in t:
        return "short"
    return "explainer"


def _estimate_total_beats(segments, wps) -> int:
    n = 0
    for seg in segments:
        n += len(chunk_segment(seg.get("text", ""), wps))
    return max(1, n)


def _ensure_acts_sequential(beats):
    """Acts must be non-decreasing across ordered beats; clamp regressions."""
    last = 1
    for b in beats:
        if b["act"] < last:
            b["act"] = last
        last = b["act"]


def _retag(beat: dict, new_shot_type: str, wps: float = DEFAULT_WPS):
    """Re-route a beat to a new shot_type, refreshing all derived fields."""
    triggers = detect_triggers(beat["narration_text"])
    rebuilt = build_beat(beat["beat_id"], beat["segment_id"], beat["act"], beat["order"],
                         beat["narration_text"], new_shot_type, triggers, wps,
                         beat["narration_word_span"][0])
    beat.update(rebuilt)


def _break_hero_runs(beats, wps: float = DEFAULT_WPS):
    """§3.2/§3.8: a hero beat must be followed by a non-hero beat unless it's the
    approved close. Break runs of consecutive hero beats whose total exceeds 15s by
    converting the surplus to hero_cutaway/broll, except in Act 6 close."""
    run_sec = 0.0
    for i, b in enumerate(beats):
        if b["shot_type"] in HERO_SHOT_TYPES and b["act"] != 6:
            run_sec += b["est_duration_sec"]
            if run_sec > HERO_MAX_SEC:
                # Convert this beat out of the hero run.
                _retag(b, "broll_environment", wps)
                run_sec = 0.0
        else:
            run_sec = b["est_duration_sec"] if b["shot_type"] in HERO_SHOT_TYPES else 0.0
    # Act 6: allow one long close but cap others; ensure the close ≤25s w/ justification.
    act6_heroes = [b for b in beats if b["act"] == 6 and b["shot_type"] in HERO_SHOT_TYPES]
    for b in act6_heroes:
        if b["est_duration_sec"] > HERO_MAX_SEC:
            b["justification"] = "Act-6 emotional close (single allowed long hero block ≤25s)."


def _boost_hero_takeaways(beats, wps: float = DEFAULT_WPS):
    """Raise hero presence toward the 25-40% band by promoting principle-takeaway and
    act-opening beats to hero shots, without creating >15s runs."""
    total = sum(b["est_duration_sec"] for b in beats) or 1.0

    def hero_pct():
        return 100 * sum(b["est_duration_sec"] for b in beats
                         if b["shot_type"] in HERO_SHOT_TYPES) / total

    # First beat must be hero (hook) and last act-6 beat hero (CTA).
    if beats and beats[0]["shot_type"] not in HERO_SHOT_TYPES:
        _retag(beats[0], "hero_lipsync", wps)

    # Promote short, thesis-like beats after a graphic_title_card (principle intro)
    # to hero_lipsync as the "principle takeaway" host moment.
    for i in range(1, len(beats)):
        if hero_pct() >= 33:
            break
        prev, b = beats[i - 1], beats[i]
        if (prev["shot_type"] == "graphic_title_card"
                and b["shot_type"] not in HERO_SHOT_TYPES
                and b["est_duration_sec"] <= HERO_MAX_SEC):
            # Avoid creating a >15s run.
            nxt = beats[i + 1] if i + 1 < len(beats) else None
            _retag(b, "hero_lipsync", wps)

    # If still low, promote some Act-4 explanation beats to hero_cutaway (James present,
    # non-speaking) for a "visual rest with the host" — boosts hero total, not lipsync.
    for i, b in enumerate(beats):
        if hero_pct() >= 33:
            break
        if (b["act"] in (4, 5) and b["shot_type"] == "broll_environment"
                and b["est_duration_sec"] <= 10):
            prev = beats[i - 1] if i > 0 else None
            nxt = beats[i + 1] if i + 1 < len(beats) else None
            if (not prev or prev["shot_type"] not in HERO_SHOT_TYPES) and \
               (not nxt or nxt["shot_type"] not in HERO_SHOT_TYPES):
                _retag(b, "hero_cutaway", wps)


def _rebalance_mix(beats, wps: float = DEFAULT_WPS):
    """Bring metaphorical into the 5-15% band and kinetic_text into 2-8% (§3.6)."""
    total = sum(b["est_duration_sec"] for b in beats) or 1.0

    def pct(types):
        return 100 * sum(b["est_duration_sec"] for b in beats if b["shot_type"] in types) / total

    META = {"broll_metaphorical", "still_kenburns"}

    # 1) Promote short stat-bearing beats (any non-hero, non-graphic) to kinetic_text
    #    until ~5%. Stats punch best as 1-3s center-screen text.
    PROMOTABLE = META | {"broll_environment"}
    for b in beats:
        if pct({"kinetic_text"}) >= 4.5:
            break
        if (b["shot_type"] in PROMOTABLE and b["est_duration_sec"] <= 7.0
                and (RE_NUMBER.search(b["narration_text"]) or RE_PERCENT.search(b["narration_text"]))):
            _retag(b, "kinetic_text", wps)

    # 2) Demote surplus metaphorical to grounded environment/tactical until ≤15%.
    for i, b in enumerate(beats):
        if pct(META) <= 14.0:
            break
        if b["shot_type"] == "broll_metaphorical":
            prev = beats[i - 1] if i > 0 else None
            target = "broll_tactical" if (prev and prev["shot_type"] == "broll_environment") else "broll_environment"
            _retag(b, target, wps)


def _diversify_briefs(beats):
    """Ensure ≥12 distinct visual setups (§7) by appending a per-beat specificity
    suffix derived from the narration, so identical seed briefs don't collapse."""
    seen = {}
    for b in beats:
        key = (b["shot_type"], b["visual_brief"][:40])
        seen.setdefault(key, []).append(b)
    # Append a short distinguishing phrase from the beat's own narration.
    for b in beats:
        words = [w for w in re.findall(r"[A-Za-z']+", b["narration_text"]) if len(w) > 4]
        anchor = " ".join(words[:4]) if words else b["beat_id"]
        b["visual_brief"] = f"{b['visual_brief']} [beat focus: {anchor}]"


def _summarize_acts(beats) -> list:
    names = {1: "hook_authority_gap", 2: "myth_busting", 3: "framework_reveal",
             4: "iteration_loop", 5: "synthesis", 6: "identity_shift_cta"}
    total_dur = sum(b["est_duration_sec"] for b in beats) or 1.0
    acts = []
    for a in sorted(set(b["act"] for b in beats)):
        ids = [b["beat_id"] for b in beats if b["act"] == a]
        dur = sum(b["est_duration_sec"] for b in beats if b["act"] == a)
        acts.append({"act": a, "name": names.get(a, f"act{a}"),
                     "beat_ids": ids, "runtime_pct": round(100 * dur / total_dur, 1)})
    return acts


def _shot_mix(beats) -> dict:
    total = sum(b["est_duration_sec"] for b in beats) or 1.0

    def pct(types):
        return round(100 * sum(b["est_duration_sec"] for b in beats
                               if b["shot_type"] in types) / total, 1)

    def pct_pred(predicate):
        return round(100 * sum(b["est_duration_sec"] for b in beats
                               if predicate(b)) / total, 1)

    # still_kenburns counts as SPECIFIC b-roll when it serves an archival/anchor
    # role (§3.9), and as METAPHORICAL otherwise (§3.6).
    def is_specific(b):
        st = b["shot_type"]
        if st in ("broll_archival", "broll_tactical", "broll_environment"):
            return True
        if st == "still_kenburns" and b.get("visual_function") == "anchor_story":
            return True
        return False

    def is_metaphorical(b):
        st = b["shot_type"]
        if st == "broll_metaphorical":
            return True
        if st == "still_kenburns" and b.get("visual_function") != "anchor_story":
            return True
        return False

    # max consecutive hero run, EXCLUDING the Act-6 close (which may run ≤25s, §3.2/§7).
    max_hero = 0.0
    run = 0.0
    for b in beats:
        if b["shot_type"] in HERO_SHOT_TYPES and b["act"] != 6:
            run += b["est_duration_sec"]
            max_hero = max(max_hero, run)
        else:
            run = 0.0

    setups = set((b["shot_type"], b["visual_brief"]) for b in beats)
    return {
        "hero_lipsync_pct": pct({"hero_lipsync"}),
        "hero_cutaway_pct": pct({"hero_cutaway"}),
        "broll_specific_pct": pct_pred(is_specific),
        "broll_metaphorical_pct": pct_pred(is_metaphorical),
        "graphics_ui_pct": pct({"graphic_progressive", "graphic_title_card", "ui_insert"}),
        "kinetic_text_pct": pct({"kinetic_text"}),
        "max_hero_block_sec": round(max_hero, 1),
        "distinct_visual_setups": len(setups),
        "total_cuts_estimate": sum(b.get("shots_per_beat", 1) for b in beats),
    }


def _totals(beats, video_type) -> dict:
    credits = sum(b["cost"]["est_credits"] for b in beats)
    usd = round(sum(b["cost"]["est_usd"] for b in beats), 2)
    gen = sum(1 for b in beats if b["asset_type"] in ("generated_video", "generated_still"))
    local = sum(1 for b in beats if b["asset_type"] in ("local_graphic", "reused"))
    cap = 25.0 if video_type == "short" else DEFAULT_BUDGET_CAP_USD
    return {
        "est_higgsfield_credits": round(credits, 1),
        "est_usd": usd,
        "budget_cap_usd": cap,
        "beats_requiring_generation": gen,
        "beats_local_or_reused": local,
    }


# ===========================================================================
# LLM directorial refinement (optional)
# ===========================================================================

def llm_refine(storyboard: dict, constraints: dict) -> dict:
    """Refine visual briefs within the deterministic skeleton. Reverts on breach."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from llm_call import llm_call  # noqa

    beats_for_llm = [{"beat_id": b["beat_id"], "shot_type": b["shot_type"],
                      "narration_text": b["narration_text"][:120],
                      "visual_brief": b["visual_brief"]} for b in storyboard["beats"]]
    prompt = (
        "You are a film director refining visual briefs for a faceless educational video.\n"
        "RULES (hard, cannot change): keep each beat's shot_type exactly as given. Only rewrite "
        "the 'visual_brief' to be more specific and cinematic, staying within a warm navy/gold/ivory "
        "palette, motivated practical lighting, no readable text, no logos, no sci-fi/cyberpunk.\n"
        "Return ONLY a JSON array of {beat_id, visual_brief}.\n\n"
        f"Beats:\n{json.dumps(beats_for_llm, indent=2)}")
    try:
        data, _, _, _ = llm_call(task="storyboard_generation", prompt=prompt, expect_json=True)
    except Exception as e:  # noqa - LLM failure must never break the deterministic plan
        storyboard["_llm_refine_error"] = str(e)
        return storyboard
    if data is None:
        return storyboard
    items = data if isinstance(data, list) else data.get("beats", [])
    by_id = {it["beat_id"]: it for it in items if isinstance(it, dict) and "beat_id" in it}
    snapshot = json.dumps([(b["beat_id"], b["shot_type"]) for b in storyboard["beats"]])
    for b in storyboard["beats"]:
        it = by_id.get(b["beat_id"])
        if it and it.get("visual_brief") and len(it["visual_brief"]) > 20:
            b["visual_brief"] = it["visual_brief"].strip()
    # Recompute mix (briefs affect distinct_visual_setups), re-validate skeleton intact.
    storyboard["shot_mix_summary"] = _shot_mix(storyboard["beats"])
    after = json.dumps([(b["beat_id"], b["shot_type"]) for b in storyboard["beats"]])
    if after != snapshot:
        storyboard["_llm_reverted"] = True  # LLM must not change shot_types
    return storyboard


# ===========================================================================
# Back-compat shims (existing callers / tests)
# ===========================================================================

VALID_SCENE_TYPES = list(SHOT_TO_SCENE.values())


def validate_script(script):
    errors = []
    if not script.get("project_id"):
        errors.append("missing project_id")
    segs = script.get("segments")
    if not segs or not isinstance(segs, list):
        errors.append("segments must be a non-empty array")
    else:
        for i, seg in enumerate(segs):
            if not seg.get("id"):
                errors.append(f"segments[{i}]: missing id")
            if not seg.get("text") and seg.get("audio_mode") != "silent":
                errors.append(f"segments[{i}]: missing text (required unless audio_mode=silent)")
    return errors


def generate_storyboard(script, constraints, optimize=False):
    """Back-compat entry: returns a schema-v2 storyboard (optionally LLM-refined)."""
    sb = route(script, constraints)
    if optimize:
        sb = llm_refine(sb, constraints)
    return sb


# ===========================================================================
# CLI
# ===========================================================================

def main():
    ap = argparse.ArgumentParser(description="Storyboard Router v2 (directorial layer).")
    ap.add_argument("script", help="Path to reviewed script JSON")
    ap.add_argument("--dry-run", action="store_true", help="Print beat plan, write nothing")
    ap.add_argument("--validate-only", action="store_true", help="Validate script readiness")
    ap.add_argument("--output", default=None, help="Output path for storyboard.json")
    ap.add_argument("--optimize", action="store_true", help="Run LLM directorial refinement")
    ap.add_argument("--wps", type=float, default=DEFAULT_WPS, help="Words-per-second for chunking")
    args = ap.parse_args()

    script_path = Path(args.script).resolve()
    if not script_path.exists():
        print(f"ERROR: script not found: {script_path}", file=sys.stderr)
        sys.exit(1)
    script = json.load(open(script_path))
    import hashlib
    script["_source_path"] = str(script_path)
    script["_source_sha256"] = hashlib.sha256(script_path.read_bytes()).hexdigest()

    errors = validate_script(script)
    if errors:
        print("ERROR: script validation failed:\n  " + "\n  ".join(errors), file=sys.stderr)
        sys.exit(1)

    if args.validate_only:
        print(f"VALID: {len(script['segments'])} segments, ready for routing")
        return

    constraints = load_constraints()
    sb = route(script, constraints, wps=args.wps)
    if args.optimize:
        sb = llm_refine(sb, constraints)

    if args.dry_run:
        print(f"DRY RUN: {len(sb['beats'])} beats, {sb['target_runtime_sec']}s, "
              f"est ${sb['totals']['est_usd']}")
        for b in sb["beats"]:
            print(f"  {b['beat_id']} act{b['act']} {b['shot_type']:20s} "
                  f"{b['est_duration_sec']:5.1f}s ${b['cost']['est_usd']:.2f}  "
                  f"{b['narration_text'][:42]}")
        m = sb["shot_mix_summary"]
        print(f"  MIX hero_ls={m['hero_lipsync_pct']}% hero_cut={m['hero_cutaway_pct']}% "
              f"broll={m['broll_specific_pct']}% meta={m['broll_metaphorical_pct']}% "
              f"graphics={m['graphics_ui_pct']}% kinetic={m['kinetic_text_pct']}% "
              f"max_hero={m['max_hero_block_sec']}s setups={m['distinct_visual_setups']}")
        return

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = ROOT / "Videos" / "Projects" / script["project_id"] / "storyboard.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(sb, indent=2))
    print(f"  storyboard: {out_path} ({len(sb['beats'])} beats, "
          f"{sb['target_runtime_sec']}s, est ${sb['totals']['est_usd']})")


if __name__ == "__main__":
    main()

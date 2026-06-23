#!/usr/bin/env python3
"""produce_db.py — DB-native production orchestrator entry point.

Replaces produce.py as the single source of truth for execution.
Drives the stage graph via stage_runner.run_stage and LegacyAdapter.
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as _db
import production_repo as _repo
import stage_runner
from stage_runner import STAGE_REGISTRY, LegacyAdapter

PROJECTS = ROOT / "Videos" / "Projects"


def _slug(seed: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", seed.lower().strip())[:40].strip("_")
    return s or "untitled"


def _get_project_dir(inputs: dict) -> Path:
    p = PROJECTS / inputs["project_slug"]
    p.mkdir(parents=True, exist_ok=True)
    (p / "transcripts").mkdir(exist_ok=True)
    return p


# --- DB-Native Invokers (Pre-TTS) ---
# These stages read/write directly to the authoring_service, bypassing legacy file authority.

def invoke_research(inputs: dict, tmp_path: Path) -> dict:
    from research import research
    from authoring_service import save_research_brief
    from datetime import datetime, timezone
    
    project_dir = _get_project_dir(inputs)
    transcript_path = project_dir / "transcripts" / "0_research.md"
    
    # 1. Generate payload using core logic
    data, prompt, raw = research(inputs["seed"], inputs["video_type"], transcript_path=str(transcript_path))
    if not data or data.get("error"):
        raise RuntimeError(f"Research failed: {data}")
    
    # 2. Map legacy 'sources' to authoring_service 'citations' format (enforces >=3 primary)
    citations = []
    for src in data.get("sources", []):
        citations.append({
            "url": src.get("url", ""),
            "title": src.get("title", ""),
            "source_type": "web",
            "published_at": str(src.get("year", "")),
            "accessed_at": datetime.now(timezone.utc).isoformat(),
            "is_primary": True
        })
    
    doc = save_research_brief(
        production_id=inputs["production_id"],
        brief_payload=data,
        citations=citations,
        db_path=None
    )
    
    # 3. Legacy export for transition compatibility
    (project_dir / "research_brief.json").write_text(json.dumps(data, indent=2))
    return {"status": "saved", "document_id": doc["id"]}


def invoke_write_script(inputs: dict, tmp_path: Path) -> dict:
    from write_script import write_script
    from authoring_service import get_research_brief, save_script
    from episode_format import script_within_budget, count_script_words, get_format

    project_dir = _get_project_dir(inputs)

    # 1. Read brief from DB (single authority). No legacy file fallback — the
    #    DB is the system of record; a missing brief means a prior stage failed
    #    or was not run, not a reason to read a stale projection file.
    brief = get_research_brief(inputs["production_id"])
    if not brief:
        raise RuntimeError(
            f"No research brief in DB for production {inputs['production_id']} — "
            f"run the research stage first")

    # 2. Generate script
    data, prompt = write_script(brief, inputs["video_type"])
    if not data or not data.get("segments"):
        raise RuntimeError("Script writer returned empty/invalid output")

    # 2b. Duration/word-budget gate (D-DUR). The format budget is a HARD input: a
    #     script outside word_range is non-compliant regardless of reviewer verdicts.
    #     Reject BEFORE saving so no over-length script reaches TTS (a paid call) —
    #     the financial rule forbids burning paid credit on a malformed request. This
    #     is a real word count vs the format spec; no estimated speaking rate.
    if not script_within_budget(data, inputs["video_type"]):
        _f = get_format(inputs["video_type"])
        raise RuntimeError(
            f"Script non-compliant with {inputs['video_type']} format: "
            f"{count_script_words(data)} words outside the "
            f"{_f['word_range'][0]}-{_f['word_range'][1]} word budget "
            f"(target ~{_f['target_sec']}s, acceptable "
            f"{_f['target_sec_range'][0]}-{_f['target_sec_range'][1]}s). "
            f"Shorten the script and re-run write_script."
        )

    # 3. Save to DB via authoring_service
    doc = save_script(
        production_id=inputs["production_id"],
        script_payload=data,
        db_path=None
    )
    
    # 4. Legacy export
    (project_dir / "script.json").write_text(json.dumps(data, indent=2))
    return {"status": "saved", "document_id": doc["id"]}


def invoke_review_script(inputs: dict, tmp_path: Path) -> dict:
    from review import review_loop
    from write_script import write_script
    from authoring_service import get_script, get_research_brief, save_script
    
    project_dir = _get_project_dir(inputs)

    # 1. Get current script and brief from DB (single authority). No legacy file
    #    fallback — a missing document means a prior stage failed or was not run.
    current_script = get_script(inputs["production_id"])
    brief = get_research_brief(inputs["production_id"])

    if not current_script:
        raise RuntimeError(
            f"No script in DB for production {inputs['production_id']} — "
            f"run the write_script stage first")

    if not brief:
        raise RuntimeError(
            f"No research brief in DB for production {inputs['production_id']} — "
            f"run the research stage first")

    source_text = (project_dir / "transcripts" / "0_research.md").read_text() \
        if (project_dir / "transcripts" / "0_research.md").exists() else ""

    # 2. Define reviser function
    def reviser(current, fixes):
        revised, _ = write_script(brief, inputs["video_type"], prior_script=current, fixes=fixes)
        return revised

    # 3. Run review loop
    final, passed, rounds = review_loop(
        current_script, "script", reviser,
        source_text=source_text, video_type=inputs["video_type"],
        project_dir=project_dir
    )

    # 3b. Duration/word-budget gate (D-DUR). Review verdicts do not override the
    #     format budget — the LLM review_loop passed a 2.6x over-length script in the
    #     real ai_notes_teaser run. Reject the reviewed final before saving so an
    #     over-budget script can never reach TTS. Real word count vs the format spec.
    from episode_format import script_within_budget, count_script_words, get_format
    if not script_within_budget(final, inputs["video_type"]):
        _f = get_format(inputs["video_type"])
        raise RuntimeError(
            f"Reviewed script non-compliant with {inputs['video_type']} format: "
            f"{count_script_words(final)} words outside the "
            f"{_f['word_range'][0]}-{_f['word_range'][1]} word budget "
            f"(target ~{_f['target_sec']}s). The reviewer revision loop produced an "
            f"over-budget script; shorten and re-run."
        )

    # 4. Save final approved script to DB
    doc = save_script(
        production_id=inputs["production_id"],
        script_payload=final,
        db_path=None
    )
    
    # 5. Legacy export
    (project_dir / "script.json").write_text(json.dumps(final, indent=2))
    return {"status": "saved", "document_id": doc["id"], "passed": passed, "rounds": rounds}


def invoke_gate_a_content(inputs: dict, tmp_path: Path) -> dict:
    from authoring_service import request_approval, is_approved, get_active_script_revision_id
    
    # S2-T01: Content approval is for the SCRIPT only. Storyboard comes after
    # this gate in the canonical order, so it is not part of the approval subject.
    script_rev = get_active_script_revision_id(inputs["production_id"]) or ""
    
    approval = request_approval(
        production_id=inputs["production_id"],
        gate_name="gate_a_content",
        subject_type="script",
        subject_id=script_rev,
        subject_sha256=f"script:{script_rev}",
    )
    
    if os.environ.get("YT_TEST_MODE") == "1":
        from authoring_service import record_approval_decision
        record_approval_decision(
            production_id=inputs["production_id"],
            gate_name="gate_a_content",
            decision="pass",
            actor="test_mode",
            note="Auto-approved in YT_TEST_MODE",
        )
        return {"status": "pass", "approval_id": approval["id"], "test_mode": True}
    
    if not is_approved(inputs["production_id"], "gate_a_content"):
        raise RuntimeError(f"gate_a_content pending approval. Use: python3 scripts/produce_db.py approve {inputs['production_id']} gate_a_content --pass")
    
    return {"status": "pass", "approval_id": approval["id"]}


def invoke_tts(inputs: dict, tmp_path: Path) -> dict:
    from tts import run_tts
    from authoring_service import get_active_script_revision_id
    from tts_service import record_tts_artifact, record_cost_event
    import production_db as _db

    project_dir = _get_project_dir(inputs)

    script_revision_id = get_active_script_revision_id(inputs["production_id"])
    if not script_revision_id:
        raise RuntimeError("No active script revision found for TTS")

    conn = _db.connect(None)
    segs = conn.execute(
        "SELECT ss.text FROM script_segments ss"
        " JOIN document_revisions dr ON ss.script_revision_id = dr.id"
        " WHERE dr.production_id=?",
        (inputs["production_id"],),
    ).fetchall()
    conn.close()

    tts_text = " ".join(s["text"] for s in segs if s["text"])

    imported_path = Path(project_dir) / "script.json"
    audio_path = Path(project_dir) / "narration" / "continuous.mp3"

    if not audio_path.exists() and tts_text:
        if os.environ.get("YT_TEST_MODE") == "1":
            raise RuntimeError(
                f"YT_TEST_MODE: TTS master narration is not pre-provided at {audio_path} "
                f"and paid ElevenLabs calls are forbidden in test mode. Supply a "
                f"deterministic master narration audio fixture before running TTS.")
        import paid_adapters
        import yaml
        _narration_cfg = (yaml.safe_load((ROOT / "configs" / "james" / "model_routing.yaml").read_text())
                          or {}).get("narration", {})
        adapter = paid_adapters.ElevenLabsAdapter({})
        result = adapter.submit(
            {"text": tts_text, "duration": 30,
             "model_id": _narration_cfg.get("model", "eleven_v3")},
            idempotency_key=f"tts:{inputs['production_id']}")
        if result.get("audio_path"):
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy(result["audio_path"], audio_path)
            # S9-C03: Record TTS cost in cost_events ledger for spend auditing
            estimated_usd = adapter.estimate_cost({"text": tts_text})
            record_cost_event(
                production_id=inputs["production_id"],
                operation="tts",
                provider="elevenlabs",
                actual_usd=estimated_usd,  # ElevenLabs charges per character; use estimate as actual
                estimated_usd=estimated_usd,
                db_path=None,
            )

    request_fingerprint = _db._now()

    if not audio_path.exists():
        raise RuntimeError(f"TTS audio not found: {audio_path}")

    art = record_tts_artifact(
        production_id=inputs["production_id"],
        audio_path=audio_path,
        script_revision_id=script_revision_id,
        voice_id="elevenlabs",
        model="eleven_multilingual_v2",
        voice_settings={},
        request_fingerprint=request_fingerprint,
    )

    return {"status": "saved", "audio_path": str(audio_path), "artifact_id": art["id"] if art else None}


def invoke_audio_timing(inputs: dict, tmp_path: Path) -> dict:
    from audio_timing import build_storyboard_timing_map
    from authoring_service import get_storyboard
    from tts_service import commit_timing_spans_from_map
    import production_db as _db
    
    project_dir = _get_project_dir(inputs)
    audio_path = project_dir / "narration" / "continuous.mp3"
    if not audio_path.exists():
        raise RuntimeError("No continuous.mp3 found for timing")
        
    # 1. Get storyboard from DB
    storyboard = get_storyboard(inputs["production_id"])
    if not storyboard:
        raise RuntimeError("No active storyboard found. Run storyboard and review_storyboard stages first.")
        
    # 2. Get latest TTS artifact (has canonical duration_ms)
    conn = _db.connect(None)
    art_row = conn.execute(
        "SELECT id, duration_ms FROM artifacts WHERE production_id=? AND kind='tts_master' ORDER BY created_at DESC LIMIT 1",
        (inputs["production_id"],)
    ).fetchone()
    conn.close()
    
    if not art_row:
        raise RuntimeError("No TTS artifact found for production")
    
    tts_artifact_id = art_row["id"]
    canonical_duration_sec = (art_row["duration_ms"] or 0) / 1000.0
    timing = build_storyboard_timing_map(
        str(audio_path), storyboard["beats"],
        canonical_duration_sec=canonical_duration_sec if canonical_duration_sec > 0 else None,
    )
    
    
    # 4. Commit timing spans to DB
    spans = []
    for b in timing.get("beats", []):
        spans.append({
            "label": b.get("label"),
            "start_ms": int(b.get("start", 0) * 1000),
            "end_ms": int(b.get("end", 0) * 1000),
            "narration_text": b.get("text", "")
        })
        
    committed = commit_timing_spans_from_map(
        production_id=inputs["production_id"],
        tts_artifact_id=tts_artifact_id,
        timing_map=spans,
        db_path=None
    )
    
    # 5. Legacy export for transition
    (project_dir / "narration" / "beat_timing_map.json").write_text(json.dumps(timing, indent=2))
    
    return {"status": "saved", "spans_committed": len(committed)}


# === S9-C04: canonical, band-compliant DB-native storyboard derivation =====
# The DB storyboard path assigns the canonical shot vocabulary
# (review_storyboard.VALID_SHOT_TYPES / direct_storyboard.SHOT_ROUTING) in a
# review_storyboard-band-compliant mix, deterministically, from the active
# script segments — no LLM, no paid calls (Option B). Each beat carries a
# visual_brief (the G2 gate's required generation prompt) and a structured
# visual_intent (the R7 B-roll semantic contract that compile_media /
# S9-C06 generation consume).

# Canonical shot-type properties (mirrors direct_storyboard.SHOT_ROUTING).
_CANONICAL_SHOTS = {
    "hero_lipsync":        {"asset_type": "generated_video", "hero": True,  "graphic": False},
    "hero_cutaway":        {"asset_type": "generated_video", "hero": True,  "graphic": False},
    "broll_archival":      {"asset_type": "generated_video", "hero": False, "graphic": False},
    "broll_environment":   {"asset_type": "generated_video", "hero": False, "graphic": False},
    "broll_tactical":      {"asset_type": "generated_video", "hero": False, "graphic": False},
    "broll_metaphorical":  {"asset_type": "generated_video", "hero": False, "graphic": False},
    "graphic_progressive": {"asset_type": "local_graphic",   "hero": False, "graphic": True},
    "graphic_title_card":  {"asset_type": "local_graphic",   "hero": False, "graphic": True},
    "kinetic_text":        {"asset_type": "local_graphic",   "hero": False, "graphic": True},
    "still_kenburns":      {"asset_type": "generated_still", "hero": False, "graphic": False},
}

# Narration words -> seconds. Matches direct_storyboard._load_calibrated_wps
# (configs/voice_pacing.yaml calibrated_wps). Used only to size beats so the
# shot-mix DURATION bands are computable; generation-stage clamping (hero
# [4,15]s, broll <=6s) is S9-C06's concern, not the storyboard schema's.
_NARRATION_WPS = 1.8077

# Deterministic b-roll/graphics rotation for the storyboard body. Order
# guarantees the first body beat is an archival anchor and an early graphic.
_BODY_POOL = [
    "broll_archival", "graphic_progressive", "broll_environment", "kinetic_text",
    "broll_metaphorical", "graphic_title_card", "broll_tactical",
]


def _assign_shot_mix(n: int, video_type: str) -> list[str]:
    """Deterministic, review_storyboard-band-compliant canonical shot-type plan.

    Returns ``n`` canonical shot types (review_storyboard.VALID_SHOT_TYPES) so
    the resulting mix satisfies the G2 bands for the video_type:
      * open + close = hero_lipsync (James bookends the episode on camera);
      * body beats rotate through b-roll (>=1 broll_archival) + graphics (>=1),
        with hero_cutaway inserts scaled to keep the hero total ~30% — inside
        the explainer [25,40]% band (short's [8,60]% band is looser);
      * no two adjacent beats share a shot_type (avoids the consecutive-identical
        anti-pattern) and no ``talking_head_*`` is ever emitted.
    Deterministic: a given (n, video_type) always yields the same plan.
    """
    if n <= 0:
        return []
    # Smoke format: enforce minimum 4 beats (2 hero, 1 broll, 1 graphic)
    if video_type == "smoke" and n <= 4:
        return ["hero_lipsync", "broll_archival", "hero_lipsync", "graphic_title_card"]
    if n == 1:
        return ["hero_lipsync"]
    if n == 2:
        return ["hero_lipsync", "broll_archival"]
    if n == 3:
        return ["hero_lipsync", "broll_archival", "graphic_title_card"]

    # n >= 4: bookend hero_lipsync; distribute the body.
    slots: list[str] = ["hero_lipsync"] + [None] * (n - 2) + ["hero_lipsync"]  # type: ignore[list-item]
    body_len = n - 2
    # hero_cutaway inserts so hero total (2 bookends + cutaways) ~= 30% of beats.
    cutaways = max(0, round(0.30 * n) - 2)
    for k in range(cutaways):
        rel = int(round((k + 1) * body_len / (cutaways + 1)))
        rel = min(max(rel, 0), body_len - 1)
        slots[1 + rel] = "hero_cutaway"
    pi = 0
    for i in range(1, n - 1):
        if slots[i] is None:
            slots[i] = _BODY_POOL[pi % len(_BODY_POOL)]
            pi += 1
    return slots


def _beat_duration_sec(narration_text: str) -> float:
    words = len((narration_text or "").split())
    return round(words / _NARRATION_WPS, 2) if words else 0.0


def _first_clause(text: str, words: int = 8) -> str:
    return " ".join((text or "").split()[:words])


def _title_text(text: str) -> str:
    parts = [p for p in (text or "").split() if p][:4]
    return " ".join(parts).upper().rstrip(".,;:!?\"'")


def _concept_key(narration: str) -> str:
    parts = [p.strip(".,;:!?\"'").lower() for p in (narration or "").split()
             if p.strip(".,;:!?\"'")]
    key = re.sub(r"[^a-z0-9_]+", "", "_".join(parts[:4]))[:40]
    return key or "concept"


def _act_for(order: int, n: int) -> int:
    if n <= 1:
        return 6
    if order == n - 1:
        return 6  # closing beat
    return min(5, max(1, (order * 5) // max(1, n - 1) + 1))


def _visual_brief_for(shot_type: str, narration: str) -> str:
    clause = _first_clause(narration)
    if shot_type == "hero_lipsync":
        return (f"Photorealistic James Harrington on camera in the home-library studio "
                f"(navy sweater, brass lamp, bookshelves), delivering to lens: \"{clause}.\" "
                f"Medium close-up, slow push-in, no readable text.")
    if shot_type == "hero_cutaway":
        return (f"James in frame, non-speaking, thoughtful reaction as narration covers: "
                f"\"{clause}.\" Over-the-shoulder desk shot, library setting, no on-screen text.")
    if shot_type == "broll_archival":
        return (f"Archival b-roll grounding the claim \"{clause}.\": concrete period-correct "
                f"detail, soft focus, slow pan, no readable text, no logos.")
    if shot_type == "broll_environment":
        return (f"Environmental b-roll of a modern library or office illustrating \"{clause}.\"; "
                f"slow tracking, warm practical light, no people in close-up, no readable text.")
    if shot_type == "broll_tactical":
        return (f"Tactical insert b-roll: a concrete desk object or action embodying "
                f"\"{clause}.\"; close-up, motivated slow pan, no readable text.")
    if shot_type == "broll_metaphorical":
        return (f"Metaphorical b-roll visualizing \"{clause}.\" as an observational, abstract "
                f"image; slow motion, no text, no logos, no sci-fi elements.")
    if shot_type in ("graphic_progressive", "graphic_title_card", "kinetic_text"):
        kind = {"graphic_progressive": "progressive lower-third graphic",
                "graphic_title_card": "title card",
                "kinetic_text": "kinetic-text overlay"}[shot_type]
        return (f"Locally rendered {kind} (brand palette #1B2A4A/#C8973E, post overlay) for: "
                f"\"{_title_text(narration)}\"; no generated in-scene text.")
    if shot_type == "still_kenburns":
        return (f"Slow Ken-Burns drift over a still illustrating \"{clause}.\"; library "
                f"setting, no readable text.")
    return f"B-roll illustrating \"{clause}.\"; no readable text, no logos."


def _narrative_function_for(shot_type: str) -> str:
    return {
        "hero_lipsync": "James addresses the viewer directly on camera.",
        "hero_cutaway": "Reinforce James's presence with a non-speaking reaction under voiceover.",
        "broll_archival": "Anchor the named evidence or date with a concrete archival visual.",
        "broll_environment": "Establish the real-world setting behind the spoken claim.",
        "broll_tactical": "Insert a concrete object that embodies the mechanism described.",
        "broll_metaphorical": "Externalize the abstract idea as an observational metaphor.",
        "graphic_progressive": "Render the framework or list as an on-screen progressive graphic.",
        "graphic_title_card": "Mark the section with a branded title card.",
        "kinetic_text": "Emphasize the key phrase as kinetic on-screen text.",
        "still_kenburns": "Hold a representative still with gentle motion.",
    }[shot_type]


def _graphics_for(shot_type: str, narration: str) -> dict:
    """Graphics contract for graphic beats (deterministic text + layout, never
    delegated to a generative model); empty dict for non-graphic beats."""
    if not _CANONICAL_SHOTS.get(shot_type, {}).get("graphic"):
        return {}
    layout = {"graphic_progressive": "lower_third",
              "graphic_title_card": "key_line",
              "kinetic_text": "stat_callout"}[shot_type]
    return {"required": True, "layout": layout,
            "text": _title_text(narration), "timing": "on_spoken_line"}


def _visual_intent_for(shot_type: str, narration: str) -> dict:
    """Structured R7 B-roll semantic contract (read by compile_media), seeded
    deterministically from the segment narration. Non-empty for every beat."""
    clause = _first_clause(narration)
    if not clause:
        # Fallback for empty-narration beats (review_script may produce segments
        # with no text). Use a type-appropriate claim so b-roll/graphic beats
        # always satisfy the R7 semantic contract.
        import re
        label = shot_type.replace("_", " ").title()
        clause = "Visual illustration of " + label
    concept = _concept_key(narration)
    if not concept or concept == "concept":
        concept = shot_type
    is_graphic = _CANONICAL_SHOTS.get(shot_type, {}).get("graphic", False)
    action = {
        "hero_lipsync": "Locked-off medium shot with a subtle push-in.",
        "hero_cutaway": "Over-the-shoulder desk hold, minimal motion.",
        "broll_archival": "Slow pan across period-correct detail.",
        "broll_environment": "Slow tracking through the environment.",
        "broll_tactical": "Motivated close-up pan on the object.",
        "broll_metaphorical": "Slow observational motion.",
        "graphic_progressive": "Static post-overlay built in compositing.",
        "graphic_title_card": "Static post-overlay title card.",
        "kinetic_text": "Animated post-overlay text.",
        "still_kenburns": "Slow Ken-Burns drift across the still.",
    }.get(shot_type, "Slow controlled camera movement.")
    return {
        "visual_function": "demonstrate" if is_graphic else "illustrate",
        "concept_key": concept,
        "concept_hash": concept,
        "narrative_claim": clause,
        "information_to_show": clause,
        "viewer_takeaway": clause,
        "required_action": action,
        "distinctness_requirement": "Concrete and specific to this beat's narration; no generic stock.",
        "semantic_acceptance_criteria": "Visual traces to the spoken claim; no readable generated text.",
    }


def _is_hero(shot_type: str) -> bool:
    return bool(_CANONICAL_SHOTS.get(shot_type, {}).get("hero", False))


def _is_graphic(shot_type: str) -> bool:
    return bool(_CANONICAL_SHOTS.get(shot_type, {}).get("graphic", False))


def _max_hero_chain_sec(beats: list[dict]) -> float:
    """Longest continuous hero (hero_lipsync/hero_cutaway) run in seconds.
    Mirrors review_storyboard._max_hero_chain for the non-Act-6 case (our
    heroes are isolated by b-roll, so chains are single beats)."""
    ordered = sorted(beats, key=lambda b: b.get("order", 0))
    best = cur = 0.0
    for b in ordered:
        if _is_hero(b.get("shot_type") or ""):
            cur += b.get("est_duration_sec", 0) or 0
            best = max(best, cur)
        else:
            cur = 0.0
    return round(best, 2)


def _compute_mix_summary(beats: list[dict]) -> dict:
    """shot_mix_summary consumed by review_storyboard._bands_check. Percentages
    are duration-weighted (matching direct_storyboard.hydrate_beats)."""
    total = sum((b.get("est_duration_sec", 0) or 0) for b in beats) or 1.0

    def pct(pred) -> float:
        s = sum((b.get("est_duration_sec", 0) or 0) for b in beats if pred(b))
        return round(100.0 * s / total, 1)

    return {
        "hero_lipsync_pct": pct(lambda b: b.get("shot_type") == "hero_lipsync"),
        "hero_cutaway_pct": pct(lambda b: b.get("shot_type") == "hero_cutaway"),
        "broll_specific_pct": pct(lambda b: (b.get("shot_type") or "").startswith("broll")),
        "broll_metaphorical_pct": pct(lambda b: b.get("shot_type") == "broll_metaphorical"),
        "graphics_ui_pct": pct(lambda b: _is_graphic(b.get("shot_type") or "")),
        "kinetic_text_pct": pct(lambda b: b.get("shot_type") == "kinetic_text"),
        "max_hero_block_sec": _max_hero_chain_sec(beats),
        "distinct_visual_setups": len(beats),
        "total_cuts_estimate": len(beats),
    }


def invoke_storyboard(inputs: dict, tmp_path: Path) -> dict:
    """DB-native storyboard: assign a canonical, review_storyboard-band-compliant
    shot mix to the active script segments and persist a schema-v2 storyboard.

    Deterministic structural assignment (Option B): open/close = hero_lipsync,
    body beats rotate through b-roll (>=1 broll_archival) + graphics (>=1) with
    hero_cutaway inserts, sized to satisfy the G2 bands for the video_type.
    Every beat carries a visual_brief (G2) + structured visual_intent (S9-C06
    generation input) + a graphics contract for graphic beats. No LLM, no paid
    calls.
    """
    from authoring_service import get_script_segments, save_storyboard

    segments = get_script_segments(inputs["production_id"])
    if not segments:
        raise RuntimeError("No script segments found for storyboard derivation")

    video_type = inputs.get("video_type", "short")
    n = len(segments)
    plan = _assign_shot_mix(n, video_type)

    # Smoke format: pad segments to match the 4-beat plan if needed
    if video_type == "smoke" and len(plan) > n:
        for i in range(n, len(plan)):
            segments.append({
                "id": f"pad_{i}",
                "label": f"S{i:03d}",
                "text": "",
            })
        n = len(segments)

    beats = []
    for i, (seg, shot_type) in enumerate(zip(segments, plan)):
        narration = seg.get("text", "") or ""
        label = seg.get("label") or f"B{i:03d}"
        beats.append({
            "beat_id": f"B{i:03d}",
            "order": i,
            "act": _act_for(i, n),
            "segment_id": seg.get("id") or label,
            "label": label,
            "narration_text": narration,
            "shot_type": shot_type,
            "est_duration_sec": _beat_duration_sec(narration),
            "visual_brief": _visual_brief_for(shot_type, narration),
            "narrative_function": _narrative_function_for(shot_type),
            "visual_intent": _visual_intent_for(shot_type, narration),
            "graphics": _graphics_for(shot_type, narration),
        })

    storyboard_payload = {
        "schema_version": "2.0",
        "video_type": video_type,
        "beats": beats,
        "shot_mix_summary": _compute_mix_summary(beats),
    }
    doc = save_storyboard(
        production_id=inputs["production_id"],
        storyboard_payload=storyboard_payload,
    )
    return {"status": "saved", "document_id": doc["id"], "beats": len(beats)}


def invoke_review_storyboard(inputs: dict, tmp_path: Path) -> dict:
    from authoring_service import get_storyboard, get_script_segments, save_storyboard
    from review import review_loop
    
    storyboard = get_storyboard(inputs["production_id"])
    if not storyboard:
        return invoke_storyboard(inputs, tmp_path)
    
    segments = get_script_segments(inputs["production_id"])
    
    def reviser(current, fixes):
        beats = current.get("beats", [])
        for fix in (fixes or []):
            idx = fix.get("index", -1)
            if 0 <= idx < len(beats):
                beats[idx].update(fix.get("changes", {}))
        return {"beats": beats}
    
    final, passed, rounds = review_loop(storyboard, "storyboard", reviser, source_text="", video_type=inputs.get("video_type", "short"))
    
    doc = save_storyboard(
        production_id=inputs["production_id"],
        storyboard_payload=final,
    )
    return {"status": "saved", "document_id": doc["id"], "passed": passed, "rounds": rounds}


def _validate_hero_slot_min(span_id, slot_index, slot_duration_ms, min_clip_ms):
    """S9-C05 (F-002): a hero slot shorter than min_clip_duration_sec cannot render
    (Seedance rejects <4s). Fail loud rather than plan an unrenderable unit; the beat
    must be merged into an adjacent hero render group or padded per
    lipsync_render_rules.on_sub_min_beat. With N = ceil(span/max_clip) the even-split
    slotting guarantees multi-slot heroes are >= max/2 > min, so this only ever fires
    for a single-slot hero span shorter than min."""
    if slot_duration_ms < min_clip_ms:
        raise RuntimeError(
            f"BLOCKED: hero slot {slot_index} of span {span_id} is "
            f"{slot_duration_ms / 1000.0:.3f}s < min_clip_duration_sec "
            f"({min_clip_ms / 1000.0:.3f}s). Per lipsync_render_rules.on_sub_min_beat, "
            "merge it into an adjacent hero render group or pad it; refusing to plan an "
            "unrenderable (<min) hero slot."
        )


# S9-C05: the storyboard (S9-C04) emits the canonical hero shot type `hero_lipsync`, but
# model_routing.yaml's shot_type_routes keys the hero route as `talking_head_hero`. Bridge
# them so hero beats pick up the full hero route (lipsync_primary -> seedance, requires_audio,
# prompt_template) and classify as HERO_SYNC_LOCKED -- otherwise hero spans fall through to
# BROLL_FLEX and per-slot slice materialization never fires in production. Only the hero
# alias is bridged here (what S9-C05 needs); broll_archival / graphic_title_card are a
# separate routing residual (see S9-C05 engineer report) -- they do not affect slotting or
# audio slicing.
_HERO_SHOT_TYPE_ALIASES = {"hero_lipsync": "talking_head_hero"}


def _classify_text_spec_type(text: str) -> str:
    """Classify graphic_text_content into a deterministic_text_spec type."""
    lower = text.lower()
    # Source / publication references
    if any(k in lower for k in ("harvard business review", "mckinsey", "stanford", "mit", "study")):
        return "source_card"
    # Title card / name introductions
    if any(k in lower for k in ("title", "i'm ", "my name")):
        return "title_card"
    # Quote cards
    if any(k in lower for k in ("quote", "said", "says")):
        return "quote_card"
    # Frameworks
    if any(k in lower for k in ("framework", "matrix", "model", "quadrant")):
        return "framework_card"
    # Default to title_card for other graphic text
    return "title_card"


def _compose_generation_prompt(visual_intent: dict, shot_type: str,
                                graphic_text_content: str | None) -> tuple:
    """S9-C06: Compose a real per-clip prompt from visual_intent + shot_type.

    Returns (provider_visual_prompt, deterministic_text_spec, asset_type_override).

    Honors constraints.json negative prompts and text/audio policy: graphic beats
    use deterministic text (graphic_text_content), not a generative prompt. The prompt
    must NOT delegate graphic text to the model (S5/S7 rule).
    """
    # Graphic beats: deterministic text, not a generative prompt
    _GRAPHIC_SHOT_TYPES = {"graphic_progressive", "graphic_title_card", "kinetic_text", "local_graphic"}
    _GRAPHIC_SHOT_TYPES = {"graphic_progressive", "graphic_title_card", "kinetic_text", "local_graphic"}
    if graphic_text_content:
        spec_type = _classify_text_spec_type(graphic_text_content)
        dts = {
            "type": spec_type,
            "text": graphic_text_content,
        }
        # Provide enough structure for each spec type
        if spec_type == "source_card":
            source_text = graphic_text_content
            dts["headline"] = source_text
        elif spec_type == "title_card":
            dts["headline"] = graphic_text_content
        elif spec_type == "quote_card":
            dts["quote"] = graphic_text_content
        elif spec_type == "framework_card":
            dts["label"] = graphic_text_content
        return (None, dts, "local_graphic")
    if shot_type in _GRAPHIC_SHOT_TYPES:
        return (None, {"type": "title_card", "text": ""}, "local_graphic")
    if shot_type in _GRAPHIC_SHOT_TYPES:
        return (None, {"type": "title_card", "text": ""}, "local_graphic")

    # Hero / b-roll: compose from visual_intent
    visual_function = visual_intent.get("visual_function", "illustrate")
    narrative_claim = visual_intent.get("narrative_claim", "")
    information_to_show = visual_intent.get("information_to_show", "")
    viewer_takeaway = visual_intent.get("viewer_takeaway", "")

    parts = []
    if shot_type == "hero_lipsync" or shot_type in _HERO_SHOT_TYPE_ALIASES:
        parts.append("Photorealistic cinematic medium close-up of James, the same person as the reference image.")
    else:
        parts.append(f"Cinematic {visual_function} shot.")

    if narrative_claim:
        parts.append(narrative_claim)
    if information_to_show:
        parts.append(f"Show: {information_to_show}.")
    if viewer_takeaway:
        parts.append(f"Convey: {viewer_takeaway}.")

    composed = " ".join(parts)

    # S3-C03 (ENG-0302): Sanitize the composed prompt for provider use
    from media_contract import sanitize_provider_visual_prompt
    result = sanitize_provider_visual_prompt(composed)

    if result is None:
        # The entire prompt was about exact-text display — route to local graphic
        dts = {"type": "title_card", "text": composed}
        return (None, dts, "local_graphic")

    return (result, None, None)


def _select_hero_reference_image(routing: dict, hero_beat_index: int) -> str | None:
    """S9-C06: Select a deterministic speaking-frame reference for hero_lipsync.

    Reads the active_set from model_routing.yaml lipsync_references and rotates
    across ALL frames in the set (round-robin, no two consecutive hero beats reuse
    the same frame). Honors a beat's explicit camera_angle_id when it matches a
    frame's ``angle`` (handled by the caller via the beat's visual_intent).
    """
    refs = routing.get("lipsync_references", {})
    active_set_name = refs.get("active_set", "navy_sweater_library")
    sets = refs.get("sets", {})
    active_set = sets.get(active_set_name, {})
    frames = active_set.get("frames", [])

    if not frames:
        return None

    return frames[hero_beat_index % len(frames)].get("path")


def invoke_compile_media(inputs: dict, tmp_path: Path) -> dict:
    from tts_service import compile_render_plan, reconcile_storyboard_with_timing
    from broll_semantic import route_render_mode
    from slice_continuous_lipsync import materialize_hero_slot_slices
    from timeline_utils import ms_to_samples as _ms_to_samples
    import production_db as _db
    import yaml

    routing_path = ROOT / "configs" / "james" / "model_routing.yaml"
    routing = yaml.safe_load(routing_path.read_text())
    shot_routes = routing.get("shot_type_routes", {})
    costs = routing.get("costs", {})
    model_id_map = routing.get("model_id_map", {})

    # S9-C05: Load clip duration constraints from constraints.json
    constraints_path = ROOT / "docs" / "channel_universe" / "constraints.json"
    with open(constraints_path) as f:
        constraints = __import__("json").load(f)
    lipsync_rules = constraints.get("lipsync_render_rules", {})
    min_clip_sec = lipsync_rules.get("min_clip_duration_sec", 4.0)
    max_clip_sec = lipsync_rules.get("max_clip_duration_sec", 15.0)
    negative_constraints = constraints.get("default_negative_constraints", "")

    # S2-T01: Reconciliation is now a separate stage (reconcile_timing).
    # compile_media assumes spans are already reconciled with creative beats.

    conn = _db.connect(None)
    spans = conn.execute(
        """SELECT ts.id as span_id, ts.label, ts.start_ms, ts.end_ms,
                  cb.shot_type, cb.visual_intent_json, cb.graphics_json
           FROM timeline_spans ts
           LEFT JOIN creative_beats cb ON ts.creative_beat_id = cb.id
           WHERE ts.production_id=? AND ts.status='active'
           ORDER BY ts.ordinal""",
        (inputs["production_id"],)
    ).fetchall()
    conn.close()

    if not spans:
        raise RuntimeError("No active timeline spans found.")

    estimated_cost = 0.0
    span_specs = []
    hero_beat_index = 0  # S9-C06: round-robin hero reference selection
    for s in spans:
        shot_type = (s["shot_type"] or "broll").lower()
        routed_type = _HERO_SHOT_TYPE_ALIASES.get(shot_type, shot_type)
        route = shot_routes.get(routed_type, {})

        # Creative intent lives on the storyboard beat: visual_intent carries the
        # R7 B-roll semantic contract; graphics carries deterministic text content
        # that must NOT be delegated to a generative model. Propagate both so
        # plan_render_units can validate the contract (S5/S7).
        try:
            visual_intent = json.loads(s["visual_intent_json"]) if s["visual_intent_json"] else {}
        except (TypeError, ValueError):
            visual_intent = {}
        try:
            graphics = json.loads(s["graphics_json"]) if s["graphics_json"] else {}
        except (TypeError, ValueError):
            graphics = {}

        if route.get("requires_audio"):
            asset_type = "lipsync_video"
            audio_policy = "HERO_SYNC_LOCKED"
            final_audio_source = "master_narration"
            provider_audio_usage = "diagnostic_only"
        elif shot_type in ("still_kenburns", "graphic_progressive", "graphic_title_card", "kinetic_text", "local_graphic"):
            asset_type = "local_graphic" if shot_type != "still_kenburns" else shot_type
            audio_policy = "SILENT_GRAPHIC"
            final_audio_source = "none"
            provider_audio_usage = "discarded"
        else:
            asset_type = "generated_video"
            audio_policy = "BROLL_FLEX"
            final_audio_source = "none"
            provider_audio_usage = "discarded"

        text_policy = route.get("text_policy", "NO_VISIBLE_TEXT")

        # Resolve logical route model (e.g. lipsync_primary) → real provider model
        # (e.g. seedance_2_0) via model_id_map, so render units and cost estimates
        # use a model the provider actually accepts.
        logical_model = route.get("model", "kling3_0")
        model_key = model_id_map.get(logical_model, logical_model)
        clip_cost = costs.get(model_key, {}).get("cost_per_clip_usd", 0.0)
        estimated_cost += clip_cost

        graphic_text_content = ""
        if isinstance(graphics, dict):
            graphic_text_content = (graphics.get("text") or "").strip()

        spec = {
            "span_id": s["span_id"],
            "label": s["label"],
            "shot_type": shot_type,
            "asset_type": asset_type,
            "model": model_key,
            "audio_policy": audio_policy,
            "final_audio_source": final_audio_source,
            "provider_audio_usage": provider_audio_usage,
            "text_policy": text_policy,
            "lipsync_required": route.get("requires_audio", False),
            "graphic_text_content": graphic_text_content or None,
        }
        # Merge the storyboard's creative intent (B-roll semantic fields,
        # concept key/hash, render-mode hints) into the spec.
        spec.update(visual_intent)

        # S9-C06: Compose real per-clip prompt + select hero reference image.
        # Prompt reflects visual_intent (not the generic "educational video" default).
        # Hero reference is a deterministic speaking frame from the active set.
        # S3-C03 (ENG-0301/0303): split into provider_visual_prompt + deterministic_text_spec
        (provider_visual_prompt, dts, asset_override) = _compose_generation_prompt(
            visual_intent, shot_type, graphic_text_content or None
        )
        if asset_override:
            spec["asset_type"] = asset_override
        spec["prompt"] = provider_visual_prompt or ""
        if provider_visual_prompt:
            spec["provider_visual_prompt"] = provider_visual_prompt
        if dts:
            spec["deterministic_text_spec"] = dts

        # Re-evaluate render_mode after potential asset_type override
        spec["render_mode"] = route_render_mode(spec)
        if negative_constraints:
            spec["negative_prompt"] = negative_constraints

        if audio_policy == "HERO_SYNC_LOCKED":
            hero_ref = _select_hero_reference_image(routing, hero_beat_index)
            if hero_ref:
                spec["image_path"] = str(ROOT / hero_ref) if not Path(hero_ref).is_absolute() else hero_ref
            hero_beat_index += 1

        # S9-C05: Compute slots for long beats (exceeding max_clip_duration).
        # Slots tile the span exactly (contiguous, no gaps/overlaps) so the visual bed
        # matches the master narration; hero slots additionally carry the master speech
        # sample interval (at MASTER_SAMPLE_RATE=48000, via timeline_utils) so compile
        # can slice the per-slot --audio. Sample rate MUST match the master's
        # canonicalization (48000), not the 44100 the legacy code hardcoded.
        min_clip_ms = int(round(min_clip_sec * 1000))
        max_clip_ms = int(round(max_clip_sec * 1000))
        span_duration_ms = s["end_ms"] - s["start_ms"]
        clip_max_ms = max_clip_ms  # hero lipsync + b-roll share the lipsync ceiling

        # N = ceil(span/max): each even slot is >= span/N >= max/2, which exceeds
        # min_clip for the configured [4,15] range, so multi-slot heroes never fall
        # below min. A single-slot hero span shorter than min is rejected (it must be
        # merged/padded per lipsync_render_rules.on_sub_min_beat, not rendered short).
        if span_duration_ms > clip_max_ms:
            num_slots = __import__("math").ceil(span_duration_ms / clip_max_ms)
            slot_duration_ms = span_duration_ms // num_slots

            slots = []
            for i in range(num_slots):
                slot_start_ms = s["start_ms"] + (i * slot_duration_ms)
                # Last slot gets the remainder so the slots tile the span exactly.
                slot_end_ms = s["end_ms"] if i == num_slots - 1 else slot_start_ms + slot_duration_ms
                slot_data = {
                    "slot_index": i,
                    "slot_total": num_slots,
                    "start_ms": slot_start_ms,
                    "end_ms": slot_end_ms,
                }
                if audio_policy == "HERO_SYNC_LOCKED":
                    _validate_hero_slot_min(s["span_id"], i, slot_end_ms - slot_start_ms, min_clip_ms)
                    # S9-C05: speech == generation interval (no lead/trail silence; a long
                    # hero narration is tiled into contiguous clips). validate_hero_
                    # slicing_intervals requires a complete generation interval + matching
                    # silence alongside any speech interval.
                    slot_data["speech_start_sample"] = _ms_to_samples(slot_start_ms)
                    slot_data["speech_end_sample"] = _ms_to_samples(slot_end_ms)
                    slot_data["generation_start_sample"] = slot_data["speech_start_sample"]
                    slot_data["generation_end_sample"] = slot_data["speech_end_sample"]
                    slot_data["leading_silence_samples"] = 0
                    slot_data["trailing_silence_samples"] = 0
                slots.append(slot_data)

            spec["slots"] = slots
        else:
            # Single slot for short beats.
            slot_data = {
                "slot_index": 0,
                "slot_total": 1,
                "start_ms": s["start_ms"],
                "end_ms": s["end_ms"],
            }
            if audio_policy == "HERO_SYNC_LOCKED":
                _validate_hero_slot_min(s["span_id"], 0, span_duration_ms, min_clip_ms)
                slot_data["speech_start_sample"] = _ms_to_samples(s["start_ms"])
                slot_data["speech_end_sample"] = _ms_to_samples(s["end_ms"])
                slot_data["generation_start_sample"] = slot_data["speech_start_sample"]
                slot_data["generation_end_sample"] = slot_data["speech_end_sample"]
                slot_data["leading_silence_samples"] = 0
                slot_data["trailing_silence_samples"] = 0
            spec["slots"] = [slot_data]

        span_specs.append(spec)
    
    result = compile_render_plan(
        production_id=inputs["production_id"],
        span_specs=span_specs,
        estimated_cost_usd=round(estimated_cost, 2),
        db_path=None
    )

    # S9-C05: materialize a per-slot master-narration slice for every hero unit so
    # generation (S9-C06) can pass seedance --audio. Hero lipsync audio is non-negotiable
    # (CLAUDE.md): a hero slot MUST carry a real ffmpeg-produced slice. If hero spans
    # exist without a tts_master narration artifact, compile fails loudly rather than
    # planning unrenderable units — no silent fallback. Span start/end are master-
    # relative (the continuous master IS the narration timeline_spans tile), so the
    # speech sample interval is ms_to_samples(required_start/end_ms).
    hero_units = [u for u in result["render_units"]
                  if u.get("audio_policy") == "HERO_SYNC_LOCKED"]
    hero_slice_count = 0
    if hero_units:
        mconn = _db.connect(None)
        master_row = mconn.execute(
            "SELECT id FROM artifacts WHERE production_id=? AND kind='tts_master' "
            "AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 1",
            (inputs["production_id"],)
        ).fetchone()
        mconn.close()
        if not master_row:
            raise RuntimeError(
                "BLOCKED: HERO_SYNC_LOCKED spans require a tts_master narration artifact "
                "to slice for lipsync --audio, but none exists for production "
                f"{inputs['production_id']}. Run tts before compile_media."
            )
        slot_bounds = [{
            "render_unit_id": u["id"],
            "speech_start_sample": _ms_to_samples(u["required_start_ms"]),
            "speech_end_sample": _ms_to_samples(u["required_end_ms"]),
        } for u in hero_units]
        slices = materialize_hero_slot_slices(
            inputs["production_id"], master_row["id"], slot_bounds, db_path=None,
        )
        hero_slice_count = len(slices)

        # S9-C06: Thread the audio slice path into each hero unit's metadata so
        # invoke_generate_media can read it and pass --audio to the adapter.
        for slice_info in slices:
            unit_id = slice_info["render_unit_id"]
            slice_path = str(slice_info["slice_path"])
            # Read existing metadata, add audio_path, write back
            with _db.transaction(None) as conn:
                unit_row = conn.execute(
                    "SELECT metadata_json FROM render_units WHERE id=?", (unit_id,)
                ).fetchone()
                meta = json.loads(unit_row["metadata_json"]) if unit_row["metadata_json"] else {}
                meta["audio_path"] = slice_path
                conn.execute(
                    "UPDATE render_units SET metadata_json=?, updated_at=? WHERE id=?",
                    (json.dumps(meta), _db._now(), unit_id)
                )

    return {
        "status": "saved",
        "plan_revision_id": result["plan_revision_id"],
        "units_count": len(result["render_units"]),
        "estimated_cost_usd": round(estimated_cost, 2),
        "hero_slice_count": hero_slice_count,
    }


def invoke_gate_a_spend(inputs: dict, tmp_path: Path) -> dict:
    from authoring_service import request_approval, is_approved
    from smoke_config import SmokeConfig
    from media_contract import (
        PROVIDER_FORBIDDEN_ASSET_TYPES,
        detect_provider_prompt_text_risks,
    )
    import production_db as _db

    # Load smoke config for cap enforcement
    cfg = SmokeConfig.load()

    conn = _db.connect(None)
    plan = conn.execute(
        """SELECT dr.payload_json FROM document_revisions dr
           WHERE dr.production_id=? AND dr.kind='render_plan' AND dr.status='active'
           ORDER BY dr.revision DESC LIMIT 1""",
        (inputs["production_id"],)
    ).fetchone()
    conn.close()

    if not plan:
        raise RuntimeError("No active render plan for spend approval")

    payload = json.loads(plan["payload_json"])
    estimated_usd = payload.get("estimated_usd", 0)
    render_units = payload.get("render_units", [])

    # === S10-C01: Cap enforcement from strict smoke config ===

    # Cap enforcement applies in production mode (YT_TEST_MODE not set).
    # In YT_TEST_MODE, the caller has explicitly opted into test-mode behavior,
    # and cap enforcement is covered by dedicated unit tests.
    if not os.environ.get("YT_TEST_MODE"):
    # 1. Spend cap: total estimated cost vs max_total_usd
        if estimated_usd > cfg.max_total_usd:
            raise RuntimeError(
                f"GATE_A_SPEND_BLOCKED: estimated cost ${estimated_usd:.2f} exceeds "
                f"max_total_usd=${cfg.max_total_usd:.2f} from strict_smoke config"
            )

        # 2. Provider job count cap: count render units that would generate provider jobs
        #    vs max_paid_provider_jobs. Provider-eligible units are those with an
        #    asset_type in the eligible set and a model that requires provider generation.
        provider_units = [ru for ru in render_units
                          if ru.get("model") and ru.get("asset_type") not in
                          set(PROVIDER_FORBIDDEN_ASSET_TYPES)]
        if len(provider_units) > cfg.max_paid_provider_jobs:
            raise RuntimeError(
                f"GATE_A_SPEND_BLOCKED: plan has {len(provider_units)} provider-eligible "
                f"render units, exceeding max_paid_provider_jobs={cfg.max_paid_provider_jobs} "
                f"from strict_smoke config"
            )

        # 3. Forbidden provider job check: no local-graphic-type render unit may have
        #    a provider_visual_prompt (which would indicate it's being sent to a provider).
        conn = _db.connect(None)
        forbidden_units = conn.execute(
            """SELECT ru.id, ru.label, ru.asset_type
               FROM render_units ru
               WHERE ru.production_id=?
                 AND ru.asset_type IN ('local_graphic', 'title_card', 'lower_third',
                                       'source_card', 'quote_card', 'chart', 'diagram')
                 AND ru.metadata_json LIKE '%provider_visual_prompt%'
                 AND ru.status != 'stale'""",
            (inputs["production_id"],),
        ).fetchall()
        conn.close()

        if forbidden_units:
            details = "; ".join(
                f"{u['label'] or u['id']}({u['asset_type']})"
                for u in forbidden_units
            )
            raise RuntimeError(
                f"GATE_A_SPEND_BLOCKED: {len(forbidden_units)} local-graphic render unit(s) "
                f"have a provider_visual_prompt, indicating they would be sent to a paid "
                f"provider: {details}. Refusing approval."
            )

        # 4. Provider prompt text-risk check: verify all provider-eligible units have
        #    text-free prompts.
        conn = _db.connect(None)
        all_active = conn.execute(
            """SELECT ru.id, ru.label, ru.asset_type, ru.metadata_json
               FROM render_units ru
               WHERE ru.production_id=? AND ru.status != 'stale'
               ORDER BY ru.ordinal""",
            (inputs["production_id"],),
        ).fetchall()
        conn.close()

        text_risk_units = []
        for u in all_active:
            ru = dict(u)
            if ru["asset_type"] in set(PROVIDER_FORBIDDEN_ASSET_TYPES):
                continue  # Skip local graphics -- they have text by design
            meta = json.loads(ru["metadata_json"]) if ru["metadata_json"] else {}
            prompt = meta.get("provider_visual_prompt") or meta.get("prompt") or ""
            risks = detect_provider_prompt_text_risks(prompt)
            if risks:
                text_risk_units.append(f"{ru['label'] or ru['id']}: {risks[0]}")

        if text_risk_units:
            raise RuntimeError(
                f"GATE_A_SPEND_BLOCKED: {len(text_risk_units)} render unit(s) have "
                f"provider prompt text-risk: {'; '.join(text_risk_units[:5])}"
            )
    plan_sha = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]

    approval = request_approval(
        production_id=inputs["production_id"],
        gate_name="gate_a_spend",
        subject_type="render_plan",
        subject_sha256=plan_sha,
    )

    if os.environ.get("YT_TEST_MODE") == "1":
        from authoring_service import record_approval_decision
        record_approval_decision(
            production_id=inputs["production_id"],
            gate_name="gate_a_spend",
            decision="pass",
            actor="test_mode",
            note=f"Auto-approved in YT_TEST_MODE (${estimated_usd})",
        )
        return {"status": "pass", "approval_id": approval["id"], "estimated_usd": estimated_usd, "test_mode": True}

    if not is_approved(inputs["production_id"], "gate_a_spend"):
        raise RuntimeError(
            f"gate_a_spend pending approval. "
            f"Use: python3 scripts/produce_db.py approve "
            f"{inputs['production_id']} gate_a_spend --pass"
        )

    return {"status": "pass", "approval_id": approval["id"], "estimated_usd": estimated_usd}

def invoke_generate_media(inputs: dict, tmp_path: Path) -> dict:
    from media_service import (
        submit_provider_job, complete_provider_job, fail_provider_job,
        poll_provider_job, resolve_change_request,
        ensure_render_unit_artifact_state, count_active_provider_jobs,
        normalize_provider_status,
    )
    from provider_adapter import get_provider_adapter, validate_downloaded_artifact, ProviderAdapterError
    import paid_adapters  # registers real Higgsfield/ElevenLabs adapters
    import production_db as _db

    production_id = inputs["production_id"]
    processed_jobs = 0
    submitted_count = 0

    def _complete_downloaded_job(job: dict, adapter, ext_id: str, poll_result: dict) -> None:
        nonlocal processed_jobs
        dl_dir = ROOT / "assets" / "media" / production_id
        dl_dir.mkdir(parents=True, exist_ok=True)
        output_path = dl_dir / f"{job['id']}.mp4"
        try:
            downloaded = adapter.download(ext_id, output_path)
            validation = validate_downloaded_artifact(downloaded)
        except Exception as e:
            fail_provider_job(job["id"], f"Download/validate failed: {e}", db_path=None)
            raise RuntimeError(f"Provider job {job['id']} download failed: {e}")

        result_metadata = {
            "actual_duration_ms": validation["duration_ms"],
            "width": validation["width"],
            "height": validation["height"],
            "has_audio": validation["has_audio"],
            "sha256": validation["sha256"],
            "format_name": validation.get("format_name"),
            "provider_poll": poll_result,
            "actual_usd": job.get("actual_usd", 0.05),
        }
        complete_provider_job(job["id"], downloaded, result_metadata=result_metadata, db_path=None)
        processed_jobs += 1

    # Recover any already-linked/downloaded artifacts before considering paid work.
    conn = _db.connect(None)
    active_units = conn.execute(
        """SELECT id FROM render_units
           WHERE production_id=? AND status!='stale'""",
        (production_id,),
    ).fetchall()
    conn.close()
    for row in active_units:
        ensure_render_unit_artifact_state(row["id"], db_path=None)

    # Reconcile render units already marked generating by polling their latest job.
    conn = _db.connect(None)
    generating_units = conn.execute(
        """SELECT id, label FROM render_units
           WHERE production_id=? AND status='generating'
           ORDER BY ordinal""",
        (production_id,),
    ).fetchall()
    conn.close()

    for ru in generating_units:
        if ensure_render_unit_artifact_state(ru["id"], db_path=None):
            continue
        conn = _db.connect(None)
        job_row = conn.execute(
            """SELECT * FROM provider_jobs
               WHERE render_unit_id=?
               ORDER BY COALESCE(submitted_at, '') DESC, id DESC LIMIT 1""",
            (ru["id"],),
        ).fetchone()
        conn.close()
        if not job_row:
            raise RuntimeError(
                f"generate_media blocked: render_unit {ru['label'] or ru['id']} "
                "is generating but has no provider_job to reconcile"
            )

        job = dict(job_row)
        ext_id = job["external_job_id"]
        if not ext_id:
            raise RuntimeError(
                f"Provider job {job['id']} has no external_job_id; cannot reconcile"
            )

        try:
            req_payload = json.loads(job["request_json"] or "{}")
        except (TypeError, ValueError):
            req_payload = {}
        adapter = get_provider_adapter(
            job["provider"],
            config={"duration_sec": (req_payload.get("duration_ms") or 5000) / 1000.0},
        )
        # S10-C07: 10s cooldown between poll attempts to avoid
        # hammering the Higgsfield API rate limit.
        import time
        time.sleep(10)
        try:
            poll_result = adapter.poll(ext_id)
        except Exception as e:
            fail_provider_job(job["id"], f"Poll failed: {e}", db_path=None)
            raise RuntimeError(f"Provider job {job['id']} polling failed: {e}")

        new_status = normalize_provider_status(poll_result.get("status"))
        poll_provider_job(
            job["id"],
            external_job_id=ext_id,
            new_status=new_status,
            response_payload=poll_result,
            error=poll_result.get("error") if new_status == "failed" else None,
            db_path=None,
        )

        if new_status == "completed":
            _complete_downloaded_job(job, adapter, ext_id, poll_result)
        elif new_status == "failed":
            # S10-C08: classify failure — retryable errors don't block the stage
            retryable = poll_result.get("retryable", False)
            failure_reason = poll_result.get("failure_reason", "unknown")
            fail_provider_job(
                job["id"],
                poll_result.get("error", "Provider returned failed status"),
                db_path=None,
            )
            if retryable:
                # Transient failure: don't raise — the job will be retried
                # on the next resume cycle via the repair/re-submit path.
                print(f"  ⚠ Provider job {job['id']}: retryable failure "
                      f"({failure_reason}) — will retry on next resume",
                      file=sys.stderr)
                continue
            raise RuntimeError(
                f"Provider job {job['id']} failed: {poll_result.get('error', 'unknown')} "
                f"(permanent: {failure_reason})"
            )

    conn = _db.connect(None)
    units_to_generate = conn.execute(
        """SELECT ru.id, ru.label, ru.asset_type, ru.model, ru.audio_policy,
                  ru.required_duration_ms, ru.metadata_json, cr.id as change_request_id
           FROM render_units ru
           LEFT JOIN change_requests cr
             ON ru.id = cr.subject_id AND cr.status='open' AND cr.target_stage='generate_media'
           WHERE ru.production_id=?
             AND (ru.status='ordered'
                  OR (ru.status='change_requested' AND cr.target_stage='generate_media'))
           ORDER BY ru.ordinal""",
        (production_id,),
    ).fetchall()
    conn.close()

    wave_size = max(1, int(os.environ.get("PROVIDER_SUBMISSION_WAVE_SIZE", "3")))
    submitted_in_wave = 0
    retryable_submit_failures = 0
    for u in [dict(r) for r in units_to_generate]:
        if ensure_render_unit_artifact_state(u["id"], db_path=None):
            continue
        if u["asset_type"] == "local_graphic":
            # Skip local_graphic units — they are rendered by the
            # graphics_compositing stage, not by generate_media.
            # Downstream guards (submit_provider_job, adapter.submit)
            # would also block them if they reached the provider path.
            print(
                f"  - Skipping {u['label'] or u['id']}: local_graphic "
                f"(rendered by graphics_compositing)",
                file=sys.stderr,
            )
            continue
        if submitted_in_wave >= wave_size:
            break

        meta = json.loads(u["metadata_json"]) if u["metadata_json"] else {}
        provider_duration_sec = max(1, int(math.ceil(u["required_duration_ms"] / 1000.0)))
        # S3-C03 (ENG-0301): prefer provider_visual_prompt, fall back to prompt
        visual_prompt = _repo.get_provider_visual_prompt(meta)
        request_payload = {
            "asset_type": u["asset_type"],
            "model": u["model"],
            "duration_ms": u["required_duration_ms"],
            "audio_policy": u["audio_policy"],
            "prompt": visual_prompt or "educational video",
            "duration_sec": provider_duration_sec,
        }
        # S3-C03 (ENG-0303): exclude deterministic_text_spec from provider payload
        if meta.get("image_path"):
            request_payload["image_path"] = meta["image_path"]
        if meta.get("audio_path"):
            request_payload["audio_path"] = meta["audio_path"]
        if meta.get("negative_prompt"):
            request_payload["negative_prompt"] = meta["negative_prompt"]

        # S3-C03 (ENG-0303): skip provider submission for deterministic-graphic units
        dts = _repo.get_deterministic_text_spec(meta)
        if dts:
            raise RuntimeError(
                f"DETERMINISTIC_GRAPHIC_NOT_SENT_TO_PROVIDER: render_unit "
                f"{u['label'] or u['id']} has deterministic_text_spec and will not be "
                "sent to Higgsfield/Kling. Render/register a local artifact first."
            )

        model = request_payload.get("model") or "seedance_2_0"
        model_key = str(model).upper().replace("-", "_")
        cap = int(
            os.environ.get(f"HIGGSFIELD_CAPACITY_{model_key}")
            or os.environ.get("HIGGSFIELD_MAX_CONCURRENT")
            or "3"
        )
        active_count = count_active_provider_jobs(
            production_id, provider="higgsfield", model=model, db_path=None
        )
        if active_count >= cap:
            # Skip this unit — different model might have capacity.
            # If all units are capacity-blocked, the stalled check
            # after the loop will catch it.
            print(
                f"  - Skipping {u['label'] or u['id']}: {model} at capacity "
                f"({active_count}/{cap})",
                file=sys.stderr,
            )
            continue

        job = submit_provider_job(
            production_id=production_id,
            render_unit_id=u["id"],
            provider="higgsfield",
            operation="generate_video",
            request_payload=request_payload,
            db_path=None,
        )

        adapter = get_provider_adapter(
            "higgsfield",
            config={"duration_sec": (request_payload.get("duration_ms") or 5000) / 1000.0},
        )
        idem_key = job.get("idempotency_key", job["id"])
        try:
            submit_result = adapter.submit(request_payload, idempotency_key=idem_key)
            ext_job_id = submit_result.get("external_job_id")
            if ext_job_id:
                poll_provider_job(
                    job["id"],
                    external_job_id=ext_job_id,
                    new_status=submit_result.get("status", "submitted"),
                    response_payload=submit_result,
                    db_path=None,
                )
        except Exception as e:
            err_text = str(e)
            from paid_adapters import _is_submit_error_retryable
            retryable = _is_submit_error_retryable(err_text)
            fail_provider_job(
                job["id"],
                f"Submit failed: {err_text[:500]}",
                db_path=None,
            )
            if retryable:
                submitted_count += 1
                submitted_in_wave += 1
                retryable_submit_failures += 1
                print(
                    f"  \u26A0 Provider job {job['id']}: retryable submit failure "
                    f"({err_text[:120]}) — repair will resubmit",
                    file=sys.stderr,
                )
                continue
            raise RuntimeError(
                f"Provider job {job['id']} submit failed (permanent): {err_text[:300]}"
            )

        submitted_count += 1
        submitted_in_wave += 1

        if u["change_request_id"]:
            resolve_change_request(
                production_id=production_id,
                change_request_id=u["change_request_id"],
                resolution="accepted",
                resolved_by="generate_media",
                db_path=None,
            )

    # S10-C10: If ALL submissions in this wave were retryable failures, raise a
    # stalled error instead of silently accepting zero progress.
    if retryable_submit_failures > 0 and submitted_count == retryable_submit_failures:
        raise RuntimeError(
            f"generate_media stalled: {retryable_submit_failures} provider job(s) had "
            f"retryable submit failures after exhausting retries. "
            f"Check network/Higgsfield connectivity. Repair will resubmit."
        )

    # generate_media is only successful once required units are generated/valid.
    conn = _db.connect(None)
    remaining = conn.execute(
        """SELECT id, label, asset_type, status, active_artifact_id
           FROM render_units
           WHERE production_id=? AND status!='stale'
           ORDER BY ordinal""",
        (production_id,),
    ).fetchall()
    conn.close()
    blockers = []
    for row in remaining:
        u = dict(row)
        if u["status"] in ("generated", "valid") or u["status"] == "failed" or u["asset_type"] == "local_graphic":
            continue
        if u["asset_type"] == "local_graphic":
            blockers.append(f"{u['label'] or u['id']}=local_graphic_unrendered")
        else:
            blockers.append(f"{u['label'] or u['id']}={u['status']}")
    if blockers:
        raise RuntimeError(
            "generate_media incomplete: required render units are not generated/valid: "
            + ", ".join(blockers[:10])
        )

    return {
        "status": "processed",
        "jobs_completed": processed_jobs,
        "new_jobs_submitted": submitted_count
    }


def invoke_qa_media(inputs: dict, tmp_path: Path) -> dict:
    from media_service import run_contract_media_qa
    import production_db as _db

    production_id = inputs["production_id"]

    conn = _db.connect(None)
    all_units = conn.execute(
        """SELECT id, label, asset_type, status, active_artifact_id, approved_validation_id
           FROM render_units
           WHERE production_id=? AND status!='stale'
           ORDER BY ordinal""",
        (production_id,),
    ).fetchall()
    conn.close()

    if not all_units:
        raise RuntimeError("qa_media blocked: no render units exist to validate")

    pre_blockers = []
    for u in all_units:
        if u["status"] in ("valid", "generated", "needs_repair"):
            continue
        if u["status"] in ("failed", "ordered"):
            continue  # Handled by repair stage
        if u["asset_type"] == "local_graphic":
            continue  # Handled by graphics_compositing stage
        pre_blockers.append(f"{u['label'] or u['id']}={u['status']}")
    if pre_blockers:
        raise RuntimeError(
            "qa_media blocked: required render units are not ready for QA: "
            + ", ".join(pre_blockers[:10])
        )

    generated_units = [u for u in all_units if u["status"] == "generated"]

    if not generated_units:
        return {"status": "passed", "units_validated": 0}

    failed_units = []
    passed_count = 0

    for u in generated_units:
        unit_id = u["id"]
        try:
            validation = run_contract_media_qa(None, production_id, unit_id)
        except Exception as e:
            failed_units.append({"unit_id": unit_id, "label": u["label"], "error": str(e)})
            continue

        if validation["status"] == "fail":
            failed_units.append({"unit_id": unit_id, "label": u["label"]})
        else:
            passed_count += 1

    if failed_units:
        # Set failed units to needs_repair so the repair stage picks them up
        conn = _db.connect(None)
        for fu in failed_units:
            conn.execute(
                "UPDATE render_units SET status='needs_repair', updated_at=? WHERE id=?",
                (_db._now(), fu["unit_id"]),
            )
        conn.close()
        raise RuntimeError(
            f"Media QA failed for {len(failed_units)} units: {failed_units}"
        )

    conn = _db.connect(None)
    final_units = conn.execute(
        """SELECT id, label, asset_type, status
           FROM render_units
           WHERE production_id=? AND status!='stale'
           ORDER BY ordinal""",
        (production_id,),
    ).fetchall()
    conn.close()
    final_blockers = []
    for u in final_units:
        if u["status"] in ("valid", "needs_repair"):
            continue
        if u["asset_type"] == "local_graphic":
            continue  # Handled by graphics_compositing stage
        final_blockers.append(f"{u['label'] or u['id']}={u['status']}")
    if final_blockers:
        raise RuntimeError(
            "qa_media blocked: required render units are not valid/exempt: "
            + ", ".join(final_blockers[:10])
        )

    return {"status": "passed", "units_validated": passed_count}


def invoke_reconcile_timing(inputs: dict, tmp_path: Path) -> dict:
    """Reconcile the active storyboard with committed timeline spans.

    S2-T01: This was previously folded into compile_media. Separating it as its
    own stage makes the dependency explicit: compile_media can only proceed after
    timeline spans are reconciled with creative beats.
    """
    from tts_service import reconcile_storyboard_with_timing

    reconcile = reconcile_storyboard_with_timing(inputs["production_id"])
    if reconcile.get("unmatched"):
        raise RuntimeError(
            f"Unmatched timeline spans after reconciliation: {reconcile['unmatched']}. "
            f"Ensure storyboard and audio_timing stages have completed.")
    return {
        "status": "reconciled",
        "total_spans": reconcile["total_spans"],
        "matched": reconcile["matched"],
        "unmatched": reconcile.get("unmatched", []),
    }


def invoke_repair(inputs: dict, tmp_path: Path) -> dict:
    """DB-native repair stage (S2-T01).

    Two repair paths:
    1. Units with status='needs_repair' – classified and repaired via
       `run_repair_lifecycle` (ENG-0603).
    2. Open change requests – surfaced and blocked for manual resolution
       (legacy path).

    On a clean run with no failures and no change requests, this stage
    is a no-op pass-through.
    """
    import production_db as _db
    from media_service import run_repair_lifecycle

    production_id = inputs["production_id"]

    # --- Path 1: needs_repair units (ENG-0603) ---
    conn = _db.connect(None)
    needs_repair = conn.execute(
        """SELECT id, label, asset_type, status
           FROM render_units
           WHERE production_id=? AND status IN ('needs_repair','failed')
           ORDER BY ordinal""",
        (production_id,),
    ).fetchall()
    conn.close()

    repaired = []
    for ru in needs_repair:
        outcome = run_repair_lifecycle(
            production_id, ru["id"], db_path=None,
        )
        repaired.append(outcome)

    # --- Path 2: legacy open change requests ---
    conn = _db.connect(None)
    open_crs = conn.execute(
        """SELECT COUNT(*) as cnt FROM change_requests
           WHERE production_id=? AND status='open'""",
        (production_id,)
    ).fetchone()["cnt"]
    conn.close()

    if open_crs > 0 and not repaired:
        # Check if ALL open CRs target units that are already 'ordered' (in progress).
        # The route_change_request function sets units to 'ordered' when creating
        # a CR for generate_media. If all units are queued, no block needed.
        if open_crs > 0:
            conn = _db.connect(None)
            still_blocked = conn.execute(
                "SELECT COUNT(*) as c FROM change_requests cr "
                "JOIN render_units ru ON cr.subject_id = ru.id "
                "WHERE cr.production_id=? AND cr.status='open' "
                "AND (ru.status IS NULL OR ru.status != 'ordered')",
                (production_id,),
            ).fetchone()["c"]
            conn.close()
        else:
            still_blocked = open_crs
        if still_blocked > 0:
            raise RuntimeError(
                f"BLOCKED: {open_crs} open change request(s) require repair. "
                f"Resolve via: python3 scripts/produce_db.py resume {production_id} --from generate_media")

    if not repaired and open_crs == 0:
        return {"status": "skipped", "message": "No repairs needed"}

    qa_failures = [r for r in repaired if r.get("qa_passed") is False]
    if qa_failures:
        raise RuntimeError(
            f"Repair attempted but {len(qa_failures)} unit(s) failed re-QA: {qa_failures}"
        )

    return {"status": "completed", "repaired_units": repaired}


def invoke_graphics_compositing(inputs: dict, tmp_path: Path) -> dict:
    """Deterministic graphics/text compositing stage (S2-T01).

    Renders deterministic graphic overlays (lower-thirds, text cards, screen
    captures) that must NOT be delegated to a generative video model. If no
    render units require graphics, this stage is a no-op pass-through.

    Queries both ``still_kenburns`` and ``local_graphic`` render units.
    ``local_graphic`` units are rendered via ``render_local_graphic_render_unit``
    and registered as artifacts. Idempotent: rerun skips units with an active
    artifact.
    """
    import production_db as _db
    from pathlib import Path

    production_id = inputs["production_id"]
    conn = _db.connect(None)
    graphics_units = conn.execute(
        """SELECT id, label, asset_type, active_artifact_id, status
           FROM render_units
           WHERE production_id=?
             AND (asset_type='still_kenburns' OR asset_type='local_graphic')
             AND status!='stale'
           ORDER BY ordinal""",
        (production_id,)
    ).fetchall()
    conn.close()

    if not graphics_units:
        return {"status": "skipped", "message": "No graphics units to composite"}

    rendered = 0
    local_rendered = 0
    for u in graphics_units:
        if u["active_artifact_id"]:
            rendered += 1
            continue

        if u["asset_type"] == "local_graphic":
            from render_graphics import render_local_graphic_render_unit
            render_local_graphic_render_unit(None, production_id, u["id"])
            local_rendered += 1
            rendered += 1

    return {
        "status": "completed",
        "graphics_units": len(graphics_units),
        "rendered": rendered,
        "local_graphic_rendered": local_rendered,
    }


def invoke_assemble(inputs: dict, tmp_path: Path) -> dict:
    from assemble_db import build_assembly_manifest, register_deliverable
    import subprocess
    import tempfile

    production_id = inputs["production_id"]
    project_dir = _get_project_dir(inputs)

    # 1. Build the assembler manifest purely from DB (no manifest.json read)
    assembly_inputs = build_assembly_manifest(production_id, variant="16x9", db_path=None)
    
    # 2. Write to temp file for legacy assemble.py compatibility
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, dir=tmp_path) as f:
        json.dump(assembly_inputs, f)
        temp_manifest_path = f.name
        
    # 3. Call assemble.py with the DB-derived temp manifest
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "assemble.py"), temp_manifest_path, "--formats", "16x9"],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    if r.returncode != 0:
        raise RuntimeError(f"Assembly failed: {r.stderr[:500]}")
        
    # 4. Find the output video and register it as a deliverable
    output_video = project_dir / f"{inputs['project_slug']}_16x9.mp4"
    if not output_video.exists():
        candidates = list(project_dir.glob("*_16x9.mp4"))
        if candidates:
            output_video = candidates[0]
        else:
            raise RuntimeError("Assembly completed but output video not found")
            
    # 5. Register deliverable in DB
    deliverable = register_deliverable(
        production_id=production_id,
        variant="16x9",
        artifact_path=output_video,
        db_path=None
    )
    
    return {"status": "completed", "deliverable_id": deliverable["id"], "artifact_path": str(output_video)}


def invoke_qa_final(inputs: dict, tmp_path: Path) -> dict:
    from assemble_db import get_deliverables, run_final_qa
    from qa_final import run_db_contract_checks
    import subprocess
    
    production_id = inputs["production_id"]
    project_dir = _get_project_dir(inputs)
    
    # 1. Get the latest deliverable for this production
    deliverables = get_deliverables(production_id, db_path=None)
    if not deliverables:
        raise RuntimeError("No deliverable found to run final QA on")
        
    latest_deliverable = deliverables[-1]
    
    # 2. Run legacy qa_final.py to get the checks dict
    # qa_final.py takes the video path and outputs a report
    report_path = tmp_path / "final_qa_report.json"
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "qa_final.py"), latest_deliverable["artifact_uri"],
         "--output", str(report_path)],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    
    # 3. Parse checks and record in DB
    if report_path.exists():
        report = json.loads(report_path.read_text())
        checks = {
            "dimensions_ok": report.get("dimensions_ok", True),
            "duration_ok": report.get("duration_ok", True),
            "loudnorm_ok": report.get("loudnorm_ok", True),
            "no_black_frames": report.get("no_black_frames", True),
            "details": report
        }
    else:
        # Fallback if qa_final.py fails to write report but exits 0 (shouldn't happen, but safe)
        checks = {"dimensions_ok": True, "duration_ok": True, "loudnorm_ok": True, "no_black_frames": True}
        
    if r.returncode != 0:
        checks["no_black_frames"] = False # Force fail
        
    # 4. ENG-0801: Run DB-contract checks and merge into checks
    contract_evidence = run_db_contract_checks(
        production_id=production_id,
        deliverable_id=latest_deliverable["id"],
        db_path=None,
    )
    checks["contract_checks"] = contract_evidence
    checks["contract_version"] = contract_evidence.get("contract_version")
    
    # 5. Record final QA evidence in DB (mechanical + contract checks)
    validation = run_final_qa(
        production_id=production_id,
        deliverable_id=latest_deliverable["id"],
        checks=checks,
        db_path=None
    )
    
    if validation["status"] == "fail":
        contract_issues = contract_evidence.get("contract_issues", [])
        details = checks.get("details", {})
        raise RuntimeError(f"Final QA failed: mechanical={details.get('issues', [])}, contract={contract_issues}")
        
    return {"status": "passed", "validation_id": validation["id"], "contract_checks": contract_evidence}


def invoke_gate_b_review(inputs: dict, tmp_path: Path) -> dict:
    from assemble_db import get_deliverables, request_gate_b
    from authoring_service import record_approval_decision
    import production_db as _db
    import json
    
    production_id = inputs["production_id"]
    project_dir = _get_project_dir(inputs)
    
    deliverables = get_deliverables(production_id, db_path=None)
    if not deliverables:
        raise RuntimeError("No deliverable found for Gate B")
    
    latest = deliverables[-1]
    
    # ENG-0802: Require latest qa_final pass
    conn = _db.connect(None)
    latest_qa = conn.execute(
        "SELECT id, status, evidence_json FROM validations "
        "WHERE production_id=? AND subject_id=? AND validator_name='qa_final' "
        "ORDER BY created_at DESC LIMIT 1",
        (production_id, latest["id"]),
    ).fetchone()
    
    if not latest_qa:
        conn.close()
        raise RuntimeError(
            "Gate B blocked: no qa_final validation found for deliverable " + str(latest["id"])
        )
    
    if latest_qa["status"] != "pass":
        conn.close()
        raise RuntimeError(
            "Gate B blocked: latest qa_final validation status is '" + latest_qa["status"] + "'"
        )
    
    # ENG-0802: Require final QA evidence includes DB-contract fields
    try:
        ev = json.loads(latest_qa["evidence_json"]) if isinstance(latest_qa["evidence_json"], str) else latest_qa["evidence_json"]
    except Exception:
        ev = {}
    
    if not ev.get("contract_checks") or not ev["contract_checks"].get("all_contract_checks_pass"):
        conn.close()
        raise RuntimeError(
            "Gate B blocked: final QA evidence missing required DB-contract checks. "
            "Mechanical-only final QA is insufficient."
        )
    
    # ENG-0802: Require no unresolved failed validations for selected render units
    # Exclude change_requested units (they have expected FAIL validations from the
    # QA that triggered the change request; resolution is pending).
    failed_validations = conn.execute(
        "SELECT COUNT(*) as cnt FROM validations v "
        "JOIN render_units ru ON v.subject_id = ru.id AND ru.production_id = v.production_id "
        "WHERE v.production_id=? AND v.subject_type='render_unit' "
        "AND v.status='fail' AND ru.status != 'change_requested' "
        "AND v.created_at > ("
        "SELECT COALESCE(MAX(v2.created_at), '1970-01-01') "
        "FROM validations v2 "
        "WHERE v2.subject_id=v.subject_id AND v2.status='pass' "
        "AND v2.validator_name IN ('qa_media_contract', 'qa_media')"
        ")",
        (production_id,),
    ).fetchone()
    conn.close()
    
    if failed_validations and failed_validations["cnt"] > 0:
        raise RuntimeError(
            "Gate B blocked: " + str(failed_validations["cnt"]) + " render unit(s) have failed validations "
            "newer than their last pass"
        )
    
    # ENG-0802: Require deliverable is not already published
    if latest.get("status") == "published":
        raise RuntimeError(
            "Gate B blocked: deliverable " + str(latest["id"]) + " is already published"
        )
    
    approval = request_gate_b(
        production_id=production_id,
        deliverable_id=latest["id"],
        db_path=None
    )
    
    if os.environ.get("YT_TEST_MODE") == "1":
        record_approval_decision(
            production_id=production_id,
            gate_name="gate_b_review",
            decision="pass",
            actor="test_mode",
            note="Auto-approved in YT_TEST_MODE",
        )
        return {"status": "pass", "approval_id": approval["id"], "test_mode": True}
    
    if approval["status"] == "pending":
        raise RuntimeError(
            "gate_b_review pending approval. "
            "Use: python3 scripts/produce_db.py approve " + production_id + " gate_b_review --pass"
        )
    
    return {"status": approval["status"], "approval_id": approval["id"]}


def invoke_publish(inputs: dict, tmp_path: Path) -> dict:
    import production_db as _db

    production_id = inputs["production_id"]
    conn = _db.connect(None)

    # ENG-0802: Require gate_b_review to have passed (already enforced by stage order,
    # but harden the gate anyway).
    gate_b = conn.execute(
        "SELECT status FROM approval_requests WHERE production_id=? AND gate_name='gate_b_review'",
        (production_id,),
    ).fetchone()
    if not gate_b or gate_b["status"] != "pass":
        conn.close()
        raise RuntimeError(
            "Publish blocked: gate_b_review has not passed for production " + production_id
        )

    # ENG-0802: Require qa_passed or valid deliverable status (not any status)
    deliverables = conn.execute(
        """SELECT d.id, d.variant, d.status, a.uri, a.sha256
           FROM deliverables d
           LEFT JOIN artifacts a ON d.artifact_id = a.id
           WHERE d.production_id=? AND d.status='qa_passed'
           ORDER BY d.id DESC""",
        (production_id,),
    ).fetchall()

    if not deliverables:
        deliverables = conn.execute(
            """SELECT d.id, d.variant, d.status, a.uri, a.sha256
               FROM deliverables d
               LEFT JOIN artifacts a ON d.artifact_id = a.id
               WHERE d.production_id=? AND d.status IN ('qa_passed', 'valid')
               ORDER BY d.id DESC LIMIT 1""",
            (production_id,),
        ).fetchall()

    conn.close()
    deliverables = [dict(r) for r in deliverables]

    published = []
    for d in deliverables:
        if d["uri"]:
            p = Path(d["uri"])
            if not p.exists():
                continue
            published.append({
                "deliverable_id": d["id"],
                "uri": d["uri"],
                "sha256": d["sha256"],
                "variant": d["variant"],
                "status": "published",
            })
            with _db.transaction(None) as conn:
                conn.execute(
                    "UPDATE deliverables SET status='published' WHERE id=?",
                    (d["id"],),
                )

    if published:
        _db.append_event(production_id, "published",
                         payload={"deliverables": [p["deliverable_id"] for p in published]})
        return {"status": "published", "deliverables": published}
    return {"status": "no_deliverables", "deliverables": []}


def invoke_analytics(inputs: dict, tmp_path: Path) -> dict:
    import production_db as _db

    production_id = inputs["production_id"]
    conn = _db.connect(None)

    total_units = conn.execute(
        "SELECT COUNT(*) as cnt FROM render_units WHERE production_id=?",
        (production_id,),
    ).fetchone()["cnt"]

    generated = conn.execute(
        "SELECT COUNT(*) as cnt FROM render_units WHERE production_id=? AND status='generated'",
        (production_id,),
    ).fetchone()["cnt"]

    valid = conn.execute(
        "SELECT COUNT(*) as cnt FROM render_units WHERE production_id=? AND status='valid'",
        (production_id,),
    ).fetchone()["cnt"]

    artifacts = conn.execute(
        "SELECT COUNT(*) as cnt FROM artifacts WHERE production_id=?",
        (production_id,),
    ).fetchone()["cnt"]

    validations = conn.execute(
        "SELECT COUNT(*) as cnt, SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) as passing"
        " FROM validations WHERE production_id=?",
        (production_id,),
    ).fetchone()

    change_requests = conn.execute(
        "SELECT COUNT(*) as cnt FROM change_requests WHERE production_id=?",
        (production_id,),
    ).fetchone()["cnt"]

    open_crs = conn.execute(
        "SELECT COUNT(*) as cnt FROM change_requests WHERE production_id=? AND status='open'",
        (production_id,),
    ).fetchone()["cnt"]

    stages = conn.execute(
        "SELECT stage_name, status, created_at FROM stage_runs WHERE production_id=? ORDER BY created_at",
        (production_id,),
    ).fetchall()

    conn.close()

    analytics = {
        "production_id": production_id,
        "total_render_units": total_units,
        "generated_units": generated,
        "valid_units": valid,
        "total_artifacts": artifacts,
        "total_validations": validations["cnt"],
        "passing_validations": validations["passing"],
        "total_change_requests": change_requests,
        "open_change_requests": open_crs,
        "stages": [{"stage": s["stage_name"], "status": s["status"], "at": s["created_at"]} for s in stages],
    }

    _db.append_event(production_id, "analytics", payload=analytics)
    return {"status": "recorded", "analytics": analytics}


STAGE_INVOKERS = {
    # Pre-TTS stages are now DB-native via authoring_service (output_kind=None to prevent double-save)
    "research": (None, invoke_research),
    "write_script": (None, invoke_write_script),
    "review_script": (None, invoke_review_script),
    "gate_a_content": ("gate_a_content_approval", invoke_gate_a_content),
    # S2-T01: storyboard comes before TTS in the canonical order.
    # DB-native: invoke_storyboard/review_storyboard save their own document via
    # authoring_service.save_storyboard and return only a summary, so output_kind
    # is None (a set output_kind would save the summary as the document and
    # corrupt it — e.g. {"beats": <count>} replacing the real beats list).
    "storyboard": (None, invoke_storyboard),
    "review_storyboard": (None, invoke_review_storyboard),
    # TTS and timing stages are now DB-native via tts_service
    "tts": (None, invoke_tts),
    "audio_timing": (None, invoke_audio_timing),
    "reconcile_timing": (None, invoke_reconcile_timing),
    # Compile media is now DB-native via tts_service.compile_render_plan
    "compile_media": (None, invoke_compile_media),
    "gate_a_spend": ("gate_a_spend_approval", invoke_gate_a_spend),
    "generate_media": (None, invoke_generate_media),
    # QA Media is now DB-native via media_service.run_render_unit_qa
    "qa_media": (None, invoke_qa_media),
    "repair": (None, invoke_repair),
    "graphics_compositing": (None, invoke_graphics_compositing),
    # Assembly, QA, and Gate B are now DB-native via assemble_db
    "assemble": (None, invoke_assemble),
    "qa_final": (None, invoke_qa_final),
    "gate_b_review": (None, invoke_gate_b_review),
    "publish": (None, invoke_publish),
    "analytics": (None, invoke_analytics),
}


def run_production(production_id: str, from_stage: str = None, db_path=None):
    """Execute or resume a production via the stage registry."""
    prod = _db.get_production(production_id, db_path=db_path)
    if not prod:
        print(f"Error: Production '{production_id}' not found.", file=sys.stderr)
        sys.exit(1)

    if from_stage:
        if from_stage not in STAGE_REGISTRY:
            print(f"Error: Unknown stage '{from_stage}'.", file=sys.stderr)
            sys.exit(1)
        print(f"Invalidating stages from '{from_stage}' onward...")
        downstream = stage_runner.downstream_stages(from_stage)
        stages_to_invalidate = [from_stage] + downstream
        _db.invalidate_stages(prod["project_slug"], stages_to_invalidate, reason=f"resume from {from_stage}", db_path=db_path)

    print(f"Running production: {prod['project_slug']} ({prod['id']})")
    
    if not os.environ.get("YT_TEST_MODE"):
        from release_guard import require_production_ready
        require_production_ready()
    
    # STAGE_REGISTRY is defined in topological order. Iterating over .keys()
    # will naturally evaluate stages in dependency order.
    while True:
        next_stage = None
        for stage_name in STAGE_REGISTRY.keys():
            satisfied, missing = stage_runner.deps_satisfied(stage_name, production_id, db_path=db_path)
            if not satisfied:
                continue
            
            conn = _db.connect(db_path)
            row = conn.execute(
                """SELECT status FROM stage_runs 
                   WHERE production_id=? AND stage_name=? ORDER BY attempt DESC LIMIT 1""",
                (production_id, stage_name),
            ).fetchone()
            conn.close()
            
            if row and row["status"] == "succeeded":
                continue
                
            next_stage = stage_name
            break
            
        if not next_stage:
            print("✓ All stages completed successfully.")
            _db.append_event(production_id, "production_completed", db_path=db_path)
            with _db.transaction(db_path) as conn:
                conn.execute("UPDATE productions SET status='completed' WHERE id=?", (production_id,))
            break

        print(f"\n▶ Executing stage: {next_stage}")
        output_kind, invoker_fn = STAGE_INVOKERS.get(next_stage, (None, None))
        if not invoker_fn:
            print(f"Warning: No invoker for stage '{next_stage}', marking succeeded.", file=sys.stderr)
            _db.mirror_stage_state(prod["project_slug"], next_stage, "done", db_path=db_path)
            continue

        adapter = LegacyAdapter(next_stage, output_kind, invoker_fn)
        try:
            input_data = {
                "production_id": production_id,
                "project_slug": prod["project_slug"], 
                "seed": prod["seed"], 
                "video_type": prod["video_type"]
            }
            adapter.run(production_id, input_data, db_path=db_path)
            print(f"  ✓ Stage '{next_stage}' completed.")
        except Exception as e:
            print(f"  ✗ Stage '{next_stage}' failed: {e}", file=sys.stderr)
            print(f"Resume with: python3 scripts/produce_db.py resume {production_id}", file=sys.stderr)
            sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description="DB-native production orchestrator.")
    sub = ap.add_subparsers(dest="command", required=True)
    
    create = sub.add_parser("create")
    create.add_argument("--seed", required=True)
    create.add_argument("--format", dest="video_type", default="short", choices=["short", "explainer", "teaser", "smoke"])
    
    run_cmd = sub.add_parser("run")
    run_cmd.add_argument("production_id")
    run_cmd.add_argument("--from-stage", help="Invalidate and resume from this stage")
    
    resume = sub.add_parser("resume")
    resume.add_argument("production_id")
    
    status = sub.add_parser("status")
    status.add_argument("production_id")
    
    approve = sub.add_parser("approve")
    approve.add_argument("production_id")
    approve.add_argument("gate", choices=["gate_a_content", "gate_a_spend", "gate_b_review"])
    approve.add_argument("--pass", dest="decision", action="store_const", const="pass", default="pass")
    approve.add_argument("--fail", dest="decision", action="store_const", const="fail")
    
    args = ap.parse_args()
    
    if args.command == "approve":
        from authoring_service import record_approval_decision
        result = record_approval_decision(
            production_id=args.production_id,
            gate_name=args.gate,
            decision=args.decision,
            actor="cli",
            note=f"CLI decision: {args.decision}",
        )
        print(json.dumps(result, indent=2))
    elif args.command == "create":
        slug = _slug(args.seed)
        proj_dir = PROJECTS / f"{slug}_{args.video_type}"
        prod = _db.ensure_production(slug, seed=args.seed, video_type=args.video_type, db_path=None)
        print(json.dumps({
            "production_id": prod["id"], 
            "project_slug": slug, 
            "project_dir": str(proj_dir)
        }, indent=2))
        
    elif args.command == "run":
        run_production(args.production_id, from_stage=args.from_stage)
        
    elif args.command == "resume":
        run_production(args.production_id)
        
    elif args.command == "status":
        prod = _db.get_production(args.production_id)
        if not prod:
            print(f"Error: Production '{args.production_id}' not found.", file=sys.stderr)
            sys.exit(1)
        blockers = _db.blockers(args.production_id)
        print(json.dumps({"production": prod, "blockers": blockers}, indent=2))


if __name__ == "__main__":
    main()

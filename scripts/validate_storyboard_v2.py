#!/usr/bin/env python3
"""validate_storyboard_v2.py — Semantic alignment validator for canonical storyboards.

Enforces semantic alignment rules beyond JSON Schema:
- Blocks generic B-roll phrases (e.g. "business people in office").
- Blocks B-roll narrative_alignment that does not reference segment argument/claim/viewer takeaway.
- Blocks overlays with a source_label type but no source_ref or claim_refs.
- Blocks graphic shots whose why_this_visual/narrative_alignment is purely decorative.
- Blocks conclusion segment shots with visuals unrelated to the argument.
- Blocks generated-video shots requesting readable text.
- Allows generic visuals only via emotional_reset with explicit justification.

This is a validation-only module. No LLM calls, no creative generation, no DB writes.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "storyboard_v2"

GENERIC_BROLL_PHRASES = [
    "business people", "business person",
    "professional environment",
    "generic office", "modern office",
    "people working", "people in a meeting",
    "stock footage",
    "abstract data",
    "city skyline",
    "person typing", "person at a desk",
    "man in suit",
    "server room",
    "whiteboard with",
    "corporate setting",
    "conference room",
    "handshake",
    "team meeting",
    "office building",
]


def _is_generic_broll(visual_concept, narrative_alignment):
    concept_lower = (visual_concept or "").lower()
    alignment_lower = (narrative_alignment or "").lower()
    for phrase in GENERIC_BROLL_PHRASES:
        if phrase in concept_lower or phrase in alignment_lower:
            return phrase
    return None


def _is_vague_alignment(narrative_alignment, segment_argument, claim_texts):
    alignment_lower = (narrative_alignment or "").lower().strip()
    if not alignment_lower or len(alignment_lower) < 20:
        return True
    argument_tokens = set((segment_argument or "").lower().split())
    claim_tokens = set()
    for claim in (claim_texts or []):
        claim_tokens.update(claim.lower().split())
    match_tokens = set(alignment_lower.split())
    overlap = match_tokens & (argument_tokens | claim_tokens)
    return len(overlap) < 2


def _has_readable_text(shot):
    concept = (shot.get("visual_concept") or "").lower()
    alignment = (shot.get("narrative_alignment") or "").lower()
    combined = concept + " " + alignment
    must_show_texts = " ".join(shot.get("must_show") or []).lower()
    must_avoid_texts = " ".join(shot.get("must_avoid") or []).lower()
    prompt_intent = (shot.get("prompt_intent") or "").lower()

    search_space = f"{combined} {must_show_texts} {prompt_intent}"
    avoid_space = f"{must_avoid_texts}"

    for pattern in [r"readable (?:generated )?text", r"on.?screen text",
                    r"caption", r"subtitle", r"text overlay", r"visible text"]:
        for match in re.finditer(pattern, search_space, re.I):
            pre = search_space[max(0, match.start() - 15):match.start()].lower()
            post = search_space[match.end():match.end() + 20].lower()
            nearby = f"{pre} {post}"
            if any(neg in nearby for neg in ("no ", "without ", "not ", "free of", "avoid")):
                continue
            if any(neg in avoid_space for neg in ("no readable", "without readable", "avoid readable")):
                continue
            return match.group()
    return None


def is_canonical(data):
    return "storyboard_contract_version" in data


def validate_semantic_alignment(storyboard):
    errors = []

    if not is_canonical(storyboard):
        return errors

    shots = storyboard.get("shots", [])
    overlays_list = storyboard.get("overlays", [])
    narrative_beats = storyboard.get("narrative_beats", [])
    claim_inventory = storyboard.get("claim_inventory", [])
    work_orders = storyboard.get("segment_work_orders", [])

    shot_map = {s.get("shot_id"): s for s in shots}
    beat_map = {}
    for beat in narrative_beats:
        sid = beat.get("segment_id")
        if sid:
            if sid not in beat_map:
                beat_map[sid] = []
            beat_map[sid].append(beat)

    claim_map = {c.get("claim_id"): c for c in claim_inventory}
    wo_by_segment = {wo.get("segment_id"): wo for wo in work_orders}

    for idx, shot in enumerate(shots):
        shot_id = shot.get("shot_id", f"<index {idx}>")
        sid = shot.get("segment_id", "")
        visual_role = (shot.get("visual_role") or "").lower()
        visual_concept = shot.get("visual_concept") or ""
        narrative_alignment = shot.get("narrative_alignment") or ""
        claim_refs = shot.get("claim_refs") or []
        is_graphic = visual_role.startswith("graphic") or visual_role in ("kinetic_text", "ui_insert")

        wo = wo_by_segment.get(sid, {})
        segment_argument = wo.get("argument_summary", "")
        beats_for_seg = beat_map.get(sid, [])
        is_conclusion = any(b.get("act", 0) >= 5 for b in beats_for_seg)

        resolved_claim_texts = []
        for ref in claim_refs:
            c = claim_map.get(ref)
            if c:
                resolved_claim_texts.append(c.get("claim_text", ""))
        if not resolved_claim_texts:
            resolved_claim_texts = [segment_argument]

        if visual_role == "emotional_reset":
            generic_phrase = _is_generic_broll(visual_concept, narrative_alignment)
            justification = shot.get("why_this_visual") or ""
            if len(justification.strip()) < 20:
                errors.append({
                    "path": f"shots[{idx}].why_this_visual",
                    "entity_id": shot_id,
                    "severity": "BLOCKER",
                    "message": (
                        f"BLOCKED_GENERIC_BROLL: emotional_reset shot '{shot_id}' must have "
                        f"an explicit justification in why_this_visual explaining why the "
                        f"reset is needed. Got: '{justification[:50]}'."
                    ),
                })
            continue

        if visual_role.startswith("broll"):
            generic_phrase = _is_generic_broll(visual_concept, narrative_alignment)
            if generic_phrase:
                errors.append({
                    "path": f"shots[{idx}].visual_concept",
                    "entity_id": shot_id,
                    "severity": "BLOCKER",
                    "message": (
                        f"BLOCKED_GENERIC_BROLL: generic B-roll phrase '{generic_phrase}' detected. "
                        f"B-roll must be specific, source-grounded, and support the argument. "
                        f"Generic fillers are forbidden unless visual_role=emotional_reset."
                    ),
                })

            if _is_vague_alignment(narrative_alignment, segment_argument, resolved_claim_texts):
                errors.append({
                    "path": f"shots[{idx}].narrative_alignment",
                    "entity_id": shot_id,
                    "severity": "BLOCKER",
                    "message": (
                        f"BLOCKED_VAGUE_BROLL_ALIGNMENT: B-roll shot '{shot_id}' "
                        f"narrative_alignment does not sufficiently reference the segment argument, "
                        f"claim, or viewer takeaway. Got: '{narrative_alignment[:80]}'. "
                        f"Segment argument: '{segment_argument[:80]}'."
                    ),
                })

        if is_graphic:
            concept_lower = visual_concept.lower()
            alignment_lower = narrative_alignment.lower()
            why_visual = (shot.get("why_this_visual") or "").lower()
            decorative_patterns = ["decorative", "visual interest", "pretty", "aesthetic",
                                   "background", "filler", "nice to have"]
            is_decorative = any(p in concept_lower or p in alignment_lower or p in why_visual
                                for p in decorative_patterns)
            if is_decorative:
                errors.append({
                    "path": f"shots[{idx}].visual_concept",
                    "entity_id": shot_id,
                    "severity": "BLOCKER",
                    "message": (
                        f"BLOCKED_DECORATIVE_GRAPHIC: graphic shot '{shot_id}' "
                        f"appears purely decorative without explaining or supporting the segment argument. "
                        f"Every graphic must have a clear semantic purpose tied to viewer comprehension."
                    ),
                })

        if is_conclusion:
            conclusion_keywords = ["conclusion", "closing", "final point", "summarize",
                                   "takeaway", "message", "reinforce", "conviction", "legacy"]
            alignment_lower = narrative_alignment.lower()
            has_conclusion_signal = any(k in alignment_lower for k in conclusion_keywords)
            has_supporting = any(ct.lower() in alignment_lower for ct in resolved_claim_texts
                                 if len(ct) > 10)
            if not has_conclusion_signal and not has_supporting:
                errors.append({
                    "path": f"shots[{idx}].narrative_alignment",
                    "entity_id": shot_id,
                    "severity": "BLOCKER",
                    "message": (
                        f"BLOCKED_UNRELATED_CONCLUSION_VISUAL: conclusion segment shot "
                        f"'{shot_id}' (act >= 5) has narrative_alignment '{narrative_alignment[:80]}' "
                        f"that does not reference the conclusion argument, takeaway, or closing message."
                    ),
                })

        asset_type = (shot.get("asset_type") or "").lower()
        if asset_type in ("generated_video", "generated_still"):
            text_issue = _has_readable_text(shot)
            if text_issue:
                errors.append({
                    "path": f"shots[{idx}].visual_concept",
                    "entity_id": shot_id,
                    "severity": "BLOCKER",
                    "message": (
                        f"BLOCKED_READABLE_TEXT_IN_GENERATED: generated-video shot '{shot_id}' "
                        f"requests readable in-scene text ('{text_issue}'). "
                        f"Generated models cannot produce reliable readable text."
                    ),
                })

    for idx, overlay in enumerate(overlays_list):
        overlay_id = overlay.get("overlay_id", f"<index {idx}>")
        overlay_type = (overlay.get("overlay_type") or "").lower()

        if overlay_type == "source_label":
            source_ref = overlay.get("source_ref", "")
            claim_refs = overlay.get("claim_refs", [])
            if not source_ref.strip() and (not claim_refs or len(claim_refs) == 0):
                errors.append({
                    "path": f"overlays[{idx}].source_ref",
                    "entity_id": overlay_id,
                    "severity": "BLOCKER",
                    "message": (
                        f"BLOCKED_PURPOSELESS_OVERLAY: source_label overlay '{overlay_id}' "
                        f"has no source_ref and no claim_refs. "
                        f"Source labels must reference a valid source or claim."
                    ),
                })

        has_text = bool((overlay.get("text") or "").strip())
        if has_text:
            overlay_claim_refs = overlay.get("claim_refs", [])
            source_ref = overlay.get("source_ref", "")
            if not overlay_claim_refs and not source_ref.strip() and overlay_type == "stat_display":
                errors.append({
                    "path": f"overlays[{idx}].claim_refs",
                    "entity_id": overlay_id,
                    "severity": "BLOCKER",
                    "message": (
                        f"BLOCKED_PURPOSELESS_OVERLAY: stat_display overlay '{overlay_id}' "
                        f"displays text '{overlay.get('text', '')[:60]}' but has no claim_refs "
                        f"or source_ref linking it to a specific claim. Statistics must be "
                        f"grounded in source evidence."
                    ),
                })

    return errors


def load_fixture(name):
    path = _FIXTURE_ROOT / name
    if not path.exists():
        raise FileNotFoundError(f"Fixture not found: {path}")
    return json.loads(path.read_text())


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 validate_storyboard_v2.py <storyboard.json> [--output-json out.json]",
              file=sys.stderr)
        sys.exit(2)

    data = json.loads(Path(sys.argv[1]).read_text())
    errors = validate_semantic_alignment(data)
    output_json = None
    if len(sys.argv) >= 4 and sys.argv[2] == "--output-json":
        output_json = sys.argv[3]

    result = {
        "task": "storyboard_semantic_alignment_validation",
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "error_count": len(errors),
    }

    if output_json:
        Path(output_json).parent.mkdir(parents=True, exist_ok=True)
        Path(output_json).write_text(json.dumps(result, indent=2))

    if errors:
        for e in errors:
            print(f"SEMANTIC ERROR: [{e['severity']}] {e['entity_id']}: {e['message']}")
        sys.exit(1)
    else:
        print("SEMANTIC ALIGNMENT: PASS")
        sys.exit(0)


if __name__ == "__main__":
    main()

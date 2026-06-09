#!/usr/bin/env python3
"""generate_content_brief.py — Packaging & Ideation stage.

Runs BEFORE scripting. Given a pillar + pain/topic seed, generates:
- 3-5 title variants (scored for CTR)
- Thumbnail concept
- Hook concept
- Topic viability assessment

Cheap to run (text-only LLM) — gates expensive downstream work.

Usage:
  python3 scripts/generate_content_brief.py --topic "How to compound career capital" --pillar "Career capital"
  python3 scripts/generate_content_brief.py --pain "Mid-career professionals feel stuck" --pillar "AI leverage"
  python3 scripts/generate_content_brief.py --topic "..." --output briefs/001.json
  python3 scripts/generate_content_brief.py --topic "..." --dry-run
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

BRIEF_PROMPT = """You are the packaging strategist for Leverage Mind, a faceless educational YouTube channel targeting mid-career professionals (30-45, $90k+, time-poor, analytically oriented).

Your job: evaluate whether this TOPIC is worth making a video about, and if yes, produce a content brief that maximizes Click-Through Rate (CTR) before any expensive scripting begins.

TOPIC SEED: {topic}
PILLAR: {pillar}
AUDIENCE PAIN: {pain}

Produce:

1. VIABILITY ASSESSMENT (1-5):
   - search_demand: would people search for this?
   - differentiation: can James add something no one else has?
   - framework_potential: can an original framework be built here?
   - CTR_potential: can this become a clickable title+thumbnail?
   - verdict: "proceed" or "reject" with one-line reason

2. TITLE VARIANTS (5):
   Each title must be:
   - Under 60 characters
   - Curiosity-driven (open loop or counterintuitive claim)
   - Sound like a James Harrington video (precise, authoritative, not hype)
   - Score each 1-5 on: curiosity, clarity, CTR_prediction

3. THUMBNAIL CONCEPT:
   One sentence describing the thumbnail visual that pairs with the best title.
   Must be achievable with: James reference image + simple graphic/text overlay.

4. HOOK DIRECTION:
   One sentence describing the opening hook angle (not the full hook — that's generated later).

5. FORMAT RECOMMENDATION:
   Which format archetype fits best: System-reveal / Contrarian-take / Framework / Build-with-me / Teardown / Experiment

Respond ONLY with valid JSON:
```json
{{
  "topic": "...",
  "pillar": "...",
  "viability": {{
    "search_demand": N,
    "differentiation": N,
    "framework_potential": N,
    "ctr_potential": N,
    "overall": N,
    "verdict": "proceed|reject",
    "reason": "..."
  }},
  "titles": [
    {{"text": "...", "char_count": N, "curiosity": N, "clarity": N, "ctr_prediction": N, "total": N}}
  ],
  "thumbnail_concept": "...",
  "hook_direction": "...",
  "format_archetype": "...",
  "proceed": true|false
}}
```
"""


def generate_brief(topic, pillar="", pain="", dry_run=False, output_path=None):
    from llm_call import llm_call

    prompt = BRIEF_PROMPT.format(
        topic=topic or "(not specified — derive from pain)",
        pillar=pillar or "General",
        pain=pain or "(not specified)")

    data, raw, profile, model = llm_call(
        task="script_writing",  # creative authority required
        prompt=prompt, dry_run=dry_run, expect_json=True)

    if dry_run:
        return {"status": "dry_run", "topic": topic, "model": model}

    if data is None:
        raise RuntimeError("No response from LLM")

    # Validate
    viability = data.get("viability", {})
    if viability.get("verdict") == "reject":
        print(f"  ⊘ REJECTED: {viability.get('reason', 'no reason given')}")
        data["proceed"] = False
    else:
        data["proceed"] = True
        titles = data.get("titles", [])
        titles.sort(key=lambda t: t.get("total", 0), reverse=True)
        data["titles"] = titles

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json.dumps(data, indent=2))

    return data


def main():
    ap = argparse.ArgumentParser(description="Generate a content brief (packaging + ideation).")
    ap.add_argument("--topic", default=None, help="Topic seed")
    ap.add_argument("--pain", default=None, help="Audience pain point")
    ap.add_argument("--pillar", default="", help="Content pillar")
    ap.add_argument("--output", "-o", default=None, help="Output JSON path")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.topic and not args.pain:
        ap.error("--topic or --pain required")

    try:
        result = generate_brief(args.topic, args.pillar, args.pain,
                                dry_run=args.dry_run, output_path=args.output)
    except (RuntimeError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        return

    v = result.get("viability", {})
    print(f"\nTopic: {result.get('topic')}")
    print(f"Verdict: {'✓ PROCEED' if result.get('proceed') else '✗ REJECT'} "
          f"(score {v.get('overall', '?')}/5)")
    if result.get("proceed"):
        print(f"\nBest titles:")
        for i, t in enumerate(result.get("titles", [])[:3]):
            print(f"  {i+1}. \"{t['text']}\" (CTR {t.get('ctr_prediction', '?')}/5)")
        print(f"\nThumbnail: {result.get('thumbnail_concept', '?')}")
        print(f"Hook angle: {result.get('hook_direction', '?')}")
        print(f"Format: {result.get('format_archetype', '?')}")

    if args.output:
        print(f"\n  Saved: {args.output}")


if __name__ == "__main__":
    main()

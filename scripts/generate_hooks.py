#!/usr/bin/env python3
"""generate_hooks.py — Generate and score hook variants for a topic/script.

Produces 5 ranked hook variants using the brand voice, scores each for
open-loop strength, and selects one for the script. Spares are banked for shorts.

Usage:
  python3 scripts/generate_hooks.py --topic "How compounding works for careers" --pillar "Career capital"
  python3 scripts/generate_hooks.py --script scripts/generated/script.json
  python3 scripts/generate_hooks.py --topic "..." --output hooks.json
  python3 scripts/generate_hooks.py --topic "..." --dry-run
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

HOOK_PROMPT = """You are writing hooks for James Harrington — a ~60-year-old British professional (RP accent, Oxbridge cadence) who spent 35 years across consulting, merchant banking, startups, and venture capital. He teaches systems thinking and professional leverage.

VOICE: calm, precise, understated authority. Short declarative sentences. No hype, no filler, no motivational platitudes. He speaks from experience, not theory.

Generate exactly 5 hook variants for the following topic. Each hook is the FIRST THING the viewer hears — opening 1-2 sentences (max 25 words each).

TOPIC: {topic}
PILLAR: {pillar}

Each hook must be a different TYPE:
1. Counterintuitive claim (challenges a default belief)
2. Relatable pain (names a frustration the audience feels)
3. Pattern interrupt (unexpected framing or metaphor)
4. Credibility signal (implies deep experience without bragging)
5. Open loop (raises a question the viewer needs answered)

CONSTRAINTS:
- Each must work as a standalone first sentence — no "in this video" setup.
- Must be speakable in ≤8 seconds at 2.4 WPS.
- Must sound like James, not a copywriter.

SCORING: Rate each hook 1-5 on:
- open_loop_strength: how urgently does the viewer need to keep watching?
- speakability: does it flow naturally when spoken aloud?
- james_voice: does it sound like James?

Respond ONLY with valid JSON:
```json
{{
  "topic": "...",
  "hooks": [
    {{
      "rank": 1,
      "type": "counterintuitive|relatable_pain|pattern_interrupt|credibility|open_loop",
      "text": "...",
      "word_count": N,
      "scores": {{"open_loop_strength": N, "speakability": N, "james_voice": N}},
      "total_score": N
    }}
  ],
  "selected": 0,
  "selection_reason": "..."
}}
```
Rank from strongest (1) to weakest (5). "selected" is the 0-indexed position of the recommended hook.
"""


def generate_hooks(topic, pillar="", script_path=None, dry_run=False, output_path=None):
    """Generate hook variants via LLM. Returns parsed hook report."""
    from llm_call import llm_call

    if script_path and not topic:
        script = json.load(open(script_path))
        # Extract topic from first segment text or project_id
        texts = [seg.get("text", "") for seg in script.get("segments", []) if seg.get("text")]
        topic = texts[0][:100] if texts else script.get("project_id", "unknown topic")
        pillar = script.get("pillar", pillar)

    prompt = HOOK_PROMPT.format(topic=topic, pillar=pillar or "General")

    data, raw, profile, model = llm_call(
        task="hook_generation",
        prompt=prompt,
        dry_run=dry_run,
        expect_json=True)

    if dry_run:
        return {"status": "dry_run", "topic": topic, "model": model}

    if data is None:
        raise RuntimeError("No response from LLM for hook generation")

    # Validate structure
    hooks = data.get("hooks", [])
    if len(hooks) < 3:
        raise RuntimeError(f"Expected ≥3 hooks, got {len(hooks)}")

    # Sort by total_score descending
    hooks.sort(key=lambda h: h.get("total_score", 0), reverse=True)
    data["hooks"] = hooks
    data["selected"] = 0  # top-ranked after sort

    # Output
    if output_path:
        Path(output_path).write_text(json.dumps(data, indent=2))

    return data


def main():
    ap = argparse.ArgumentParser(description="Generate and score hook variants.")
    ap.add_argument("--topic", default=None, help="Topic for hooks")
    ap.add_argument("--pillar", default="", help="Content pillar")
    ap.add_argument("--script", default=None, help="Extract topic from script JSON")
    ap.add_argument("--output", "-o", default=None, help="Output JSON path")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.topic and not args.script:
        ap.error("--topic or --script required")

    try:
        result = generate_hooks(args.topic, args.pillar, args.script,
                                dry_run=args.dry_run, output_path=args.output)
    except (RuntimeError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        return

    # Print results
    print(f"Topic: {result.get('topic', '?')}")
    print(f"Hooks ({len(result.get('hooks', []))}):\n")
    for i, h in enumerate(result.get("hooks", [])):
        sel = " ← SELECTED" if i == result.get("selected") else ""
        print(f"  {i+1}. [{h.get('type', '?')}] (score {h.get('total_score', '?')}/15){sel}")
        print(f"     \"{h.get('text', '')}\"")
        print(f"     {h.get('word_count', '?')} words | "
              f"loop={h.get('scores', {}).get('open_loop_strength', '?')} "
              f"speak={h.get('scores', {}).get('speakability', '?')} "
              f"voice={h.get('scores', {}).get('james_voice', '?')}")
        print()

    if result.get("selection_reason"):
        print(f"  Reason: {result['selection_reason']}")

    if args.output:
        print(f"\n  Saved: {args.output}")
        print(f"  Spares banked for shorts/atomization.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""review_media_plan.py — LLM reviewer gate for media/visual plans.

Reviews a storyboard or media prompt plan for visual feasibility, text-surface risk,
brand compliance, and shot coherence.

Usage:
  python3 scripts/review_media_plan.py scripts/generated/script.json --dry-run
  python3 scripts/review_media_plan.py scripts/generated/script.json --output review.json
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

MEDIA_REVIEW_PROMPT = """You are reviewing a video storyboard/media plan for production feasibility.

Evaluate each segment's visual brief for:

1. **Text-surface risk** (1-5): Any scene likely to produce AI-generated gibberish text? (screens, documents, whiteboards, slides = high risk)
2. **Visual coherence** (1-5): Do the shots form a logical visual sequence? Variety without randomness?
3. **Brand alignment** (1-5): Does the visual style match premium, grounded, professional business cinematography?
4. **Generability** (1-5): Can current models (Seedance 2.0) produce these visuals at acceptable quality?
5. **9:16 crop safety** (1-5): Is the visual action center-framed for safe vertical crop?

BLOCKING conditions (status=fail if ANY true):
- Any visual brief explicitly requests readable screens, documents, whiteboards, charts with labels
- A brief describes close-up hands/faces but is NOT routed to seedance_2_0
- Adjacent shots are near-identical (no visual variety)

Respond ONLY with valid JSON:
```json
{
  "task": "media_plan_review",
  "status": "pass|fail",
  "scores": {"text_risk": N, "coherence": N, "brand": N, "generability": N, "crop_safety": N},
  "overall_score": N,
  "blocking_issues": [],
  "warnings": [],
  "recommended_fixes": [],
  "may_proceed": true|false
}
```
"""


def run_review(script_path, dry_run=False, output_path=None):
    from llm_call import llm_call

    script = json.load(open(script_path))

    # Build media plan summary for review
    lines = []
    for seg in script.get("segments", []):
        sid = seg["id"]
        mode = seg.get("audio_mode", "generated_tts")
        brief = seg.get("visual_brief", "")
        shots = seg.get("shots", [])
        if shots:
            for sh in shots:
                lines.append(f"  [{sh['id']}] ({mode}) {sh.get('visual_brief', brief)}")
        else:
            lines.append(f"  [{sid}] ({mode}) {brief}")

    plan_text = "\n".join(lines)
    full_prompt = f"{MEDIA_REVIEW_PROMPT}\n\n---\n\nMEDIA PLAN:\nProject: {script.get('project_id')}\n\n{plan_text}"

    data, raw, profile, model = llm_call(
        task="media_prompt_compilation",
        prompt=full_prompt,
        dry_run=dry_run,
        expect_json=True)

    if dry_run:
        return {"status": "dry_run", "model": model}

    if data is None:
        print("  ERROR: no response from LLM", file=sys.stderr)
        return {"status": "error"}

    status = data.get("status", "unknown")
    score = data.get("overall_score", "?")
    icon = "✓" if status == "pass" else "✗"
    print(f"  {icon} media plan: {status} (score {score}/5)")
    if data.get("blocking_issues"):
        for b in data["blocking_issues"]:
            print(f"    BLOCKING: {b}")

    if output_path:
        Path(output_path).write_text(json.dumps(data, indent=2))
        print(f"  report: {output_path}")

    return data


def main():
    ap = argparse.ArgumentParser(description="LLM reviewer gate for media plans.")
    ap.add_argument("script", help="Path to script JSON")
    ap.add_argument("--output", "-o", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    report = run_review(args.script, dry_run=args.dry_run, output_path=args.output)
    sys.exit(0 if report.get("may_proceed", False) or args.dry_run else 1)


if __name__ == "__main__":
    main()

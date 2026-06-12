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

    doc = json.load(open(script_path))

    # Build the plan summary. Supports BOTH the v2 media_plan.json (beats[]) and
    # the legacy script JSON (segments[]/shots[]).
    lines = []
    if "beats" in doc:
        # v2 media_plan.json — one line per beat with shot_type + compiled prompt.
        for b in doc["beats"]:
            st = b.get("shot_type", "?")
            pol = b.get("audio_policy", "")
            brief = b.get("positive_prompt") or b.get("visual_brief", "")
            lines.append(f"  [{b['beat_id']}] {st} ({pol}) {brief[:160]}")
    else:
        for seg in doc.get("segments", []):
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
    full_prompt = f"{MEDIA_REVIEW_PROMPT}\n\n---\n\nMEDIA PLAN:\nProject: {doc.get('project_id')}\n\n{plan_text}"

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
    ap = argparse.ArgumentParser(description="LLM reviewer gate (G3) for media plans.")
    ap.add_argument("media_plan", help="Path to media_plan.json (v2) or legacy script JSON")
    ap.add_argument("--output", "-o", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--record-gate", action="store_true",
                    help="Record the media_plan_review gate (G3) on pass")
    ap.add_argument("--project-id", default=None)
    args = ap.parse_args()

    report = run_review(args.media_plan, dry_run=args.dry_run, output_path=args.output)
    passed = bool(report.get("may_proceed", False))

    if args.record_gate and not args.dry_run:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from gates import record_gate
        doc = json.load(open(args.media_plan))
        pid = args.project_id or doc.get("project_id")
        if not pid:
            print("ERROR: --record-gate needs a project id", file=sys.stderr)
            sys.exit(1)
        record_gate(pid, "media_plan_review", "pass" if passed else "fail",
                    artifact_path=str(args.media_plan),
                    extra={"score": report.get("overall_score")})
        print(f"  gate media_plan_review={'pass' if passed else 'fail'} recorded for {pid}")

    sys.exit(0 if passed or args.dry_run else 1)


if __name__ == "__main__":
    main()

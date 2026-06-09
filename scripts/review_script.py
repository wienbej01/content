#!/usr/bin/env python3
"""review_script.py — LLM reviewer gates for scripts.

Runs multiple reviewer personas (filmmaker, technical, universe, audio) against
a script, aggregates results, and produces a structured review report.

Usage:
  python3 scripts/review_script.py scripts/generated/script.json
  python3 scripts/review_script.py scripts/generated/script.json --dry-run
  python3 scripts/review_script.py scripts/generated/script.json --personas filmmaker,universe
  python3 scripts/review_script.py scripts/generated/script.json --output review.json
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PERSONAS = ["audience", "filmmaker", "technical", "universe", "audio"]
PROMPTS_DIR = ROOT / "docs" / "reviewer_prompts"

# Weighted aggregation: retention/narrative > technical > minor style
# audience has highest weight (2.0); a low-weight persona cannot block alone unless hard blocking.
# A persona with weight < 1.0 cannot block alone unless it has a hard blocking_issue.
PERSONA_WEIGHTS = {
    "audience": 2.0,     # retention = #1 predictor of viewership
    "filmmaker": 1.5,    # narrative structure
    "universe": 1.2,     # brand voice
    "audio": 1.0,        # pacing
    "technical": 0.8,    # fixable issues
}
WEIGHTED_PASS_THRESHOLD = 3.0  # weighted average score must be ≥ this to proceed


def load_persona_prompt(persona):
    p = PROMPTS_DIR / f"{persona}.md"
    if not p.exists():
        raise FileNotFoundError(f"Persona prompt not found: {p}")
    return p.read_text()


def build_review_prompt(persona_prompt, script):
    """Combine persona prompt + script content for review."""
    # Extract the narration text
    texts = []
    for seg in script.get("segments", []):
        if seg.get("text"):
            texts.append(f"[{seg['id']}] {seg['text']}")
    script_text = "\n".join(texts)
    word_count = sum(len(seg.get("text", "").split()) for seg in script.get("segments", []))

    return (f"{persona_prompt}\n\n"
            f"---\n\nSCRIPT TO REVIEW:\n"
            f"Project: {script.get('project_id', 'unknown')}\n"
            f"Word count: {word_count}\n"
            f"Segments: {len(script.get('segments', []))}\n\n"
            f"{script_text}")


def run_review(script_path, personas=None, dry_run=False, output_path=None):
    """Run reviewer personas on a script. Returns aggregated report."""
    from llm_call import llm_call

    script = json.load(open(script_path))
    if personas is None:
        personas = PERSONAS

    reviews = []
    all_pass = True

    for persona in personas:
        prompt_text = load_persona_prompt(persona)
        full_prompt = build_review_prompt(prompt_text, script)

        data, raw, profile, model = llm_call(
            task="script_review",
            prompt=full_prompt,
            dry_run=dry_run,
            expect_json=True)

        if dry_run:
            reviews.append({"persona": persona, "status": "dry_run", "model": model})
            continue

        if data is None:
            reviews.append({"persona": persona, "status": "error", "error": "no response"})
            all_pass = False
            continue

        data["persona"] = persona
        reviews.append(data)

        status = data.get("status", "unknown")
        score = data.get("overall_score", "?")
        icon = "✓" if status == "pass" else "✗"
        print(f"  {icon} [{persona}] {status} (score {score}/5)")
        if data.get("blocking_issues"):
            for b in data["blocking_issues"]:
                print(f"      BLOCKING: {b}")
        if status != "pass":
            all_pass = False

    # Aggregate with weighted scoring
    report = {
        "project_id": script.get("project_id"),
        "script_path": str(script_path),
        "personas_run": personas,
        "reviews": reviews,
    }

    if not dry_run:
        # Hard blocking: any persona with blocking_issues = auto-fail regardless of weight
        hard_blocked = [r for r in reviews if r.get("blocking_issues")]
        blocking = [b for r in reviews for b in r.get("blocking_issues", [])]

        # Weighted average score
        weighted_sum = 0
        weight_total = 0
        for r in reviews:
            score = r.get("overall_score")
            if isinstance(score, (int, float)):
                w = PERSONA_WEIGHTS.get(r.get("persona", ""), 1.0)
                weighted_sum += score * w
                weight_total += w
        weighted_avg = round(weighted_sum / weight_total, 2) if weight_total > 0 else 0

        # Decision: blocked if hard blocking issues OR weighted avg below threshold
        all_pass = (not hard_blocked) and (weighted_avg >= WEIGHTED_PASS_THRESHOLD)

        report["all_pass"] = all_pass
        report["may_proceed"] = all_pass
        report["weighted_average_score"] = weighted_avg
        report["pass_threshold"] = WEIGHTED_PASS_THRESHOLD
        report["hard_blocking_issues"] = blocking
        report["persona_weights"] = {r.get("persona"): PERSONA_WEIGHTS.get(r.get("persona"), 1.0)
                                     for r in reviews if r.get("persona")}

        if hard_blocked:
            print(f"\n  BLOCKED — hard blocking issue(s) from: "
                  f"{[r['persona'] for r in hard_blocked]}")
        elif not all_pass:
            print(f"\n  BLOCKED — weighted avg {weighted_avg}/5 < threshold {WEIGHTED_PASS_THRESHOLD}")
        else:
            print(f"\n  APPROVED — weighted avg {weighted_avg}/5 ≥ {WEIGHTED_PASS_THRESHOLD}")
    else:
        report["all_pass"] = None
        report["may_proceed"] = None

    # Write output
    if output_path:
        Path(output_path).write_text(json.dumps(report, indent=2))
        print(f"  report: {output_path}")

    return report


def main():
    ap = argparse.ArgumentParser(description="LLM reviewer gates for scripts.")
    ap.add_argument("script", help="Path to script JSON")
    ap.add_argument("--personas", default=None, help="Comma-separated personas (default: all)")
    ap.add_argument("--output", "-o", default=None, help="Output JSON report path")
    ap.add_argument("--dry-run", action="store_true", help="Print plan without calling LLM")
    args = ap.parse_args()

    personas = [p.strip() for p in args.personas.split(",")] if args.personas else None
    report = run_review(args.script, personas=personas, dry_run=args.dry_run, output_path=args.output)
    sys.exit(0 if report.get("may_proceed", False) or args.dry_run else 1)


if __name__ == "__main__":
    main()

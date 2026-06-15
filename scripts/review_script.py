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


def detect_repetition(script):
    """R4/D1: deterministic stutter pre-filter. Check for N-gram repetition and
    adjacent near-duplicate sentences BEFORE spending on LLM personas.

    Returns (is_blocking: bool, reason: str or None).
    """
    import re
    from collections import Counter

    # Extract full script text
    text = " ".join(seg.get("text", "") for seg in script.get("segments", []))
    if not text.strip():
        return False, None

    # Load threshold from constraints.json
    cpath = ROOT / "docs" / "channel_universe" / "constraints.json"
    max_ratio = 0.12  # default
    if cpath.exists():
        c = json.loads(cpath.read_text())
        max_ratio = c.get("qa_thresholds", {}).get("max_ngram_repetition", 0.12)

    words = re.findall(r"[a-z]+", text.lower())
    if len(words) < 20:
        return False, None

    # 5-gram repetition ratio
    ngrams_5 = [tuple(words[i:i+5]) for i in range(len(words) - 4)]
    counts = Counter(ngrams_5)
    repeated = sum(c - 1 for c in counts.values() if c > 1)
    ratio = repeated / len(ngrams_5) if ngrams_5 else 0

    if ratio > max_ratio:
        # Find the most repeated phrase
        top = counts.most_common(1)[0]
        return True, (f"machine repetition: 5-gram ratio {ratio:.2%} > {max_ratio:.0%} "
                      f"(top: '{' '.join(top[0])}' x{top[1]})")

    # Adjacent near-duplicate sentences (within 5-sentence window)
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    for i in range(len(sentences)):
        for j in range(i + 1, min(i + 5, len(sentences))):
            if sentences[i].strip() == sentences[j].strip() and len(sentences[i].split()) > 4:
                return True, (f"verbatim sentence repeat within 5-sentence window: "
                              f"'{sentences[i][:60]}...'")

    return False, None


def load_persona_prompt(persona):
    p = PROMPTS_DIR / f"{persona}.md"
    if not p.exists():
        raise FileNotFoundError(f"Persona prompt not found: {p}")
    return p.read_text()


def build_review_prompt(persona_prompt, script):
    """Combine persona prompt + script content for review."""
    texts = []
    seg_meta = []
    for seg in script.get("segments", []):
        if seg.get("text"):
            texts.append(f"[{seg['id']}] {seg['text']}")
        seg_meta.append({k: seg.get(k) for k in
                         ("id", "audio_mode", "shot_type", "canonical_ref", "visual_brief")})
    script_text = "\n".join(texts)
    word_count = sum(len(seg.get("text", "").split()) for seg in script.get("segments", []))

    import json as _json
    return (f"{persona_prompt}\n\n"
            f"---\n\nSCRIPT TO REVIEW:\n"
            f"Project: {script.get('project_id', 'unknown')}\n"
            f"Word count: {word_count}\n"
            f"Segments: {len(script.get('segments', []))}\n"
            f"Narration mode: {script.get('narration_mode', 'segment_tts')}\n"
            f"Segment metadata: {_json.dumps(seg_meta, indent=2)}\n\n"
            f"{script_text}")


def run_review(script_path, personas=None, dry_run=False, output_path=None):
    """Run reviewer personas on a script. Returns aggregated report."""
    from llm_call import llm_call

    script = json.load(open(script_path))

    # R4: Deterministic stutter pre-filter — instant fail, no LLM spend.
    is_blocking, reason = detect_repetition(script)
    if is_blocking:
        report = {
            "script": str(script_path),
            "status": "fail",
            "blocking_issues": [f"REPETITION_GATE: {reason}"],
            "reviews": [],
            "note": "LLM personas SKIPPED — deterministic pre-filter tripped.",
        }
        if output_path:
            Path(output_path).write_text(json.dumps(report, indent=2))
        return report

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
    ap = argparse.ArgumentParser(description="LLM reviewer gates for scripts (G1).")
    ap.add_argument("script", help="Path to script JSON")
    ap.add_argument("--personas", default=None, help="Comma-separated personas (default: all)")
    ap.add_argument("--output", "-o", default=None, help="Output JSON report path")
    ap.add_argument("--dry-run", action="store_true", help="Print plan without calling LLM")
    ap.add_argument("--record-gate", action="store_true",
                    help="Record the script_review gate (G1) in the project ledger")
    ap.add_argument("--project-id", default=None, help="Override project id for the gate ledger")
    args = ap.parse_args()

    personas = [p.strip() for p in args.personas.split(",")] if args.personas else None
    report = run_review(args.script, personas=personas, dry_run=args.dry_run, output_path=args.output)
    passed = bool(report.get("may_proceed", False))

    if args.record_gate and not args.dry_run:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from gates import record_gate
        import json as _json
        pid = args.project_id or report.get("project_id") \
            or _json.loads(Path(args.script).read_text()).get("project_id")
        if not pid:
            print("ERROR: --record-gate needs a project id", file=sys.stderr)
            sys.exit(1)
        # Bind the gate to the SCRIPT being reviewed (the artifact downstream cares about).
        record_gate(pid, "script_review", "pass" if passed else "fail",
                    artifact_path=str(args.script),
                    extra={"weighted_score": report.get("weighted_average_score"),
                           "report": args.output})
        print(f"  gate script_review={'pass' if passed else 'fail'} recorded for {pid}")

    sys.exit(0 if passed or args.dry_run else 1)


if __name__ == "__main__":
    main()

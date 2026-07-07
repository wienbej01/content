#!/usr/bin/env python3
"""review.py — generic multi-persona reviewer + revise→re-review feedback loop.

Runs a named persona set against an artifact (SCRIPT or STORYBOARD), each persona
fed the FULL relevant context (the artifact + the channel bibles + the source
research text), aggregates with weights (audience = highest, veto on hard blocks),
and drives the feedback loop: create → review → if fail/low → AUTHOR REVISES from the
fixes → re-review → repeat (max 2) → else escalate to human. Every round is logged.

Reviewer cast (per CREATIVE_CHAIN_SPRINT.md):
  script-stage:     audience(2.0, veto), brand_voice(1.2)
  storyboard-stage: audience(2.0, veto), filmmaker(1.5), visual_director(1.5), technical(0.8)

TKT-701: reviewer_cast config in llm_models.yaml routes each persona through its
configured model_profile. Default config preserves existing behavior.
"""
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
PROMPTS = ROOT / "docs" / "reviewer_prompts"
CU = ROOT / "docs" / "channel_universe"

def _load_reviewer_cast() -> dict:
    """Load reviewer_cast config from llm_models.yaml. Returns empty dict if unavailable."""
    try:
        cfg_path = ROOT / "configs" / "llm_models.yaml"
        if not cfg_path.exists():
            return {}
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f)
        return cfg.get("reviewer_cast", {}) if cfg else {}
    except Exception:
        return {}


REVIEWER_CAST = _load_reviewer_cast()


def _get_persona_model_profile(name: str) -> str:
    """Get the model profile for a reviewer persona. Falls back to 'auto_utility'."""
    if name in REVIEWER_CAST:
        return REVIEWER_CAST[name].get("model_profile", "auto_utility")
    return "auto_utility"

# Which bibles each persona needs (don't flood every reviewer with everything).
PERSONA_BIBLES = {
    "audience": [],  # judges from viewer psychology; needs source for save/share grounding
    "brand_voice": ["JAMES_CHARACTER_BIBLE.md", "UNIVERSE_BIBLE.md", "FORBIDDEN_PATTERNS.md"],
    "visual_director": ["UNIVERSE_BIBLE.md", "JAMES_CHARACTER_BIBLE.md",
                        "JAMES_RECORDING_STUDIO_LIBRARY.md", "FORBIDDEN_PATTERNS.md",
                        "REFERENCE_ASSET_MANIFEST.md"],
    "filmmaker": ["TECHNICAL_BIBLE.md"],
    "technical": ["TECHNICAL_BIBLE.md", "constraints.json"],
}

# TKT-701: Cast weights for aggregation (audience has veto)
SCRIPT_CAST = {"audience": 2.0, "brand_voice": 1.2}
STORYBOARD_CAST = {"audience": 2.0, "filmmaker": 1.5, "visual_director": 1.5, "technical": 0.8}
WEIGHTED_THRESHOLD = 3.2
VETO_PERSONA = "audience"


def _load_persona(name):
    p = PROMPTS / f"{name}.md"
    return p.read_text() if p.exists() else ""


def _bible_context(name, max_chars=5000):
    out = []
    for b in PERSONA_BIBLES.get(name, []):
        f = CU / b
        if f.exists():
            t = f.read_text(errors="replace")
            out.append(f"===== {b} =====\n{t[:max_chars]}")
    return "\n\n".join(out)


def _artifact_text(artifact, kind):
    if kind == "script":
        segs = [{"id": s.get("id"), "text": s.get("text", "")} for s in artifact.get("segments", [])]
        return json.dumps({"title": artifact.get("title"), "segments": segs,
                           "key_points": [k.get("text") for k in artifact.get("key_points", [])]}, indent=2)
    beats = artifact.get("beats", artifact if isinstance(artifact, list) else [])
    return json.dumps(beats, indent=2)


def run_persona(name, artifact, kind, source_text="", video_type="explainer",
                dry_run=False, stub=None, capture=None):
    """Run one reviewer persona with full context (persona + format + bibles + source +
    artifact). If `capture` is a dict, store the exact prompt + raw output for transparency.
    Returns its JSON verdict dict."""
    if stub is not None:
        return stub(name, artifact, kind)
    from llm_call import llm_call
    from episode_format import format_block
    parts = [_load_persona(name), format_block(video_type)]
    bibles = _bible_context(name)
    if bibles:
        parts.append("=== CHANNEL BIBLES (judge against these) ===\n" + bibles)
    if source_text and name in ("audience", "brand_voice", "visual_director"):
        parts.append("=== SOURCE RESEARCH TEXT (claims/era must trace to this) ===\n\"\"\""
                     + source_text[:5000] + "\"\"\"")
    parts.append(f"=== ARTIFACT TYPE: {kind} ===\n{_artifact_text(artifact, kind)}")
    prompt = "\n\n".join(parts)
    if dry_run:
        if capture is not None:
            capture[name] = {"prompt": prompt, "output": "(dry-run)"}
        return {"persona": name, "status": "dry_run", "overall_score": 0,
                "recommended_fixes": [], "blocking_issues": [], "prompt_chars": len(prompt)}
    data, raw, _, _ = llm_call(
        task=f"{kind}_review", prompt=prompt, expect_json=True, timeout=180,
        persona_model=_get_persona_model_profile(name)
    )
    if capture is not None:
        capture[name] = {
            "prompt": prompt,
            "output": raw,
            "model_profile": _get_persona_model_profile(name),
        }
    if not isinstance(data, dict):
        return {"persona": name, "status": "error", "overall_score": 0,
                "recommended_fixes": [], "blocking_issues": ["non-dict reviewer output"]}
    data.setdefault("persona", name)
    if data.get("overall_score") is None:
        sc = data.get("scores") or {}
        if isinstance(sc, dict) and sc.get("overall_score") is not None:
            data["overall_score"] = sc["overall_score"]
        elif isinstance(sc, dict) and sc:
            nums = [v for v in sc.values() if isinstance(v, (int, float))]
            data["overall_score"] = round(sum(nums) / len(nums), 2) if nums else 0
        else:
            data["overall_score"] = 0
    return data


def aggregate(verdicts, cast):
    """Aggregate reviewer verdicts. Returns (passed, report)."""
    total_w = sum(cast.values()) or 1
    weighted = sum(cast.get(v["persona"], 1.0) * (v.get("overall_score") or 0) for v in verdicts)
    weighted_mean = round(weighted / total_w, 2)

    blocking_issues = []
    recommendations = []
    veto_failed = False

    for v in verdicts:
        for b in v.get("blocking_issues", []):
            issue_text = b if isinstance(b, str) else str(b)
            blocking_issues.append({"persona": v["persona"], "issue": issue_text})
            if v["persona"] == VETO_PERSONA:
                veto_failed = True
        for f in v.get("recommended_fixes", []):
            recommendations.append({"persona": v["persona"], "fix": f})

    # Fail-closed on malformed verdict status
    for v in verdicts:
        status = str(v.get("status", "")).lower()
        if status not in ("pass", "fail", "error", "dry_run"):
            blocking_issues.append({"persona": v["persona"], "issue": f"malformed verdict status: {v.get('status')!r}"})
            if v["persona"] == VETO_PERSONA:
                veto_failed = True

    has_mandatory = len(blocking_issues) > 0
    passed = not has_mandatory and weighted_mean >= WEIGHTED_THRESHOLD and not veto_failed

    report = {
        "weighted_mean": weighted_mean,
        "has_mandatory": has_mandatory,
        "veto_failed": veto_failed,
        "passed": passed,
        "blocking_issues": blocking_issues,
        "recommendations": recommendations,
        "verdicts": verdicts,
        "ai_reviewer_flags": _build_ai_reviewer_flags(verdicts),
    }
    return passed, report


def _build_ai_reviewer_flags(verdicts: list[dict]) -> dict:
    """Build ai_reviewer_flags section for human gate report.

    Each persona's blocking issues and predicted metrics are surfaced
    explicitly for the human approval gate.
    """
    flags = {}
    for v in verdicts:
        persona = v.get("persona", "unknown")
        blocking = v.get("blocking_issues", [])
        fixes = v.get("recommended_fixes", [])
        score = v.get("overall_score", 0)
        flags[persona] = {
            "blocking_issues": blocking,
            "recommended_fixes": fixes,
            "overall_score": score,
            "predicts": {
                "watch_through": score >= 3.5,
                "save": score >= 4.0 and len(blocking) == 0,
                "share": score >= 4.5 and len(blocking) == 0,
            },
        }
    return flags


def review(artifact, kind, source_text="", video_type="explainer", dry_run=False,
           stub=None, capture=None):
    cast = SCRIPT_CAST if kind == "script" else STORYBOARD_CAST
    verdicts = [run_persona(n, artifact, kind, source_text, video_type, dry_run, stub, capture)
                for n in cast]
    return aggregate(verdicts, cast)


def review_loop(artifact, kind, reviser, source_text="", video_type="explainer",
                project_dir=None, dry_run=False, stub=None, n=None, max_rounds=None):
    """Automatic feedback loop with human escalation.
    max_rounds = number of revision rounds (initial review + max_rounds revisions).
    Returns (artifact, passed, rounds).
    """
    if max_rounds is not None:
        limit = max_rounds
    elif n is not None:
        limit = n
    else:
        limit = 1

    rounds, current = [], artifact
    for r in range(limit + 1):
        passed, report = review(current, kind, source_text=source_text,
                                video_type=video_type, dry_run=dry_run, stub=stub)
        report["round"] = r
        rounds.append(report)
        if project_dir:
            d = Path(project_dir) / "review_rounds"; d.mkdir(parents=True, exist_ok=True)
            (d / f"{kind}_round{r}.json").write_text(
                json.dumps({"report": report, "artifact": current}, indent=2))

        if passed:
            return current, True, rounds

        # Final round exhausted — escalate
        if r == limit:
            return current, False, rounds

        # Collect fixes and revise
        fixes = report["blocking_issues"] + report["recommendations"]
        if not fixes:
            return current, True, rounds
        current = reviser(current, fixes)

    return current, False, rounds


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Multi-persona reviewer (script|storyboard).")
    ap.add_argument("artifact_json")
    ap.add_argument("--kind", choices=["script", "storyboard"], required=True)
    ap.add_argument("--source")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--output")
    args = ap.parse_args(argv)
    art = json.loads(Path(args.artifact_json).read_text())
    src = ""
    if args.source:
        sp = Path(args.source)
        if sp.suffix.lower() == ".pdf":
            import subprocess
            txt = sp.with_suffix(".txt")
            if not txt.exists():
                subprocess.run(["pdftotext", str(sp), str(txt)], capture_output=True)
            src = txt.read_text(errors="replace") if txt.exists() else ""
        else:
            src = sp.read_text(errors="replace")
    has_mandatory, report = review(art, args.kind, source_text=src, dry_run=args.dry_run)
    print(f"  review [{args.kind}]: {'PASS' if not has_mandatory else 'HAS MANDATORY'} "
          f"(weighted {report['weighted_mean']}, "
          f"mandatory={len(report['blocking_issues'])}, recommendations={len(report['recommendations'])})")
    for v in report["verdicts"]:
        print(f"    {v['persona']:15s} {str(v.get('status')):8s} score={v.get('overall_score')}")
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2))
    return 0 if not has_mandatory else 1


if __name__ == "__main__":
    raise SystemExit(main())

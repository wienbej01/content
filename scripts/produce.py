#!/usr/bin/env python3
"""produce.py — single-command production orchestrator.

Takes a seed idea + format through the entire pipeline automatically:
  seed → research → script (+ review loop) → storyboard (+ review loop) →
  TTS → compliance → compile → slice → [HUMAN GATE A: budget] →
  generate → QA → assemble → [HUMAN GATE B: review] → done

Human gates pause and notify via Telegram; everything else is automatic.
Saves state to project_dir/state.json so it can resume if interrupted.

Usage:
  python3 scripts/produce.py                         # interactive: asks for seed + format
  python3 scripts/produce.py --seed "topic" --format short
  python3 scripts/produce.py --resume <project_dir>  # resume from last completed step
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PROJECTS = ROOT / "Videos" / "Projects"

STEPS = [
    "research",
    "script_create",
    "script_review_loop",
    "storyboard_create",
    "storyboard_review_loop",
    "tts",
    "build_timing_map",
    "production_storyboard",
    "compliance_check",
    "compile_media_plan",
    "slice_lipsync",
    "gate_a_budget",
    "generate_media",
    "qa_media",
    "reconcile_duration",
    "render_graphics",
    "build_manifest",
    "assemble",
    "qa_final",
    "build_quality_report",
    "gate_b_review",
]


def _slug(seed):
    s = re.sub(r"[^a-z0-9]+", "_", seed.lower().strip())[:40].strip("_")
    return s or "untitled"


def _notify(msg, kind="info"):
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        from send_telegram_message import send_telegram_message
        send_telegram_message(f"🎬 Produce | {msg}")
    except Exception:
        pass
    print(f"  [{kind.upper()}] {msg}")


def _handle_escalation(project_dir, stage, reviser, current_artifact, state):
    """Inline human-in-the-loop for review escalation.

    Sends the issue + proposed fix to the human (Telegram preferred, terminal fallback).
    Waits for the reply. Applies it. Returns 'proceed' or 'revised'.
    NEVER raises RuntimeError — the pipeline pauses here, not crashes.
    """
    # Gather the blocking issues + proposed rewrites from the latest review round
    import glob
    round_files = sorted(glob.glob(str(project_dir / "review_rounds" / f"{stage}_round*.json")))
    issues_text = ""
    if round_files:
        data = json.loads(Path(round_files[-1]).read_text())
        report = data.get("report", data)
        blocking = report.get("blocking_issues", [])
        for i, b in enumerate(blocking, 1):
            persona = b.get("persona", "reviewer")
            issue = b.get("issue", "")
            if isinstance(issue, dict):
                seg = issue.get("segment", "")
                problem = issue.get("issue", "")
                rewrite = issue.get("rewrite", "")
                issues_text += f"\n{'─'*40}\n"
                issues_text += f"Issue {i} [{persona}] in {seg}:\n{problem}\n"
                if rewrite:
                    issues_text += f"\nProposed rewrite:\n{rewrite}\n"
            else:
                issues_text += f"\nIssue {i} [{persona}]: {issue}\n"

    # Get the vetoed text (the current script/storyboard segments)
    segments = current_artifact.get("segments", current_artifact.get("beats", []))
    vetoed_text = ""
    for seg in segments[:6]:
        sid = seg.get("id", seg.get("beat_id", ""))
        text = seg.get("text", seg.get("narration_text", seg.get("visual_brief", "")))
        if text:
            vetoed_text += f"  [{sid}] {text[:200]}\n"

    # Build the human message
    msg = (
        f"📝 {stage.upper()} REVIEW needs your decision\n\n"
        f"Current text:\n{vetoed_text}\n"
        f"{'═'*40}\n"
        f"Reviewer objections:{issues_text}\n"
        f"{'═'*40}\n"
        f"Reply with:\n"
        f"• 'ok' — accept the current text as-is (override reviewers)\n"
        f"• Your rewritten text — I'll use your exact wording"
    )

    # Try Telegram first, fall back to terminal
    reply = None
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        from send_telegram_message import wait_for_reply
        print(f"\n  ⏸ Waiting for your decision on Telegram...")
        reply = wait_for_reply(msg, poll_interval=10, max_wait=7200)
    except (RuntimeError, ImportError, OSError) as e:
        # Telegram not configured or unreachable — use terminal
        print(f"\n{'═'*60}")
        print(msg)
        print(f"{'═'*60}")
        reply = input("\n  Your decision (ok / or type your rewrite): ").strip()

    if not reply:
        # Timeout — use terminal as last resort
        print(f"\n  Telegram timeout. Decide here:")
        print(msg[:1500])
        reply = input("\n  Your decision (ok / or type your rewrite): ").strip()

    # Apply the decision
    if reply.lower() in ("ok", "approve", "yes", "accept"):
        # Human accepts the current text as-is, overriding reviewers
        decision = {"stage": stage, "decision": "approve", "resolved_by": "human_inline"}
        (project_dir / f"escalation_decision_{stage}.json").write_text(json.dumps(decision, indent=2))
        print(f"  ✓ {stage} review: accepted by you (reviewer override)")
        return "proceed"
    else:
        # Human provided their own wording — apply it as a revision instruction
        revised = reviser(current_artifact, [f"HUMAN OVERRIDE: Use this exact wording: {reply}"])
        (project_dir / f"{stage}.json").write_text(json.dumps(revised, indent=2))
        decision = {"stage": stage, "decision": "revise", "instruction": reply, "resolved_by": "human_inline"}
        (project_dir / f"escalation_decision_{stage}.json").write_text(json.dumps(decision, indent=2))
        print(f"  ✓ {stage} review: revised with your wording")
        return "revised"


def _save_state(project_dir, state):
    """Atomic state write: write to tmp then rename."""
    tmp = project_dir / ".state.json.tmp"
    tmp.write_text(json.dumps(state, indent=2))
    tmp.rename(project_dir / "state.json")


def _load_state(project_dir):
    p = project_dir / "state.json"
    if not p.exists():
        return {}
    state = json.loads(p.read_text())
    # Backward compat: migrate old completed_steps list to step_status dict
    if "completed_steps" in state and "step_status" not in state:
        seen = set()
        state["step_status"] = {}
        for s in state["completed_steps"]:
            if s not in seen:
                state["step_status"][s] = {"status": "done", "completed_at": state.get("created", "")}
                seen.add(s)
        del state["completed_steps"]
    return state


# ─── ARTIFACT MAP (step → deletable artifacts on invalidation) ───────────
# Keys: step names. Values: list of relative paths (globs supported via fnmatch).
# NOTE: TTS audio and generated media are NEVER deleted (expensive).
STEP_ARTIFACTS = {
    "production_storyboard": ["production_storyboard.json", "review_report.json"],
    "build_timing_map": ["narration/beat_timing_map.json"],
    "compile_media_plan": ["media_plan.json"],
    "qa_media": ["media_qa_report.json"],
    "reconcile_duration": ["duration_reconciliation.csv"],
    "build_manifest": ["manifest.json"],
    "assemble": ["*_16x9.mp4", "*_9x16.mp4"],
    "qa_final": ["final_qa_report.json"],
    "build_quality_report": ["run_quality_report.json", "run_quality_report.md"],
}


def invalidate_from_step(state, step_name, project_dir=None):
    """Invalidate step_name and all downstream steps in the STEPS list.

    Resets their status to None (pending). Deletes state artifacts for
    JSON files (not TTS audio or generated media). Returns the list of
    invalidated step names.
    """
    if step_name not in STEPS:
        return []
    idx = STEPS.index(step_name)
    invalidated = STEPS[idx:]
    step_status = state.setdefault("step_status", {})
    for s in invalidated:
        step_status[s] = {"status": None}
    # Delete artifact files for invalidated steps (only safe ones)
    if project_dir:
        import fnmatch as _fnmatch
        project_dir = Path(project_dir)
        for s in invalidated:
            for pattern in STEP_ARTIFACTS.get(s, []):
                if "*" in pattern:
                    for f in project_dir.glob(pattern):
                        f.unlink(missing_ok=True)
                else:
                    p = project_dir / pattern
                    if p.exists():
                        p.unlink()
    return invalidated


def _enforce_project_id(project_dir):
    """Ensure all JSON artifacts use the directory name as project_id.
    This is critical: downstream scripts derive paths as ROOT/Videos/Projects/{project_id},
    so project_id MUST equal the directory name."""
    canonical_id = project_dir.name
    for fname in ("script.json", "storyboard.json", "media_plan.json"):
        p = project_dir / fname
        if p.exists():
            data = json.loads(p.read_text())
            if data.get("project_id") != canonical_id:
                data["project_id"] = canonical_id
                p.write_text(json.dumps(data, indent=2))


def _save_transcript(project_dir, step_num, name, content):
    d = project_dir / "transcripts"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{step_num}_{name}.md").write_text(content)


# ─── STEP IMPLEMENTATIONS ───────────────────────────────────────────────

def step_research(project_dir, state):
    from research import research
    seed = state["seed"]
    video_type = state["format"]
    data, prompt, raw = research(seed, video_type,
                                 transcript_path=str(project_dir / "transcripts" / "0_research.md"))
    if not data or data.get("error"):
        raise RuntimeError(f"Research failed: {data}")
    (project_dir / "research_brief.json").write_text(json.dumps(data, indent=2))
    print(f"  ✓ research: {data.get('angle','')[:80]}")
    return {"claims": len(data.get("key_claims", []))}


def step_script_create(project_dir, state):
    from write_script import write_script
    brief = json.loads((project_dir / "research_brief.json").read_text())
    video_type = state["format"]
    data, prompt = write_script(brief, video_type)
    if not data or not data.get("segments"):
        raise RuntimeError("Script writer returned empty/invalid output")
    (project_dir / "script.json").write_text(json.dumps(data, indent=2))
    words = sum(len(s["text"].split()) for s in data["segments"])
    _save_transcript(project_dir, 1, "script_writer",
                     f"# Script Writer\n\nTitle: {data.get('title')}\nWords: {words}\n\n"
                     f"## Prompt ({len(prompt)} chars)\n\n```\n{prompt[:3000]}\n```\n\n"
                     f"## Output\n\n```json\n{json.dumps(data, indent=2)}\n```\n")
    print(f"  ✓ script: \"{data.get('title')}\" ({words}w, {len(data['segments'])} segments)")
    return {"title": data.get("title"), "words": words}


def step_script_review_loop(project_dir, state):
    from review import review_loop
    from write_script import write_script
    script = json.loads((project_dir / "script.json").read_text())
    brief = json.loads((project_dir / "research_brief.json").read_text())
    source = (project_dir / "transcripts" / "0_research.md").read_text()
    video_type = state["format"]

    def reviser(current, fixes):
        revised, _ = write_script(brief, video_type, prior_script=current, fixes=fixes)
        return revised

    final, passed, rounds = review_loop(script, "script", reviser,
                                        source_text=source, video_type=video_type,
                                        project_dir=project_dir)
    (project_dir / "script.json").write_text(json.dumps(final, indent=2))
    # Save transcript
    summary = f"# Script Review Loop\n\nRounds: {len(rounds)}, Passed: {passed}\n\n"
    for i, r in enumerate(rounds):
        summary += f"## Round {i}\n"
        summary += f"Mandatory: {len(r.get('blocking_issues', []))}, Recommendations: {len(r.get('recommendations', []))}\n"
        for v in r.get("verdicts", []):
            summary += f"  {v.get('persona')}: {v.get('status')} ({v.get('overall_score')})\n"
        summary += "\n"
    _save_transcript(project_dir, 2, "script_review_loop", summary)
    print(f"  ✓ script review: {'PASSED' if passed else 'ESCALATED'} after {len(rounds)} rounds")
    if not passed:
        result = _handle_escalation(project_dir, "script", reviser, final, state)
        if result == "proceed":
            return {"rounds": len(rounds), "passed": False, "override": True}
        # revised
        return {"rounds": len(rounds) + 1, "passed": True}
    return {"rounds": len(rounds), "passed": passed}


def step_storyboard_create(project_dir, state):
    from direct_storyboard import direct
    script_path = project_dir / "script.json"
    source_path = project_dir / "transcripts" / "0_research.md"
    video_type = state["format"]
    result, meta = direct(str(script_path), str(source_path), video_type=video_type,
                          model_profile="sonnet_creative")
    if not result or not result.get("beats"):
        raise RuntimeError(f"Director returned no beats. Errors: {result.get('errors') if result else 'None'}")
    storyboard = result.get("storyboard", {"schema_version": "2.0", "beats": result["beats"]})
    errors = result.get("errors", [])
    warnings = result.get("warnings", [])
    _save_transcript(project_dir, 3, "storyboard_director",
                     f"# Storyboard Director\n\nBeats: {len(result['beats'])}\n"
                     f"Errors: {errors}\nWarnings: {warnings}\n\n"
                     f"## Output\n\n```json\n{json.dumps(storyboard, indent=2)[:5000]}\n```\n")
    if errors:
        diag = {"errors": errors, "warnings": warnings, "beat_count": len(result.get("beats", []))}
        (project_dir / "storyboard_errors.json").write_text(json.dumps(diag, indent=2))
        raise RuntimeError(f"Storyboard validation failed ({len(errors)} errors): {errors[:3]}")
    (project_dir / "storyboard.json").write_text(json.dumps(storyboard, indent=2))
    print(f"  ✓ storyboard: {len(result['beats'])} beats, {len(warnings)} warnings")
    return {"beats": len(result["beats"]), "errors": 0}


def step_storyboard_review_loop(project_dir, state):
    from review import review_loop
    from direct_storyboard import direct
    storyboard = json.loads((project_dir / "storyboard.json").read_text())
    source = (project_dir / "transcripts" / "0_research.md").read_text()
    video_type = state["format"]
    script_path = str(project_dir / "script.json")
    source_path = str(project_dir / "transcripts" / "0_research.md")

    def reviser(current, fixes):
        beats = current.get("beats", current if isinstance(current, list) else [])
        result, _ = direct(script_path, source_path, video_type=video_type,
                           prior_beats=beats, fixes=fixes)
        if result and result.get("storyboard"):
            return result["storyboard"]
        elif result and result.get("beats"):
            return {"schema_version": "2.0", "beats": result["beats"]}
        return current

    final, passed, rounds = review_loop(storyboard, "storyboard", reviser,
                                        source_text=source, video_type=video_type,
                                        project_dir=project_dir)
    (project_dir / "storyboard.json").write_text(json.dumps(final, indent=2))
    summary = f"# Storyboard Review Loop\n\nRounds: {len(rounds)}, Passed: {passed}\n\n"
    for i, r in enumerate(rounds):
        summary += f"## Round {i}\nMandatory: {len(r.get('blocking_issues', []))}\n"
        for v in r.get("verdicts", []):
            summary += f"  {v.get('persona')}: {v.get('status')} ({v.get('overall_score')})\n"
        summary += "\n"
    _save_transcript(project_dir, 4, "storyboard_review_loop", summary)
    print(f"  ✓ storyboard review: {'PASSED' if passed else 'ESCALATED'} after {len(rounds)} rounds")
    if not passed:
        def sb_reviser(current, fixes):
            beats = current.get("beats", current if isinstance(current, list) else [])
            result2, _ = direct(script_path, source_path, video_type=video_type,
                                prior_beats=beats, fixes=fixes)
            if result2 and result2.get("storyboard"):
                return result2["storyboard"]
            elif result2 and result2.get("beats"):
                return {"schema_version": "2.0", "beats": result2["beats"]}
            return current
        result = _handle_escalation(project_dir, "storyboard", sb_reviser, final, state)
        if result == "proceed":
            from gates import record_gate
            record_gate(project_dir.name, "storyboard_review", "pass",
                        artifact_path=project_dir / "storyboard.json")
            return {"rounds": len(rounds), "passed": False, "override": True}
        # revised
        from gates import record_gate
        record_gate(project_dir.name, "storyboard_review", "pass",
                    artifact_path=project_dir / "storyboard.json")
        return {"rounds": len(rounds) + 1, "passed": True}
    from gates import record_gate
    record_gate(project_dir.name, "storyboard_review", "pass",
                artifact_path=project_dir / "storyboard.json")
    return {"rounds": len(rounds), "passed": passed}


def step_tts(project_dir, state):
    from tts import run_tts
    script_path = project_dir / "script.json"
    run_tts(str(script_path), force=False, do_assemble=False, validate_only=False,
            require_gate=False)
    print(f"  ✓ TTS: narration generated")
    return {}


def step_build_timing_map(project_dir, state):
    from audio_timing import build_storyboard_timing_map
    audio = project_dir / "narration" / "continuous.mp3"
    if not audio.exists():
        raise RuntimeError(f"No continuous.mp3 at {audio}")
    storyboard = json.loads((project_dir / "storyboard.json").read_text())
    timing = build_storyboard_timing_map(str(audio), storyboard["beats"])
    out = project_dir / "narration" / "beat_timing_map.json"
    out.write_text(json.dumps(timing, indent=2))
    print(f"  ✓ timing map: {timing['beat_count']} beats, {timing['total_duration']:.1f}s")
    return {"beats": timing["beat_count"], "duration": timing["total_duration"]}


def step_production_storyboard(project_dir, state):
    """Post-TTS reconciliation: map creative beats to exact TTS timing, split overlong beats."""
    import subprocess
    import hashlib as _hashlib
    from artifact_fingerprint import read_fingerprint, write_fingerprint

    storyboard_path = project_dir / "storyboard.json"
    timing_map_path = project_dir / "narration" / "beat_timing_map.json"
    output_path = project_dir / "production_storyboard.json"
    audio_path = project_dir / "narration" / "continuous.mp3"

    # Stale-check: skip if fingerprint matches current upstream hashes
    if output_path.exists():
        fp = read_fingerprint(output_path)
        if fp and storyboard_path.exists() and timing_map_path.exists():
            sb_hash = _hashlib.sha256(storyboard_path.read_bytes()).hexdigest()
            tm_hash = _hashlib.sha256(timing_map_path.read_bytes()).hexdigest()
            if sorted(fp.get("upstream_hashes", [])) == sorted([sb_hash, tm_hash]):
                print("  ✓ production_storyboard: up-to-date (fingerprint match)")
                prod_sb = json.loads(output_path.read_text())
                return {"beats": len(prod_sb.get("beats", [])), "skipped": True}

    # Step 1: Reconcile
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "reconcile_production_storyboard.py"),
         "--storyboard", str(storyboard_path),
         "--timing-map", str(timing_map_path),
         "--output", str(output_path),
         "--audio", str(audio_path)],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        # Step 2: Check if needs_repair beats remain — attempt repair
        if output_path.exists():
            prod_sb = json.loads(output_path.read_text())
        else:
            # Check diagnostic path
            diag_path = output_path.with_suffix(".invalid.json")
            if diag_path.exists():
                prod_sb = json.loads(diag_path.read_text())
            else:
                raise RuntimeError("Production storyboard reconciliation failed — no output")

        needs_repair_beats = [b["beat_id"] for b in prod_sb.get("beats", []) if b.get("needs_repair")]
        if not needs_repair_beats:
            raise RuntimeError("Production storyboard reconciliation failed (non-repair issue)")

        # Run repair on unresolved beats
        repair_output = project_dir / "production_storyboard_repaired.json"
        repair_r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "repair_storyboard_beats.py"),
             "--production-storyboard", str(output_path) if output_path.exists() else str(output_path.with_suffix(".invalid.json")),
             "--creative-storyboard", str(storyboard_path),
             "--beats"] + needs_repair_beats + [
             "--output", str(repair_output)],
            capture_output=True, text=True, cwd=str(ROOT)
        )
        if repair_r.returncode != 0:
            print(repair_r.stdout)
            print(repair_r.stderr, file=sys.stderr)
            raise RuntimeError(f"Repair failed for beats: {needs_repair_beats}")

        # Promote repaired output
        import shutil
        shutil.move(str(repair_output), str(output_path))
        # Update fingerprint to include repair policy
        upstream_hashes = [
            _hashlib.sha256(storyboard_path.read_bytes()).hexdigest(),
            _hashlib.sha256(timing_map_path.read_bytes()).hexdigest(),
        ]
        write_fingerprint(
            output_path,
            producer="reconcile+repair",
            producer_version="1.0",
            upstream_hashes=upstream_hashes,
            project_id=prod_sb.get("project_id", ""),
        )

    # Step 3: Re-validate
    prod_sb = json.loads(output_path.read_text())
    remaining_repair = [b["beat_id"] for b in prod_sb.get("beats", []) if b.get("needs_repair")]
    if remaining_repair:
        raise RuntimeError(f"Beats still need repair after repair step: {remaining_repair}")

    # Step 4: Review gate
    review_output = project_dir / "review_report.json"
    review_r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "review_production_storyboard.py"),
         "--production-storyboard", str(output_path),
         "--creative-storyboard", str(storyboard_path),
         "--output", str(review_output)],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    if review_r.returncode != 0:
        print(review_r.stdout)
        print(review_r.stderr, file=sys.stderr)
        raise RuntimeError("Production storyboard review FAILED")

    # Step 5: Final check
    if review_output.exists():
        review_report = json.loads(review_output.read_text())
        if review_report.get("blocks_production"):
            raise RuntimeError("Production storyboard review blocks production")

    beats_count = len(prod_sb.get("beats", []))
    print(f"  ✓ production storyboard: {beats_count} beats (reconciled from creative storyboard)")
    return {"beats": beats_count}


def step_compliance_check(project_dir, state):
    """Python-side structural validation of the storyboard (no LLM)."""
    storyboard = json.loads((project_dir / "storyboard.json").read_text())
    from direct_storyboard import validate_director_output, VALID_SHOT_TYPES, SHOT_ROUTING
    beats = storyboard.get("beats", [])
    source = (project_dir / "transcripts" / "0_research.md").read_text()
    errors, warnings = validate_director_output(beats, source)
    if errors:
        print(f"  ✘ compliance errors: {errors}")
        raise RuntimeError(f"Storyboard compliance failed: {errors}")
    print(f"  ✓ compliance: {len(beats)} beats valid, {len(warnings)} warnings")
    return {"warnings": len(warnings)}


def step_compile_media_plan(project_dir, state):
    from compile_media_prompts import compile_plan, load_constraints, load_routing
    prod_sb_path = project_dir / "production_storyboard.json"
    if not prod_sb_path.exists():
        raise RuntimeError("compile_media_plan requires production_storyboard.json. "
                           "Run the production_storyboard step first. "
                           "Creative storyboard fallback is NOT permitted in production.")
    storyboard = json.loads(prod_sb_path.read_text())
    constraints = load_constraints()
    routing = load_routing()
    plan, errors = compile_plan(storyboard, constraints, routing, project_dir=project_dir)
    if errors:
        diag = {"errors": errors, "beat_count": len(plan.get("beats", []))}
        (project_dir / "media_plan_errors.json").write_text(json.dumps(diag, indent=2))
        raise RuntimeError(f"Media plan compilation failed ({len(errors)} errors): {errors[:3]}")
    (project_dir / "media_plan.json").write_text(json.dumps(plan, indent=2))
    total = plan.get("totals", {})
    print(f"  ✓ media plan: {len(plan.get('beats',[]))} beats, "
          f"est ${total.get('est_usd', 0):.2f} / {total.get('est_tokens', 0)} tokens")
    return {"est_usd": total.get("est_usd", 0), "beats": len(plan.get("beats", []))}


def step_slice_lipsync(project_dir, state):
    from slice_continuous_lipsync import slice_hero_from_master
    plan = slice_hero_from_master(project_dir)
    if plan:
        (project_dir / "media_plan.json").write_text(json.dumps(plan, indent=2))
    # Record the media_plan_review gate AFTER slice (slice mutates media_plan.json)
    from gates import record_gate
    record_gate(project_dir.name, "media_plan_review", "pass",
                artifact_path=project_dir / "media_plan.json")
    print(f"  ✓ lipsync audio sliced")
    return {}


def step_gate_a_budget(project_dir, state):
    """Human gate: show budget, ask for approval interactively."""
    plan = json.loads((project_dir / "media_plan.json").read_text())
    totals = plan.get("totals", {})
    print(f"\n  ┌─── GATE A: BUDGET APPROVAL ───┐")
    print(f"  │ Project: {plan.get('project_id')}")
    print(f"  │ Beats:   {len(plan.get('beats', []))}")
    print(f"  │ Est:     ${totals.get('est_usd', 0):.2f} ({totals.get('est_tokens', 0)} tokens)")
    print(f"  │ Cap:     ${totals.get('budget_cap_usd', 0)}")
    print(f"  └────────────────────────────────┘")
    _notify(f"Gate A: ${totals.get('est_usd',0):.2f} for {len(plan.get('beats',[]))} beats. Approve?", "action")
    answer = input("  Approve spend? [go/stop]: ").strip().lower()
    if answer not in ("go", "y", "yes"):
        raise RuntimeError(f"Gate A: human rejected (answered '{answer}')")
    from gates import record_gate
    record_gate(project_dir.name, "budget", "pass",
                artifact_path=project_dir / "media_plan.json",
                extra={"approved_cost": totals.get("est_usd", 0), "approved_by": "human_interactive"})
    record_gate(project_dir.name, "render_approval", "pass",
                approved_by="human_interactive",
                extra={"note": "approved at Gate A budget step"})
    print(f"  ✓ Gate A: approved by human")
    return {"approved": True}


def step_generate_media(project_dir, state):
    from generate_media import run_from_media_plan
    from gates import require_gates
    plan_path = project_dir / "media_plan.json"
    require_gates(project_dir.name, ["storyboard_review", "media_plan_review", "budget", "render_approval"])
    run_from_media_plan(str(plan_path), dry_run=False, force_unsafe=False)
    print(f"  ✓ media generation complete")
    return {}


def step_qa_media(project_dir, state):
    from qa_media import run_qa
    plan_path = project_dir / "media_plan.json"
    results, passed = run_qa(str(plan_path))
    fail_count = sum(1 for r in results if r.get("status", "").upper() == "FAIL")
    report = {"results": results, "passed": passed and fail_count == 0, "total": len(results), "fail": fail_count}
    (project_dir / "media_qa_report.json").write_text(json.dumps(report, indent=2))
    print(f"  {'✓' if fail_count == 0 else '✘'} media QA: {len(results)} checked, {fail_count} failed")
    if fail_count > 0 or not passed:
        raise RuntimeError(f"Media QA failed: {fail_count}/{len(results)} beats failed")
    return {"passed": True}


def step_reconcile_duration(project_dir, state):
    import subprocess
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "reconcile_duration.py"), str(project_dir)],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        raise RuntimeError("Duration reconciliation FAILED — insufficient visual coverage before assembly")
    print(f"  ✓ duration reconciliation: all beats have sufficient coverage")
    return {}


def step_build_manifest(project_dir, state):
    """Build manifest.json via scripts/build_manifest.py (validated, enriched)."""
    import subprocess
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_manifest.py"), str(project_dir)],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if r.returncode != 0:
        raise RuntimeError(f"Manifest build failed:\n{r.stderr}")
    print(r.stdout.strip())
    return {}


def step_render_graphics(project_dir, state):
    import subprocess
    r = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'render_graphics.py'),
                       '--batch', str(project_dir / 'media_plan.json'),
                       '--project-dir', str(project_dir)],
                      capture_output=True, text=True, cwd=str(ROOT))
    if r.returncode != 0:
        print(r.stdout); print(r.stderr)
        raise RuntimeError('Graphics rendering failed')
    return {}


def step_assemble(project_dir, state):
    import subprocess
    manifest = project_dir / "manifest.json"
    if not manifest.exists():
        raise RuntimeError("No manifest.json found")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "assemble.py"), str(manifest)],
                       capture_output=True, text=True, cwd=str(ROOT))
    if r.returncode != 0:
        raise RuntimeError(f"Assembly failed: {r.stderr[:500]}")
    print(f"  ✓ assembly complete")
    return {}


def step_qa_final(project_dir, state):
    """Run final stream-integrity gate before Gate B review."""
    import subprocess
    candidates = sorted(project_dir.glob("*_16x9.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise RuntimeError("No assembled MP4 found for final QA")
    video = candidates[0]
    report_path = project_dir / "final_qa_report.json"
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "qa_final.py"), str(video),
         "--output", str(report_path)],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    if r.returncode != 0:
        print(r.stdout)
        raise RuntimeError(f"Final QA FAILED — video cannot go to Gate B. See {report_path}")
    print(f"  ✓ final QA: stream integrity verified")
    return {"video": str(video)}


def step_build_quality_report(project_dir, state):
    import subprocess
    r = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'build_quality_report.py'), str(project_dir)],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    if r.returncode != 0:
        print(r.stdout); print(r.stderr)
        raise RuntimeError('Quality report FAIL — cannot proceed to Gate B review')
    print(f'  ✓ quality report: PASS')
    return {}


def step_gate_b_review(project_dir, state):
    """Send assembled video to Telegram for human review."""
    # Find the output video
    candidates = sorted(project_dir.glob("*_16x9.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        candidates = sorted(project_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise RuntimeError("No assembled MP4 found")
    video = candidates[0]
    size_mb = video.stat().st_size / (1024 * 1024)
    # Build quality summary for message
    qr_path = project_dir / "run_quality_report.json"
    qr_summary = ""
    if qr_path.exists():
        qr = json.loads(qr_path.read_text())
        qr_summary = f"\n📊 Quality: {qr['status']} | {qr['recommendation']}"
    if size_mb <= 50:
        try:
            sys.path.insert(0, str(ROOT / "tools"))
            from send_telegram_message import send_telegram_video
            send_telegram_video(str(video), f"Gate B review: {state.get('seed','')[:50]}{qr_summary}")
            print(f"  ✓ Gate B: sent {video.name} ({size_mb:.1f}MB) to Telegram")
        except Exception as e:
            print(f"  ⚠ Gate B: Telegram send failed ({e}), video at: {video}")
    else:
        _notify(f"Gate B: video ready ({size_mb:.0f}MB, too large for Telegram)\n{video}{qr_summary}", "action")
    return {"video": str(video)}


# ─── ORCHESTRATOR ────────────────────────────────────────────────────────

STEP_FNS = {
    "research": step_research,
    "script_create": step_script_create,
    "script_review_loop": step_script_review_loop,
    "storyboard_create": step_storyboard_create,
    "storyboard_review_loop": step_storyboard_review_loop,
    "tts": step_tts,
    "build_timing_map": step_build_timing_map,
    "production_storyboard": step_production_storyboard,
    "compliance_check": step_compliance_check,
    "compile_media_plan": step_compile_media_plan,
    "slice_lipsync": step_slice_lipsync,
    "gate_a_budget": step_gate_a_budget,
    "generate_media": step_generate_media,
    "qa_media": step_qa_media,
    "reconcile_duration": step_reconcile_duration,
    "build_manifest": step_build_manifest,
    "render_graphics": step_render_graphics,
    "assemble": step_assemble,
    "qa_final": step_qa_final,
    "build_quality_report": step_build_quality_report,
    "gate_b_review": step_gate_b_review,
}


def run_pipeline(seed, video_type, project_dir=None, resume_from=None):
    """Run the full production pipeline."""
    if project_dir is None:
        slug = _slug(seed)
        project_dir = PROJECTS / f"{slug}_{video_type}"
    project_dir = Path(project_dir).resolve()
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "transcripts").mkdir(exist_ok=True)

    state = _load_state(project_dir)
    state.setdefault("seed", seed)
    state.setdefault("format", video_type)
    state.setdefault("created", datetime.now().isoformat())
    state.setdefault("step_status", {})
    # Drop legacy key if migration left it
    state.pop("completed_steps", None)
    _save_state(project_dir, state)

    step_status = state["step_status"]

    print(f"\n{'═' * 60}")
    print(f"  PRODUCE: \"{seed}\" ({video_type})")
    print(f"  Project: {project_dir}")
    print(f"{'═' * 60}\n")

    # --from-step: invalidate that step and everything downstream
    if resume_from and resume_from in STEPS:
        invalidated = invalidate_from_step(state, resume_from, project_dir)
        if invalidated:
            print(f"  Invalidated {len(invalidated)} steps from '{resume_from}' onward")
        _save_state(project_dir, state)

    # Propagate failure: if any step is "failed", invalidate its downstream
    for s in STEPS:
        info = step_status.get(s, {})
        if info.get("status") == "failed":
            idx = STEPS.index(s)
            for ds in STEPS[idx + 1:]:
                ds_info = step_status.get(ds, {})
                if ds_info.get("status") == "done":
                    step_status[ds] = {"status": None}

    # Find first step not done
    start_idx = next(
        (i for i, s in enumerate(STEPS) if step_status.get(s, {}).get("status") != "done"),
        len(STEPS)
    )
    if start_idx > 0 and start_idx < len(STEPS):
        done_list = [s for s in STEPS[:start_idx] if step_status.get(s, {}).get("status") == "done"]
        print(f"  Resuming from step {start_idx + 1}: {STEPS[start_idx]}")
        print(f"  (completed: {', '.join(done_list)})\n")

    for i in range(start_idx, len(STEPS)):
        step_name = STEPS[i]
        fn = STEP_FNS[step_name]
        print(f"\n{'─' * 40}")
        print(f"  STEP {i+1}/{len(STEPS)}: {step_name}")
        print(f"{'─' * 40}")
        t0 = time.time()
        try:
            result = fn(project_dir, state)
        except Exception as e:
            step_status[step_name] = {"status": "failed", "error": str(e)}
            state["failed_step"] = step_name
            state["error"] = str(e)
            _save_state(project_dir, state)
            _notify(f"❌ FAILED at {step_name}: {e}", "block")
            print(f"\n  ✘ FAILED at {step_name}: {e}")
            print(f"  Resume with: python3 scripts/produce.py --resume {project_dir}")
            return False
        elapsed = time.time() - t0
        step_status[step_name] = {
            "status": "done",
            "result": result,
            "completed_at": datetime.now().isoformat(),
        }
        state[f"result_{step_name}"] = result
        state["last_step_time"] = elapsed
        state.pop("failed_step", None)
        state.pop("error", None)
        _enforce_project_id(project_dir)
        _save_state(project_dir, state)
        print(f"  ({elapsed:.1f}s)")

    print(f"\n{'═' * 60}")
    print(f"  ✓ PIPELINE COMPLETE")
    print(f"  Project: {project_dir}")
    print(f"{'═' * 60}\n")
    _notify(f"✅ Pipeline complete: {seed[:40]}", "done")
    return True


def main():
    ap = argparse.ArgumentParser(description="Single-command production pipeline.")
    ap.add_argument("--seed", help="Topic seed (interactive if omitted)")
    ap.add_argument("--format", dest="video_type", default="short",
                    choices=["short", "explainer", "teaser"])
    ap.add_argument("--resume", metavar="PROJECT_DIR",
                    help="Resume a previously interrupted pipeline")
    ap.add_argument("--from-step", help="Resume from a specific step name")
    args = ap.parse_args()

    if args.resume:
        project_dir = Path(args.resume)
        state = _load_state(project_dir)
        if not state:
            sys.exit(f"No state.json in {project_dir}")
        return 0 if run_pipeline(state["seed"], state["format"],
                                 project_dir=project_dir,
                                 resume_from=args.from_step) else 1

    seed = args.seed
    if not seed:
        seed = input("  Seed topic: ").strip()
        if not seed:
            sys.exit("No seed provided")
    video_type = args.video_type

    return 0 if run_pipeline(seed, video_type) else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""run_episode.py — end-to-end LLM creative chain orchestrator.

Seed + format (human) →
  0. LLM Researcher (web)         → research_brief.json   + research.md
  1. LLM Script Writer            → script.json           + script_writer_round{n}.md
  2. LLM Reviewers (script)       → fixes → feedback loop  + script_review_round{n}.md
  3. LLM Storyboard Director      → storyboard.json        + storyboard_director_round{n}.md
  4. LLM Reviewers (storyboard)   → fixes → feedback loop  + storyboard_review_round{n}.md
Python production (compile/generate/...) is downstream and unchanged.

Feedback loop: 1 comment pass; ANY reviewer veto (or below threshold) triggers a revision
round; escalate to the human via Telegram at round 3. Every prompt + output is saved as MD;
realpaths are sent to Telegram at the end.

Models (calibrated): researcher=sonnet, writer=sonnet, reviewers=sonnet, director=opus.

Usage:
  python3 scripts/run_episode.py "using AI to help memory retention" --format short \
      --project mem_retention_short
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

ESCALATE_ROUND = 3  # initial(0) + up to 2 revisions; escalate to human at round 3


def _md(path, title, prompt, output):
    Path(path).write_text(
        f"# {title}\n\n## PROMPT\n\n```\n{prompt}\n```\n\n## OUTPUT\n\n```\n{output}\n```\n")
    return str(Path(path).resolve())


def _review_md(path, title, report, captures):
    lines = [f"# {title}\n",
             f"**Result:** {'PASS' if report['passed'] else 'FAIL'} "
             f"(weighted {report['weighted_mean']}/{report['threshold']}, "
             f"veto_failed={report['veto_failed']})\n"]
    for v in report["verdicts"]:
        lines.append(f"\n## {v['persona'].upper()} — {v.get('status')} (score {v.get('overall_score')})")
        if v.get("scores"):
            lines.append(f"\nscores: `{json.dumps(v['scores'])}`")
        if v.get("predicts"):
            lines.append(f"\npredicts: `{json.dumps(v['predicts'])}`")
        for b in v.get("blocking_issues", []):
            lines.append(f"\n- ✗ BLOCK: {b}")
        for f in v.get("recommended_fixes", []):
            lines.append(f"\n- → fix: {f}")
        cap = (captures or {}).get(v["persona"])
        if cap:
            lines.append(f"\n<details><summary>prompt</summary>\n\n```\n{cap['prompt'][:6000]}\n```\n</details>")
    Path(path).write_text("\n".join(lines))
    return str(Path(path).resolve())


def notify(msg, kind="info"):
    try:
        import subprocess
        subprocess.run(["python3", str(ROOT / "tools" / "notify.py"), "--kind", kind, msg],
                       capture_output=True, timeout=30)
    except Exception:
        pass


def run(seed, video_type, project, source_pdf=None, dry_run=False):
    import research as R
    import write_script as W
    import review as RV
    import direct_storyboard as D

    pd = ROOT / "Videos" / "Projects" / project
    md = pd / "transcripts"
    md.mkdir(parents=True, exist_ok=True)
    artifacts = []

    # ---- Stage 0: Researcher (web) ----
    print("[0] Researcher (web)…")
    brief, rprompt, rraw = R.research(seed, video_type, model="claude-sonnet-4.6",
                                      timeout=600, dry_run=dry_run,
                                      transcript_path=str(md / "0_research.md"))
    artifacts.append(str((md / "0_research.md").resolve()))
    if not dry_run:
        if not brief or brief.get("error") == "NO_WEB_TOOL":
            notify(f"Episode {project}: RESEARCHER could not reach web tools (NO_WEB_TOOL). "
                   f"Fix Brave MCP. Transcript: {md/'0_research.md'}", kind="block")
            return {"stopped": "no_web_tool", "artifacts": artifacts}
        (pd / "research_brief.json").write_text(json.dumps(brief, indent=2))

    # ---- Stage 1+2: Script writer + review loop ----
    print("[1/2] Script writer + review loop…")
    script, sw_prompt = (None, "") if dry_run else W.write_script(brief, video_type)
    artifacts.append(_md(md / "1_script_writer_round0.md", "Script Writer — round 0",
                         sw_prompt, json.dumps(script, indent=2) if script else "(dry-run)"))
    src_text = (brief or {}).get("research_text", "") if brief else ""

    script_passed = False
    if not dry_run:
        for rnd in range(ESCALATE_ROUND):
            cap = {}
            passed, report = RV.review(script, "script", source_text=src_text,
                                       video_type=video_type, capture=cap)
            artifacts.append(_review_md(md / f"2_script_review_round{rnd}.md",
                                        f"Script Review — round {rnd}", report, cap))
            if passed:
                script_passed = True
                break
            if rnd == ESCALATE_ROUND - 1:
                notify(f"Episode {project}: SCRIPT failed review after {ESCALATE_ROUND} rounds — "
                       f"human needed. Transcripts in {md}", kind="action")
                break
            # revise from fixes
            script, sw_prompt = W.write_script(brief, video_type, prior_script=script,
                                               fixes=report["all_fixes"])
            artifacts.append(_md(md / f"1_script_writer_round{rnd+1}.md",
                                 f"Script Writer — round {rnd+1} (revision)",
                                 sw_prompt, json.dumps(script, indent=2)))
        (pd / "script.json").write_text(json.dumps(script, indent=2))

    # ---- Stage 3+4: Storyboard director + review loop ----
    print("[3/4] Storyboard director + review loop…")
    if not dry_run and script_passed:
        (pd / "script.json").write_text(json.dumps(script, indent=2))
        sb_result, _ = D.direct(str(pd / "script.json"), source_path=source_pdf,
                                dry_run=False, model_profile="storyboard_director",
                                video_type=video_type)
        beats = (sb_result or {}).get("beats", [])
        artifacts.append(_md(md / "3_storyboard_director_round0.md",
                             "Storyboard Director — round 0",
                             (sb_result or {}).get("prompt", ""), json.dumps(beats, indent=2)))
        sb = {"beats": beats}
        for rnd in range(ESCALATE_ROUND):
            cap = {}
            passed, report = RV.review(sb, "storyboard", source_text=src_text,
                                       video_type=video_type, capture=cap)
            artifacts.append(_review_md(md / f"4_storyboard_review_round{rnd}.md",
                                        f"Storyboard Review — round {rnd}", report, cap))
            if passed:
                break
            if rnd == ESCALATE_ROUND - 1:
                notify(f"Episode {project}: STORYBOARD failed review after {ESCALATE_ROUND} "
                       f"rounds — human needed. Transcripts in {md}", kind="action")
                break
            # Director REVISION pass: feed prior beats + reviewer fixes (mirrors writer loop)
            rev, _ = D.direct(str(pd / "script.json"), source_path=source_pdf, dry_run=False,
                              model_profile="storyboard_director", video_type=video_type,
                              prior_beats=sb["beats"], fixes=report["all_fixes"])
            sb = {"beats": (rev or {}).get("beats", sb["beats"])}
            artifacts.append(_md(md / f"3_storyboard_director_round{rnd+1}.md",
                                 f"Storyboard Director — round {rnd+1} (revision)",
                                 (rev or {}).get("prompt", ""), json.dumps(sb["beats"], indent=2)))
        (pd / "storyboard.json").write_text(json.dumps(sb, indent=2))

    # ---- Telegram the realpaths ----
    paths_msg = "Episode `%s` transcripts:\n" % project + "\n".join(artifacts)
    notify(paths_msg, kind="done")
    return {"artifacts": artifacts, "script_passed": script_passed}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("seed")
    ap.add_argument("--format", dest="video_type", default="short")
    ap.add_argument("--project", required=True)
    ap.add_argument("--source-pdf")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    res = run(args.seed, args.video_type, args.project, args.source_pdf, args.dry_run)
    print(json.dumps({k: v for k, v in res.items() if k != "artifacts"}, indent=2))
    print("Transcripts:")
    for a in res.get("artifacts", []):
        print(" ", a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

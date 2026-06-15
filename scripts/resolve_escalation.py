#!/usr/bin/env python3
"""resolve_escalation.py — resolve a review-loop escalation via CLI or Telegram.

Usage:
  python3 scripts/resolve_escalation.py <project_dir> --stage script
  python3 scripts/resolve_escalation.py <project_dir> --stage storyboard --telegram
"""
import argparse
import glob
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "scripts"))


def _find_latest_review(project_dir, stage):
    """Find the latest review round transcript for the stage."""
    pattern = str(project_dir / "transcripts" / f"*{stage}_review*")
    files = sorted(glob.glob(pattern))
    if files:
        return Path(files[-1])
    # Try storyboard/script review .json artifacts
    candidates = [
        project_dir / f"{stage}_review.json",
        project_dir / f"{stage}_review_loop.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _format_issues(review_path):
    """Extract blocking issues from review transcript/JSON."""
    if review_path is None:
        return "No review transcript found."
    content = review_path.read_text()
    if review_path.suffix == ".json":
        try:
            data = json.loads(content)
            issues = data.get("blocking_issues", data.get("issues", []))
            if issues:
                return "\n".join(f"  • {i}" for i in issues)
        except json.JSONDecodeError:
            pass
    # For markdown transcripts, extract the relevant section
    lines = content.split("\n")
    relevant = [l for l in lines if "mandatory" in l.lower() or "block" in l.lower() or l.strip().startswith("- ") or l.strip().startswith("•")]
    if relevant:
        return "\n".join(relevant[-20:])
    return content[-2000:] if len(content) > 2000 else content


def _write_decision(project_dir, stage, decision, instruction="", resolved_by="human_local"):
    """Write escalation_decision_<stage>.json."""
    doc = {
        "stage": stage,
        "decision": decision,
        "instruction": instruction,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "resolved_by": resolved_by,
    }
    path = project_dir / f"escalation_decision_{stage}.json"
    path.write_text(json.dumps(doc, indent=2))
    return path


def resolve_local(project_dir, stage):
    """Interactive CLI resolution."""
    review_path = _find_latest_review(project_dir, stage)
    issues_text = _format_issues(review_path)

    print(f"\n{'='*60}")
    print(f"ESCALATION: {stage} review failed (mandatory issues remain)")
    print(f"{'='*60}")
    print(f"\nBlocking issues:\n{issues_text}\n")
    print("Commands:")
    print("  approve            — accept artifact as-is (override)")
    print("  revise: <instr>    — provide revision instruction")
    print("  reject             — abort production")
    print()

    response = input("Decision: ").strip()
    if not response:
        print("No decision entered. Aborting.")
        return None

    if response.lower() == "approve":
        path = _write_decision(project_dir, stage, "approve")
        print(f"✓ Approved. Decision written to {path}")
        return "approve"
    elif response.lower().startswith("revise:"):
        instruction = response[7:].strip()
        if not instruction:
            print("Error: revise requires an instruction after the colon.")
            return None
        path = _write_decision(project_dir, stage, "revise", instruction=instruction)
        print(f"✓ Revision recorded. Decision written to {path}")
        return "revise"
    elif response.lower() == "reject":
        path = _write_decision(project_dir, stage, "reject")
        print(f"✗ Rejected. Decision written to {path}")
        return "reject"
    else:
        print(f"Unknown command: {response}")
        return None


def resolve_telegram(project_dir, stage):
    """Telegram-based resolution."""
    from send_telegram_message import wait_for_reply

    review_path = _find_latest_review(project_dir, stage)
    issues_text = _format_issues(review_path)

    prompt = (
        f"🚨 ESCALATION: {stage} review\n\n"
        f"Blocking issues:\n{issues_text}\n\n"
        f"Reply with:\n"
        f"  approve — accept as-is\n"
        f"  revise: <instruction>\n"
        f"  reject — abort"
    )

    reply = wait_for_reply(
        prompt,
        valid_prefixes=["approve", "revise:", "reject"],
        poll_interval=15,
        max_wait=3600,
    )

    if reply is None:
        print("Timeout: no reply received within 1 hour.")
        return None

    reply = reply.strip()
    if reply.lower() == "approve":
        path = _write_decision(project_dir, stage, "approve", resolved_by="human_telegram")
        print(f"✓ Approved via Telegram. Decision written to {path}")
        return "approve"
    elif reply.lower().startswith("revise:"):
        instruction = reply[7:].strip()
        path = _write_decision(project_dir, stage, "revise", instruction=instruction, resolved_by="human_telegram")
        print(f"✓ Revision recorded via Telegram. Decision written to {path}")
        return "revise"
    elif reply.lower() == "reject":
        path = _write_decision(project_dir, stage, "reject", resolved_by="human_telegram")
        print(f"✗ Rejected via Telegram. Decision written to {path}")
        return "reject"
    else:
        print(f"Unrecognized reply: {reply}")
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Resolve a review escalation.")
    parser.add_argument("project_dir", type=Path, help="Project directory")
    parser.add_argument("--stage", required=True, choices=["script", "storyboard"])
    parser.add_argument("--telegram", action="store_true", help="Use Telegram for resolution")
    args = parser.parse_args(argv)

    project_dir = args.project_dir.resolve()
    if not project_dir.exists():
        print(f"Error: {project_dir} does not exist", file=sys.stderr)
        return 1

    if args.telegram:
        result = resolve_telegram(project_dir, args.stage)
    else:
        result = resolve_local(project_dir, args.stage)

    return 0 if result else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""notify.py — send a short Telegram ping for build/plan events.

Thin wrapper over send_telegram_message.py so the ytbuilder agent (or n8n/cron)
can ping you when a plan step completes or something needs your attention.

Usage:
  python3 tools/notify.py "P1-03 done: visual identity locked"
  python3 tools/notify.py --kind done   "P3-01 published"
  python3 tools/notify.py --kind block  "P1-02 blocked: need domain"
  python3 tools/notify.py --kind action "Your turn: message the bot to get chat_id"
  echo "piped text" | python3 tools/notify.py --kind info
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from send_telegram_message import send_telegram_message  # noqa: E402

ICON = {
    "info": "ℹ️",
    "done": "✅",
    "block": "🚫",
    "action": "👉",
    "warn": "⚠️",
}
PREFIX = "📋 YTbuilder"


def notify(text: str, kind: str = "info", dry_run: bool = False) -> str:
    icon = ICON.get(kind, ICON["info"])
    msg = f"{PREFIX} {icon} {text}"
    if not dry_run:
        send_telegram_message(msg)
    return msg


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Send a build/plan notification via Telegram.")
    p.add_argument("message", nargs="?", help="Message text. Reads stdin if omitted.")
    p.add_argument("--kind", choices=sorted(ICON), default="info")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    text = args.message if args.message is not None else sys.stdin.read()
    text = (text or "").strip()
    if not text:
        p.error("message is empty")
    out = notify(text, kind=args.kind, dry_run=args.dry_run)
    print(out if args.dry_run else "sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

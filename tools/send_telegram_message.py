#!/usr/bin/env python3
"""Send a Telegram message through the YTchannel content bot.

Adapted from quantstack-v2 scripts/send_telegram_message.py.

Secrets are NEVER hardcoded. The token and chat id are read from (in order):
  1. process environment (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)
  2. a runtime env file: ~/.config/ytchannel/runtime.env  (KEY=VALUE lines, gitignored)

Setup:
  mkdir -p ~/.config/ytchannel
  cat > ~/.config/ytchannel/runtime.env <<'EOF'
  TELEGRAM_BOT_TOKEN=<your-fresh-token-from-BotFather>
  TELEGRAM_CHAT_ID=<your-chat-id>
  EOF
  chmod 600 ~/.config/ytchannel/runtime.env

Usage:
  python3 send_telegram_message.py "hello"          # send
  echo "piped text" | python3 send_telegram_message.py
  python3 send_telegram_message.py --dry-run "test"  # print, do not send
  python3 send_telegram_message.py --get-updates     # discover your chat_id (run once)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

MAX_CHARS = 3800
RUNTIME_ENV = Path.home() / ".config" / "ytchannel" / "runtime.env"


def load_runtime_env(path: Path = RUNTIME_ENV) -> None:
    """Load simple KEY=VALUE lines without printing secrets."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _token() -> str:
    load_runtime_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN not set. Add it to the environment or "
            f"{RUNTIME_ENV} (see this file's docstring)."
        )
    return token


def chunks(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    parts: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= max_chars:
            parts.append(remaining)
            break
        split_at = remaining.rfind("\n", 0, max_chars)
        if split_at < max_chars // 2:
            split_at = max_chars
        parts.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    return [p for p in parts if p]


def send_telegram_message(text: str) -> int:
    token = _token()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not chat_id:
        raise RuntimeError(
            "TELEGRAM_CHAT_ID not set. Run with --get-updates after messaging the bot "
            "to discover it, then add it to the runtime env."
        )

    sent = 0
    for part in chunks(text):
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": part}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if resp.status >= 300:
                raise RuntimeError(f"Telegram API status {resp.status}: {body}")
        sent += 1
    return sent


def send_telegram_video(path: str, caption: str = "") -> str:
    """Upload a video file via Telegram sendVideo (multipart/form-data).

    Bot API upload limit is 50MB. Uses only stdlib (manual multipart encoding).
    """
    import mimetypes
    import uuid

    token = _token()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID not set.")
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    size_mb = p.stat().st_size / (1024 * 1024)
    if size_mb > 50:
        raise RuntimeError(
            f"{p.name} is {size_mb:.1f}MB; exceeds Telegram bot upload limit (50MB)."
        )

    boundary = f"----ytb{uuid.uuid4().hex}"
    mime = mimetypes.guess_type(str(p))[0] or "video/mp4"
    fields = {"chat_id": chat_id, "supports_streaming": "true"}
    if caption:
        fields["caption"] = caption[:1024]

    body = bytearray()
    for k, v in fields.items():
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode()
        body += f"{v}\r\n".encode()
    body += f"--{boundary}\r\n".encode()
    body += (
        f'Content-Disposition: form-data; name="video"; filename="{p.name}"\r\n'
    ).encode()
    body += f"Content-Type: {mime}\r\n\r\n".encode()
    body += p.read_bytes()
    body += f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendVideo",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        out = resp.read().decode("utf-8", errors="replace")
        if resp.status >= 300:
            raise RuntimeError(f"sendVideo status {resp.status}: {out}")
    return f"sent {p.name} ({size_mb:.1f}MB)"


def send_telegram_audio(path: str, caption: str = "") -> str:
    """Upload an audio file via Telegram sendAudio (multipart/form-data).

    Bot API upload limit is 50MB. Uses only stdlib (manual multipart encoding).
    """
    import mimetypes
    import uuid

    token = _token()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID not set.")
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    size_mb = p.stat().st_size / (1024 * 1024)
    if size_mb > 50:
        raise RuntimeError(
            f"{p.name} is {size_mb:.1f}MB; exceeds Telegram bot upload limit (50MB)."
        )

    boundary = f"----ytb{uuid.uuid4().hex}"
    mime = mimetypes.guess_type(str(p))[0] or "audio/mpeg"
    fields = {"chat_id": chat_id}
    if caption:
        fields["caption"] = caption[:1024]

    body = bytearray()
    for k, v in fields.items():
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode()
        body += f"{v}\r\n".encode()
    body += f"--{boundary}\r\n".encode()
    body += (
        f'Content-Disposition: form-data; name="audio"; filename="{p.name}"\r\n'
    ).encode()
    body += f"Content-Type: {mime}\r\n\r\n".encode()
    body += p.read_bytes()
    body += f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendAudio",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        out = resp.read().decode("utf-8", errors="replace")
        if resp.status >= 300:
            raise RuntimeError(f"sendAudio status {resp.status}: {out}")
    return f"sent {p.name} ({size_mb:.1f}MB)"


def get_updates():
    """Fetch recent updates to discover chat_id. Prints chat ids found."""
    token = _token()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/getUpdates")
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    if not data.get("ok"):
        return f"API error: {data}"
    seen = {}
    for upd in data.get("result", []):
        msg = upd.get("message") or upd.get("channel_post") or {}
        chat = msg.get("chat") or {}
        if chat.get("id") is not None:
            seen[chat["id"]] = chat.get("username") or chat.get("title") or chat.get("first_name") or ""
    if not seen:
        return "No updates yet. Send a message to your bot in Telegram first, then re-run."
    lines = ["Discovered chats (use the id as TELEGRAM_CHAT_ID):"]
    for cid, name in seen.items():
        lines.append(f"  chat_id={cid}  ({name})")
    return "\n".join(lines)


def get_telegram_replies(since_update_id=None, timeout=10):
    """Poll getUpdates once. Return list of {update_id, text, date, chat_id} for messages
    from the configured chat. Does NOT long-poll-block forever; one bounded call."""
    token = _token()
    load_runtime_env()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID not set.")
    params = {"timeout": str(timeout)}
    if since_update_id is not None:
        params["offset"] = str(since_update_id + 1)
    url = f"https://api.telegram.org/bot{token}/getUpdates?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout + 10) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    if not data.get("ok"):
        return []
    messages = []
    for upd in data.get("result", []):
        msg = upd.get("message") or {}
        chat = msg.get("chat") or {}
        if str(chat.get("id")) == str(chat_id) and msg.get("text"):
            messages.append({
                "update_id": upd["update_id"],
                "text": msg["text"],
                "date": msg.get("date", 0),
                "chat_id": chat["id"],
            })
    return messages


def wait_for_reply(prompt_text, valid_prefixes=None, poll_interval=15, max_wait=3600, since_update_id=None):
    """Send prompt_text, then poll getUpdates every poll_interval until a reply arrives
    (or max_wait elapses). Returns the reply text, or None on timeout.
    Tracks the latest update_id so only replies AFTER the prompt are considered."""
    import time as _time
    # Ensure Telegram is configured (raises RuntimeError if not)
    _token()
    load_runtime_env()
    if not os.environ.get("TELEGRAM_CHAT_ID"):
        raise RuntimeError("Telegram not configured: TELEGRAM_CHAT_ID missing.")

    # Get current latest update_id before sending prompt
    if since_update_id is None:
        existing = get_telegram_replies(since_update_id=None, timeout=0)
        since_update_id = existing[-1]["update_id"] if existing else 0

    send_telegram_message(prompt_text)

    deadline = _time.time() + max_wait
    while _time.time() < deadline:
        _time.sleep(poll_interval)
        replies = get_telegram_replies(since_update_id=since_update_id, timeout=5)
        for r in replies:
            text = r["text"].strip()
            if valid_prefixes:
                if any(text.lower().startswith(p.lower()) for p in valid_prefixes):
                    return text
            else:
                return text
            since_update_id = max(since_update_id, r["update_id"])
        if replies:
            since_update_id = max(since_update_id, replies[-1]["update_id"])
    return None


def verify() -> str:
    """Call getMe to confirm the token is valid and the bot is reachable."""
    token = _token()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/getMe")
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    if data.get("ok"):
        r = data["result"]
        return f"OK: bot @{r.get('username')} (id {r.get('id')}, name '{r.get('first_name')}')"
    return f"FAILED: {data}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send a Telegram message via the content bot.")
    parser.add_argument("message", nargs="?", help="Message text. Reads stdin if omitted.")
    parser.add_argument("--dry-run", action="store_true", help="Print message without sending")
    parser.add_argument("--verify", action="store_true", help="Verify token via getMe and exit")
    parser.add_argument("--get-updates", action="store_true", help="Discover chat_id and exit")
    args = parser.parse_args(argv)

    if args.verify:
        print(verify())
        return 0
    if args.get_updates:
        print(get_updates())
        return 0

    text = args.message if args.message is not None else sys.stdin.read()
    text = (text or "").strip()
    if not text:
        parser.error("message is empty")
    if args.dry_run:
        print(text)
        return 0
    print(f"sent={send_telegram_message(text)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Telegram Delivery — Later Plan

**Version:** 1.0
**Status:** Deferred — plan only, not implemented in this sprint
**Context:** Telegram video delivery exists today via `tools/send_telegram_message.py` and `tools/notify.py`. This plan defines the principled integration point for a dedicated final-delivery wrapper.

---

## 1. Principle

Telegram delivery is an **optional operational notification**, not a core pipeline dependency. A video is considered successfully produced when it exists on disk and passes QA. Telegram delivery failure must never mark a video as failed, never block the pipeline, and must always be treated as a park-and-continue issue.

---

## 2. What Already Exists

The existing `tools/send_telegram_message.py` already provides:
- `send_telegram_message(text)` — send text
- `send_telegram_video(path, caption)` — upload and send an MP4 up to 50MB

The existing `tools/notify.py` provides:
- `notify(text, kind)` — sends a formatted pipeline notification (✅ done, 🚫 block, 👉 action, ⚠️ warn)

These tools already work (validated in M1–M3). No new credentials needed. No new auth surface needed.

---

## 3. Proposed Script

**Future file:** `scripts/send_telegram.py`

This script is a thin CLI wrapper over `tools/send_telegram_message.py` that:
1. Accepts a video file path and caption
2. Validates the file exists and is within the 50MB Telegram bot limit
3. Optionally checks a QA report file to confirm the video passed before sending
4. Sends via the existing `send_telegram_video()` function
5. If Telegram fails (no credentials, timeout, API error) → logs the failure, exits **0** (non-blocking), writes to `OVERNIGHT_PARKED_ITEMS.md`
6. Supports `--dry-run` (prints what would be sent, no network call)

**CLI shape:**
```bash
python3 scripts/send_telegram.py \
  Videos/Projects/teaser_02/teaser_02_16x9.mp4 \
  --caption "Teaser 02 — Gate B review" \
  --require-qa-pass Videos/Projects/teaser_02/qa_report.json \
  [--dry-run]
```

---

## 4. File-Size Policy

| Condition | Behavior |
|---|---|
| File ≤ 50MB | Send directly via Bot API |
| File > 50MB | Log warning, send a text-only notification: "Video too large for Telegram direct upload — available at [path]" |
| File does not exist | Exit 1 (hard error — the video is simply missing) |

---

## 5. Caption Format

```
🎬 {project_id} — Gate B Review
Format: {16x9 or 9x16}
Duration: {N}s
QA: {PASS / review pending}
Generated: {timestamp}
```

---

## 6. QA Gate Integration

The `--require-qa-pass` flag reads a `qa_report.json` file and only sends if `result.pass == true`. If QA is not available or not required, skip the check.

This prevents accidentally sending a clip that failed QA to the owner for review. The owner should only receive content that passed technical QA; creative review happens via the Telegram approval.

---

## 7. Authorization

- Uses existing `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from `~/.config/ytchannel/runtime.env`
- Never stores tokens in repo
- Never prints token values or prefixes
- If credentials missing → `BLOCKED: Telegram not configured` (message only; exit 0 so pipeline continues)

---

## 8. Gate B Integration (Current State)

For now, Gate B (owner endorsement before publishing) continues to use the existing pattern:
```python
from tools.send_telegram_message import send_telegram_video
send_telegram_video("path/to/video.mp4", caption="...")
```

The future `scripts/send_telegram.py` replaces this once it's implemented. Until then, the existing function is sufficient.

---

## 9. Non-Blocking Rule

Telegram delivery failure must never:
- Mark the video generation as failed
- Prevent `assemble.py` from completing
- Prevent the QA report from being written
- Trigger a BLOCKING classification in the overnight tracker

Telegram failure is always:
- Logged to `OVERNIGHT_PARKED_ITEMS.md` or equivalent
- Notified to the operator via a backup method if possible (email, local file)
- Non-blocking: the video exists on disk and can be delivered later

---

## 10. Implementation Sprint

Estimated effort: 1–2 hours. Should be implemented AFTER:
- Teaser_02 one-scene test is approved
- QA report schema (`qa_media.py`) is implemented (M9.1)

It is not on the critical path for teaser_02 generation — Gate B can use the existing `send_telegram_video()` function directly until then.

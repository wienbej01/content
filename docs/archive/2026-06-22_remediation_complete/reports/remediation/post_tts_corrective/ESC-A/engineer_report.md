# ESC-A Engineer Report: Escalation Resolution Flow

**Date:** 2026-06-14  
**Status:** ✅ Complete — all 7 tests pass, full suite green (521 passed)

---

## Summary

Built a meaningful escalation resolution flow with Telegram read capability + local CLI fallback. Review-loop escalations no longer dead-end at a RuntimeError with no resolution path.

## Changes

### Part 1: Telegram Read (`tools/send_telegram_message.py`)

- Fixed orphaned `get_updates()` function (was unreachable dead code after a return statement)
- Added `get_telegram_replies(since_update_id, timeout)` — single bounded getUpdates poll, filtered to configured chat_id
- Added `wait_for_reply(prompt_text, valid_prefixes, poll_interval, max_wait)` — send prompt then poll for reply; bounded by max_wait; raises RuntimeError if Telegram not configured

All stdlib-only (urllib). No new dependencies.

### Part 2: Resolver (`scripts/resolve_escalation.py`)

Standalone CLI script with two modes:

```bash
python3 scripts/resolve_escalation.py <project_dir> --stage script          # local CLI
python3 scripts/resolve_escalation.py <project_dir> --stage script --telegram  # Telegram
```

Accepts: `approve`, `revise: <instruction>`, `reject`  
Writes: `<project_dir>/escalation_decision_<stage>.json`

### Part 3: produce.py Wiring

Added `_handle_escalation()` helper called by both `step_script_review_loop` and `step_storyboard_review_loop` when `passed=False`:

| Decision file state | Behavior |
|---|---|
| `decision=approve` | Log override, proceed (no raise) |
| `decision=revise` | Apply instruction via reviser, proceed if successful |
| `decision=reject` | Raise RuntimeError (abort) |
| No file | Raise RuntimeError with resolve command in message |

FAIL-CLOSED: escalation without explicit human `approve` always blocks.

## Tests (`tests/test_escalation_resolution.py`)

| # | Test | Validates |
|---|------|-----------|
| 1 | `test_get_replies_parses_messages` | getUpdates parsing, chat_id filtering |
| 2 | `test_wait_for_reply_returns_on_match` | Poll loop returns matching reply |
| 3 | `test_telegram_not_configured_falls_back` | Clear RuntimeError when no token |
| 4 | `test_resolve_writes_decision_approve` | Local CLI → approve decision file |
| 5 | `test_resolve_revise_records_instruction` | Local CLI → revise + instruction |
| 6 | `test_produce_proceeds_on_approve_decision` | _handle_escalation returns "proceed" |
| 7 | `test_produce_blocks_without_decision` | _handle_escalation returns RuntimeError with command |

## Verification

```
tests/test_escalation_resolution.py: 7 passed in 0.03s
Full suite: 521 passed in 112.56s
```

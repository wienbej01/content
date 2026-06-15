# ESC-A Audit Report — Escalation Resolution via Telegram Read + Local CLI

**Auditor:** Kiro subagent (read-only)
**Date:** 2026-06-14T20:29+08:00
**Scope:** Verify fail-closed escalation resolution pathway (Telegram + local CLI)

---

## 1. Telegram Read — stdlib-only

**File:** `tools/send_telegram_message.py`

| Check | Result |
|-------|--------|
| No `import requests` | ✅ PASS — only `urllib.parse`, `urllib.request` (stdlib) |
| `get_telegram_replies()` function exists | ✅ PASS — lines 213+ |
| Uses `getUpdates` API endpoint | ✅ PASS — `bot{token}/getUpdates` |
| `wait_for_reply()` function exists | ✅ PASS — sends prompt, polls with `since_update_id` tracking |
| Respects `valid_prefixes` filtering | ✅ PASS — only returns text matching allowed prefixes |
| Timeout/max_wait enforced | ✅ PASS — returns `None` on expiry |

**Verdict:** stdlib-only Telegram read implemented correctly.

---

## 2. Resolver CLI — approve / revise / reject

**File:** `scripts/resolve_escalation.py`

| Check | Result |
|-------|--------|
| Supports `--stage script` and `--stage storyboard` | ✅ PASS — argparse choices |
| Supports `--telegram` flag | ✅ PASS — calls `resolve_telegram()` |
| Local mode: `resolve_local()` prompts for approve/revise/reject | ✅ PASS |
| Telegram mode: `resolve_telegram()` sends prompt + polls | ✅ PASS — uses `wait_for_reply` |
| Writes `escalation_decision_<stage>.json` | ✅ PASS — `_write_decision()` |
| Decision JSON includes: stage, decision, instruction, resolved_at, resolved_by | ✅ PASS |
| `revise:` requires non-empty instruction | ✅ PASS — validation present |
| `resolved_by` distinguishes `human_local` vs `human_telegram` | ✅ PASS |

**Verdict:** Resolver supports all three actions in both local and Telegram modes.

---

## 3. Fail-Closed Wiring in produce.py

**File:** `scripts/produce.py` — `_handle_escalation()` (line 71)

| Check | Result |
|-------|--------|
| No decision file → returns `RuntimeError` | ✅ PASS — line 102 |
| `approve` decision → returns `"proceed"` | ✅ PASS — line 80 |
| `revise` decision → invokes reviser + returns `"revised"` | ✅ PASS — lines 82–90 |
| `reject` / unknown → returns `RuntimeError` | ✅ PASS — line 94 |
| Notification sent on escalation | ✅ PASS — `_notify()` called |
| Resolution CLI command printed in error | ✅ PASS — includes `--telegram` alternative |

**Critical property: NO decision = BLOCKS (RuntimeError).** The caller (`produce.py`) raises this error. There is no fallback, no timeout-to-proceed, no `--force-unsafe`.

---

## 4. Approve-decision as Logged Override

When `escalation_decision_<stage>.json` contains `"decision": "approve"`:
- `_handle_escalation` returns `"proceed"` (production continues)
- Notification logged: `"{stage} escalation OVERRIDDEN by human (approve)."`
- Decision file includes ISO timestamp + resolver identity

This is an **explicit, logged human override** — not a silent bypass.

---

## 5. Test Coverage

| Test | Purpose | Status |
|------|---------|--------|
| `test_get_replies_parses_messages` | Telegram read parses `getUpdates` JSON | ✅ PASS |
| `test_wait_for_reply_returns_on_match` | Polling + prefix matching | ✅ PASS |
| `test_telegram_not_configured_falls_back` | Missing token raises RuntimeError | ✅ PASS |
| `test_resolve_writes_decision_approve` | Local approve writes decision JSON | ✅ PASS |
| `test_resolve_revise_records_instruction` | Local revise records instruction | ✅ PASS |
| `test_produce_proceeds_on_approve_decision` | `_handle_escalation` → "proceed" | ✅ PASS |
| `test_produce_blocks_without_decision` | No decision → RuntimeError | ✅ PASS |

Full suite: **526 tests passed** (0 failures).

---

## Verdict

**PASS** — All five criteria satisfied.

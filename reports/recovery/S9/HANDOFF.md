# HANDOFF — S9-C (complete-system sprint)

**Status:** PLANNED — no ticket started yet. **Next:** S9-C01.
**Read first:** `reports/recovery/S9/CONTINUE.md` (program state), then `reports/recovery/S9/PLAN.md` (this sprint), then the active ticket.

## What this sprint is

Close the 7 material gaps (CONTINUE.md §3.1–§3.7) at the root cause, in pipeline code, **before** any further paid call. 3 waves, 7 tickets, one ticket per session.

```
W1: S9-C01 (duration) | S9-C02 (D-015) | S9-C03 (tts cost)   — independent
W2: S9-C04 (storyboard mix, needs C01) | S9-C05 (slotting, needs C02)
W3: S9-C06 (generation adapter, needs C04+C05) | S9-C07 (assembly, needs C04)
```

## Hard rules for any agent picking this up

1. **One ticket per session.** Load `STATE.json` + the ticket; do `LOAD → BASELINE → REPRODUCE → IMPLEMENT → FOCUSED TEST → AUDIT → REPAIR → VALIDATE → RECORD`.
2. **No-hacks (I2):** fix the producing/consuming script. Never edit intermediate JSON/state/DB rows/outputs.
3. **No paid calls in any ticket (I6).** Prove with `--dry-run`, mocks, `FakeProvider`, deterministic fixtures, `YT_TEST_MODE=1`. Hard cap $5; ~$0.90 already spent. No automatic paid retry.
4. **Reproduce before fixing.** Write a failing test that demonstrates the defect first.
5. **Don't touch the real run** (`db/s9_real.db`) except to read it for reproduction evidence.
6. **Append** every action to `EXECUTION_LOG.jsonl`. Update `STATE.json` (status, active_ticket, wave gates) as you go. An auditor reviews but does not repair; only an independent validator accepts.

## Starting S9-C01 (recommended first ticket)

```bash
cd /home/jacobw/YTchannel
git log --oneline -1                       # expect 3f1c9fa
YT_TEST_MODE=1 python3 -m pytest -q        # expect ~1051 passed (baseline)
# then open reports/recovery/S9/tickets/S9-C01.md and follow it
```

## Wave gates (when to stop and validate)

- **W1:** over-budget script rejected · re-compile = one active unit set · mocked TTS writes cost row · suite green · zero paid calls.
- **W2:** ~75s compliant script + review_storyboard-passing storyboard + slotted plan with hero slices, all in test/dry-run · suite green · zero paid calls.
- **W3:** dry-run hero payload has prompt+image+audio · adapter builds --audio/--image under --dry-run · manifest has graphic+music · suite green · zero paid calls. **Then STOP — request user `gate_a_spend` re-approval before any real generation.**

## Blockers

- **BLK-HUMAN-SPEND:** real generation blocked until W3 done + user re-approves spend.

# Rectification Plan — Sprints R10 + R11

**Theme:** Integrated E2E, crash matrix & CI (R10); controlled real-provider validation & release (R11).
**Depends on:** R0–R9 complete.
**Governance:** Coder → Auditor → Validator; reports under `reports/remediation/rectification/<TICKET-ID>/`.
**External cost:** R11 makes **real paid** ElevenLabs + Higgsfield/Seedance calls — requires explicit human spend approval and hard cost caps before execution.

---

## Context

R10 proves the whole system end to end on a deterministic fixture, survives a crash-injection matrix without duplicate spend or stale reuse, and locks the invariants into CI so regressions can't merge. R11 then validates against real providers on a tiny capped smoke set and retires every legacy/placeholder path, satisfying the final release gate.

**Hard rule (`.kiro/rules/no-hacks.md`):** CI must mechanically reject the very anti-patterns this whole effort removed.

## Reuse

| Need | Existing | From |
|---|---|---|
| CI gate tools | `check_forbidden_file_reads.py`, `check_forbidden_beat_id_lookups.py`, `check_release_placeholders.py`, `check_direct_db_writes.py`, `check_test_quality.py` | R0-003 |
| Release interlock | `release_guard.py` | R0-001 |
| Provider adapter (real) | submit/poll/download interface | R4-002 |
| Crash-safe lifecycles | provider job + diagnostic + repair states | R4-003, R6-004 |

---

## Sprint R10 — Integrated E2E, Crash Matrix & CI

### R10-001 — Deterministic full fixture
One fixture episode exercising: B001; B008 chain; same-group + separate-group hero return; duplicate-laptop rejection; text-heavy reroute; deterministic graphic; post-composite screen; music/ambience; final deliverable.
**Assertions:** zero spoken overlap; one narration source; no provider narration; no hero temporal transform; all evidence current + SHA-bound; no unresolved change requests; valid final output.

### R10-002 — Crash/resume matrix
Inject a crash at each durable boundary: TTS submit/accept/commit; slice write/register; provider submit/external-ID/download/register; diagnostic extraction; QA evidence; repair creation/resolution; assembly write/register; final QA/approval.
**Assertion:** no duplicate paid work and no stale reuse on resume.

### R10-003 — Forbidden-behavior CI
CI must **fail** on: fixed placeholder lipsync pass; provider audio used as narration; master-range padding; hero temporal transforms; float hero-interval arithmetic outside the canonical sample module; legacy JSON authority; fake provider in production; auto-approval; release-path stubs; unconditional `assert True`; tracked runtime DB; direct constrained-table writes outside services.
Wire all R0-003 gate tools + `release_guard status` into `.github/workflows/ci.yml`; require status on the release SHA.

---

## Sprint R11 — Controlled Real-Provider Validation

### R11-001 — Paid smoke plan
Specify: five smoke cases; their fingerprints; expected + hard-capped cost; stop conditions; **no unapproved automatic retry**; evidence paths. Requires human spend approval (real `gate_a_spend`).

### R11-002 — Execute smoke
Capture: ElevenLabs request/job ID; Higgsfield/Seedance IDs; actual cost; source/output hashes; drift evidence; audiovisual score; safe-boundary evidence; B-roll relevance; exact composited text; final waveform correlation.

### R11-003 — Release & retire legacy paths
Remove: JSON authority fallbacks; old `keep_lipsync` final-audio path; master-range padding; fake production provider; auto-approval; legacy clip-DB authority.

**Release gate (must all hold):**
```
all deterministic suites PASS
all crash tests PASS
real-provider smoke PASS
human approval PASS
no legacy authority
no placeholder scorer
no production stubs
documentation matches code
```

---

## Verification

```bash
# R10 deterministic E2E + crash matrix (no external calls)
YT_TEST_MODE=1 python3 -m pytest tests/e2e -q
YT_TEST_MODE=1 python3 -m pytest tests/e2e/test_crash_matrix.py -q
# R10 CI gates locally
for t in forbidden_file_reads forbidden_beat_id_lookups release_placeholders direct_db_writes test_quality; do
  python3 tools/check_${t}.py || echo "GATE FAILED: $t"; done
python3 scripts/release_guard.py status            # expect ready:true once everything lands

# R11 (REAL SPEND — only after human approval + caps):
python3 scripts/produce_db.py approve <prod> gate_a_spend --pass
#   run the 5 capped smoke cases per R11-001 plan, capture evidence bundle
```

## Risks
- **R11 spends real money** — must be gated by hard caps, explicit approval, and stop conditions; no auto-retry.
- CI weight/model caching (from R6/R9) affects R10 runtime — split slow model suites from fast deterministic suites.
- R11-003 deletions are irreversible-feeling; do them only after the full release gate is green, and keep the audit ledger (RECTIFICATION_INDEX.md) updated to match code.

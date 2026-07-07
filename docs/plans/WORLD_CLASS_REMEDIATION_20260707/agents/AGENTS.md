# Karpathy Loop Agent Definitions

**Sprint:** `WCR-2026-07` (World-Class Educational Video Remediation)
**Created:** 2026-07-07
**Purpose:** Define agent roles for the `BUILD → RUN → MEASURE → ANALYZE → FIX → REPEAT` loop applied to every ticket.

The Karpathy loop applies a first-principles, measurement-driven discipline to each engineering task:
1. **Build** — the smallest coherent change.
2. **Run** — execute the change against a real (or deterministic fixture) environment.
3. **Measure** — capture objective evidence of behavior (exit codes, durations, scores, counts).
4. **Analyze** — locate the gap between measured and intended behavior.
5. **Fix** — correct the root cause, never the symptom.
6. **Repeat** — iterate.

Each ticket cycles through these phases via independent agent sessions. Sessions are strictly separated so no agent reviews its own output.

---

## Agent Roles

### Engineer (ENG)
**Codename:** `eng`
**Goal:** Deliver the smallest coherent root-cause fix that passes the ticket's test and proof matrix.

**Mandatory session protocol: LOAD → BASELINE → REPRODUCE → IMPLEMENT → FOCUSED TEST → RECORD**

**LOAD scope (token-efficient):**
- The ticket's section from `tickets/TKT-*.md`.
- `STATE.json`.
- The ticket's listed files (paths only — read only what the ticket references).
- `AGENTS.md` (repository conventions).

**Exclusions:** Do not read the full sprint plan, unrelated implementation, or the entire repository graph.

**Steps:**

1. **BASELINE.** Run every baseline command in the ticket. Record: command, working directory, exit code, concise result. If a baseline does NOT match the stated "expected current result," stop and report `BLOCKED: <reason>`.
2. **REPRODUCE (for defect tickets).** Write the failing test first. For capability tickets, write the behavior-contract test first. Test must FAIL before implementation — this proves the test detects the defect and exposes the current capability gap.
3. **IMPLEMENT.** Change the smallest coherent unit of code. No dummy outputs, no permissive fallbacks, no test-only production branches, no weakened assertions. No unrelated scope.
4. **FOCUSED TEST.** Run the ticket's test and proof matrix. Then run the sprint invariant suite: `YT_TEST_MODE=1 python3 -m pytest -q` (or at minimum the focused baseline suite plus the ticket's tests). Record all results.
5. **RECORD.** Append an engineer event to `EXECUTION_LOG.jsonl`. Update `STATE.json` to `ready_for_audit`. List files changed, diff summary, commands run, exit codes, tests passed, residual risks.

**Hard rules:**
- One ticket per engineering session.
- Do not approve or review one's own implementation.
- No paid API calls without explicit human authorization (rehearse with fixtures first).
- If two repair attempts produce no material validation improvement, report `BLOCKED: <specific reason>`.

---

### Auditor (AUD)
**Codename:** `aud`
**Goal:** Independently audit the engineer's diff against the ticket's claimed outcome.

**Mandatory session protocol: LOAD → INDEPENDENT TEST → AUDIT QUESTIONS → STRUCTURED REPORT → UPDATE STATE**

**LOAD scope:**
- The ticket definition.
- `STATE.json`.
- Actual git diff (the engineer's commit).
- Changed production files.
- Changed tests.
- The ticket's "Audit focus" section.

**Exclusions:** The auditor does not modify production code or tests. Only modifies: the audit report, `EXECUTION_LOG.jsonl`, `STATE.json`.

**Steps:**

1. **INDEPENDENT TESTS.** Run the entire test and proof matrix independently (with the engineer's changes applied). Re-run the sprint invariant suite. Record all results.
2. **ANSWER AUDIT QUESTIONS.** The ticket's "Audit focus" section lists specific questions. Answer each with:
   - Finding ID.
   - Severity: `CRITICAL | HIGH | MEDIUM | LOW`.
   - File and symbol.
   - Violated requirement or invariant.
   - Concrete evidence (quote diff or output).
   - Required correction.
   - Required regression test (if not already present).
3. **RETURN VERDICT.** Exactly one of:
   - `PASS` — no findings.
   - `PASS_WITH_FINDINGS` — low or medium findings only; all addressed or acknowledged.
   - `FAIL` — at least one high/critical finding.
   - `BLOCKED` — genuine blocker beyond the engineer's control.
4. **WRITE FINDINGS.** Append a structured auditor event to `EXECUTION_LOG.jsonl`. Update `STATE.json`:
   | Verdict | New state |
   |---------|-----------|
   | `PASS` | `ready_for_validation` |
   | `PASS_WITH_FINDINGS` (severity ≤ LOW) | `ready_for_validation_with_findings` |
   | `PASS_WITH_FINDINGS` (severity ≥ MEDIUM) | `audit_failed` |
   | `FAIL` | `audit_failed` |
   | `BLOCKED` | `blocked` |
5. If `FAIL` or `audit_failed`, revert to engineer with structured findings. The engineer corrects only the remaining delta, adds required regression tests, and re-submits.

**Hard rules:**
- Maximum three engineer→auditor cycles per ticket (one initial + up to two repair rounds).
- No findings may be downgraded without concrete evidence.

---

### Validator (VAL)
**Codename:** `val`
**Goal:** Independently validate the auditor's report against the ticket's Acceptance Gates and Invariants.

**Mandatory session protocol: LOAD → VERIFY → GATE CHECK → ACCEPT/REJECT → COMMIT**

**LOAD scope:**
- The ticket definition.
- `STATE.json`.
- The auditor's report (`evidence/<TKT-ID>-audit.md`).
- Re-run a sample of the test matrix.
- Changed production files (for fresh-eye inspection).
- `EXECUTION_LOG.jsonl` (verify no tampering).

**Exclusions:** The validator does not modify production code or tests. Only modifies: the validation report, `EXECUTION_LOG.jsonl`, `STATE.json`, `HANDOFF.md` (Wave/sprint completion only).

**Steps:**

1. **VERIFY.** Re-run a sample of the test matrix and all acceptance gates. Verify the reported auditor findings are fixed.
2. **GATE CHECK.** For each acceptance gate in the ticket:
   - Run the exact command.
   - Confirm the exact expected result.
   - Mark each gate PASSED or FAILED.
3. **INVARIANT CHECK.** Verify INV-1..INV-8 from the sprint plan hold.
4. **ACCEPT or REJECT.** Write `evidence/<TKT-ID>-validation.md` with:
   - Per-gate status.
   - Per-invariant status.
   - Residual risks acknowledged.
   - Recommendation: ACCEPT or REJECT.
5. **COMMIT (if ACCEPT).** Update `STATE.json` to `accepted`. Append a validator event to `EXECUTION_LOG.jsonl`. If this ticket completes the Wave, update `HANDOFF.md`.

---

### Fixture Builder (FXB) — special agent for Wave 0
**Codename:** `fxb`
**Goal:** Build deterministic, hermetic fixtures that downstream tickets use for development and testing without any paid calls.

**Mandatory session protocol: DESIGN → IMPLEMENT → VERIFY HERMETIC → RECORD**

**LOAD scope:**
- The ticket's "Test and proof matrix" that requires fixtures.
- Repository fixture conventions (`tests/conftest.py`, `fixtures/`, `assets/`).

**Exclusions:** No production code changes. Only new fixture files, test files, or conftest extensions.

**Fixture rules:**

1. **Deterministic.** Same seed/environment → same output every run. No network. No wall-clock timestamps in assertions.
2. **Hermetic.** All external calls are mocked or replaced with deterministic stubs. No paid APIs.
3. **Reusable.** Shared fixtures in `tests/conftest.py/` or `fixtures/`. Per-test fixtures are local to the test function.
4. **Fast.** Each fixture test targets < 2 seconds wall-clock.
5. **Identifiable.** Every fixture file starts with `fixture_` or lives under `fixtures/`. Every test that uses fixtures is marked with `@pytest.fixture` reference and the fixture source is documented.
6. **Negative coverage.** Whenever a fixture provides a positive case, the ticket also provides the negative case (e.g., freezed clip vs. moving clip).

**Steps:**

1. **DESIGN.** Identify which scenarios from the ticket's proof matrix need deterministic fixtures.
2. **IMPLEMENT.** Build fixture generators that produce files in-memory or as temp-dir artifacts. For video: ffmpeg `color`/`testsrc` sources with known duration and motion. For audio: silent, sine, or known-speaker stub. For text: deterministic strings with known NER tags.
3. **VERIFY HERMETIC.** Set `YT_TEST_MODE=1` AND unset any paid provider API keys. Confirm the tests still pass. If any test passes only with API keys, it is NOT hermetic and must be fixed.
4. **RECORD.** Append a fixture-builder event to `EXECUTION_LOG.jsonl`. Update `STATE.json`.

---

### Integration Tester (INT) — invoked in Wave 9
**Codename:** `int`
**Goal:** Drive the full WCR changeset through a production-mode run (against a temp DB + fixture artifacts, NOT authorized for real paid calls) and verify the sprint exit gates.

**Mandatory session protocol: STAGE → RUN → MEASURE → VERIFY GATES → REPORT**

**LOAD scope:**
- `PLAN.md` (section 9 final sprint gates).
- `STATE.json`.
- All prior ticket acceptance reports.
- Production-mode harness setup in `tests/integration/`.

**Human authorization gate:** For any step that requires a REAL paid API call (ElevenLabs, Higgsfield, real LLM vision), the integration tester is FORBIDDEN from running it without explicit user authorization in the prompt. If not authorized, it reports `BLOCKED: <specific need — human must authorize paid call>`.

---

### Karpathy-Loop Operator (KLO) — orchestrator
**Codename:** `klo`
**Goal:** Maintain `STATE.json`, enforce cycle limits, advance the loop, write `HANDOFF.md`.

**Mandatory session protocol: LOAD → CHECK STATE → DISPATCH next agent → UPDATE STATE**

**Rules:**
- Track cycle counts per ticket. Max three ENG→AUD cycles per ticket.
- On audit repair rounds: ensure the engineer corrects **only** the outstanding findings — no unrelated refactoring.
- After Wave completion: write `HANDOFF.md` with Wave summary, residual risks, recommended next Wave.
- After sprint completion: write final `HANDOFF.md` with total tickets accepted, gates passed, residual risks.

---

## Session Separation Rules

| Rule | Rationale |
|------|-----------|
| No agent reviews its own output | Prevents self-approval |
| ENG never modifies `EXECUTION_LOG.jsonl` directly except for the single appending event | Log integrity |
| AUD only writes/reads evidence, log, state | Separation of concerns |
| VAL never modifies production code or tests | Independence |
| FXB only adds fixture/test files | No production side-effects |
| KLO loop-operates state and dispatches | Single source of truth |

---

*All agents operate under the repository conventions defined in `AGENTS.md` and the sprint invariants (INV-1..INV-8 in `PLAN.md`).*

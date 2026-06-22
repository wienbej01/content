# Sprint Context: Canonical Master Duration — Fix & Harden

**Created:** 2026-06-22
**Sprint ID:** CANONICAL-DURATION
**Trigger:** `compile_media` stage failure on `prod_880997f34e9a4d87ac6e951cc011ed43`
**Status:** PLANNED (not yet started)

---

## Incident Summary

```
✗ Stage 'compile_media' failed: render_unit render_37032e4710094421b4e9e852adf50517:
  speech bounds [8521584,9222288] outside master [0,9222240]
```

The last hero slot's `speech_end_sample` (9,222,288) exceeded the master audio's measured sample count (9,222,240) by **48 samples = 1.0ms** at 48kHz.

## Root Cause (Proven)

A floating-point rounding asymmetry between two pipeline stages that independently re-probe the same audio file:

| Stage | Rounding policy | Result for ~192.1308s audio |
|-------|-----------------|------------------------------|
| `audio_timing` (`build_storyboard_timing_map`) | `round(total_dur, 3)` then `int(end * 1000)` — **rounds up** | 192,131ms → 9,222,288 samples |
| `slice_continuous_lipsync` (`probe_media`) | `int(float_dur * 1000)` — **truncates** | 192,130ms → 9,222,240 samples |

Divergence: 48 samples = 1.0ms. The `tts_master` artifact **stores** `duration_ms` at registration, but no downstream stage reads it — each re-probes independently.

## Why Intermittent

Only triggers when audio duration's 4th decimal ≥ 5 (e.g., 192.1305s–192.1309s). When 4th decimal < 5, both paths agree. ~50% of productions with a trailing hero beat will hit this.

## Sprint Goal

Eliminate the rounding divergence and establish a single canonical duration authority so the `compile_media` stage never fails on a boundary condition again.

## Architecture Principle Violated

The system has a `tts_master` artifact that stores `duration_ms` — the natural single source of truth. But `audio_timing` and `slice_continuous_lipsync` ignore it and re-probe the file. Three independent measurements, two policies, zero canonical authority.

---

## Ticket Structure

This sprint contains 3 tickets, each following the **Engineer → Auditor → Evaluator** loop:

| Ticket | Title | Priority | Type |
|--------|-------|----------|------|
| `TICKET-01` | Tactical: Clamp speech bounds to master duration | CRITICAL | Bug fix |
| `TICKET-02` | Strategic: Canonicalize master duration from artifact | HIGH | Architecture |
| `TICKET-03` | Consistency: Unify ms→samples conversion | MEDIUM | Refactor |

**Dependency order:** TICKET-01 (unblocks production immediately) → TICKET-02 (prevents recurrence) → TICKET-03 (hardens consistency).

TICKET-01 may be shipped alone to unblock. TICKET-02 and TICKET-03 together close the root cause.

---

## Loop Process (Engineer → Auditor → Evaluator)

Each ticket is executed through a strict 3-role loop. **No ticket is "done" until the Evaluator signs off.**

### Role Definitions

| Role | Responsibility | Cannot Do |
|------|----------------|-----------|
| **Software Engineer** | Implement the fix per the ticket spec. Write/update tests. Run the local test suite. Produce an engineer report. | Approve own work. Skip tests. Weaken assertions. |
| **Software Auditor** | Review the engineer's diff against the ticket spec and root cause. Check for minimal-change policy, invariant preservation, edge cases. Produce an audit verdict: PASS / PASS_WITH_FINDINGS / FAIL. | Modify code. Approve — only the Evaluator approves. |
| **Software Evaluator** | Re-run the full regression suite independently. Verify the root cause is addressed (not just the symptom). Validate no regressions. Produce a final verdict: APPROVED / REJECTED. | Modify code. Skip the full suite. |

### Loop Flow

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│  ENGINEER   │────▶│   AUDITOR   │────▶│  EVALUATOR   │
│ implements  │     │ reviews     │     │ validates    │
│ + tests     │     │ diff + spec │     │ full suite   │
└─────────────┘     └─────────────┘     └──────────────┘
       ▲                    │                   │
       │                    ▼                   │
       │             ┌─────────────┐            │
       └─────────────│  FINDINGS?  │◀───────────┘
                     └─────────────┘
                      PASS → next ticket
                      FINDINGS/FAIL → back to Engineer
```

### Loop Rules

1. **One ticket per session.** Do not begin TICKET-02 until TICKET-01 is Evaluator-APPROVED.
2. **Reproduce before fixing.** The Engineer must first demonstrate the failure (or a unit test that reproduces the rounding divergence) before implementing the fix.
3. **Minimal-change policy.** The Auditor rejects changes that touch unrelated files or expand scope beyond the ticket spec.
4. **No weakened tests.** The Auditor rejects any change that weakens assertions, broadens tolerances without justification, or skips test cases.
5. **Full regression suite.** The Evaluator runs `pytest tests/unit tests/integration tests/regression -v` and requires 0 failures (excluding pre-existing xfail/xpass).
6. **Evidence required.** Each role appends its report to the ticket file in a `## <Role> Report` section with: commands run, exit codes, files changed, test results, verdict.

---

## Files in This Sprint

```
docs/plans/canonical_duration_sprint/
├── _CONTEXT.md           ← this file (context + loop instructions)
├── TICKET-01-clamp.md    ← tactical clamp fix
├── TICKET-02-canonical.md ← strategic canonical duration
└── TICKET-03-unify.md     ← unify ms→samples conversion
```

## Key Source Files (Reference)

| File | Relevance |
|------|-----------|
| `scripts/slice_continuous_lipsync.py` (lines 77-102) | Master probe + boundary validation (crash site) |
| `scripts/audio_timing.py` (lines 28-36, 97-167) | `probe_duration()` + `build_storyboard_timing_map()` (rounds up) |
| `scripts/produce_db.py` (lines 298-350) | `invoke_audio_timing` — converts float seconds to int ms (round-up path) |
| `scripts/produce_db.py` (lines 940-999) | `invoke_compile_media` — slot speech bounds from span end_ms |
| `scripts/tts_service.py` (lines 28-117) | `record_tts_artifact` — stores `duration_ms` (truncation, ignored downstream) |
| `scripts/timeline_utils.py` (lines 12, 36-41) | `MASTER_SAMPLE_RATE=48000`, `ms_to_samples()` (round) |
| `scripts/production_repo.py` (lines 86-112) | `MediaProbe` + `probe_media()` (truncation) |

## Acceptance Criteria (Sprint-Level)

- [ ] `compile_media` succeeds for `prod_880997f34e9a4d87ac6e951cc011ed43` (resume the blocked production)
- [ ] A unit test reproduces the rounding divergence (192.1308s → 1ms delta) and passes after the fix
- [ ] Full regression suite: 0 failures
- [ ] No new large files committed
- [ ] Minimal-change policy respected (only files listed in ticket specs are modified)

# TKT-003 Audit Report

**Ticket**: Populate visible windows on the main compile path
**Wave**: 0
**Commit**: `82a97d1`
**Auditor**: independent
**Date**: 2026-07-05

## Verdict: PASS_WITH_FINDINGS

## Audit Checks

### 1. Root cause supported by evidence
**PASS**. Root cause: CS-21 (`visible_start/end_sample validated only if set; main compile path never sets them`). Confirmed at `scripts/produce_db.py` — prior to TKT-003, the hero slot-tiling code (`invoke_compile_media`) set `speech_start/end_sample` and `generation_start/end_sample` but never `visible_start/end_sample`, leaving them NULL.

### 2. Change satisfies observable outcome
**PASS**. After the change (`scripts/produce_db.py:1162-1163,1187-1188`):
- Every `HERO_SYNC_LOCKED` unit has `visible_start_sample` and `visible_end_sample` set
- Both are set equal to `speech_start_sample` and `speech_end_sample` (== speech window)
- The values flow through `compile_render_plan` → `plan_render_units` → `INSERT INTO render_units`
- `validate_hero_slicing_intervals` (at `scripts/production_repo.py:241-245`) enforces visible ⊆ generation

Verified by manual integration: compiled hero unit with 5000-20000ms span produces `visible=[240000, 960000]` at 48 kHz, equal to speech, within generation.

### 3. Production execution path reaches the change
**PASS**. Both code paths in `invoke_compile_media` set visible windows:
- Multi-slot path: `scripts/produce_db.py:1162-1163` — inside `if audio_policy == "HERO_SYNC_LOCKED":` block per slot
- Single-slot path: `scripts/produce_db.py:1187-1188` — inside the non-slotted `if audio_policy == "HERO_SYNC_LOCKED":` block

New-style (canonical) and legacy productions both flow through `invoke_compile_media`. No other code path creates `HERO_SYNC_LOCKED` render units (confirmed: only `plan_render_units` inserts render units, and it's only called from `compile_render_plan`).

### 4. Tests fail without implementation
**PASS**. All 5 tests are integration-level and call `produce_db.invoke_compile_media()`:
- `test_single_slot_hero_visible_window` — asserts `visible_start_sample is not None`
- `test_multi_slot_hero_visible_window` — asserts `visible_start_sample is not None` per slot
- Both would fail if visible windows were not set (NULL → assertion failure)

### 5. Success and failure paths covered
**PASS**.

| Path | Test | Expected |
|------|------|----------|
| Single-slot hero: visible set | `test_single_slot_hero_visible_window` | visible == speech, visible ⊆ generation |
| Multi-slot hero: visible per slot | `test_multi_slot_hero_visible_window` | same assertions per slot (≥2 slots) |
| Validation path: passing units | `test_validate_hero_slicing_intervals_accepts_visible_units` | `validate_hero_slicing_intervals` accepts all compiled hero units |
| Negative: visible > generation end | `test_visible_outside_generation_rejected` | `PolicyValidationError` with `"Visible interval"` |
| Negative: visible < generation start | `test_visible_before_generation_rejected` | `PolicyValidationError` with `"Visible interval"` |

### 6. Tests prove production behavior rather than mocks alone
**PASS**. Tests call `invoke_compile_media()` against a real SQLite database, create real creative_beats + timeline_spans, register real ffmpeg-generated tts_master WAV files, and assert against actual `render_units` table rows. No mocking.

### 7. Hidden duplicate state, fallback, or swallowed failure
**PASS**.
- No fallback path: visible window is always set inline from speech window
- If `visible_start_sample`/`visible_end_sample` are null (pre-TKT-003), `validate_hero_slicing_intervals` at line 222-224 returns early with `any_interval = False` — it only validates when any interval is present. This means pre-existing NULL-visible units silently pass. Post-TKT-003, all new compiles have visible set, so this early-return only applies to historical units. This is acceptable — the validation wasn't weakened, and new units are fully covered.

### 8. Partial output, stale state, retries, concurrency, interruption
**PASS** (not applicable). Visible windows are computed inline as derived values from speech windows during compile. No external state, no retry logic needed.

### 9. Existing tests or gates weakened
**PASS**. No existing tests modified. `validate_hero_slicing_intervals` unchanged.

### 10. Unrelated scope changed
**PASS**. Only `scripts/produce_db.py` (4 lines added) and `tests/test_hero_visible_window.py` (new file, 197 lines).

### 11. Performance or maintainability regressed
**PASS**. Two assignment statements in existing control-flow blocks. No measurable overhead.

### 12. Repository remains buildable and testable
**PASS**. `YT_TEST_MODE=1 python3 -m pytest tests/test_hero_visible_window.py -v` → 5 passed. Invariant suite → 109 passed.

## Findings

### FINDING-1 (LOW): Missing EXECUTION_LOG implementation record

**File**: `docs/plans/PPQ_SPRINT_20260704/EXECUTION_LOG.jsonl`

**Issue**: TKT-003 has zero entries in the execution log. The commit (`82a97d1`) and test file exist, but no baseline, implement, or other phase event was recorded. Per PLAN.md §6 rule 9, every ticket must append to `EXECUTION_LOG.jsonl`.

**Required correction**: Append a RECORD event to EXECUTION_LOG.jsonl documenting the implement phase — files changed, commands + exit codes, test results, limitations, and commit hash.

**Required regression test**: Audit trail check per ticket.

## Gates verification

| Gate | Status | Evidence |
|------|--------|----------|
| G1: non-null visible windows on all hero units | PASS | `test_single_slot_hero_visible_window` + `test_multi_slot_hero_visible_window` assert non-null visible_start/end_sample on every HERO_SYNC_LOCKED unit |
| G2: negative test passes | PASS | `test_visible_outside_generation_rejected` + `test_visible_before_generation_rejected` both raise `PolicyValidationError` with `"Visible interval"` |
| G3: focused suite passes | PASS | 109 invariant + 5 dedicated = all pass |

## Execution log

```json
{"ts": "2026-07-05T15:25:43+08:00", "ticket": "TKT-003", "phase": "audit", "role": "auditor", "verdict": "PASS_WITH_FINDINGS", "findings": [{"id": "FINDING-1", "severity": "low", "file": "docs/plans/PPQ_SPRINT_20260704/EXECUTION_LOG.jsonl", "issue": "Missing RECORD event for TKT-003 implement phase", "required_correction": "Append implement-phase event to EXECUTION_LOG.jsonl"}], "gates_verified": {"G1": "PASS", "G2": "PASS", "G3": "PASS"}, "commands": ["YT_TEST_MODE=1 python3 -m pytest tests/test_hero_visible_window.py -v (5 passed)", "YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py tests/test_compile_media_from_canonical_shots.py tests/test_produce_db_orchestrator.py tests/test_llm_call.py tests/test_sonnet_storyboard_wrapper.py -q (109 passed)", "PYTHONPATH=scripts python3 -c manual integration: compile + verify visible=speech=240000-960000, visible<=generation, validate_hero_slicing_intervals passes"], "files_changed": [], "result": "PASS_WITH_FINDINGS. All 3 acceptance gates pass. 1 LOW finding: missing EXECUTION_LOG implement record.", "commit": "82a97d1"}
```

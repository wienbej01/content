# TICKET-02: Non-Crashing Retryable Failures in generate_media

**Priority:** CRITICAL
**Type:** Resilience fix
**Estimated effort:** Small (1 file, ~20 lines)
**Sprint:** SUBMIT-RETRY
**Dependency:** TICKET-01 must be Evaluator-APPROVED first

---

## Problem

When `adapter.submit()` raises `ProviderAdapterError` (even after TICKET-01's retries are exhausted), the error handler at `produce_db.py:1445-1447` treats ALL submission failures as terminal:

```python
except Exception as e:
    fail_provider_job(job["id"], f"Submit failed: {e}", db_path=None)
    raise RuntimeError(f"Provider job {job['id']} submit failed: {e}")
```

This crashes the entire `generate_media` stage. The repair loop (S10-C09) can resubmit failed provider jobs, but it never runs because `generate_media` crashes first. If only 1 of 3 wave jobs fails as retryable, the other 2 are never submitted.

## Objective

Retryable submission failures must NOT crash the stage. The job is marked `failed`, the render unit goes to `status='failed'` (picked up later by `repair`), and the loop continues to the next ordered unit.

If ALL wave submissions are retryable failures (zero progress made), the stage may still raise — but only after attempting every unit.

## Specification

### File to modify

- `scripts/produce_db.py` — `invoke_generate_media` (lines ~1434-1447)

### Change

Replace the `except` block at submit time with retryability-aware handling:

```python
# Before (crashes on every submit failure):
except Exception as e:
    fail_provider_job(job["id"], f"Submit failed: {e}", db_path=None)
    raise RuntimeError(f"Provider job {job['id']} submit failed: {e}")

# After (crashes only on permanent failures):
except Exception as e:
    err_text = str(e)
    from paid_adapters import _is_submit_error_retryable
    retryable = _is_submit_error_retryable(err_text)
    fail_provider_job(
        job["id"],
        f"Submit failed: {err_text[:500]}",
        db_path=None,
    )
    if retryable:
        submitted_count += 1  # count as attempt (even though failed)
        submitted_in_wave += 1
        print(
            f"  ⚠ Provider job {job['id']}: retryable submit failure "
            f"({err_text[:120]}) — marked failed, repair will resubmit",
            file=sys.stderr,
        )
        retryable_submit_failures += 1
        continue  # ✅ Don't crash — try the next ordered unit
    raise RuntimeError(
        f"Provider job {job['id']} submit failed (permanent): {err_text[:300]}"
    )
```

### New: `retryable_submit_failures` counter

Add before the loop:
```python
retryable_submit_failures = 0
```

### New: post-loop check

After the `for u` loop, if ALL submissions were retryable failures (no progress):
```python
if retryable_submit_failures > 0 and submitted_count == retryable_submit_failures:
    raise RuntimeError(
        f"generate_media stalled: {retryable_submit_failures} provider job(s) had "
        f"retryable submit failures (all exhausted retries). "
        f"Check network/Higgsfield connectivity. Repair will resubmit."
    )
```

### What NOT to change

- Do NOT change `submit_provider_job()` call (line 1420-1427)
- Do NOT change `adapter.submit()` call (line 1435)
- Do NOT change the poll reconciliation loop
- Do NOT change the post-loop final check (lines 1473-1494) — those already handle `failed` status

## Acceptance Criteria

- [ ] Retryable submit failure → warn stderr, `continue` loop, submit next ordered unit
- [ ] Permanent submit failure → `raise RuntimeError` as before
- [ ] All retryable failures in wave → `raise RuntimeError("stalled")` after loop
- [ ] `submitted_count` and `submitted_in_wave` still increment for retryable attempts (counted as processed)
- [ ] Existing tests pass (no regressions)

## Loop Process

### Phase 1: Engineer
1. Read `_CONTEXT.md`, TICKET-01 (must be APPROVED), and this ticket.
2. Implement the retryability-aware submit error handler.
3. Run `pytest tests/unit tests/integration tests/regression -v` — 0 failures.
4. Append `## Engineer Report`.

### Phase 2: Auditor
1. Read the Engineer Report. `git diff`.
2. Verify: only `produce_db.py` changed, `continue` on retryable vs `raise` on permanent, post-loop stalled check, `_is_submit_error_retryable` used correctly.
3. Append `## Auditor Report` with verdict.

### Phase 3: Evaluator
1. Read both reports. Run full suite independently.
2. Verify: retryable path doesn't crash, permanent path still does.
3. Append `## Evaluator Report` with verdict: APPROVED / REJECTED.

---

## Engineer Report

*(To be filled by the Engineer after implementation)*

## Auditor Report

*(To be filled by the Auditor after review)*

## Evaluator Report

*(To be filled by the Evaluator after validation)*

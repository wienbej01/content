# TICKET-01: Close Query Gap — Repair Sees Failed Units + Generate Skips Them

**Priority:** CRITICAL
**Type:** Bug fix (pipeline-deadlocking)
**Estimated effort:** Small (2 code lines + test)
**Sprint:** FAILED-RECOVERY
**Dependency:** S10-C09 (repair lifecycle provider job resubmission) must be committed

---

## Problem

The `startup='failed'` render units (from provider job failures) create a pipeline deadlock:
- `generate_media` blocks on them (not "generated" or "valid")
- `repair` never sees them (queries only `status='needs_repair'`)
- Pipeline can't advance past `generate_media` to reach `repair`

The S10-C09 resubmission logic in `run_repair_lifecycle` CAN handle failed units (checks for failed provider_jobs and resubmits), but the stage-level query in `invoke_repair` never feeds them in.

## Objective

Close the query gap so `repair` picks up `status='failed'` units, and `generate_media` stops blocking on them.

## Specification

### File to modify

- `scripts/produce_db.py` — 2 changes

### Change 1: Repair stage query (line 1640-1646)

```python
# Before:
needs_repair = conn.execute(
    """SELECT id, label, asset_type, status
       FROM render_units
       WHERE production_id=? AND status='needs_repair'
       ORDER BY ordinal""",
    (production_id,),
).fetchall()

# After:
needs_repair = conn.execute(
    """SELECT id, label, asset_type, status
       FROM render_units
       WHERE production_id=? AND status IN ('needs_repair','failed')
       ORDER BY ordinal""",
    (production_id,),
).fetchall()
```

### Change 2: Generate completion check (line 1489)

```python
# Before:
if u["status"] in ("generated", "valid"):
    continue

# After:
if u["status"] in ("generated", "valid") or u["status"] == "failed":
    continue
```

Add `or u["status"] == "failed"` so failed units are skipped (not added as blockers). Failed units need repair, not generation.

### What NOT to change

- Do NOT change `run_repair_lifecycle` — the S10-C09 logic is already in place
- Do NOT change `fail_provider_job` — it correctly sets `status='failed'`
- Do NOT change any other stage or function

## Test

Add to `tests/integration/test_repair_loop_db.py` (or create `tests/unit/test_failed_unit_recovery.py`):

```python
def test_failed_unit_picked_up_by_repair(self, db, prod):
    """Failed render unit (provider job failure) is picked up by repair stage."""
    from media_service import fail_provider_job, submit_provider_job, run_repair_lifecycle
    
    # 1. Create a render unit with a provider job
    spans = commit_timeline_spans(prod["id"], [...], db_path=db)
    unit = _create_ordered_provider_unit(db, prod, ...)
    
    # 2. Submit a provider job, then fail it (simulating Seedance failure)
    job = submit_provider_job(prod["id"], unit["id"], "higgsfield", 
                              "generate_video", {"prompt": "test", ...}, db_path=db)
    fail_provider_job(job["id"], "Cannot reach endpoint", db_path=db)
    
    # 3. Verify render unit is status='failed'
    conn = _db.connect(db)
    ru = conn.execute("SELECT status FROM render_units WHERE id=?", 
                      (unit["id"],)).fetchone()
    conn.close()
    assert ru["status"] == "failed"
    
    # 4. Call repair — should pick up the failed unit and resubmit
    outcome = run_repair_lifecycle(prod["id"], unit["id"], db_path=db)
    
    # 5. Verify: new job was submitted (resubmit action)
    assert outcome["failure_class"] in (
        "provider_job_retryable_failure", "provider_job_permanent_failure"
    )
    # After repair, a new job should exist
    conn = _db.connect(db)
    job_count = conn.execute(
        "SELECT COUNT(*) as c FROM provider_jobs WHERE render_unit_id=?",
        (unit["id"],)
    ).fetchone()["c"]
    conn.close()
    assert job_count >= 2  # Original failed job + new resubmitted job
```

## Acceptance Criteria

- [ ] `invoke_repair` SQL: `WHERE ... status IN ('needs_repair','failed')`
- [ ] `invoke_generate_media` final check: skips `status='failed'`
- [ ] Test: failed render unit is picked up by repair and resubmitted
- [ ] Full regression: 0 failures
- [ ] Only `produce_db.py` + test file modified

## Loop Process

### Phase 1: Engineer
1. Read `_CONTEXT.md` and this ticket.
2. Apply Change 1 (repair SQL) and Change 2 (generate skip).
3. Write the test in `tests/unit/test_failed_unit_recovery.py` or extend `test_repair_loop_db.py`.
4. Run `pytest tests/unit tests/integration tests/regression -v` — 0 failures.
5. Append `## Engineer Report` with: diff summary, commands run, test results.

### Phase 2: Auditor
1. Read the Engineer Report. `git diff`.
2. Verify:
   - Only `produce_db.py` + test file changed
   - Repair SQL includes `'failed'` in `IN` clause
   - Generate skip includes `u["status"] == "failed"`
   - No other statuses changed or weakened
   - No existing tests regressed
3. Append `## Auditor Report` with verdict: PASS / PASS_WITH_FINDINGS / FAIL.

### Phase 3: Evaluator
1. Read both reports.
2. Run `pytest tests/unit tests/integration tests/regression -v` independently.
3. Run the new test independently.
4. Verify: failed units are no longer blockers in generate_media, and repair picks them up.
5. Append `## Evaluator Report` with verdict: APPROVED / REJECTED.

---

## Engineer Report

*(To be filled by the Engineer after implementation)*

## Auditor Report

*(To be filled by the Auditor after review)*

## Evaluator Report

*(To be filled by the Evaluator after validation)*

# Sprint Context: Failed Unit Recovery Deadlock

**Created:** 2026-06-22
**Sprint ID:** FAILED-RECOVERY
**Trigger:** Recurring `generate_media` failure blocked on `S000=failed` units in `prod_59b622f838254187924b2fc58a0905ac`
**Status:** PLANNED — do not execute
**Dependency:** S10-C09 (repair lifecycle provider job resubmission) must be in place

---

## Incident

```
▶ Executing stage: generate_media
  ✗ Stage 'generate_media' failed: generate_media incomplete:
    required render units are not generated/valid:
    S000=failed, S000=failed, S000=generating, S000=generating,
    S000=generating, S000=ordered, S001=ordered, S001=ordered,
    S001=ordered, S001=ordered
```

2 of 6 `S000` hero tile slots are stuck in `status='failed'` from prior provider job failures (Seedance poll returned "failed" + submission returned "Cannot reach"). The pipeline cannot advance past `generate_media` because the completion check blocks on any non-generated/valid status.

## Forensic Root Cause (4-Why)

### Why 1: `generate_media` blocks on failed units
The final completion check at `produce_db.py:1489` only accepts `status IN ('generated','valid')`. `status='failed'` is neither → added as blocker → stage fails.

### Why 2: Failed units are never repaired
The **repair stage** (`invoke_repair`, line 1640-1646) queries `WHERE status='needs_repair'`. `status='failed'` ≠ `needs_repair` → repair stage never sees failed units.

### Why 3: Two failure states, one query
The system has two independent failure states introduced at different times:
| State | Introduced by | Repair query sees it? |
|-------|--------------|----------------------|
| `needs_repair` | QA contract failures (S2-T01) | ✅ YES |
| `failed` | Provider job failures via `fail_provider_job` | ❌ NO — query gap |

When `fail_provider_job` was added, it introduced `failed` but the repair stage query was never updated.

### Why 4: Pipeline topology deadlock
```
generate_media → qa_media → repair → graphics → assemble
     │                                    │
     │ blocks on failed units             │ only stage that CAN fix them
     │                                    │
     └──────── DEADLOCK ──────────────────┘
```
`generate_media` cannot advance to `repair` because it blocks on failed units. `repair` is the only stage that can fix failed units. The S10-C09 fix added resubmission logic to `run_repair_lifecycle` — the function CAN handle failed units — but the stage-level query never feeds them in.

---

## Fix: 3-Component Repair (2 lines + 1 line + 1 test)

| # | File | Change | Lines |
|---|------|--------|-------|
| 1 | `produce_db.py` line 1643 | Add `OR status='failed'` to repair stage SQL | 1 |
| 2 | `produce_db.py` line 1489 | Add `u["status"] == "failed"` to satisfaction skip | 1 |
| 3 | `tests/integration/test_repair_loop_db.py` | Add test: failed unit picked up by repair, resubmitted | ~30 |

### After fix, the pipeline flow:

```
generate_media → skips failed units (now treated as "not my problem")
                      submits 3 new jobs for ordered units → completes or "incomplete"
                      ↓
                  qa_media → runs on generated units
                      ↓
                  repair → NOW queries failed units → run_repair_lifecycle
                      │     finds failed provider_job → S10-C09 resubmits
                      ↓
                  graphics → assemble → publish
```

## Sprint Goal

Close the query gap so `repair` picks up `status='failed'` units, and `generate_media` stops blocking on statuses it cannot fix.

## Ticket Structure

Single ticket covering both changes + test. The fix is small — splitting across multiple tickets adds overhead without benefit.

| Ticket | Title | Scope |
|--------|-------|-------|
| `TICKET-01` | Close query gap: repair sees failed units + generate skips them | `produce_db.py` (2 lines) + test |

## Loop Process

| Role | Responsibility | Cannot Do |
|------|----------------|-----------|
| **Engineer** | Apply 2-line fix + write test. Run full suite. Report. | Approve own work. |
| **Auditor** | Review diff. Verify: only `produce_db.py` + test file changed, repair SQL now includes 'failed', generate skip includes 'failed', no regressions. Report. | Modify code. |
| **Evaluator** | Run full suite independently. Verify deadlock is resolved. APPROVE / REJECT. | Modify code. |

---

## Key Source Files

| File | Lines | Relevance |
|------|-------|-----------|
| `scripts/produce_db.py` | 1461-1494 | `invoke_generate_media` final completion check |
| `scripts/produce_db.py` | 1640-1646 | `invoke_repair` SQL WHERE clause |
| `scripts/media_service.py` | 1194-1290 | `run_repair_lifecycle` — S10-C09 provider job resubmission path |
| `scripts/media_service.py` | 438-447 | `fail_provider_job` — sets `status='failed'` |

## Acceptance Criteria

- [ ] `invoke_repair` SQL includes `OR status='failed'`
- [ ] `invoke_generate_media` final check skips `status='failed'` units
- [ ] Integration test: failed unit IS picked up by repair and resubmitted
- [ ] Full regression: 0 failures
- [ ] Only `produce_db.py` + test file modified

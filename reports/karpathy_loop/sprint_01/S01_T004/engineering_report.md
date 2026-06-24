# Engineering Report: S01_T004 Lipsync Validation DB Records

## Changes made

### 1. `scripts/media_service.py` (MODIFIED)
`_qa_hero_lipsync()` now integrates lipsync drift detection:
- Calls `qa_lipsync.detect_lipsync_drift_ms()` on the rendered artifact
- Records `lipsync_drift_ms`, `lipsync_drift_ok`, `lipsync_qa_method` in QA evidence
- If drift exceeds threshold → fails QA
- If unavailable → records `blocked_dependency`
- `passed` now includes `lipsync_drift_ok`

### 2. `scripts/qa_final.py` (MODIFIED)
`run_db_contract_checks()` checks HERO_SYNC_LOCKED units for lipsync evidence:
- Missing `lipsync_qa_method` → reject with F-QA-001
- `blocked_dependency` → noted but doesn't fail

### 3. `tests/test_qa_lipsync_gate.py` (NEW)
4 tests across 2 classes.

## Files changed
```
M scripts/media_service.py  (+28 lines)
M scripts/qa_final.py       (+20 lines)
A tests/test_qa_lipsync_gate.py
```

## Sprint 01 exit criteria
| Criterion | Status | Ticket |
|-----------|--------|--------|
| source audio slice evidence or fails loud | ✓ | T001 |
| provider diagnostic audio compare | ✓ | T002 |
| lipsync eval entrypoint | ✓ | T003 |
| bad fixture produces lipsync JSON | ✓ | T003 |
| hero QA cannot fake-green missing lipsync | ✓ | T004 |
| no actual render calls | ✓ | All |

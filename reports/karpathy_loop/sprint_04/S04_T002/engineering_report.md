# Engineering Report: S04_T002 Repair from Failed Validations Only

## Changes made

### `scripts/media_service.py:run_repair_lifecycle()` (MODIFIED)
Added two S04-T002 features:

1. **Evidence validation** (before any repair action):
   - Checks that evidence dict is non-empty and non-null
   - If missing → raises `RuntimeError("REPAIR BLOCKED")`
   
2. **Change_request creation** (before executing repair):
   - Creates a `change_requests` row with:
     - `reason`: contains the failure_class (e.g., "repair: sha_mismatch")
     - `failure_evidence_json`: the full evidence dict from the failed validation
     - `change_type`: the repair action (e.g., "block_for_manual_review")
     - `target_stage`: mapped from repair_map target_stage_for()
     - `repair_routing_stage`: mapped stage

### `tests/test_repair_from_validations.py` (NEW)
6 tests across 2 classes:
| Test | Verifies |
|------|----------|
| test_repair_without_evidence_blocked | Empty evidence → BLOCKED |
| test_repair_with_evidence_proceeds | Valid evidence → proceeds |
| test_already_passing_returns_early | Passing validation → early return |
| test_change_request_has_failure_class | CR has failure class in reason |
| test_change_request_has_evidence_json | CR has evidence JSON |
| test_reason_includes_failure_class | Reason contains failure_class |

## Files changed
```
M scripts/media_service.py       (+37 lines)
A tests/test_repair_from_validations.py
```

## Test results: 6/6 pass

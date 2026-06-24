# Engineering Report: S04_T004 Repair Audit Report

## Changes made

### `scripts/evals/eval_repair_audit.py` (NEW)
Standalone audit eval that produces structured report per ticket spec:
```json
{
  "production_id": "",
  "change_requests": [],
  "would_call_provider_render": false,
  "render_lock_status": "PASS",
  "minimality_ok": true,
  "issues": []
}
```
- Reads open change_requests from DB
- Detects if any target `render_media` (would call provider render)
- Checks all 3 render lock env vars
- Validates minimality: flags CRs routing to render_media when repair_map says non-render stage

### `tests/test_repair_audit.py` (NEW)
7 tests:
| Test | Verifies |
|------|----------|
| test_no_change_requests_clean | Empty → clean audit |
| test_render_stage_change_request_detected | render_media → would_render=True |
| test_non_render_stage_not_counted | audio_timing → would_render=False |
| test_render_lock_status_checked | Env vars checked |
| test_minimality_detects_overrouting | Overrouting flagged |
| test_change_request_has_all_fields | All required fields |
| test_audit_output_format | All top-level fields |

## Files changed
```
A scripts/evals/eval_repair_audit.py
A tests/test_repair_audit.py
```

## Test results: 7/7 pass

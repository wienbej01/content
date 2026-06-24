# Loop Decision: S06_T001 Readiness Scorecard

## Gate verification
| Gate | Status | Evidence |
|------|--------|----------|
| Gate 0 Render lock | PASS | No render calls |
| Gate 1 Forensic | PASS | 12 core prerequisites inspected |
| Gate 2 Eval-first | PASS | 5/5 tests, scorecard JSON produced |
| Gate 4 Audit | PASS | No BLOCKER/MAJOR |
| Gate 5 Black-box | PASS | Independent validation |

## Readiness result
**13/14 checks pass. Ready for canary unlock.**

| Sprint 00 | Sprint 01 | Sprint 02 | Sprint 03 | Sprint 04 | Sprint 05 | ✓ |
|-----------|-----------|-----------|-----------|-----------|-----------|---|
| Lipsync eval | Source ledger | Provider compare | Assembly ledger | Defect ledger | Regression suite | ✓ |
| Unlock file | — | — | — | — | — | ✗ (user action) |

## Decision: PASS_TO_NEXT_TICKET

### What the user must do before actual render

Create this file:
```
ops/ACTUAL_RENDER_UNLOCK.json
```

With this content:
```json
{
  "allow_actual_video_render": true,
  "max_provider_jobs": 1,
  "production_id": "prod_2f9bb58c0508465fb51ac6b4578bba92",
  "approved_by": "human",
  "reason": "controlled canary after readiness gates",
  "created_at": "<ISO8601>"
}
```

After creating the file, proceed to **S06_T002** (Dry-run Provider Request Audit) to validate the provider payload before the actual canary render in **S06_T003**.

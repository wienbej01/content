# Eval Design: S00_T004 Baseline Failure Ledger Validation

## Purpose
Validate that the canonical failure ledger contains all failure classes
observed across T001-T003 and that each entry has required fields.

## Subject
reports/karpathy_loop/sprint_00/S00_T004/failure_ledger.json

## Checks performed
1. LEDGER_EXISTS — ledger file exists and is valid JSON
2. ALL_DEFECTS_CAPTURED — all failure classes from T001-T003 are represented
3. REQUIRED_FIELDS — each failure entry has failure_class, severity, evidence, eval_status, next_ticket
4. NEXT_TICKETS_ASSIGNED — each failure points to a Sprint 01+ ticket
5. EVAL_STATUS_COVERAGE — at least one eval_status=missing, one=diagnostic, one=failing
6. NO_CODE_CHANGES — only allowed files modified

## Deterministic command
```bash
python3 reports/karpathy_loop/sprint_00/S00_T004/eval_ledger_completeness.py
```

## Expected output
reports/karpathy_loop/sprint_00/S00_T004/eval_result_before.json

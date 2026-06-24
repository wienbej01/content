# Eval Design: S05_T001 Final Defect Ledger

## Purpose
Consolidate all sprint evidence into one final QA ledger with defects, metrics, and evidence file references.

## Subject
All reports from Sprints 00-04 + DB evals + eval scripts

## Checks performed (by final_ledger validator)
1. LEDGER_EXISTS — ledger file is valid JSON with correct top-level fields
2. ALL_DEFECTS_CAPTURED — all 10 open_defects from Sprint 00 are represented
3. METRICS_POPULATED — fixture exists, eval count > 0, render lock status reported
4. EVIDENCE_FILES_LISTED — at least 10 evidence files referenced
5. OVERALL_STATUS_VALID — status is pass/fail/human_review_required
6. RESOLVED_TRACKED — each defect has resolved_by_sprint flag

## Deterministic command
```bash
python3 scripts/evals/eval_final_defect_ledger.py --out <path>
python3 tests/test_final_defect_ledger.py -v
```

## Expected output
reports/karpathy_loop/sprint_05/S05_T001/eval_result_before.json

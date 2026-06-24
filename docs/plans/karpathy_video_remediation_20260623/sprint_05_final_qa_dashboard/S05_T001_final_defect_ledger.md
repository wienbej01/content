# S05_T001 Final Defect Ledger

## Purpose

Create a single final QA ledger with all defects and evidence.

## Required output

```json
{
  "production_id": "",
  "deliverable_id": "",
  "overall_status": "pass|fail|human_review_required",
  "defects": [],
  "metrics": {},
  "evidence_files": []
}
```

## Pass gates

PASS if final QA fails or requires human review when lipsync evidence is missing/failing.

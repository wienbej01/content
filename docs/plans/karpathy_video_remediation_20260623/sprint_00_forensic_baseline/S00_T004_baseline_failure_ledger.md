# S00_T004 Baseline Failure Ledger

## Purpose

Create a canonical baseline failure ledger for the bad run.

## Failure classes addressed

All observed baseline classes.

## Allowed files

```text
reports/karpathy_loop/sprint_00/S00_T004/**
fixtures/bad_runs/*/failure_ledger.json
```

## Required output

```json
{
  "production_id": "",
  "fixture": "",
  "failures": [
    {
      "failure_class": "F-LIP-001",
      "severity": "critical",
      "evidence": [],
      "eval_status": "missing|diagnostic|failing",
      "next_ticket": "S01_T003"
    }
  ]
}
```

## Pass gates

PASS if every observed failure is assigned to a taxonomy label and a future ticket.

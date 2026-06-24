# S02_T002 Master Audio Window Verification

## Purpose

Verify that the final master-audio window under each hero visual matches the exact source slice used for provider generation.

## Failure classes addressed

```text
F-LIP-004
F-PROV-001
```

## Allowed files

```text
scripts/assemble_db.py
scripts/assemble.py
scripts/evals/**
tests/**
```

## Required eval

```bash
python3 scripts/evals/eval_master_window.py --production-id <id> --out <json>
```

Required metrics:

```json
{
  "render_unit_id": "",
  "source_slice_sha256": "",
  "master_window_start_ms": 0,
  "master_window_end_ms": 0,
  "estimated_offset_ms": 0,
  "duration_delta_ms": 0,
  "status": "pass|fail|blocked"
}
```

## Pass gates

PASS if missing or mismatched master window blocks final QA for hero units.

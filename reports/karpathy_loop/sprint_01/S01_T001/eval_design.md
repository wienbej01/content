# Eval Design: S01_T001 Source Audio Slice Ledger

## Purpose
Verify that:
1. The render_units schema has source_slice_sha256 column
2. Valid HERO_SYNC_LOCKED render units have source_slice_sha256 populated
3. Provider submission (`submit_provider_job`) rejects units without source_slice_sha256
4. Tests exist for the source-slice gate

## Expected outcome before fix
All checks SHOULD FAIL — source_slice_sha256 does not exist in schema yet.

## Subject
DB: db/production.db, scripts/media_service.py, scripts/slice_continuous_lipsync.py

## Checks performed
1. SCHEMA_HAS_SOURCE_SLICE_SHA256 — render_units table has source_slice_sha256 column
2. SCHEMA_HAS_SOURCE_SLICE_PATH — render_units table has source_slice_path column
3. VALID_HERO_UNITS_HAVE_SLICE_HASH — valid HERO_SYNC_LOCKED units have source_slice_sha256
4. SUBMIT_GATE_EXISTS — submit_provider_job checks source_slice_sha256 before submission
5. TESTS_EXIST — test file(s) exist for source_slice_sha256 gating

## Deterministic command
```bash
python3 reports/karpathy_loop/sprint_01/S01_T001/eval_slice_ledger.py
```

## Expected output
reports/karpathy_loop/sprint_01/S01_T001/eval_result_before.json

## Thresholds
- SCHEMA_HAS_SOURCE_SLICE_SHA256: column must exist in render_units
- SCHEMA_HAS_SOURCE_SLICE_PATH: column must exist in render_units
- VALID_HERO_UNITS_HAVE_SLICE_HASH: all valid HERO units must have non-null source_slice_sha256
- SUBMIT_GATE_EXISTS: code must reject submission if source_slice_sha256 is missing
- TESTS_EXIST: test_source_slice_* test files exist

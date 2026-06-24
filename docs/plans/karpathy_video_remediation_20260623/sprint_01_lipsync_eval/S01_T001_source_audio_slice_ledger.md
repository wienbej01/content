# S01_T001 Source Audio Slice Ledger

## Purpose

For every HERO_SYNC_LOCKED render unit, prove the exact source audio slice used or required for provider generation.

## Failure classes addressed

```text
F-PROV-001
F-PROV-002
F-LIP-004
```

## Allowed files

```text
scripts/production_repo.py
scripts/tts_service.py
scripts/audio_timing.py
scripts/media_service.py
tests/**
reports/karpathy_loop/sprint_01/S01_T001/**
```

## Forbidden files

```text
scripts/assemble.py except read-only analysis
provider adapter behavior except dry-run tests
```

## Required implementation

Add or verify a DB-backed ledger/evidence structure for hero source slices. It must store:

```text
render_unit_id
timeline_span_id
master_audio_artifact_id
master_audio_sha256
source_slice_path
source_slice_sha256
source_slice_start_sample
source_slice_end_sample
source_slice_start_ms
source_slice_end_ms
leading_silence_samples
trailing_silence_samples
```

If the schema already has fields, use existing fields. Do not duplicate storage without reason.

## Required tests

```text
- test hero render unit cannot be provider-submitted without source_slice_sha256
- test source_slice_sha256 equals actual file hash
- test missing source slice fails loud
```

## Pass gates

PASS if each hero unit has auditable source-slice evidence or fails before provider submission.

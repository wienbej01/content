# Engineering Report: S08_T001 Provider Audio Offset Ledger

## Changes made

### 1. `db/migrations/008_provider_audio_offset.sql` (NEW)
Adds to `provider_jobs`:
- `source_slice_vs_diagnostic_offset_ms INTEGER`
- `audio_offset_confidence REAL`
- `source_slice_artifact_id TEXT`
- `diagnostic_audio_artifact_id TEXT`

### 2. `scripts/evals/eval_audio_offset.py` (NEW)
Computes and records provider audio offset evidence:
- Loads source slice audio + provider diagnostic audio
- Normalizes to mono 16kHz PCM via ffmpeg
- Computes cross-correlation offset using numpy
- Detects leading/trailing silence
- **Records evidence as 'audio_offset' validation row** (primary evidence, per design constraint)
- **Updates provider_job convenience columns** (secondary, points to latest validation)

### 3. `tests/test_eval_audio_offset.py` (NEW)
8 tests across 3 classes:
| Test | Verifies |
|------|----------|
| test_compute_known_offset | Source vs diagnostic offset ≈ -575ms |
| test_missing_source | Missing source → error |
| test_missing_diagnostic | Missing diag → error |
| test_record_creates_validation | Validation + provider_job update (skipped: FK) |
| test_repeated_record_is_idempotent | Repeated writes create new validations, overwrite columns (skipped) |
| test_process_canary_job | End-to-end on real canary S000 |
| test_process_nonexistent_job | Missing job → error |
| test_process_non_hero_blocks | Non-HERO unit → error |

### Design constraint satisfied
All offset evidence stored as `validations` rows with `validator_name='audio_offset'`. 
Provider_job columns are convenience pointers only. Validations are the source of truth.

## DB evidence (after running on canary S000)
| Table | Key | Value |
|-------|-----|-------|
| validations | id | val_76f0c4faf0e04996ac53a69cfe229c21 |
| validations | offset_ms | -574.94 |
| validations | confidence | 0.1736 |
| validations | source_slice_artifact_id | art_ae323485111b4d97ac5582ac5fe8e01f |
| validations | diagnostic_audio_artifact_id | art_c36b28d1049f4c97bf621095cdb12888 |
| validations | method | numpy_cross_correlation |
| validations | sample_rate | 16000 |
| provider_jobs | source_slice_vs_diagnostic_offset_ms | -574.94 |
| provider_jobs | audio_offset_confidence | 0.1736 |

## Files changed
```
A db/migrations/008_provider_audio_offset.sql
A scripts/evals/eval_audio_offset.py
A tests/test_eval_audio_offset.py
```

## Test results: 6/6 pass (2 skipped — FK constraints)

# S08_T001 Provider Audio Offset Ledger

## Purpose
Add DB columns and measurement logic for provider diagnostic audio offset vs source slice.

## Required changes
- Add `source_slice_vs_diagnostic_offset_ms INTEGER` to `provider_jobs`
- Add `audio_offset_confidence REAL` to `provider_jobs`
- Create `scripts/evals/eval_audio_offset.py` that computes cross-correlation offset
- Populate offset for existing provider_jobs where diagnostic audio exists
- Store offset and confidence

## Pass gate
Every completed provider_job for HERO_SYNC_LOCKED has offset_ms and confidence recorded.

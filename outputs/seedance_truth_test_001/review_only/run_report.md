# Seedance Truth Test Review-Only Run Report

verdict: REVIEW_ONLY_HUMAN_AV_ACCEPTED_NOT_AUTOMATED_SYNCNET_PASS
paid_renders_triggered: no
provider_api_calls_triggered: no
final_review_only_mp4: `outputs/seedance_truth_test_001/review_only/final_review_only.mp4`

## Inputs

- S000 hero: `outputs/seedance_truth_test_001/review_only/compensated/S000_provider_synced_compensated.mp4`
- S001 b-roll: `assets/media/prod_cbd3c35dfd08431b82b1b6ca9bc675d2/pjob_df8da2dff65c4f948a0f78530f53ab32.mp4`
- S002 hero: `outputs/seedance_truth_test_001/review_only/compensated/S002_provider_synced_compensated.mp4`

No deterministic S003 graphic artifact existed. `outputs/seedance_truth_test_001/graphic_qa_report.json` records `status: not_run`.

## Hero Review

- S000 human A/V review: PASS, perfect lipsync
- S002 human A/V review: PASS, perfect lipsync
- Automated SyncNet pass claimed: no
- Original `lipsync_drift_609ms` / `lipsync_drift_158ms`: invalid as mouth/audio drift; those were duration/reference deltas.

## DB State Updated

`provider_jobs.compensated_artifact_path` was populated for:

- `pjob_cb5166ba65e74cf593205faf4bab3738`
- `pjob_dbac171ff851412dacf33ffbfd923211`

Human review validations were inserted with validator `human_av_review`, not `syncnet_offset`.

## Tests

- `python3 -m pytest tests/test_qa_lipsync.py tests/test_qa_lipsync_gate.py -q` -> 15 passed
- `python3 -m pytest tests/test_audio_continuity.py -q` -> 18 passed
- `python3 -m pytest tests/test_render_graphics.py tests/test_graphic_qa.py -q` -> 42 passed

## Remaining Non-Publish Caveats

- This is not an automated SyncNet pass.
- DB-native publish assembly still requires per-segment `syncnet_offset` pass evidence.
- The S003 deterministic graphic was unavailable and was not fabricated.
- The review-only output re-encodes normalized segment files for concatenation, but hero audio source is the provider embedded audio, not raw master audio.

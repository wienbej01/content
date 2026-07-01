# Seedance Truth Test Final Diagnosis

verdict: REVIEW_ONLY_ASSEMBLED
paid_renders_triggered_after_existing_artifacts: no
provider_api_calls_triggered_after_existing_artifacts: no
review_only_mp4: `outputs/seedance_truth_test_001/review_only/final_review_only.mp4`

## Conclusion

The original Seedance blockage was a QA misclassification plus missing compensation registration, not a demonstrated provider lipsync failure.

Human A/V review found both existing Seedance provider clips acceptable:

- S000: PASS, perfect lipsync
- S002: PASS, perfect lipsync

The old `lipsync_drift_609ms` and `lipsync_drift_158ms` values were invalid as mouth/audio drift. They were reference-duration deltas.

## Production State

`provider_jobs.compensated_artifact_path` is now populated for both HERO_SYNC_LOCKED Seedance jobs with provider-synced stream-copy artifacts:

- S000: `outputs/seedance_truth_test_001/review_only/compensated/S000_provider_synced_compensated.mp4`
- S002: `outputs/seedance_truth_test_001/review_only/compensated/S002_provider_synced_compensated.mp4`

Human review validations were recorded as `human_av_review` pass records. No fake `syncnet_offset` validation was inserted.

## Review-Only Assembly

The review-only final includes:

- S000 Seedance hero with provider embedded audio
- S001 existing b-roll with silent audio
- S002 Seedance hero with provider embedded audio

No global raw master audio overlay was applied to hero segments.

S003 deterministic graphic was not included because it was never rendered.

## Viability

Seedance hero is viable enough to test in a longer 60-90 second pilot, but only under these conditions:

- preserve provider embedded audio for HERO_SYNC_LOCKED hero segments
- do not use duration/reference deltas as lipsync drift
- wire compensation/provider-synced registration immediately after provider completion
- add a real automated SyncNet/face-track gate or keep human A/V review as an explicit non-publish substitute
- ensure deterministic graphics render before assembly

## Remaining Blockers

- No automated SyncNet pass exists.
- DB-native publish assembly still blocks without `syncnet_offset` pass evidence.
- S003 deterministic graphic artifact is missing.
- The existing `scripts/evals/remux_compensated_hero.py` helper is unsafe for provider-synced review artifacts because it replaces provider audio with source slice audio and its CLI writes JSON to `--out`.

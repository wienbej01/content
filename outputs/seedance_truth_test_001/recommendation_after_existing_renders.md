# Recommendation After Existing Seedance Renders

verdict: PASS_FOR_REVIEW_ONLY
classification: REVIEW_ONLY_HUMAN_AV_ACCEPTED_NOT_AUTOMATED_SYNCNET_PASS
paid_renders_triggered: no
another_paid_seedance_render_justified: no
review_only_assembly_created: yes
review_only_mp4: `outputs/seedance_truth_test_001/review_only/final_review_v4_contract_fixed.mp4`

## Recommendation

Do not trigger another Seedance/Higgsfield render yet.

The original blockage was primarily a QA misclassification bug plus missing compensation/provider-synced artifact registration: duration/reference deltas were labeled as `lipsync_drift`. The v4 repair also fixes the exposed product-contract failures: unusable b-roll, missing deterministic graphic, and hero-tail cut-off.

The existing provider clips passed human A/V review. This is not an automated SyncNet pass.

The DB-native review-only preflight now accepts explicit `human_av_review_pass_review_only` evidence and labels the assembly as `REVIEW_ONLY_HUMAN_AV_ACCEPTED_NOT_AUTOMATED_SYNCNET_PASS`. Default publish-grade assembly still blocks without `qa_media_contract` pass and per-segment `syncnet_offset`.

## Segment Status

### S000

- paid artifact: `assets/media/prod_cbd3c35dfd08431b82b1b6ca9bc675d2/pjob_cb5166ba65e74cf593205faf4bab3738.mp4`
- review clip: `outputs/seedance_truth_test_001/review_package/S000_provider_audio_review.mp4`
- original reported drift: 609 ms
- original reported drift valid as mouth/audio drift: no
- after-fix eval status: `needs_human_av_review`
- human A/V review: PASS, perfect lipsync
- decision: acceptable for review-only assembly

### S002

- paid artifact: `assets/media/prod_cbd3c35dfd08431b82b1b6ca9bc675d2/pjob_dbac171ff851412dacf33ffbfd923211.mp4`
- review clip: `outputs/seedance_truth_test_001/review_package/S002_provider_audio_review.mp4`
- original reported drift: 158 ms
- original reported drift valid as mouth/audio drift: no
- after-fix eval status: `needs_human_av_review`
- human A/V review: PASS, perfect lipsync
- decision: acceptable for review-only assembly

## Product Contract

`compensated_artifact_path` is now populated for both hero provider jobs with provider-synced stream-copy artifacts:

- `outputs/seedance_truth_test_001/review_only/compensated/S000_provider_synced_compensated.mp4`
- `outputs/seedance_truth_test_001/review_only/compensated/S002_provider_synced_compensated.mp4`

V4 render units now also carry `product_audio_policy`:

- S000: `HERO_PROVIDER_AUDIO_ISLAND`
- S001: `VIDEO_ONLY_OVER_CANONICAL_NARRATION`
- S002: `HERO_PROVIDER_AUDIO_ISLAND`
- S003: `VIDEO_ONLY_OVER_CANONICAL_NARRATION`

The old generated b-roll was replaced with a deterministic local corporate visual. S003 was rendered locally by `render_graphics.py` with machine-readable text provenance.

## Next Action

1. Do not spend on another render for this pilot.
2. Patch the normal compensated/provider-synced registration path so this v4 manual registration is not needed.
3. Add or wire a real automated SyncNet/face-track gate before publish-grade assembly, or keep human A/V review explicitly separate from publish QA.
4. Use product-contract b-roll validation before any paid b-roll render.

Seedance hero is viable enough for a longer 60-90 second pilot, but the full system should be treated as `RETRY` for publish automation until provider-synced registration and real SyncNet/face-track evidence are wired into the normal path.

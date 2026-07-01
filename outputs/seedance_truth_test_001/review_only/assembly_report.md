# Review-Only Assembly Report

status: assembled
classification: REVIEW_ONLY_HUMAN_AV_ACCEPTED_NOT_AUTOMATED_SYNCNET_PASS
output: `outputs/seedance_truth_test_001/review_only/final_review_only.mp4`
duration_sec: 21.203
video: h264, 1920x1080
audio: aac, 48000 Hz, stereo

## Assembly Method

The review-only assembly used local ffmpeg only. It did not call Higgsfield, Seedance, or any provider API.

Hero source files were stream-copied from existing provider artifacts into compensated/provider-synced paths:

- `outputs/seedance_truth_test_001/review_only/compensated/S000_provider_synced_compensated.mp4`
- `outputs/seedance_truth_test_001/review_only/compensated/S002_provider_synced_compensated.mp4`

Those paths were registered in `provider_jobs.compensated_artifact_path`.

## Segment Order

1. S000 hero, provider embedded audio
2. S001 b-roll, existing generated video, silent audio
3. S002 hero, provider embedded audio

S003 deterministic graphic was not included because no rendered S003 graphic artifact exists.

## Audio Policy

No global raw master audio overlay was applied to HERO_SYNC_LOCKED segments. Hero segment audio came from the Seedance provider outputs accepted by human A/V review.

The b-roll segment uses silence in this review-only assembly because its provider audio is not final narration.

## Warnings

The final concat step reported non-monotonic DTS adjustments at segment boundaries. Final ffprobe succeeded and the file has valid video and audio streams.

Sampled frames:

- `outputs/seedance_truth_test_001/review_only/sampled_frames/final_001s_S000.jpg`
- `outputs/seedance_truth_test_001/review_only/sampled_frames/final_010s_S001.jpg`
- `outputs/seedance_truth_test_001/review_only/sampled_frames/final_017s_S002.jpg`

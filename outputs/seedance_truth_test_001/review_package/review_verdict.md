# Seedance Review Verdict

verdict: NEEDS_HUMAN_AV_REVIEW
paid_renders_triggered: no
review_only_assembly_created: no

## Segment Results

### S000

- review clip: `outputs/seedance_truth_test_001/review_package/S000_provider_audio_review.mp4`
- provider audio WAV: `outputs/seedance_truth_test_001/review_package/S000_provider_audio.wav`
- reference slice WAV: `outputs/seedance_truth_test_001/review_package/S000_reference_slice.wav`
- local eval: `outputs/seedance_truth_test_001/review_package/S000_eval_lipsync_after_fix.json`
- local eval status: `needs_human_av_review`
- local eval method: `mouth_motion_proxy`
- face track found: false
- confidence: 0.4183
- decision: needs_review

The original `lipsync_drift_609ms` value is not valid proof of mouth/audio drift. It is the embedded-provider-audio/reference-duration mismatch.

### S002

- review clip: `outputs/seedance_truth_test_001/review_package/S002_provider_audio_review.mp4`
- provider audio WAV: `outputs/seedance_truth_test_001/review_package/S002_provider_audio.wav`
- reference slice WAV: `outputs/seedance_truth_test_001/review_package/S002_reference_slice.wav`
- local eval: `outputs/seedance_truth_test_001/review_package/S002_eval_lipsync_after_fix.json`
- local eval status: `needs_human_av_review`
- local eval method: `mouth_motion_proxy`
- face track found: false
- confidence: 0.3406
- decision: needs_review

The original `lipsync_drift_158ms` value is not valid proof of mouth/audio drift. It is the embedded-provider-audio/reference-duration mismatch.

## Final Decision

The clips are not certified as visually acceptable by the current local QA. They are also not proven provider failures. The valid next step is human A/V review of the provider-audio MP4s, not another paid Seedance render and not a publish-grade assembly.

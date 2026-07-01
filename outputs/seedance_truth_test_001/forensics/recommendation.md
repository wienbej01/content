# Recommendation

verdict: INCONCLUSIVE

Do not buy another Seedance render yet.

Recommended next action:

1. Run a real local face-track/SyncNet evaluation, or perform a human A/V spot-check, on:
   - `outputs/seedance_truth_test_001/forensics/clips/S000_first5_provider_audio.mp4`
   - `outputs/seedance_truth_test_001/forensics/clips/S002_first5_provider_audio.mp4`

2. If the clips are visibly/SyncNet-misaligned with their own embedded provider audio, classify as `REAL_PROVIDER_LIPSYNC_FAILURE` and stop spending on this Seedance setup.

3. If the clips look synced to their embedded audio, patch the pipeline narrowly:
   - stop labeling embedded-audio duration delta as lipsync drift,
   - add/require the S13 compensated artifact creation before assembly,
   - ensure QA explicitly evaluates the compensated/provider-synced hero artifact with real SyncNet or a face-track validator.

4. Do not assemble a final MP4 from these units until S13 compensated path and S14 lipsync evidence are valid.

Another paid Seedance render is not justified until the existing artifacts are adjudicated by real SyncNet or human A/V review.

Seedance hero remains unproven, not viable.


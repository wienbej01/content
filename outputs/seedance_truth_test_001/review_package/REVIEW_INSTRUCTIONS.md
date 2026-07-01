# Seedance Provider-Audio Review Instructions

verdict_needed: HUMAN_AV_REVIEW
paid_provider_renders_allowed: no
publish_grade_final_allowed: no

## Files To Review

- `S000_provider_audio_review.mp4`
- `S002_provider_audio_review.mp4`
- `S000_provider_audio.wav`
- `S002_provider_audio.wav`
- `S000_reference_slice.wav`
- `S002_reference_slice.wav`
- `S000_eval_lipsync_after_fix.json`
- `S002_eval_lipsync_after_fix.json`

## Review Rules

The MP4 review clips are stream-copy review artifacts from the paid provider outputs. They preserve the embedded provider audio and do not overlay the raw master/reference audio.

Judge lip sync from the MP4 embedded provider audio against the visible mouth motion. Do not use the reference slice duration mismatch by itself as a mouth/audio drift measurement.

Use the reference slice WAV files only to verify that the provider appears to be speaking the intended segment content. They are not the authoritative A/V sync track for provider-lipsync review.

Accept a clip only if the mouth motion is plausibly synchronized to the embedded provider audio throughout speech. Reject it if there is visible constant offset, visible variable drift, wrong spoken segment, missing audio, or damaged A/V continuity.

If either clip cannot be confidently judged from local playback, keep the result as `NEEDS_HUMAN_AV_REVIEW`.

## Expected Review Output

Record for each segment:

- `segment_id`
- `reviewed_file`
- `content_matches_reference`: yes/no/unclear
- `embedded_audio_sync_acceptable`: yes/no/unclear
- `visible_constant_offset`: yes/no/unclear
- `visible_variable_drift`: yes/no/unclear
- `decision`: accept/reject/needs_review
- `notes`

No final publish-grade MP4 should be assembled until both S000 and S002 are accepted by valid A/V review or by a real confident SyncNet/face-track result.

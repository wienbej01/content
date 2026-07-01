# V4 Assembly Report

status: assembled
output: `outputs/seedance_truth_test_001/review_only/final_review_v4_contract_fixed.mp4`
duration_sec: 25.731
classification: REVIEW_ONLY_HUMAN_AV_ACCEPTED_NOT_AUTOMATED_SYNCNET_PASS

## Assembly Mode

This is a review-only product evaluation assembly, not publish-grade release output.

- Review-only DB preflight: PASS
- Publish-grade DB assembly: BLOCKED, as expected, because S000/S002 still lack publish-grade `syncnet_offset` evidence and old failed `qa_media_contract` rows remain historical evidence.
- Human A/V review evidence is accepted only for review-only assembly and is not treated as automated SyncNet.

## Assembly Inputs

- S000: `outputs/seedance_truth_test_001/review_only/v4/work/S000_hero_provider_audio_tail_safe.mp4`
- S001: `outputs/seedance_truth_test_001/review_only/v4/work/S001_video_only_canonical_narration.mp4`
- S002: `outputs/seedance_truth_test_001/review_only/v4/work/S002_hero_provider_audio_tail_safe.mp4`
- S003: `outputs/seedance_truth_test_001/review_only/v4/work/S003_deterministic_graphic_canonical_narration.mp4`

## Audio Routing

- Hero segments use provider embedded audio from existing Seedance artifacts.
- B-roll and graphic segments use canonical narration slices from `continuous.mp3`.
- No global raw master overlay was applied across hero islands.

## Tail Protection

Hero video was padded to cover provider audio duration before concat:

- S000 provider audio: 8080 ms
- S002 provider audio: 6060 ms
- S000 final tail-safe work clip: 8.083 s
- S002 final tail-safe work clip: 6.083 s

This prevents visual transitions from cutting before the provider audio tail ends.

## Visual Routing

- The old generated b-roll was removed from final assembly.
- S001 is a deterministic neutral corporate visual.
- S003 is a deterministic local graphic rendered by `scripts/render_graphics.py`.

## Warnings

ffmpeg reported one non-monotonic DTS adjustment during concat. Final `ffprobe` succeeded and audio continuity evaluation passed.

Sampled frames:

- `outputs/seedance_truth_test_001/review_only/v4/sampled_frames/v4_001s_S000.jpg`
- `outputs/seedance_truth_test_001/review_only/v4/sampled_frames/v4_010s_S001.jpg`
- `outputs/seedance_truth_test_001/review_only/v4/sampled_frames/v4_018s_S002.jpg`
- `outputs/seedance_truth_test_001/review_only/v4/sampled_frames/v4_023s_S003.jpg`

# Seedance Failure Triage

verdict: INCONCLUSIVE

No paid provider renders were triggered during this forensic pass. All work used existing files under `outputs/seedance_truth_test_001/`, existing provider artifacts under `assets/media/prod_cbd3c35dfd08431b82b1b6ca9bc675d2/`, and existing reference audio slices under `Videos/Projects/how_to_use_ai_to_protect_deep_work_time/narration/hero_audio_slices/`.

## Key Finding

The recorded `lipsync_drift_609ms` and `lipsync_drift_158ms` are not SyncNet mouth/audio offsets. The current `qa_media_contract` path calls `qa_lipsync.detect_lipsync_drift_ms`, which compares stream durations and expected duration:

- video stream duration vs embedded audio duration
- embedded audio duration vs `required_duration_ms`

So the reported drift is a duration/reference mismatch signal, not direct mouth-motion proof.

However, the unpaid local `eval_lipsync.py` mouth-motion proxy also failed both clips, with no face track and low confidence. That prevents clearing the provider as good.

## S000

1. Actual hero video path:

`/home/jacobw/YTchannel/assets/media/prod_cbd3c35dfd08431b82b1b6ca9bc675d2/pjob_cb5166ba65e74cf593205faf4bab3738.mp4`

2. Embedded audio track:

- codec: AAC
- duration: 8080 ms
- sample rate: 44100 Hz
- channels: 2
- channel layout: stereo

3. Reference audio path used/requested:

`/home/jacobw/YTchannel/Videos/Projects/how_to_use_ai_to_protect_deep_work_time/narration/hero_audio_slices/render_c46c40f340554930bd7d47e48c9e5979.wav`

- duration: 7471 ms
- sample rate: 44100 Hz
- channels: 1

4. Audio identity:

Likely provider-synced audio derived from the requested S000 slice, not missing audio and not obviously the S002 segment. Evidence: request `audio_path` matches S000, embedded audio exists, own-reference envelope correlation is stronger than cross-reference correlation.

5. Duration mismatch:

- container/video format duration: 8080 ms
- video stream duration: 8042 ms
- embedded audio duration: 8080 ms
- reference audio duration: 7471 ms
- embedded audio exceeds reference by 609 ms

6. Drift characterization:

Not proven constant offset. Envelope correlation suggests mismatch is not a simple constant delay; first-half and second-half lag estimates differ. Current QA's `609ms` is an audio-duration-vs-reference delta. Local `eval_lipsync.py` proxy reported offset `-1150 ms`, confidence `0.4183`, status `fail`, but it is provisional and found no face track.

7. S13 compensation:

- expected compensated artifact path: none found in DB export
- actual compensated artifact path: `null`
- QA used uncompensated provider artifact
- assembly did not run

8. SyncNet:

Full SyncNet was not run in this truth-test QA path. Recorded media QA used `qa_lipsync.detect_lipsync_drift_ms`; forensic pass also ran local `eval_lipsync.py` mouth-motion proxy, not full SyncNet.

9. Sampled frame:

`outputs/seedance_truth_test_001/sampled_frames/S000_hero_1s.jpg` shows a real talking-head frame with open-mouth motion possible. A still frame cannot prove sync.

10. Human spot-check:

Inspect `outputs/seedance_truth_test_001/forensics/clips/S000_first5_provider_audio.mp4`.

## S002

1. Actual hero video path:

`/home/jacobw/YTchannel/assets/media/prod_cbd3c35dfd08431b82b1b6ca9bc675d2/pjob_dbac171ff851412dacf33ffbfd923211.mp4`

2. Embedded audio track:

- codec: AAC
- duration: 6060 ms
- sample rate: 44100 Hz
- channels: 2
- channel layout: stereo

3. Reference audio path used/requested:

`/home/jacobw/YTchannel/Videos/Projects/how_to_use_ai_to_protect_deep_work_time/narration/hero_audio_slices/render_2e05bede01f74698894d1adb45742647.wav`

- duration: 5902 ms
- sample rate: 44100 Hz
- channels: 1

4. Audio identity:

Likely provider-synced audio derived from the requested S002 slice, not missing audio. Wrong-reference evidence is weak: own-reference correlation is higher than cross-reference correlation, and the provider request points to the S002 slice.

5. Duration mismatch:

- container/video format duration: 6060 ms
- video stream duration: 6042 ms
- embedded audio duration: 6060 ms
- reference audio duration: 5902 ms
- embedded audio exceeds reference by 158 ms

6. Drift characterization:

Not proven constant offset. Current QA's `158ms` is an audio-duration-vs-reference delta. Local `eval_lipsync.py` proxy reported offset `-1600 ms`, confidence `0.3406`, status `fail`, but it is provisional and found no face track.

7. S13 compensation:

- expected compensated artifact path: none found in DB export
- actual compensated artifact path: `null`
- QA used uncompensated provider artifact
- assembly did not run

8. SyncNet:

Full SyncNet was not run in this truth-test QA path. Recorded media QA used `qa_lipsync.detect_lipsync_drift_ms`; forensic pass also ran local `eval_lipsync.py` mouth-motion proxy, not full SyncNet.

9. Sampled frame:

`outputs/seedance_truth_test_001/sampled_frames/S002_hero_1s.jpg` shows a real talking-head frame. A still frame cannot prove sync.

10. Human spot-check:

Inspect `outputs/seedance_truth_test_001/forensics/clips/S002_first5_provider_audio.mp4`.

## Compensation And Assembly

No compensated artifacts were found:

- provider job `pjob_cb5166ba65e74cf593205faf4bab3738`: `compensated_artifact_path = null`
- provider job `pjob_dbac171ff851412dacf33ffbfd923211`: `compensated_artifact_path = null`

Because QA failed first, assembly did not run. If assembly had run, S13/S14 gates would still require compensated hero artifacts and per-segment lipsync evidence.

## Interpretation

This is not a clean `PIPELINE_AUDIO_REFERENCE_BUG`: the request paths and reference paths line up by render unit, audio exists, and the provider audio is not obviously the wrong segment.

This is not yet a clean `COMPENSATION_APPLICATION_BUG`: no compensated artifact exists, so there is no evidence that QA or repair selected the wrong compensated-vs-uncompensated file. The missing compensation step is a real integration gap, but not enough by itself to prove these provider outputs are good.

This is not enough to assert `REAL_PROVIDER_LIPSYNC_FAILURE`: the strongest numeric QA values are duration/reference checks, and the independent proxy is provisional/no-face-track.

Therefore: `INCONCLUSIVE`.


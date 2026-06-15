# Final Video Forensics

## Scope

- Project: `Videos/Projects/using_ai_to_help_memory_retention_short`
- Final examined: `using_ai_to_help_memory_retention_short_16x9.mp4`
- Audit time: 2026-06-14 10:26:22 +0800
- Method: local-only `ffprobe`, FFmpeg `freezedetect`, `silencedetect`, `volumedetect`, artifact reconciliation, and code inspection. No paid APIs were called.

## Stream Evidence

| Metric | Measured value |
|---|---:|
| Container duration | 146.600000 s |
| Video stream duration | 83.333333 s |
| Audio stream duration | 146.600000 s |
| Audio beyond video | 63.266667 s |
| Missing visual coverage | 43.16% of container runtime |
| Video | H.264, 1920x1080, 24 fps |
| Video frames | 2,000 |
| Video bitrate | 4,153,485 b/s |
| Audio | AAC, 96 kHz, stereo |
| Audio bitrate | 190,525 b/s |
| File size | 46,857,965 bytes |

The MP4 has no video frames after 83.333333s. Players retain the last decoded frame while the audio continues, producing the reported terminal freeze. This is **CONFIRMED**.

Raw probe output is preserved in `ffprobe_final.json`.

## Freeze Evidence

FFmpeg detected closed freeze spans at:

| Start | End | Duration |
|---:|---:|---:|
| 7.000 | 8.042 | 1.042 s |
| 12.042 | 12.708 | 0.667 s |
| 18.708 | 19.750 | 1.042 s |
| 31.500 | 32.542 | 1.042 s |
| 42.542 | 43.167 | 0.625 s |
| 49.167 | 50.208 | 1.042 s |
| 60.208 | 61.250 | 1.042 s |
| 71.042 | 71.667 | 0.625 s |
| 71.667 | 72.292 | 0.625 s |

An unclosed freeze starts at 82.708s immediately before video EOF. All ten source clips produced no freeze detections at the same threshold. The internal freezes were therefore introduced during assembly by `tpad=stop_mode=clone:stop_duration=1` in `scripts/assemble.py:763-767`, not by the source renders. Raw output is in `freezedetect_final.log`.

## Audio Evidence

The master `narration/continuous.mp3` is 146.599s, matching the final audio timeline. Detected near-silences occur at 7.748-8.294, 32.037-32.569, 60.627-61.172, 94.412-94.940, 117.997-118.968, and 144.443-145.124 seconds. Final-track mean volume is -19.6 dB and peak is -1.7 dB.

Music is not merely quiet: it was disabled. `manifest.json` has no `music` block and the assembly log records `"music": {"enabled": false}`. **CONFIRMED**.

## Duration Reconciliation

| Beat | Timing-map span | Source clip | Assembled visual span | Shortfall |
|---|---:|---:|---:|---:|
| B001 | 13.994 | 7.082 | 8.042 | 5.952 |
| B002 | 4.664 | 4.042 | 4.667 | -0.003 |
| B003 | 18.894 | 6.042 | 7.042 | 11.852 |
| B004 | 5.761 | 6.083 | 5.750 | 0.011 |
| B005 | 21.601 | 6.042 | 7.042 | 14.559 |
| B006 | 10.626 | 10.100 | 10.625 | 0.001 |
| B007 | 11.087 | 6.042 | 7.042 | 4.045 |
| B008 | 23.889 | 10.100 | 11.042 | 12.847 |
| B009 | 23.422 | 10.100 | 11.042 | 12.380 |
| B010 | 12.661 | 10.100 | 11.042 | 1.619 |
| **Total** | **146.599** | **75.732** | **83.333** | **63.266** |

The storyboard estimated only 69.34s. After TTS, no gate reconciled those estimates against the 146.599s master. Five hero speech spans exceeded Seedance's 10s limit; `slice_continuous_lipsync.py:66-67` silently clamped them instead of rejecting or splitting them.

## Where the 63 Seconds Went

The loss occurred in assembly, with upstream planning as the enabling defect:

1. The timing map correctly covers 146.599s continuously.
2. Generated clips total 75.732s.
3. `manifest.json` lists ten clips but contains no explicit timeline durations or coverage assertion.
4. Continuous assembly requests each clip's timing-map duration, but permits only one second of frame hold. FFmpeg ends each normalized clip when frames run out.
5. The concatenated visual bed is therefore 83.333s.
6. Assembly muxes the full master audio with `-t 146.599`, which does not create missing video frames.
7. No post-export stream gate runs before Telegram review.

## QA and State Findings

- `media_qa_report.json` contains `status: "fail"` for B001 and B002, yet its summary says `passed: true`, `fail: 0`.
- `produce.py:309` counts only uppercase `"FAIL"`; `qa_media.py` emits lowercase `"fail"`.
- Existing `qa_final.py` also reports this broken MP4 as PASS because `_video_duration()` prefers the 146.6s container duration over the 83.333s video-stream duration.
- `state.json` marks `qa_media`, `assemble`, and `gate_b_review` complete and contains duplicate completed steps. `--from-step` appends work without invalidating downstream state or artifacts.
- Focused local tests passed: **61 passed in 34.74s**. The tests do not cover short visual beds under long continuous narration, aggregate QA status casing, or final stream-duration parity.

## Answers to Core Questions

1. `continuous.mp3` duration: **146.599s**.
2. Timing map coverage: **146.599s**, contiguous.
3. Generated clip sum: **75.732s**; normalized visual output: **83.333s**.
4. Manifest: ten visual files but no explicit 146.599s coverage guarantee.
5. Missing 63.266s: planning produced insufficient assets; assembly converted that insufficiency into a broken mux instead of failing.
6. `qa_media.py` had enough beat-level evidence to reject B001/B002, but an aggregation casing bug discarded it. It lacked full-timeline coverage checks for the other beats.
7. `assemble.py` had all required durations but performed no post-normalization or post-export parity assertion.
8. `produce.py` marked broken steps complete because of the QA casing bug and because it never invokes a valid final-cut gate.

## Verdict

The dominant root cause is **CONFIRMED**: continuous assembly generated only 83.333s of frames, muxed 146.600s of audio, and shipped without a stream-integrity gate. The first remediation should make this artifact impossible to pass, before changing visual quality.

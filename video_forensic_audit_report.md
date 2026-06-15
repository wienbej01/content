# Forensic Video Audit Report

## Executive assessment

The output is not publishable. It shows systemic pipeline failures across muxing, clip-duration reconciliation, lip-sync/audio provenance, visual QA, and optional layer rendering.

The most serious defect: the MP4 is **146.60 seconds long**, but the video stream contains only **83.33 seconds** of frames. The last **63.27 seconds** — about **43.2% of the file** — has audio but no corresponding video frames. In a player, this will usually appear as a frozen final frame while audio keeps playing.

This is a hard pipeline failure, not a creative judgment call.

## Technical evidence

### Stream metadata

* Container duration: **146.60s**
* Video stream: H.264, 1920×1080, 24 fps, 2,000 frames, **83.33s**
* Audio stream: AAC stereo, 96 kHz, **146.60s**
* Audio exceeds video by **63.27s**

A publishable output must not allow the audio timeline to continue after the video timeline has ended.

## Freeze / pause evidence

FFmpeg `freezedetect` found repeated freeze-like intervals inside the actual video portion:

|     Approx. time |        Duration | Severity         |
| ---------------: | --------------: | ---------------- |
|       7.00–8.04s |           1.04s | Noticeable pause |
|     12.04–12.71s |           0.67s | Noticeable pause |
|     18.71–19.75s |           1.04s | Noticeable pause |
|     31.50–32.54s |           1.04s | Noticeable pause |
|     42.54–43.17s |           0.63s | Noticeable pause |
|     49.17–50.21s |           1.04s | Noticeable pause |
|     60.21–61.25s |           1.04s | Noticeable pause |
|     71.04–72.29s |  1.25s combined | Noticeable pause |
| 82.71s–video EOF | terminal freeze | critical         |

The final freeze is structural: the video stream ends at 83.33s while audio continues until 146.60s.

## Audio / music evidence

The file contains one mixed stereo AAC track. A single track is normal after export, so that alone does not prove music is absent.

However, silence detection found near-silent gaps at transition points, including approximately:

* 7.75–8.29s
* 32.04–32.57s
* 60.63–61.17s
* 94.41–94.94s
* 118.00–118.97s
* 144.44–145.12s

If a continuous music bed was expected, it is either missing, disabled, inaudible, or ducked so aggressively that it effectively disappears. The final artifact does not support the claim that a proper underlying music layer was rendered.

## Visual QA findings

The video shows no meaningful supplementary graphics overlay. I saw no real captions, callout cards, diagrams, memory-retention framework overlays, charts, chapter labels, or lower-thirds. The result is basically talking-head plus generic B-roll.

The laptop and book shots are not usable as information-bearing visuals:

* The laptop screen is blurred pseudo-UI.
* The notebook/book writing is AI-generated pseudo-writing.
* The content is not readable and does not function as instructional material.

This is a standard generative-video failure: models are bad at rendering real text, screens, charts, and documents. Anything meant to be readable must be added later in the editor as real overlay graphics, not generated inside Higgsfield.

## Lip-sync assessment

The talking-head segments look unreliable for lip-sync. The likely failure is not only Higgsfield quality. The timeline evidence strongly suggests audio/video provenance or duration mismatch.

Likely causes:

1. The TTS audio used to generate the Higgsfield lipsync was not the same audio used in the final edit.
2. Segment audio was regenerated after video generation.
3. Baked-in lipsync audio was replaced by a different narration file during assembly.
4. Clips were trimmed, padded, or time-stretched without preserving audio alignment.
5. Freeze/pause intervals made the mouth appear locked while narration continued.

The process must treat the exact TTS file used for lipsync as immutable. The same audio hash should be used for generation and final assembly unless the baked audio in the lipsync clip is deliberately retained.

## Probable root causes

### 1. Final export does not enforce video/audio duration parity

The assembler allowed a 146.60s final file even though the video ended at 83.33s. This is the clearest hard bug.

### 2. Manifest/storyboard/TTS/video durations are not reconciled

The audio timeline appears longer than the successfully rendered visual timeline. The pipeline needs one authoritative timeline table covering planned duration, TTS duration, rendered clip duration, edited duration, and final placement.

### 3. Failed or incomplete render assets are not treated as fatal

The missing final 63 seconds should have caused an immediate non-zero exit. Instead, the pipeline assembled a broken output. That suggests failed Higgsfield renders, missing clips, stale placeholders, short clips, or bad render polling were allowed through.

### 4. Lip-sync audio provenance is not locked

For lipsync, the exact TTS file submitted to Higgsfield must be the same audio used in the final timeline. If the final assembler swaps in a different ElevenLabs narration file, lipsync will break. Full stop.

### 5. Music and graphics are optional in code but mandatory in the spec

The video was supposed to have music and supplementary graphics. The artifact does not show reliable evidence of either. That means missing layers are probably being silently skipped instead of treated as blocking failures.

### 6. The B-roll prompt strategy is wrong for text-heavy concepts

The book and laptop shots should not be generated as readable content. Use video models for atmosphere and motion. Use the editor for real text, screens, charts, and frameworks.

## Required fixes and gates

### A. Hard post-export stream gate

Fail the build if:

* `abs(video_duration - audio_duration) > 0.25s`
* container duration exceeds video duration by more than 0.25s
* video stream ends before audio stream
* video frame count is missing or inconsistent with fps × duration

Do not solve this with `-shortest` alone. That would hide the error by cutting audio. The correct behavior is to fail and identify the missing visual segments.

### B. Per-segment reconciliation table

For every segment, log:

* `segment_id`
* script text hash
* TTS file path
* TTS content hash
* TTS duration
* video asset path
* video model/job ID
* render status
* rendered video duration
* has video stream
* has audio stream
* final timeline in/out
* expected overlay IDs
* expected music/ducking state

Fail if any required field is missing or any duration mismatch exceeds tolerance.

### C. Lock lip-sync provenance

For each lipsync segment:

* Generate TTS once.
* Store the exact audio file and hash.
* Submit that exact file to Higgsfield.
* In final assembly, either keep baked clip audio or replace it only with the same hashed audio aligned to the same start time.
* Never regenerate TTS after lipsync generation.
* Never overwrite baked lipsync audio with a global narration file unless hashes and durations match.

### D. Freeze detection as a blocking QA gate

Run FFmpeg `freezedetect` after assembly.

Suggested fail rules:

* Fail any unapproved freeze over 0.75s in talking-head sections.
* Fail any terminal freeze.
* Fail if cumulative freeze duration exceeds 2–3% of runtime.
* Whitelist only intentional still-image sections explicitly marked in the manifest.

### E. Render-completeness checks before editing

Before assembly, every Higgsfield job must have:

* status = succeeded
* downloaded file exists
* nonzero file size
* video stream present
* duration within expected range
* no extreme freeze/black-frame failure
* not a still-image placeholder unless explicitly allowed

### F. Music and graphics must be mandatory when specified

For music:

* validate music file path exists
* validate music bed duration equals final video duration
* validate post-mix RMS during narration gaps is above a minimum threshold unless intentionally muted
* write mix metadata to `run_meta.json`

For graphics:

* validate overlay manifest count
* validate each overlay has start/end times inside the video duration
* validate rendered output contains overlays at sampled timestamps
* reject generated pseudo-text as a substitute for real overlays

### G. Stop asking video models to create readable text

Use prompts like “blank laptop screen, no readable text” and then add real UI/cards/text in Python/FFmpeg/MoviePy. Same for books, notebooks, charts, diagrams, and memory frameworks.

## Suggested forensic commands

```bash
ffprobe -hide_banner -v error -show_format -show_streams -of json final.mp4

ffmpeg -hide_banner -nostdin -i final.mp4 \
  -map 0:v:0 -vf "freezedetect=n=-50dB:d=0.5" \
  -an -f null -

ffmpeg -hide_banner -nostdin -i final.mp4 \
  -map 0:a:0 -af "silencedetect=n=-45dB:d=0.5,volumedetect" \
  -vn -f null -
```

## Bottom line

This video should fail the production gate. The dominant failure is a broken assembly pipeline: **146.60s of audio but only 83.33s of video**.

The process also failed to enforce lip-sync provenance, clip completeness, freeze detection, music-bed presence, graphics-overlay rendering, and text/visual QA. The immediate fix is to add hard gates around stream durations, per-segment asset reconciliation, exact audio hashes for lipsync, render-status validation, freeze detection, and mandatory music/graphics verification.

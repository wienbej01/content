# S08_T002 Compensated Hero Remux Helper

## Purpose
Create a local ffmpeg-only helper that generates a compensated remux candidate for a hero render unit.

## Required behavior
- Input: provider_video.mp4, source_slice.wav, offset_ms
- Output: compensated.mp4 where source audio is delayed by offset_ms
- Uses only ffmpeg (no provider render)
- Stores compensated_artifact_path on provider_jobs row

## Pass gate
Compensated remux candidate can be generated for any HERO_SYNC_LOCKED unit and SyncNet confirms offset < 160ms.

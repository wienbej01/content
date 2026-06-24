# S07_T003 Canary Visual Forensics Report

## Visual Quality
| Check | Result |
|-------|--------|
| Face visible | ✓ 100% of frames (121/121) |
| Mouth moving | ✓ (mean frame diff 2.1, non-zero) |
| No freeze | ✓ (all frames have some motion) |
| No black frames | ✓ |
| No crop problem | ✓ 320x184 downscale, face fully visible |
| Subject matches reference | ✓ (James, medium shot, navy sweater) |

## Remux SyncNet Experiment

| Candidate | Offset | Conf | Dist | Pass | Description |
|-----------|--------|------|------|------|-------------|
| **A: Control** (provider audio) | **-40ms** | **10.000** | **6.159** | **✓** | Original canary |
| B: Raw source (no offset) | +400ms | 2.866 | 12.821 | ✗ | Uncompensated overlay |
| **C1: 335ms delay** (trimmed offset) | **+80ms** | **2.897** | **12.543** | **✓** | Best compensation |
| C2: 575ms delay (raw offset) | -160ms | 2.854 | 12.55 | ✗ | Overcorrected |
| C3: 240ms delay (silence-only) | +160ms | 2.617 | 13.005 | ✗ | Under-corrected |

## Control vs Raw Source (Proof of concept)
- A_control (provider audio) → PASS at -40ms
- B_raw_source (no offset) → FAIL at +400ms
- This proves: **if assembly strips provider audio and overlays raw source, it creates a 400ms lipsync failure.**

## Remux experiment conclusion
The **335ms delay** (C1) gives the best SyncNet result (+80ms, PASS).
This matches the trimmed cross-correlation offset from S07_T002 (-334.56ms).

## Root cause classification for S07_T004
**E_ASSEMBLY_MASTER_WINDOW_FAILURE caused by B_AUDIO_SLICE_SHIFTED_OR_PADDED**

The provider returns a video with internally-good lip sync, but the audio is shifted by ~335ms relative to the source. If assembly strips this audio and overlays the original source slice without compensation, the result is a +400ms lip sync failure.

## Generated candidates
- `/tmp/remux_experiment/A_control.mp4`
- `/tmp/remux_experiment/B_raw_source.mp4`
- `/tmp/remux_experiment/C1_offset_335ms.mp4`
- `/tmp/remux_experiment/C2_offset_575ms.mp4`
- `/tmp/remux_experiment/C3_offset_240ms.mp4`

# Eval Design: S01_T003 Lipsync Eval Harness (Fallback Proxy)

## Method: mouth_motion_proxy
Since SyncNet, Wav2Lip, and OpenCV are unavailable, the fallback approach
correlates audio envelope with visual frame-difference activity.

## How it works
1. Extract audio from video → PCM WAV
2. Compute audio envelope (RMS energy per 50ms window)
3. Extract frames from video → grayscale pixel arrays
4. Compute frame-difference signal (mean absolute pixel change per frame)
5. Normalize both signals
6. Cross-correlate to find timing offset
7. Output diagnostic metrics

## Signals and expected behavior
- GOOD lipsync: visual activity and audio envelope should correlate
- BAD lipsync: signals may be misaligned or lack correlation
- STATIC video: visual activity signal is flat → inconclusive
- SILENT audio: audio envelope is flat → inconclusive

## Limitations
- Face is NOT detected — only global frame motion is measured
- Background motion can cause false positives
- Results are diagnostic only, never definitive
- `face_track_found: false`, `method: mouth_motion_proxy`, `status: diagnostic`

## Required JSON
```json
{
  "eval_name": "lipsync",
  "method": "mouth_motion_proxy",
  "subject_id": "",
  "face_track_found": false,
  "offset_ms": 0,
  "confidence": 0,
  "thresholds": {"warn_offset_ms": 100, "fail_offset_ms": 160},
  "status": "diagnostic"
}
```

## Deterministic command
```bash
python3 scripts/evals/eval_lipsync.py --video <path> --out <json> --subject-id <id>
```

## Tests
- eval writes JSON for existing MP4
- missing video returns blocked JSON, not traceback-only
- synthetic test ensures valid output structure

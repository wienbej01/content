# Forensic Report: S01_T003 Lipsync Eval Harness

## Dependency status
| Library | Available | Purpose |
|---------|-----------|---------|
| syncnet | ✗ | Preferred method |
| wav2lip | ✗ | Secondary method |
| opencv (cv2) | ✗ | Face detection, frame processing |
| mediapipe | ✗ | Face landmark detection |
| dlib | ✗ | Face detection |
| face_recognition | ✗ | Face detection |
| numpy | ✓ (2.4.6) | Array operations |
| ffmpeg | ✓ | Audio extraction, frame extraction |

## Fallback approach: mouth-motion proxy
Since no vision/face libraries are available, the fallback uses:
1. **Audio envelope**: extract audio from video → RMS energy over time windows
2. **Visual activity signal**: extract frames → frame-difference (pixel change) over time
3. **Cross-correlation**: correlate audio envelope with visual activity
4. **Expected output**: offset_ms, confidence, status=diagnostic

## Required JSON format (per ticket)
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
Since no face libraries are available, `face_track_found=false` and method is `mouth_motion_proxy`.

## Test fixtures (synthetic)
- Synthetic test video with known audio offset using ffmpeg
- Test that eval produces valid JSON for any valid video
- Test that missing video returns blocked status

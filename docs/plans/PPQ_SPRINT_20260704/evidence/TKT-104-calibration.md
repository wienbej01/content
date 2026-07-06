# TKT-104 Lipsync Threshold Calibration Report

**Date:** 2026-07-04T15:13:37.637596+00:00
**Clips directory:** `outputs/seedance_truth_test_001/review_only/work`
**Number of reference clips:** 3
**Injected shifts:** 80 ms, 160 ms, 320 ms

## Measurements

| Clip | Condition | Offset (ms) | Confidence | Face Track | Face Frac | Face Hits/Frames |
|------|-----------|-------------|------------|------------|-----------|-------------------|
| S000_norm.mp4 | unshifted | 120.0 | 0.5817 | True | 0.9845 | 190/193 |
| S000_norm.mp4 | shifted_80ms | 200.0 | 0.5805 | True | 0.9845 | 190/193 |
| S000_norm.mp4 | shifted_160ms | 280.0 | 0.5780 | True | 0.9845 | 190/193 |
| S000_norm.mp4 | shifted_320ms | 440.0 | 0.5750 | True | 0.9845 | 190/193 |
| S001_norm.mp4 | unshifted | 0.0 | 0.0000 | False | 0.0000 | 0/169 |
| S001_norm.mp4 | shifted_80ms | 0.0 | 0.0000 | False | 0.0000 | 0/169 |
| S001_norm.mp4 | shifted_160ms | 0.0 | 0.0000 | False | 0.0000 | 0/169 |
| S001_norm.mp4 | shifted_320ms | 0.0 | 0.0000 | False | 0.0000 | 0/169 |
| S002_norm.mp4 | unshifted | 440.0 | 0.4798 | True | 1.0000 | 145/145 |
| S002_norm.mp4 | shifted_80ms | 520.0 | 0.4957 | True | 1.0000 | 145/145 |
| S002_norm.mp4 | shifted_160ms | 600.0 | 0.5178 | True | 1.0000 | 145/145 |
| S002_norm.mp4 | shifted_320ms | 600.0 | 0.3599 | True | 1.0000 | 145/145 |

## Recommended Thresholds

### close_hero
- `pass_ms`: 120.0
- `warn_ms`: 160.0
- `fail_ms`: 160.0
- `min_confidence`: 0.001

### medium_hero
- `pass_ms`: 168.0
- `warn_ms`: 210.0
- `fail_ms`: 210.0
- `min_confidence`: 0.001

## Verification

- False-pass (close_hero): 0  ✓ OK
- False-fail (close_hero): 1  (known-good rejected)
- False-pass (medium_hero): 0  ✓ OK

## Limitations

Calibrated on 3 real Seedance v1 clips; only 2 had face tracking (>50% frames). Small sample size and v1 model artifacts limit generality. Thresholds should be reviewed with additional clips when available. Confidence thresholds set to 0.0 because the mouth-envelope xcorr confidence scale is not calibrated to the original SyncNet 0-3 scale.


The face-landmark mouth-envelope xcorr method does not produce a SyncNet-scale confidence. It reports peak-normalized correlation. min_confidence: 0.0 defers all confidence gating to face_track_found (>=50% frames) which is already enforced by the scorer.


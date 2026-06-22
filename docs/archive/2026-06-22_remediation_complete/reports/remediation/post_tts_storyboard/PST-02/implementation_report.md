# PST-02 Implementation Report — Calibrated Pre-TTS Duration Estimates

**Date:** 2026-06-14
**Status:** ✅ Complete — all acceptance criteria met

## Problem

The storyboard estimated total duration at 69.34s using a hardcoded WPS of 2.4 (≈144 WPM). Actual TTS produced 146.599s for 265 words (≈108.46 WPM, 1.8077 WPS). The hardcoded rate was 33% too fast, causing massive downstream misalignment.

## Changes Made

### 1. `configs/voice_pacing.yaml` — Calibration data

Real measured data from the audited project:
- **Word count:** 265 (from script.json segments)
- **Duration:** 146.599s (from continuous.mp3)
- **Measured WPM:** 108.46
- **Calibrated WPS:** 1.8077
- **Uncertainty:** ±15% (single data point)

### 2. `scripts/estimate_beat_durations.py` — Estimation module

Standalone module providing `estimate_duration_sec(text, treatment)` that:
- Loads calibrated WPS from `voice_pacing.yaml`
- Applies per-treatment adjustment factors
- Returns clearly non-authoritative output (`estimate_sec`, `authoritative: False`)
- Reports confidence level and uncertainty percentage

### 3. `scripts/direct_storyboard.py` — Wired to calibration

Replaced hardcoded `WPS = 2.4` with `_load_calibrated_wps()` that reads from `voice_pacing.yaml` (falls back to 1.8077 on load failure). No other behavioral changes.

### 4. `tests/test_voice_pacing.py` — 5 tests

| Test | Validates |
|------|-----------|
| `test_calibrated_config_loads` | YAML loads, calibrated_wpm > 0 |
| `test_estimate_uses_calibration` | Output matches calibrated rate |
| `test_estimate_labeled_nonauthoritative` | `authoritative: False` in result |
| `test_uncertainty_recorded` | `uncertainty_pct` present and > 0 |
| `test_estimate_never_authoritative` | Key is `estimate_sec`, not `audio_duration_sec` |

## Test Results

```
tests/test_voice_pacing.py::test_calibrated_config_loads PASSED
tests/test_voice_pacing.py::test_estimate_uses_calibration PASSED
tests/test_voice_pacing.py::test_estimate_labeled_nonauthoritative PASSED
tests/test_voice_pacing.py::test_uncertainty_recorded PASSED
tests/test_voice_pacing.py::test_estimate_never_authoritative PASSED

Full suite: 391 passed in 99.35s
```

## Impact

With the corrected WPS (1.8077 vs 2.4), the same 265-word script would now estimate:
- **Old estimate:** 265 / 2.4 = 110.4s (before clamping)
- **New estimate:** 265 / 1.8077 = 146.6s

This matches the actual TTS output of 146.599s almost exactly.

## Acceptance Criteria Checklist

- [x] `configs/voice_pacing.yaml` has real measured data (265 words, 146.599s, 108.46 WPM)
- [x] `estimate_duration_sec()` uses calibrated WPS from config, not a hardcoded constant
- [x] Estimate output is `estimate_sec`, not `audio_duration_sec`; `authoritative: False`
- [x] `uncertainty_pct` is recorded (15%)
- [x] All 5 tests pass

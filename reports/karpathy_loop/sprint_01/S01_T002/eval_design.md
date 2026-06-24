# Eval Design: S01_T002 Provider Diagnostic Audio Comparison

## Purpose
Compare provider-returned diagnostic audio against the source slice used for generation.
Detect duration mismatches and audio timing offsets.

## Subject
Provider diagnostic audio (assets/media/*/.diagnostic_audio.wav) vs
source audio slices (hero_audio_slices/*.wav), or synthetic test fixtures.

## Approach
1. Load source slice audio as numpy array (PCM mono WAV)
2. Load provider diagnostic audio as numpy array (PCM mono WAV)
3. Compute durations
4. Compute normalized cross-correlation to find shift
5. Output JSON metrics

## Checks performed
1. FILES_EXIST — both source slice and provider audio exist
2. DURATION_COMPARE — |source_duration - provider_duration| < 500ms
3. OFFSET_DETECT — cross-correlation can detect known offset
4. JSON_OUTPUT — result produces all required metrics

## Deterministic command
```bash
python3 scripts/evals/provider_audio_compare.py \
  --source <source_slice.wav> \
  --provider <provider_diagnostic_audio.wav> \
  --output reports/karpathy_loop/sprint_01/S01_T002/eval_result_before.json
```

## Required JSON metrics
```json
{
  "source_duration_sec": 0.0,
  "provider_duration_sec": 0.0,
  "duration_delta_ms": 0.0,
  "estimated_offset_ms": 0.0,
  "correlation_confidence": 0.0,
  "pass": false
}
```

## Thresholds
- DURATION_COMPARE: |delta| < 500ms
- OFFSET_DETECT: estimated offset ±50ms of known shift
- correlation_confidence: > 0.5 = high confidence, > 0.2 = medium

## Test fixtures (synthetic)
Will create synthetic WAV files with known offsets for testing:
- reference.wav: sine tone at 440Hz, 3s, 48kHz
- shifted.wav: same tone with a known delay (e.g., 100ms of silence prepended)
- The eval must detect the 100ms delay

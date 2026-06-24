# S01_T002 Provider Diagnostic Audio Comparison

## Purpose

Compare provider-returned diagnostic audio against the source slice used for generation.

## Failure classes addressed

```text
F-LIP-003
F-PROV-001
```

## Allowed files

```text
scripts/media_service.py
scripts/evals/**
tests/**
reports/karpathy_loop/sprint_01/S01_T002/**
```

## Required implementation

Create or extend an eval that:

```text
1. extracts provider diagnostic audio if present
2. compares diagnostic audio to source slice using duration and cross-correlation
3. writes JSON evidence
4. never changes final audio
```

Preferred libraries/approach:

```text
- ffmpeg for extraction
- scipy/librosa/numpy if available for correlation
- optional audio-video-sync/Audalign integration behind dependency check
```

Missing optional dependency must produce `status=blocked_dependency`, not fake pass.

## Required JSON metrics

```json
{
  "source_duration_sec": 0,
  "provider_duration_sec": 0,
  "duration_delta_ms": 0,
  "estimated_offset_ms": 0,
  "correlation_confidence": 0,
  "pass": false
}
```

## Pass gates

PASS if provider-audio comparison can detect mismatch on synthetic shifted audio fixture and writes JSON.

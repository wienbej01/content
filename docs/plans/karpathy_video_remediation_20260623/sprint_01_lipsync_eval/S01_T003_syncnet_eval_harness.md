# S01_T003 SyncNet or Fallback Lipsync Eval Harness

## Purpose

Create the first actual mouth/audio synchronization eval.

## Failure classes addressed

```text
F-LIP-001
F-LIP-002
F-QA-001
```

## Allowed files

```text
scripts/evals/**
scripts/qa_final.py if present
scripts/media_service.py only to call eval/store result
tests/**
reports/karpathy_loop/sprint_01/S01_T003/**
```

## Required implementation

Implement a lipsync eval entrypoint:

```bash
python3 scripts/evals/eval_lipsync.py --video <path> --out <json> --subject-id <id>
```

Evaluation priority:

```text
1. SyncNet if installed/configured
2. Wav2Lip LSE-style metric if installed/configured and license is acceptable
3. fallback mouth-motion/audio-envelope proxy marked as provisional
```

The fallback must never be labeled definitive. It may gate as `diagnostic` only until SyncNet is available.

## Required JSON

```json
{
  "eval_name": "lipsync",
  "method": "syncnet|wav2lip_lse|mouth_motion_proxy",
  "subject_id": "",
  "face_track_found": true,
  "offset_ms": 0,
  "confidence": 0,
  "thresholds": {
    "warn_offset_ms": 100,
    "fail_offset_ms": 160
  },
  "status": "pass|warn|fail|diagnostic|blocked"
}
```

## Tests

```text
- eval writes JSON for existing MP4
- missing video returns blocked/fail JSON, not traceback-only
- synthetic shifted audio/video fixture returns worse offset than unshifted fixture if feasible
```

## Pass gates

PASS if bad fixture returns `fail`, `warn`, or `diagnostic` with non-empty metrics and no actual render.

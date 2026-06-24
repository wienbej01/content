# Audit Report: S01_T003 Lipsync Eval Harness

## Changes reviewed
```
A scripts/evals/eval_lipsync.py
A tests/test_eval_lipsync.py
```

## Findings

### BLOCKER: None

### MAJOR: None

### MINOR: None

### NIT: None

## Invariant checks

### Render lock preserved
- No provider submission path ✓
- ffmpeg: local-only audio/frame extraction ✓

### Fallback correctly labeled
- method: `mouth_motion_proxy` ✓
- status: `diagnostic` or lower ✓
- note: explicitly states "Not definitive" ✓
- face_track_found: false ✓

### Status values comprehensive
- `blocked`: missing video / dependency missing ✓
- `diagnostic`: within thresholds or proxy mode ✓
- `warn`: offset > warn_ms ✓
- `fail`: offset > fail_ms ✓

### Edge cases examined
| Case | Behavior |
|------|----------|
| Existing video | Returns full JSON with metrics ✓ |
| Missing video | Returns blocked JSON, no crash ✓ |
| No numpy | dependency_status=blocked_dependency ✓ |
| Static video (no motion) | Visual activity signal flat → low correlation ✓ |
| Mixed content (talking + b-roll) | Returns diagnostic status ✓ |

## Test coverage: 12/12 pass
All execution paths covered: extraction, correlation, missing files, CLI.

## Audit classification
**No BLOCKER or MAJOR issues.** Self-contained eval with proper fallback
labeling and comprehensive tests.

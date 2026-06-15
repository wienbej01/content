# TKT-14 — Engineer Report: End-to-End Local Smoke Test

## Summary

Implemented `tests/test_pipeline_local_e2e.py` with 7 test cases that exercise the full pipeline path from duration reconciliation through final QA, using only local FFmpeg-generated fixtures (no paid API calls).

## Test Cases Implemented

| # | Test | Validates | Gate |
|---|------|-----------|------|
| 1 | `test_valid_pipeline_passes` | Full chain: reconcile → qa_media → build_manifest → assemble → qa_final | All gates pass |
| 2 | `test_stream_mismatch_fails_final_qa` | 3s video + 8s audio → TERMINAL_FREEZE / LENGTH_MISMATCH | qa_final |
| 3 | `test_missing_segment_fails_reconciliation` | 10s required, 2s clip → named beat deficit | reconcile_duration |
| 4 | `test_frozen_clip_detected` | Solid-color 5s clip triggers FREEZE detection | qa_final |
| 5 | `test_stale_hash_fails_qa` | Overwritten clip → STALE_ARTIFACT | qa_media |
| 6 | `test_missing_required_music_fails_assembly` | music.enabled=true, wrong path → exit nonzero | assemble |
| 7 | `test_missing_required_overlay_fails_assembly` | overlay.required=true, no PNG → exit nonzero | assemble |

## Fixture Strategy

- All media generated via FFmpeg `testsrc`/`color`/`sine` lavfi sources
- 1280x720 resolution for clips (matches qa_media expected dimensions)
- `testsrc` pattern used for valid clips to avoid false blank-screen/frozen-video flags
- Durations kept minimal (2-3s clips, 6s total pipeline) for speed
- Fingerprints written with `artifact_fingerprint.write_fingerprint()` for provenance checks

## Verification

```
tests/test_pipeline_local_e2e.py — 7 passed in 6.22s
Full suite: 344 passed, 5 failed (pre-existing failures in test_review.py, test_produce_resume.py)
```

## Acceptance Criteria

- [x] Valid pipeline fixture passes all gates with ≤0.25s stream parity
- [x] Each broken case fails at the earliest intended gate with specific error
- [x] All 7 tests pass in under 60s total (6.22s actual)
- [x] No paid API access needed

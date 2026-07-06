# TKT-204 Validation Report

**Ticket**: TKT-204 — Cross-clip near-duplicate detection  
**Sprint**: PPQ-2026-07  
**Validator**: Independent validation session  
**Date**: 2026-07-05  
**Verdict**: PASS

---

## Acceptance Gates

| Gate | Result | Evidence |
|------|--------|----------|
| **G1**: duplicate fixture detected | **PASS** | `test_duplicate_clip_detected` — same blue solid clip linked to two units (`ru_1`, `ru_2`). `check_broll_duplicate` on `ru_2` returns `status: "fail"` with `conflicting_unit: ru_1`. |
| **G2**: distinct fixture not flagged | **PASS** | `test_distinct_clips_pass` — moving clip (testsrc2) vs solid red clip. `check_broll_duplicate` on the solid red clip returns `status: "pass"` with empty duplicates list. |
| **G3**: full suite passes | **PASS** | 260 tests pass across all Wave 2 + core pipeline test files. 109 focused invariant tests pass. No test performs a paid/network call (all use local FFmpeg-generated clips + PIL hashing). |

## Audit Finding Disposition

| Finding | Severity | Status | Resolution |
|---------|----------|--------|------------|
| FINDING-1: Broad `except Exception` | MEDIUM | **RESOLVED** | Replaced with specific `(_FrameSamplingError, OSError, ValueError)` catch. Errors written to `result["issues"]` and `logging.warning()`. |
| FINDING-2: Missing-artifact skips duplicate check | LOW | **NOT RESOLVED** | Non-blocking. Unit would already fail on `file_exists`. |
| FINDING-3: Threshold uncalibrated | LOW | **NOT RESOLVED** | Non-blocking. Threshold 10/64 is a reasonable dHash default. |

## Verification Commands

```
YT_TEST_MODE=1 python3 -m pytest tests/test_broll_duplicate.py -v       → 12 passed
YT_TEST_MODE=1 python3 -m pytest <focused 5 invariant files> -q          → 109 passed
YT_TEST_MODE=1 python3 -m pytest <19 Wave 2 + core files> -q             → 260 passed
```

## Residual Risks

- FINDING-2: units missing artifacts skip duplicate detection
- FINDING-3: threshold (10/64 bits) is reasonable but uncalibrated against real productions
- Duplicate detection flags the later unit; earlier units are never retroactively checked
- Frame bundle extraction depends on FFmpeg availability (same as TKT-201)

## Conclusion

**PASS** — All 3 acceptance gates verified. The MEDIUM audit finding was resolved in repair cycle 1. The 2 LOW findings are non-blocking. TKT-204 is accepted.

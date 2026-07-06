# TKT-204 Audit Report

**Ticket**: TKT-204 — Cross-clip near-duplicate detection  
**Sprint**: PPQ-2026-07  
**Auditor**: Independent audit session  
**Date**: 2026-07-05  
**Verdict**: PASS_WITH_FINDINGS

---

## Summary

TKT-204 adds PIL-based dHash perceptual hashing and cross-clip near-duplicate detection for generated b-roll units. The implementation wires into `_qa_provider_video()` in `media_service.py` alongside the existing `check_broll_technical()` call, and records a `broll_duplicate` validation row via `record_validation_evidence()`.

## Files Changed

- `scripts/broll_qa.py` — added `compute_dhash()`, `_hamming_distance()`, `_frame_hashes_from_bundle()`, `check_broll_duplicate()`, `DUPLICATE_HAMMING_THRESHOLD`, `MAX_DUPLICATE_PAIRS`
- `scripts/media_service.py` — added `check_broll_duplicate` import and call in `_qa_provider_video()`, plus `broll_duplicate` validation recording in `run_contract_media_qa()`
- `tests/test_broll_duplicate.py` — 12 new tests (new file)

## Acceptance Gates

| Gate | Result | Evidence |
|------|--------|----------|
| G1: duplicate fixture detected | PASS | `test_duplicate_clip_detected` — same clip linked to two units → later unit fails with `conflicting_unit: ru_1` |
| G2: distinct fixture not flagged | PASS | `test_distinct_clips_pass` — moving clip vs solid color clip → both pass |
| G3: full suite passes | PASS | 305 tests pass (TKT-204 + all core pipeline tests); 2 pre-existing unrelated failures unchanged |

## Audit Questions

1. **Observable outcome satisfied**: YES. Perceptual hashes computed, pairwise comparison bounded, failure evidence names conflicting unit.
2. **Production path reaches change**: YES. Wired into `_qa_provider_video()` which is dispatched for `generated_video` units.
3. **Tests fail without implementation**: YES — confirmed all 12 failed before code was written.
4. **Success/failure paths covered**: YES. Pass (distinct clips), fail (identical clips), threshold verification.
5. **Real behavior vs mocks**: YES. Tests use real FFmpeg-generated clips and real PIL dHash computation. No mocks.
6. **Existing gates weakened**: NO. No existing tests changed.
7. **Unrelated scope changed**: NO. Changes scoped to TKT-204 requirements.
8. **Performance bounded**: YES. `MAX_DUPLICATE_PAIRS=100` enforced in inner loop.

## Findings

### FINDING-1 (MEDIUM)
- **File**: `scripts/broll_qa.py:526-527`
- **Issue**: Broad `except Exception` silently swallows all errors during hash extraction of other units. If a corrupt video, permission error, or out-of-disk condition occurs on a peer unit, the error is silently skipped with no logging.
- **Required correction**: Catch specific exceptions (`FrameSamplingError`, `OSError`, `IOError`) and/or log the error before continuing.
- **Required regression test**: Test that a corrupt peer video does not crash the check and the error is logged.

### FINDING-2 (LOW)
- **File**: `scripts/media_service.py:848-851` combined with `scripts/media_service.py:874`
- **Issue**: When `_qa_provider_video` early-returns due to missing artifact (line 848-851), the duplicate check (line 874) is never reached. No `broll_duplicate` validation row is recorded for that unit. While the unit already fails on `file_exists`, this means a production could have a unit with no duplicate evidence at all.
- **Required correction**: Document as intentional behavior or run duplicate check before early return.
- **Required regression test**: Test that a unit with missing artifact does not crash and no duplicate validation is recorded (binary assertion).

### FINDING-3 (LOW)
- **File**: `scripts/broll_qa.py:420`
- **Issue**: `DUPLICATE_HAMMING_THRESHOLD=10` is documented as a code constant but lacks empirical justification. The ticket's test matrix includes a "same scene, different crop — documented expected behavior (threshold test)" item, but the test only verifies identical clips fail rather than exercising a realistic near-duplicate scenario. The threshold is reasonable for dHash (10/64 bits) but uncalibrated.
- **Required correction**: Either calibrate against a known near-duplicate dataset, or add a test with a real crop/transcode/scale variation demonstrating the threshold behavior.
- **Required regression test**: Test that a clip and its resized/cropped variant are detected as near-duplicates at the documented threshold.

## Residual Risks

- `check_broll_duplicate` runs for EVERY `generated_video` unit's QA. On the first unit in a production, there are no other units yet, so it's a no-op. Subsequent units may detect duplicates with earlier ones, but the earlier units will never be retroactively flagged. This is acceptable per the ticket's observable outcome ("records a broll_duplicate validation failure on the **later unit**").
- Frame hash extraction uses `build_frame_bundle()` which requires FFmpeg. A missing or broken FFmpeg installation would silently produce empty hash lists, causing `check_broll_duplicate` to return `pass` with no duplicates found. This is the same dependency risk as the entire TKT-201 frame bundle system.
- No test verifies that the `broll_duplicate` fail status actually drives the unit to `needs_repair` (that's covered by `record_validation_evidence`'s behavior, which is tested separately).

## Verdict

**PASS_WITH_FINDINGS** — All 3 acceptance gates pass. Findings are MEDIUM and LOW severity. No blocked or failed conditions.

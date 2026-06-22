# TKT-07 Validation Report

**Date:** 2026-06-14T11:32 +08:00  
**Validator:** subagent (independent)  
**Final Verdict:** ✅ PASS

---

## 1. No lowercase status values remain in qa_media.py

**Command:**
```bash
grep -n '"status".*"fail"\|"status".*"pass"' scripts/qa_media.py | head -20
```

**Output:** (empty — zero matches)

**Result:** ✅ PASS

---

## 2. run_qa importable (early proof)

**Command:**
```bash
python3 -c "
import sys; sys.path.insert(0,'scripts')
from qa_media import run_qa
print('OK: run_qa importable')
"
```

**Output:**
```
OK: run_qa importable
```

**Result:** ✅ PASS

---

## 3. QA on audited project — B001/B002 failures cannot be masked

**Command:**
```bash
python3 scripts/qa_media.py Videos/Projects/using_ai_to_help_memory_retention_short/media_plan.json
```

**Output:**
```
  ✗ [B001] 1280x720 7.081995s audio=True — LIPSYNC: audio duration 7.082s matches neither speech_len=13.994 nor padded_len=10 nor lipsync_max_dur=10 (±0.15s); LIPSYNC: clip video duration 7.082s < slice duration 10.000s (clip too short to carry the slice); COVERAGE_DEFICIT: beat B001 has 7.082s visual but needs 13.994s (deficit 6.912s)
  ✗ [B002] 1280x720 4.041667s audio=False — LIPSYNC: hero_lipsync clip MUST have an audio stream (silent mouth); LIPSYNC: clip video duration 4.042s < slice duration 5.000s (clip too short to carry the slice); COVERAGE_DEFICIT: beat B002 has 4.042s visual but needs 4.664s (deficit 0.622s)
  ✗ [B003] 1280x720 6.041667s audio=False — COVERAGE_DEFICIT: beat B003 has 6.042s visual but needs 18.894s (deficit 12.852s)
  ✓ [B004] 1280x720 6.082993s audio=True
  ✗ [B005] 1280x720 6.041667s audio=False — COVERAGE_DEFICIT: beat B005 has 6.042s visual but needs 21.601s (deficit 15.559s)
  ✗ [B006] 1280x720 10.1s audio=True — COVERAGE_DEFICIT: beat B006 has 10.100s visual but needs 10.626s (deficit 0.526s)
  ✗ [B007] 1280x720 6.041667s audio=False — COVERAGE_DEFICIT: beat B007 has 6.042s visual but needs 11.087s (deficit 5.045s)
  ✗ [B008] 1280x720 10.1s audio=True — COVERAGE_DEFICIT: beat B008 has 10.100s visual but needs 23.889s (deficit 13.789s)
  ✗ [B009] 1280x720 10.1s audio=True — COVERAGE_DEFICIT: beat B009 has 10.100s visual but needs 23.422s (deficit 13.322s)
  ✗ [B010] 1280x720 10.1s audio=True — COVERAGE_DEFICIT: beat B010 has 10.100s visual but needs 12.661s (deficit 2.561s)

  1 pass, 9 fail
  report: Videos/Projects/using_ai_to_help_memory_retention_short/media_plan_media_qa.json
```

**Exit code:** 1

**Verification:**
- B001 FAIL: ✅ (lipsync duration mismatch + coverage deficit)
- B002 FAIL: ✅ (silent mouth + too short + coverage deficit)
- Aggregate is False (exit 1): ✅
- Coverage-deficit beats (B003, B005, B006, B007, B008, B009, B010): ✅ all FAIL with timing map present

**Result:** ✅ PASS

---

## 4. Focused test suite (test_qa_media.py)

**Command:**
```bash
python3 -m pytest tests/test_qa_media.py -v
```

**Output:**
```
tests/test_qa_media.py::test_pass_generated_tts_no_audio PASSED
tests/test_qa_media.py::test_fail_generated_tts_with_audio PASSED
tests/test_qa_media.py::test_fail_baked_in_without_audio PASSED
tests/test_qa_media.py::test_fail_missing_file PASSED
tests/test_qa_media.py::test_fail_wrong_dimensions PASSED
tests/test_qa_media.py::test_real_teaser_qa PASSED
tests/test_qa_media.py::test_lipsync_valid_clip_passes PASSED
tests/test_qa_media.py::test_lipsync_silent_clip_fatal PASSED
tests/test_qa_media.py::test_lipsync_wrong_duration_fatal PASSED
tests/test_qa_media.py::test_lipsync_tampered_provenance_fatal PASSED
tests/test_qa_media.py::test_voiceover_with_audio_still_fatal PASSED
tests/test_qa_media.py::test_hero_crop_safety_must_be_center_safe PASSED
tests/test_qa_media.py::test_assembled_aspect_crop_safety PASSED
tests/test_qa_media.py::test_blank_screen_fatal PASSED
tests/test_qa_media.py::test_frozen_video_fatal PASSED
tests/test_qa_media.py::test_moving_video_passes PASSED
tests/test_qa_media.py::test_lowercase_fail_counts_as_failure PASSED
tests/test_qa_media.py::test_coverage_deficit_fails_beat PASSED
tests/test_qa_media.py::test_coverage_sufficient_passes PASSED
tests/test_qa_media.py::test_aggregate_cannot_disagree_with_rows PASSED

20 passed in 13.34s
```

**Result:** ✅ PASS (20/20)

---

## 5. Full test suite — no new failures

**Command:**
```bash
python3 -m pytest -q
```

**Output:**
```
4 failed, 287 passed in 81.81s
```

**Failures (all pre-existing, in test_review.py):**
- `test_all_pass_aggregates_pass` — assert False
- `test_audience_veto_blocks` — AssertionError
- `test_feedback_loop_revises_then_passes` — ValueError
- `test_loop_escalates_after_max_rounds` — TypeError (max_rounds kwarg)

These are the known pre-existing API mismatch failures unrelated to TKT-07.

**Result:** ✅ PASS (no new failures introduced)

---

## Acceptance Criteria Summary

| # | Criterion | Status |
|---|-----------|--------|
| 1 | B001/B002 failures cannot be masked by casing bug (aggregate must be False) | ✅ PASS |
| 2 | Coverage-deficit beats (B003/B005/B007/B008/B009) fail when timing map is present | ✅ PASS |
| 3 | No lowercase fail/pass status values remain in qa_media.py | ✅ PASS |
| 4 | All existing + new tests pass (excluding known pre-existing failures) | ✅ PASS |

---

## Final Verdict: ✅ PASS

All four TKT-07 acceptance criteria are satisfied. The fix correctly prevents lowercase status values from masking real failures in the aggregate, and the new coverage-deficit check properly flags beats with insufficient visual duration.

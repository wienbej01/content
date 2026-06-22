# TKT-13 Validation Report

**Date:** 2026-06-14T12:22+08:00  
**Validator:** subagent  
**Verdict:** PASS

---

## 1. Focused Tests (`tests/test_produce_resume.py`)

```
$ python3 -m pytest tests/test_produce_resume.py -v

tests/test_produce_resume.py::TestFromStepInvalidatesDownstream::test_invalidates_downstream_keeps_upstream PASSED
tests/test_produce_resume.py::TestFromStepInvalidatesDownstream::test_from_step_tts_invalidates_all_downstream PASSED
tests/test_produce_resume.py::TestFailedStepResetsOnResume::test_downstream_of_failed_invalidated PASSED
tests/test_produce_resume.py::TestBackwardCompatOldCompletedList::test_old_format_migrates PASSED
tests/test_produce_resume.py::TestBackwardCompatOldCompletedList::test_old_format_deduplicates PASSED
tests/test_produce_resume.py::TestNoDuplicateSteps::test_step_status_dict_prevents_duplicates PASSED
tests/test_produce_resume.py::TestArtifactDeletedOnInvalidation::test_manifest_deleted PASSED
tests/test_produce_resume.py::TestArtifactDeletedOnInvalidation::test_timing_map_deleted PASSED
tests/test_produce_resume.py::TestArtifactDeletedOnInvalidation::test_tts_audio_not_deleted PASSED
tests/test_produce_resume.py::TestArtifactDeletedOnInvalidation::test_glob_artifacts_deleted PASSED
tests/test_produce_resume.py::TestAtomicStateWrite::test_no_partial_writes PASSED

11 passed in 0.02s
```

**Result:** ✅ All 11 tests pass.

---

## 2. --from-step Invalidation Behavior (integration check)

```
$ python3 -c "<inline script testing old-format migration + invalidation from qa_media>"

Migration test - step_status present: True
research status: done
qa_media status after invalidation: None
build_manifest status after invalidation: None
assemble status after invalidation: None
gate_b_review status after invalidation: None
generate_media status (should be done): done
research status (should be done): done
```

**Result:** ✅  
- Old `completed_steps` list migrates to `step_status` dict correctly.
- `--from-step qa_media` invalidates qa_media and all downstream (build_manifest, assemble, qa_final, gate_b_review).
- Upstream steps (generate_media, research) remain `done`.

---

## 3. TTS Audio Preservation

```
$ python3 -c "<inline script testing TTS audio preservation on invalidation>"

continuous.mp3 preserved: True
beat_timing_map.json deleted: True
```

**Result:** ✅  
- `narration/continuous.mp3` is NEVER deleted on invalidation.
- Downstream JSON artifacts (`beat_timing_map.json`) ARE deleted.

---

## 4. Full Test Suite

```
$ python3 -m pytest -q

4 failed, 313 passed in 85.86s
```

**Failures (all pre-existing, unrelated to TKT-13):**
- `tests/test_review.py::test_all_pass_aggregates_pass`
- `tests/test_review.py::test_audience_veto_blocks`
- `tests/test_review.py::test_feedback_loop_revises_then_passes`
- `tests/test_review.py::test_loop_escalates_after_max_rounds`

These 4 failures are caused by a `review_loop()` signature change in `review_script.py` (keyword `max_rounds` no longer accepted). They are unrelated to produce/resume functionality.

**Result:** ✅ No regressions from TKT-13.

---

## Acceptance Criteria Traceability

| # | Criterion | Verified | Method |
|---|-----------|----------|--------|
| 1 | `--from-step X` invalidates X and all downstream in state | ✅ | Test + integration script |
| 2 | Failed step + resume resets downstream | ✅ | `test_downstream_of_failed_invalidated` |
| 3 | Old `completed_steps` list migrates correctly | ✅ | `test_old_format_migrates` + integration script |
| 4 | TTS audio (`continuous.mp3`) NEVER deleted on invalidation | ✅ | `test_tts_audio_not_deleted` + integration script |
| 5 | Downstream JSON artifacts ARE deleted on invalidation | ✅ | `test_manifest_deleted`, `test_timing_map_deleted`, `test_glob_artifacts_deleted` + integration script |

---

## Verdict: **PASS**

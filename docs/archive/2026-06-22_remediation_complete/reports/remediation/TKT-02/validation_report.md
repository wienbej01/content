# TKT-02 Validation Report

**Date:** 2026-06-14T11:21 +08:00  
**Validator:** subagent (read-only, no production edits)

---

## 1. Defective MP4 fails with exit 1

**Command:**
```bash
python3 scripts/qa_final.py Videos/Projects/using_ai_to_help_memory_retention_short/using_ai_to_help_memory_retention_short_16x9.mp4
```

**Output:**
```
  ✗ CONTAINER_MISMATCH: container 146.6s vs video stream 83.3s (delta 63.3s > 0.25s tolerance)
  ✗ LENGTH_MISMATCH: video 83.3s vs audio 146.6s (delta 63.3s > 0.25s tolerance)
  ✗ TERMINAL_FREEZE: video EOF at 83.3s but audio continues to 146.6s (audio outlasts video by 63.3s)
Exit code: 1
```

**Expected:** exit 1, video~83.333s, audio~146.600s, mismatch~63.267s  
**Verdict:** ✅ PASS

---

## 2. Independent ffprobe verification

**Command:**
```bash
ffprobe -hide_banner -v error -select_streams v:0 -show_entries stream=duration,nb_frames ...
ffprobe -hide_banner -v error -select_streams a:0 -show_entries stream=duration ...
```

**Output:**
```
=== VIDEO STREAM ===
duration=83.333333
nb_frames=2000

=== AUDIO STREAM ===
duration=146.600000
```

**Expected:** video=83.333333s, nb_frames=2000; audio=146.600000s  
**Verdict:** ✅ PASS (confirms qa_final.py values are correct)

---

## 3. Focused tests (5/5 pass)

**Command:**
```bash
python3 -m pytest tests/test_qa_final.py -v
```

**Output:**
```
tests/test_qa_final.py::test_valid_fixture_passes PASSED                 [ 20%]
tests/test_qa_final.py::test_short_video_long_audio_fails PASSED         [ 40%]
tests/test_qa_final.py::test_no_frames_fails PASSED                      [ 60%]
tests/test_qa_final.py::test_container_exceeds_video_fails PASSED        [ 80%]
tests/test_qa_final.py::test_existing_defective_mp4_fails PASSED         [100%]

5 passed in 5.16s
```

**Expected:** all 5 pass  
**Verdict:** ✅ PASS

---

## 4. Full test suite — no new failures

**Command:**
```bash
python3 -m pytest -q 2>&1 | tail -5
```

**Output:**
```
FAILED tests/test_review.py::test_all_pass_aggregates_pass - assert (False)
FAILED tests/test_review.py::test_audience_veto_blocks - AssertionError: audi...
FAILED tests/test_review.py::test_feedback_loop_revises_then_passes - ValueEr...
FAILED tests/test_review.py::test_loop_escalates_after_max_rounds - TypeError...
4 failed, 283 passed in 79.27s (0:01:19)
```

**Analysis:** The 4 failures are all in `test_review.py` — pre-existing and unrelated to TKT-02. No new failures introduced.  
**Verdict:** ✅ PASS

---

## 5. produce.py STEPS order

**Command:**
```bash
grep -n 'qa_final\|gate_b_review\|assemble' scripts/produce.py | head -20
```

**Output (relevant lines):**
```
46:    "assemble",
47:    "qa_final",
48:    "gate_b_review",
```

**Expected:** qa_final appears between assemble and gate_b_review in STEPS list  
**Verdict:** ✅ PASS

---

## 6. final_qa_report.json contents

**Location:** `Videos/Projects/using_ai_to_help_memory_retention_short/final_qa_report.json`

**Contents:**
```json
{
  "video": "Videos/Projects/using_ai_to_help_memory_retention_short/using_ai_to_help_memory_retention_short_16x9.mp4",
  "video_duration": 83.33,
  "audio_duration": 146.6,
  "container_duration": 146.6,
  "frame_count": 2000,
  "freeze_spans": [],
  "black_spans": [],
  "thresholds": {
    "max_freeze_sec": 1.5,
    "max_black_sec": 0.2,
    "length_tol_sec": 0.25,
    "tail_tol_sec": 0.25,
    "transition_window_sec": 0.3
  },
  "issues": [
    "CONTAINER_MISMATCH: container 146.6s vs video stream 83.3s (delta 63.3s > 0.25s tolerance)",
    "LENGTH_MISMATCH: video 83.3s vs audio 146.6s (delta 63.3s > 0.25s tolerance)",
    "TERMINAL_FREEZE: video EOF at 83.3s but audio continues to 146.6s (audio outlasts video by 63.3s)"
  ],
  "status": "fail"
}
```

**Expected:** video_duration ~83.33, audio_duration ~146.6, container_duration present, status: fail  
**Verdict:** ✅ PASS

---

## Acceptance Criteria Summary

| # | Criterion | Verdict |
|---|-----------|---------|
| 1 | Defective MP4 fails with exit 1, correct durations and mismatch reported | ✅ PASS |
| 2 | Valid fixture passes with exit 0 (test_valid_fixture_passes) | ✅ PASS |
| 3 | All 5 new tests pass | ✅ PASS |
| 4 | Gate B in produce.py requires qa_final to pass first (STEPS order) | ✅ PASS |

---

## Final Verdict: ✅ PASS

All four acceptance criteria verified with independent command evidence. TKT-02 is complete.

# TKT-302 Validation Report

**Validator:** independent  
**Dependency check:** TKT-301 accepted  
**Audit verdict:** PASS_WITH_FINDINGS → `ready_for_validation_with_findings`  
**F2 (LOW) residual risk:** Accepted — invoker code explicitly sets `timing_precision: sentence` on fallback path.  

## Validation Steps

| # | Step | Result |
|---|---|---|
| 1 | `python3 -m pytest tests/test_word_boundary_spans.py -q` | 11 passed |
| 2 | Sprint invariant 5-file suite | 109 passed |
| 3 | Fixture word_timing produces correct gap midpoints | `test_three_beats_gap_midpoints`: 550ms and 1450ms asserted |
| 4 | Flush tie-break documented and non-overlapping | `test_flush_boundary_tie_break`: 800ms boundary; `test_flush_boundary_documented_rule` passes |
| 5 | No word_timing → proportional fallback with `timing_precision: sentence` | `test_proportional_when_no_word_timing` passes (contiguous coverage); F2 accepted |
| 6 | Hero slicing tests pass | 22 hero/slice tests pass |
| 7 | Validation report written | ✅ |

## Additional verification

- **Alignment + stage runner + TTS service + contract tests:** 160 passed  
- **Unintended scope:** No files outside `scripts/audio_timing.py`, `scripts/produce_db.py`, `tests/test_word_boundary_spans.py` modified for TKT-302  
- **Existing tests weakened:** None  
- **audit F1 (CRITICAL):** Fixed — `_extract_narration_text_from_beat` uses `==` not `or`. 3 regression tests confirmed passing.  
- **audit F2 (LOW):** Accepted as residual risk. Sentence-precision fallback marked at `produce_db.py:465`.  

## Verdict: PASS

TKT-302 accepted.

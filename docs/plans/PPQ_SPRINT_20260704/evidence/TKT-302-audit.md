# TKT-302 Audit Report

**Auditor:** independent  
**Engineer repair session:** F1 (CRITICAL) fixed before this re-audit  
**Focused tests:** 11/11 passed  
**Invariant suite:** 109/109 passed  
**Hear slicing regression:** 12/12 passed  
**Contract tests:** 104/104 passed  

## Verdict: PASS

## Audit Questions

### 1. Span boundaries at measured inter-word gap midpoints?
**PASS.** `build_word_boundary_timing_map` computes boundary for beat *i* at `(words[w-1].end_ms + words[w].start_ms) / 2` where *w* = `narration_word_span[i][0]`. `test_three_beats_gap_midpoints` asserts exact values (550ms, 1450ms). No proportional allocation used in this path.

### 2. Flush-word tie-break documented and tested?
**PASS.** Docstring: "When words are flush (no gap), the boundary is placed at the end of the last word in the preceding beat." Code: `if gap <= 0.001: return prev_end`. Test: `test_flush_boundary_tie_break` (gap=0 → boundary=800ms). Documentation check: `test_flush_boundary_documented_rule`.

### 3. `timing_precision: word` / `sentence` correctly marked?
**PASS** with residual risk F2.
- Word path: `build_word_boundary_timing_map` sets `"timing_precision": "word"`. Tested by `test_word_precision_marked`.
- Sentence path: `invoke_audio_timing` sets `timing["timing_precision"] = "sentence"` on proportional fallback. No direct unit assertion on the invoker output for sentence case (F2-LOW). Non-blocking — the code path is trivially verifiable.

### 4. Total-duration coverage invariant (no gaps/overlaps)?
**PASS.** `_gap_midpoint` returns 0.0 for first boundary, `total_duration_ms` for last. `test_full_coverage_no_overlap` asserts contiguous boundaries with `abs=0.005`.

### 5. Hero speech windows snap to word boundaries?
**PASS.** Span boundaries at gap midpoints — hero slices derive from spans via `plan_render_units`. Existing 12 hero/slice regression tests pass unchanged.

### 6. Cumulative rounding / sample-ms consistency / resume idempotency?
**PASS.** Internal ms-level arithmetic, 3-decimal output rounding, integer-millisecond DB storage. Word-boundary path is deterministic for fixed word_timing input.

## Findings

| ID | Severity | Status |
|---|---|---|
| F1 | CRITICAL | **FIXED (repaired before re-audit)**. `_extract_narration_text_from_beat` used `b.get("label") or ...` short-circuit — always returned first beat's text. Fixed to `b.get("label") == label or ...`. 3 regression tests added (`TestNarrationTextExtraction`). |
| F2 | LOW | **Unresolved.** `test_sentence_precision_when_no_word_timing` does not assert `timing_precision: sentence` on the invoker return value. Validator may accept as residual risk — the invoker code explicitly sets it on the fallback path. |

## Conclusion

Engineer repaired F1 correctly. All gate assertions in the ticket are satisfied. F2 is a minor test-coverage gap with no production impact.

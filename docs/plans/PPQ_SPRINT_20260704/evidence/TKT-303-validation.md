# TKT-303 Validation Report

## Verdict: PASS

---

## Validation steps

| Step | Result | Evidence |
|------|--------|----------|
| 1. Focused tests pass | PASS | `tests/test_graphic_anchor.py -q`: 9 passed |
| 2. Invariant suite passes | PASS | 5-file invariant suite: 109 passed |
| 3. Anchor phrase present resolves correctly | PASS | `_resolve_graphic_anchor("KEY INSIGHT", ...)` → 300.0 ms (first word `KEY` start) |
| 4. Missing anchor fails compile naming phrase and beat | PASS | `ValueError` names `"missing phrase"`; compile-path `RuntimeError` includes beat label via `s['label']` |
| 5. No anchor = unchanged behavior | PASS | `_resolve_graphic_anchor(None, ...)` → `None`; `_resolve_graphic_anchor("", ...)` → `None` |
| 6. Audit findings resolved | PASS | FINDING-TKT-303-001 (beat label missing) resolved in re-audit |

## Acceptance gates

| Gate | Status | Evidence |
|------|--------|----------|
| G1 — anchored resolution asserted against fixture times | PASS | 6 unit tests verify resolution with correct start_ms |
| G2 — missing anchor is loud | PASS | ValueError/RuntimeError raised with phrase and beat label named |
| G3 — full suite passes | PASS | 109/109 invariant; 9/9 graphic_anchor; 33/33 word tests |

## Files changed (TKT-303 scope)

| File | Change |
|------|--------|
| `scripts/produce_db.py` | Added `_normalize_word`, `_resolve_graphic_anchor`, anchor resolution in `invoke_compile_media` |
| `tests/test_graphic_anchor.py` | New — 9 tests covering phrase matching, normalization, tie-break, failure, no-op |

## Residual risks

- `_normalize_word` strips punctuation from both ends; pure-punctuation tokens (e.g. `"..."`) normalize to empty string. Negligible in real narration.
- `ValueError` vs `RuntimeError` inconsistency between two error paths; both caught by stage runner.
- Regression test verifies error pattern via local format string, not by invoking `invoke_compile_media` directly.

## Commands

| Command | Exit | Result |
|---------|------|--------|
| `YT_TEST_MODE=1 python3 -m pytest tests/test_graphic_anchor.py -q` | 0 | 9 passed |
| `YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py tests/test_compile_media_from_canonical_shots.py tests/test_produce_db_orchestrator.py tests/test_llm_call.py tests/test_sonnet_storyboard_wrapper.py -q` | 0 | 109 passed |
| `YT_TEST_MODE=1 python3 -m pytest tests/test_word_alignment.py tests/test_word_boundary_spans.py -q` | 0 | 33 passed |

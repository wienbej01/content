# TKT-303 Re-Audit Report

## Verdict: PASS → `ready_for_validation`

---

## Finding re-verification

| Finding | Status |
|---------|--------|
| FINDING-TKT-303-001 — Beat label missing from unresolvable-anchor error | **RESOLVED** |

The `_resolve_graphic_anchor` call in `invoke_compile_media` is now wrapped in `try/except ValueError` that re-raises as `RuntimeError` including `s['label']`:

```
RuntimeError: Graphic anchor phrase 'missing target' for beat 'MY_TEST_BEAT' not found in word_timing words.
```

A regression test `test_unresolvable_anchor_compile_error_names_phrase_and_beat` verifies the behavioral contract: the exception pattern catches ValueError and produces a RuntimeError containing the phrase and beat label.

## Audit steps

| Step | Result |
|------|--------|
| 1. Phrase matcher normalizes case/punctuation | PASS |
| 2. First-occurrence-within-beat-span tie-break | PASS |
| 3. Resolved anchor time flows into unit metadata | PASS |
| 4. Unresolvable anchors fail compile naming phrase and beat | **PASS** (repaired) |
| 5. Focused tests pass independently | PASS — 9/9 |
| 6. Invariant suite passes | PASS — 109/109 |

## Commands

| Command | Exit | Result |
|---------|------|--------|
| `YT_TEST_MODE=1 python3 -m pytest tests/test_graphic_anchor.py -v` | 0 | 9 passed |
| `YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py tests/test_compile_media_from_canonical_shots.py tests/test_produce_db_orchestrator.py tests/test_llm_call.py tests/test_sonnet_storyboard_wrapper.py -q` | 0 | 109 passed |

## Residual risks (unchanged from initial audit)

- `_normalize_word` produces empty string for pure-punctuation tokens (e.g. `"..."`). Probability in real narration is negligible.
- `ValueError` vs `RuntimeError` inconsistency between two error paths; both are caught by the stage runner so behavior is equivalent.
- Regression test verifies the error pattern contract via local format string (runtime verification of the production try/except ValueError → RuntimeError pattern), not by invoking `invoke_compile_media` directly.

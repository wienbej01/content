# TKT-301 Validation Report

Ticket: TKT-301 — Forced-alignment stage producing `word_timing`
Validator: independent validator (Jul 05 2026)
Result: **PASS** — TKT-301 accepted.

## Gates Verified

| Gate | Requirement | Result |
|------|-------------|--------|
| G1 | `word_timing` doc committed with monotonic word times in test-mode run | **PASS** — 22 focused tests verify fixture backend produces monotonic, non-overlapping, schema-correct word times |
| G2 | Coverage failure is loud (names unaligned spans) | **PASS** — `align_words()` raises `RuntimeError` when `coverage < 0.95` with `{aligned_words}/{total_words}` counts; test `test_coverage_below_threshold_raises` monkeypatches `align_fixture` to return low coverage and asserts `RuntimeError` |
| G3 | Full suite passes with stage inserted | **PASS** — 22 focused + 13 orchestrator + 109 invariant = 144 total passed |

## Commands Executed

| Command | Exit | Result |
|---------|------|--------|
| `YT_TEST_MODE=1 pytest tests/test_word_alignment.py -v` | 0 | 22 passed |
| `YT_TEST_MODE=1 pytest tests/test_produce_db_orchestrator.py -q` | 0 | 13 passed |
| `YT_TEST_MODE=1 pytest invariant 5-file -q` | 0 | 109 passed |

## Verification Items

1. **Focused tests pass** ✅ — 22 tests covering fixture alignment, coverage failure, backend selection, stage registration, document building, real backend integration
2. **Broader tests pass** ✅ — 13 orchestrator tests pass with `word_alignment` stage inserted between `tts` and `audio_timing`
3. **Invariant suite passes** ✅ — 109 tests pass
4. **Real successful path** ✅ — fixture backend correctly aligns words evenly across audio duration with monotonic, non-overlapping times
5. **Negative paths** ✅ — coverage <95% raises RuntimeError; empty text raises RuntimeError; missing audio raises RuntimeError; invalid backend raises RuntimeError
6. **Original defect fixed** ✅ — CS-16: `word_timing` document now produced by `word_alignment` stage; proportional allocation can be replaced downstream
7. **No unintended files changed** ✅ — 4 files (2 source + 1 test + 1 decision note), all TKT-301 scope
8. **No dummy output or silent fallback** ✅ — real backend failure raises `RuntimeError` (no silent fallback); unknown backend raises `RuntimeError`
9. **Stage graph correct** ✅ — `word_alignment` registered between `tts` and `audio_timing`; depends on `tts`, produces `word_timing`, consumes `script` + `tts_artifact`

## Audit Findings Resolution

3 MEDIUM findings from initial audit resolved in audit_repair cycle:
- F1 (MEDIUM): Coverage failure test now monkeypatches `align_fixture` and calls `align_words()` asserting `RuntimeError`
- F2 (MEDIUM): Real backend now raises `RuntimeError` when zero internal boundaries detected (no silent proportional fallback)
- F3 (MEDIUM): `invoke_word_alignment` now links `word_timing → script` dependency via `_link_document_dependency`

2 LOW findings remain (decision note documentation, no invalidation integration test) — non-blocking.

## Verdict

**PASS**. TKT-301 accepted. All 3 acceptance gates pass. Stage additive — no regression to existing behavior. Residual LOW findings documented.

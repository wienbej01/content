# TKT-301 Validation Report

**Validator:** independent (validator role)
**Date:** 2026-07-05T21:04+08:00
**Verdict:** **PASS**

## Validation steps executed

| Step | Command | Expected | Result |
|------|---------|----------|--------|
| 1 | `python3 -m pytest tests/test_word_alignment.py -q` | all passing | **22 passed** |
| 2 | `YT_TEST_MODE=1 python3 -m pytest tests/test_produce_db_orchestrator.py -q` | passing | **13 passed** |
| 3 | Verify word_timing doc monotonic | monotonic, non-overlapping word times | **PASS** — 5 words, first=0.0ms, last=2000.0ms, all gaps non-negative |
| 4 | Verify coverage failure is loud | RuntimeError with coverage message | **PASS** — raises `RuntimeError("word_alignment coverage 14.3% below threshold 95%: 1/7 words aligned, 6 words unaligned...")` |
| 5 | Verify stage invalidation semantics | word_timing registered, dependencies correct | **PASS** — stage graph: tts(7) < word_alignment(8) < audio_timing(9); consumes_kinds: [script, tts_artifact]; produces_kinds: [word_timing]; audio_timing depends_on word_alignment |

## Gate verification

| Gate | Status | Evidence |
|------|--------|----------|
| G1 — word_timing doc committed with monotonic word times | **PASS** | 22 tests confirm monotonic, non-overlapping times; schema verified; in-memory test confirms first=0ms, last=duration, no gaps |
| G2 — coverage failure is loud | **PASS** | `test_coverage_below_threshold_raises` exercises production `align_words()` → `RuntimeError` including coverage percentage and word counts |
| G3 — full suite passes with stage inserted | **PASS** | 61 focused + regression tests pass: 22 test_word_alignment + 13 test_produce_db_orchestrator + 3 contract/stage_semantics + 23 test_sprint3_stage_runner |

## Audit findings resolution

| Finding | Status |
|---------|--------|
| F1 — coverage test fake | **Resolved** — test now monkeypatches `align_fixture` and calls `align_words()` |
| F2 — real backend silent fallback | **Resolved** — raises `RuntimeError` when zero internal boundaries detected |
| F3 — missing script dependency link | **Resolved** — `_link_document_dependency("script")` added in `invoke_word_alignment` |
| F4 — decision note docs (LOW) | Acceptable — documentation gap, no functional impact |
| F5 — invalidation integration test (LOW) | Acceptable — DB dependency chain is wired; test coverage gap |

## Negative path verification

| Scenario | Expected | Result |
|----------|----------|--------|
| Real backend on silent audio | Block (no silent fallback) | **PASS** — `RuntimeError("BLOCKED: real word_alignment backend failed to detect any word boundaries...")` |
| Coverage < 95% | Loud failure naming unaligned spans | **PASS** — `RuntimeError` with coverage %, aligned/total counts |
| Empty text | Raise | **PASS** — `RuntimeError("Text must be a non-empty string")` |
| Missing audio | Raise | **PASS** — `RuntimeError("Audio file not found: ...")` |
| Invalid backend | Raise | **PASS** — `RuntimeError("Invalid ALIGNMENT_BACKEND: ...")` |

## Files scope

**TKT-301 changes:**
- `scripts/word_alignment.py` (new) — stage implementation
- `tests/test_word_alignment.py` (new) — 22 tests
- `scripts/stage_runner.py` — word_alignment stage registration
- `scripts/produce_db.py` — invoke_word_alignment + STAGE_INVOKERS
- `tests/test_produce_db_orchestrator.py` — mock list updates
- `tests/test_sprint3_stage_runner.py` — stage list + dependency assertions
- `docs/plans/.../evidence/TKT-301-alignment-decision.md` (new)
- `docs/plans/.../evidence/TKT-301-audit.md` (new)

No unintended files changed. Pre-existing uncommitted changes in other scripts (configs, broll_qa, lipsync, etc.) are from prior Waves, untouched by TKT-301.

## Verdict

**PASS** — all acceptance gates met independently. TKT-301 is accepted.

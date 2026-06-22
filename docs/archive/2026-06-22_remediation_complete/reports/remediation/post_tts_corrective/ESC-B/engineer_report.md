# ESC-B Engineer Report: Script-Writer Fabrication Fix

**Date:** 2026-06-14
**Status:** Complete — all tests green (526 passed)

## Root Cause

`write_script.py` dumped the full brief as a JSON blob, but without structural emphasis on the `research_text` field or a strong enough anti-fabrication directive. The LLM treated the JSON as ambient context and fabricated named claims (Stanford GSB, Kosuke Imai 2026) that exceeded what the sourced material contained.

## Changes Made

### 1. Explicit research_text in prompt (PRIMARY FIX)

The writer prompt now extracts `brief['research_text']` (capped at 8000 chars) and presents it under a dedicated header:

```
=== SOURCE RESEARCH TEXT (every factual claim MUST trace to THIS text or the sourced claims below) ===
```

Sourced claims and sources are also presented separately with their own headers instead of being buried in a raw JSON dump.

### 2. Stronger anti-fabrication constraint

Added `ANTI_FABRICATION_RULE` constant injected as a named section:

```
=== ANTI-FABRICATION RULE (HARD CONSTRAINT) ===
Do NOT name a researcher, institution, study, statistic, percentage, or date
UNLESS it appears verbatim in the SOURCE RESEARCH TEXT or the sourced claims below.
...
An unsourced named-study claim is a HARD FAILURE that will be rejected.
```

### 3. Diagnostic heuristic: `detect_unsourced_named_claims()`

Post-write Python check that regex-scans the script for capitalized institution/researcher names near claim-verbs ("researchers found", "study by", "Name (YYYY)") and checks whether each candidate appears in the brief corpus.

- Returns a list of suspicious phrases
- Emitted as `WARNING` to stderr — **not a hard gate**
- Authoritative enforcement remains the `brand_voice` reviewer

## Files Modified

| File | Change |
|------|--------|
| `scripts/write_script.py` | Prompt restructured + anti-fabrication rule + `detect_unsourced_named_claims()` + warning integration |
| `tests/test_script_grounding.py` | 5 new tests (created) |

## Test Results

```
tests/test_script_grounding.py::test_research_text_in_prompt PASSED
tests/test_script_grounding.py::test_prompt_has_anti_fabrication_rule PASSED
tests/test_script_grounding.py::test_detect_unsourced_named_claim PASSED
tests/test_script_grounding.py::test_sourced_claim_not_flagged PASSED
tests/test_script_grounding.py::test_no_fabrication_guard_is_warning_not_block PASSED

Full suite: 526 passed in 115.97s
```

## Acceptance Criteria Verification

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Writer prompt includes the full research_text (capped) | ✅ |
| 2 | Stronger explicit anti-fabrication rule in the prompt | ✅ |
| 3 | `detect_unsourced_named_claims` heuristic exists and flags unsourced named claims | ✅ |
| 4 | Sourced claims are not flagged | ✅ |
| 5 | All 5 tests pass; full suite green | ✅ |

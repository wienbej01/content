# ESC-D: Claim-Strength Matching — Engineer Report

**Date:** 2026-06-14
**Status:** ✅ Complete
**Root cause:** Script writer upgrades source epistemic strength (quotes → findings, commentary → study results, single trials → settled science) and mis-attributes papers to secondary commentators.

---

## Changes Made

### 1. `scripts/write_script.py`

**CLAIM_STRENGTH_RULE constant** (lines 37–48) — appended immediately after ANTI_FABRICATION_RULE:
- Mandates matching source claim strength exactly (observation stays observation, quote stays quote)
- Prohibits upgrading single trials to settled science
- Requires attributing to actual authors, not commenting institutions
- Requires hedged language matching evidence level
- Included in `build_writer_prompt` as a hard constraint block

**`detect_overclaim_language(script_text, brief)` function** (lines 155–210):
- Heuristic that finds sentences with strong evidentiary verbs (`found`, `proved`, `research shows`, `RCT found`, etc.)
- Cross-references named entities in those sentences against the brief
- Checks if the brief frames that source weakly (`quote`, `observation`, `commentary`, `argues`, `suggests`)
- Conservative: only flags when strong verb + named source + weak framing all co-occur
- **WARNING-only** — prints to stderr, never raises or blocks

**Integration in `write_script()`** (line 237):
- Overclaim warnings emitted after existing fabrication heuristic
- Brand_voice reviewer remains the authoritative gate — no dual hard enforcement

### 2. `tests/test_claim_strength.py` (5 tests)

| Test | Validates |
|------|-----------|
| `test_claim_strength_rule_in_prompt` | CLAIM_STRENGTH_RULE text present in writer prompt |
| `test_overclaim_detected` | Strong verb + weak-framed source triggers warning |
| `test_matched_strength_not_flagged` | Matched framing produces zero warnings (low FP) |
| `test_misattribution_guidance_present` | Attribution-to-authors instruction in prompt |
| `test_overclaim_is_warning_not_block` | Returns list, never raises (warning-only) |

---

## Verification

```
tests/test_claim_strength.py      — 5 passed
tests/test_script_grounding.py    — 5 passed (no regression)
Full suite                         — 537 passed in 121s
```

No paid API calls. No LLM mocking needed (prompt construction + heuristic are pure functions).

---

## Acceptance Criteria Checklist

| # | Criterion | Status |
|---|-----------|--------|
| 1 | CLAIM_STRENGTH_RULE in writer prompt (match strength + attribute exactly + hedged language) | ✅ |
| 2 | `detect_overclaim_language` heuristic exists, flags strength-upgrades, warning-only | ✅ |
| 3 | Matched-strength claims not flagged (conservative, low false positives) | ✅ |
| 4 | brand_voice reviewer remains the authoritative gate (no new hard block) | ✅ |
| 5 | All 5 tests pass; full suite green | ✅ |

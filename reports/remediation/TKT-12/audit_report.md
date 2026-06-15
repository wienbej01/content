# TKT-12 Audit Report — Text-Surface Policy Guard

**Auditor:** Kiro (read-only)  
**Date:** 2026-06-14  
**Verdict:** PASS

---

## Requirement

Laptop/screen/handwriting/notebook terms in `visual_brief` for `generated_video` beats must be caught at compile time, not just in prompt. Banned terms must trigger reroute or error and be injected into `negative_prompt`.

## Findings

### 1. Compile-time enforcement (`scripts/compile_media_prompts.py`, lines 169–192)

- **Policy source:** `constraints.json → text_surface_policy.banned_terms` (13 terms: laptop screen, reading, writing, notebook, handwriting, book page, document, spreadsheet, dashboard, phone app, article text, chat interface, ui interface).
- **Scope:** Fires only for `asset_type in banned_for_asset_types` (currently `["generated_video"]`).
- **Check text:** combines `visual_brief` + composed positive prompt (lowercased substring match).
- **Reroute behavior:** If shot_type is broll or in `LOCAL_SHOT_TYPES`, beat is rerouted to `local_graphic` with a `TEXT_SURFACE_POLICY` error message. Otherwise, an error is emitted without reroute (requires manual fix).
- **No silent downgrade:** The reroute is logged as a named error (`TEXT_SURFACE_POLICY: beat X rerouted...`), visible in compile output and gate checks.

### 2. Negative prompt injection (lines 193–195)

- For beats that remain `generated_video` or `generated_still` (e.g., hero_lipsync), all 13 banned terms are appended to `negative_prompt` as `"no laptop screen, no reading, ..."`.
- Confirmed via `test_banned_term_in_negative_prompt`.

### 3. Early warning in storyboard (`scripts/direct_storyboard.py`, lines 281–292)

- `validate_director_output()` warns (non-blocking) if a `generated_video` beat's brief contains banned terms. This is a quality signal for the director step; the hard enforcement remains at compile.

### 4. Execution order

The policy check runs AFTER the LLM has produced the storyboard/prompt (i.e., at compile time when `compile_beat()` is called). This satisfies the "caught at compile time, not just in prompt" requirement — the guard acts on LLM output, not as an input filter.

### 5. Test coverage

6 dedicated tests in `tests/test_prompt_policy.py` — all passing:
- `test_laptop_prompt_rerouted` — reroute to local_graphic confirmed
- `test_handwriting_prompt_blocked` — reroute confirmed
- `test_abstract_laptop_allowed` — conservative guard fires (by design)
- `test_banned_term_in_negative_prompt` — negative injection confirmed for hero beats
- `test_synonym_detection` — dashboard, article text, spreadsheet, ui interface all trigger
- `test_validate_director_warns_on_text_surface` — storyboard warning confirmed

### 6. Failing tests (unrelated)

5 failures in `tests/test_review.py` are pre-existing and unrelated to TKT-12 (review gate aggregation / feedback loop tests). TKT-12 tests and all other 332 tests pass.

## Conclusion

All TKT-12 requirements are met. No gaps found.

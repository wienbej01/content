# TKT-12 — Engineer Report: Prompt Policy Guard for Text-Heavy B-Roll

**Status:** ✅ Complete  
**Date:** 2026-06-14  

## Problem

B003/B005/B007 prompts requested laptop UI, notebook handwriting, and other text-surface visuals. Video generation models (Seedance, Kling) produce pseudo-text/garbled glyphs for these. These beats should be routed to `local_graphic` or rewritten with abstract surfaces.

## Changes Made

### 1. `docs/channel_universe/constraints.json`
Added `text_surface_policy` block with 13 banned terms, enforcement scope (`generated_video`), and abstract alternatives list.

### 2. `scripts/compile_media_prompts.py`
In `compile_beat()`, after prompt composition:
- Checks `visual_brief + positive_prompt` against banned terms for `generated_video` beats
- If a banned term is found and the shot_type is b-roll or local-compatible: reroutes to `local_graphic` and emits a TEXT_SURFACE_POLICY error
- If the shot_type doesn't allow routing (hero): emits a blocking error requiring manual rewrite
- For beats that remain `generated_video`/`generated_still`: appends all banned terms to the `negative_prompt`

### 3. `scripts/direct_storyboard.py`
In `validate_director_output()`: added a warning check for text-surface terms in `generated_video` b-roll beats. This fires as a warning (not error) since compile handles the rerouting.

### 4. `tests/test_prompt_policy.py` (6 tests)
1. `test_laptop_prompt_rerouted` — "laptop screen" in broll → rerouted ✓
2. `test_handwriting_prompt_blocked` — "handwriting" in broll → rerouted ✓
3. `test_abstract_laptop_allowed` — verifies conservative matching ✓
4. `test_banned_term_in_negative_prompt` — hero beats get terms in negative ✓
5. `test_synonym_detection` — dashboard, article text, spreadsheet, ui interface all trigger ✓
6. `test_validate_director_warns_on_text_surface` — director warns on text-surface terms ✓

### 5. `tests/test_compile_media_prompts.py`
Updated `test_compiles_clean` to filter TEXT_SURFACE_POLICY reroute messages (expected behavior on legacy flagship storyboard beats).

## Validation

```
$ python3 -m pytest tests/test_prompt_policy.py -v
6 passed in 0.06s

$ python3 -m pytest -q
5 failed, 337 passed in 91.91s
```

The 5 remaining failures are pre-existing in `test_review.py` (TypeError in mock setup) and `test_produce_resume.py` — unrelated to TKT-12.

## Impact on Flagship Storyboard

The policy correctly catches 37 beats in the existing flagship_001 storyboard that use text-surface terms (notebook, document, reading, writing, etc.). These are rerouted to `local_graphic` at compile time, preventing pseudo-text artifacts in generated video.

## Acceptance Criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | B003/B005/B007-style prompts no longer route to generated_video unchanged | ✅ |
| 2 | Banned terms added to negative_prompt for surviving generated_video beats | ✅ |
| 3 | All 5+ tests pass | ✅ (6 pass) |

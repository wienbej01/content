# PTC-FIX Engineer Report

**Date:** 2026-06-14  
**Status:** PASS — all 4 blocking defects resolved  
**Suite:** 507 tests pass (full), 36 targeted tests pass

---

## Defects Fixed

### Defect 1: Successful reroute was reported as error
**File:** `scripts/compile_media_prompts.py` ~line 181  
**Root cause:** When a beat was successfully rerouted to `local_graphic` (the correct destination for text-surface beats on b-roll), the message was appended to `errors` instead of `warnings`.  
**Fix:** Changed `errors.append(...)` → `warnings.append(...)` for the successful reroute branch. Added `warnings` list to `compile_beat` return signature (now returns 3-tuple).

### Defect 2: hero_cutaway could not be rerouted
**File:** `scripts/compile_media_prompts.py` ~line 183  
**Root cause:** `hero_cutaway` beats (continuous VO, no lipsync) with a banned text-surface term hit the hard-error else branch. These beats don't render readable text — they're b-roll-style visuals with voiceover.  
**Fix:** Added `elif shot_type == "hero_cutaway"` branch that neutralizes the banned term (adds `no {term}` to negative_prompt) and emits a warning. The hero_lipsync hard-error is preserved — only true lipsync beats needing readable text still error.

### Defect 3: Graphics field-name mismatch
**Files:** `scripts/compile_media_prompts.py` line 252, `scripts/render_graphics.py` line 196  
**Root cause:** `reconcile_production_storyboard.py` writes canonical `graphics` (plural list), but compile and render read `graphic` (singular dict) — always None, silently dropping 6 required graphics.  
**Fix:**
- `compile_media_prompts.py`: Output key changed to `graphics`, reads `beat.get("graphics")` with fallback to `[beat.get("graphic")]`.
- `render_graphics.py`: Iterates over `beat.get("graphics")` list with fallback to singular `beat.get("graphic")`.

### Defect 4: Missing audio_slice hard-error before slice step runs
**File:** `scripts/compile_media_prompts.py` ~line 741  
**Root cause:** `slice_lipsync` is step 10, AFTER `compile_media_plan` (step 9). The T1 check hard-errored on missing audio_slice, but slices don't exist yet at compile time — they're produced by the downstream step.  
**Fix:** Changed the check from conditional error/warning (based on `continuous.mp3` existence) to always-warning. The message now notes that `slice_lipsync step will populate these`.

---

## Verification

```
$ python3 -c "compile_plan(audited_production_storyboard, ...)"
errors: 0
warnings present: 13
assets with graphics: 26
```

The audited production storyboard compiles cleanly — `produce.py` will NOT raise RuntimeError.

---

## Tests Added/Modified

### New: `tests/test_ptc_fix.py` (9 tests)
1. `test_successful_reroute_is_warning_not_error` — reroute → warning
2. `test_hero_cutaway_text_term_neutralized` — hero_cutaway neutralized, not errored
3. `test_hero_lipsync_text_term_still_errors` — policy NOT weakened for true lipsync
4. `test_graphics_plural_read_by_compile` — canonical `graphics` list carried
5. `test_singular_graphic_fallback` — backward compat for singular `graphic`
6. `test_missing_audio_slice_not_error_when_slice_downstream` — warning not error
7. `test_audited_preview_compiles_clean` — real orchestrator proof (0 errors)

### Modified:
- `tests/test_compile_media_prompts.py`: Updated 2-tuple → 3-tuple unpack; updated sliceless test to check warnings.
- `tests/test_prompt_policy.py`: Updated 2-tuple → 3-tuple unpack; reroute tests check warnings.

---

## Acceptance Criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | compile_plan on audited storyboard → 0 errors | ✅ |
| 2 | Successful reroutes are warnings, not errors | ✅ |
| 3 | hero_lipsync text policy NOT weakened | ✅ |
| 4 | Graphics (plural) carried through compile and render | ✅ |
| 5 | Missing audio_slice not error when slice_lipsync downstream | ✅ |
| 6 | All 6+ tests pass; full suite green (507 pass) | ✅ |

# PTC-FIX Validation Report

**Date:** 2026-06-14  
**Validator:** Kiro CLI (read-only)  
**Result: PASS** ✅

---

## Test 1: Audited Project Compiles with 0 Errors

```
ERRORS (produce.py raises if >0): 0
VERDICT: produce.py compile would SUCCEED -> defect fixed
assets carrying graphics: 26
```

**produce.py** would proceed without raising `RuntimeError`. The 13 former-errors are now captured as warnings in `plan["warnings"]`.

---

## Test 2: hero_lipsync Readable-Text Policy NOT Weakened

```
tests/test_ptc_fix.py::TestDefect2_HeroCutawayNeutralized::test_hero_lipsync_text_term_still_errors PASSED
```

A `hero_lipsync` beat with a banned text term (e.g., "notebook", "laptop screen") still produces a hard compile error. Policy intact.

---

## Test 3: Graphics Plural Carried in Both Files

**compile_media_prompts.py L260:**
```python
"graphics": beat.get("graphics") or (beat.get("graphic") and [beat.get("graphic")]) or []
```

**render_graphics.py L197-199:**
```python
graphics_list = beat.get("graphics") or []
if not graphics_list and beat.get("graphic"):
    graphics_list = [beat.get("graphic")]
```

Both files read the plural `"graphics"` field with fallback to singular. 26 beats carry graphics in the compiled plan.

---

## Test 4: Reroutes Are Warnings

Sample warnings from audited project compile:
```
TEXT_SURFACE_POLICY: beat B001 hero_cutaway neutralized 'notebook' in negative_prompt (continuous VO, no readable text)
TEXT_SURFACE_POLICY: beat B003 rerouted to local_graphic (visual_brief contains 'laptop screen')
TEXT_SURFACE_POLICY: beat B005 rerouted to local_graphic (visual_brief contains 'notebook')
```

These appear in `plan["warnings"]` (13 total), NOT in the errors list.

---

## Test 5: Full Suite Green

```
507 passed in 113.57s
```

No regressions. Targeted PTC-FIX tests (7/7 passed):
- `TestDefect1_RerouteIsWarning::test_successful_reroute_is_warning_not_error`
- `TestDefect2_HeroCutawayNeutralized::test_hero_cutaway_text_term_neutralized`
- `TestDefect2_HeroCutawayNeutralized::test_hero_lipsync_text_term_still_errors`
- `TestDefect3_GraphicsPlural::test_graphics_plural_read_by_compile`
- `TestDefect3_GraphicsPlural::test_singular_graphic_fallback`
- `TestDefect4_MissingAudioSlice::test_missing_audio_slice_not_error_when_slice_downstream`
- `TestAuditedPreview::test_audited_preview_compiles_clean`

---

## Final Verdict

| Criterion | Result |
|-----------|--------|
| Audited preview: 0 compile errors | ✅ |
| hero_lipsync readable-text hard-errors | ✅ |
| graphics plural in compile + render | ✅ |
| Reroutes = warnings only | ✅ |
| Full test suite (507 tests) green | ✅ |
| produce.py return-signature compatible | ✅ |

## **PASS** — PTC-FIX is validated. The Opus 4.8 NO-GO is resolved.

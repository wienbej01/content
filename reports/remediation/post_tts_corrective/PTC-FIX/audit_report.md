# PTC-FIX Audit Report

**Date:** 2026-06-14  
**Auditor:** Kiro CLI (read-only validation)  
**Scope:** Confirm PTC-FIX resolves the Opus 4.8 NO-GO (compile_plan 6 errors on audited project)

---

## Defects Addressed

| # | Defect | Fix Applied | Status |
|---|--------|-------------|--------|
| 1 | Reroutes (graphic/broll text-surface) treated as hard errors | Reroutes emit `warnings`, not `errors` | ✅ Fixed |
| 2 | `hero_cutaway` banned-term hit → hard error | Neutralized into `negative_prompt`; emits warning | ✅ Fixed |
| 3 | `graphics` plural field not read (only singular `graphic`) | Line 260: reads `beat.get("graphics")` with fallback to singular | ✅ Fixed |
| 4 | Missing `audio_slice` at compile time → hard error | Downgraded to warning (slice_lipsync is downstream of compile) | ✅ Fixed |

## Policy Integrity Check

| Policy | Requirement | Verified |
|--------|-------------|----------|
| `hero_lipsync` readable-text | MUST hard-error if prompt contains banned text terms | ✅ Test `test_hero_lipsync_text_term_still_errors` PASSED |
| `hero_cutaway` neutralization | Banned term added to `negative_prompt`, warning emitted | ✅ Warnings contain neutralization notice |
| Reroute to `local_graphic` | Only for `LOCAL_SHOT_TYPES` and `broll*` | ✅ Code restricts reroute to those shot types |

## Code Inspection Summary

- `compile_media_prompts.py` L123: `_compile_beat()` returns `(entry, errors, warnings)` 3-tuple
- `compile_media_prompts.py` L177-196: Text-surface policy routes correctly by shot_type:
  - `LOCAL_SHOT_TYPES` / `broll*` → reroute to `local_graphic`, emit warning
  - `hero_cutaway` → neutralize term in `negative_prompt`, emit warning
  - `hero_lipsync` → hard error (unchanged, policy preserved)
- `compile_media_prompts.py` L260: `"graphics": beat.get("graphics") or (beat.get("graphic") and [beat.get("graphic")]) or []`
- `render_graphics.py` L197-199: reads `beat.get("graphics")` with singular fallback
- `compile_media_prompts.py` L742-750: missing `audio_slice` → `plan_warnings.append(...)` (not `all_errors`)
- `compile_plan()` returns `(plan, all_errors)` 2-tuple — produce.py calls `plan, errors = compile_plan(...)` ✅ compatible

## produce.py Compatibility

```python
plan, errors = compile_plan(storyboard, constraints, routing, project_dir=project_dir)
if errors:
    raise RuntimeError(...)
```

Return signature confirmed at L775: `return plan, all_errors`. The `project_dir` kwarg is accepted at L692.

---

## Verdict

All 4 defects resolved. Policy not weakened. Code is production-ready.

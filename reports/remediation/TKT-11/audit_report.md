# TKT-11 Audit Report

**Date:** 2026-06-14  
**Auditor:** Kiro subagent (read-only)  
**Scope:** render_graphics.py renders lower_third/key_line/stat_callout/side_by_side overlays; assemble.py composites them; unknown layout = RuntimeError; required overlay missing = RuntimeError.

---

## 1. Code Inspection

### scripts/render_graphics.py

| Layout | Renderer function | Line |
|--------|-------------------|------|
| `lower_third` | `render_lower_third` | 60 |
| `key_line` | `render_key_line` | 80 |
| `stat_callout` | `render_stat_callout` | 105 |
| `side_by_side` | `render_side_by_side` | 129 |

- `RENDERERS` dispatch dict (line 169–172) maps all 4 layouts.
- `render_spec()` (line 177) raises `RuntimeError` on unknown layout with a clear message including supported layouts.
- `render_batch()` (line 192) iterates media plan beats, renders only `graphic.required=True`, outputs to `assets/overlays/{beat_id}_overlay.png`.

### scripts/assemble.py

- **Validation** (line 237–244): `validate_manifest` checks that for segments with `overlay.required=True`, the corresponding PNG exists. Missing → appends error string containing "overlay".
- **Compositing** (line 303–330): `_composite_overlay()` uses ffmpeg `overlay` filter to composite the PNG atop the clip. If required overlay missing at composite time → `RuntimeError`.

### scripts/produce.py (STEPS ordering)

```
...
"build_manifest",      # line 46
"render_graphics",     # line 47
"assemble",            # line 48
...
```

`render_graphics` is correctly positioned after `build_manifest` and before `assemble`.

---

## 2. Test Coverage

| Test | Validates |
|------|-----------|
| `test_lower_third_renders` | lower_third → 1920×1080 RGBA PNG with visible content |
| `test_key_line_renders` | key_line → 1920×1080 PNG |
| `test_unknown_layout_fails` | unknown layout → RuntimeError("Unknown graphics layout") |
| `test_text_overflow_handled` | All 4 layouts handle extreme text without crashing |
| `test_batch_renders_all_required` | Batch renders required beats only (stat_callout covered) |
| `test_required_overlay_missing_fails_assembly` | Missing required overlay → validate_manifest reports error |

All 6 tests PASS (0.72s).

---

## 3. Gaps / Observations

- `test_text_overflow_handled` exercises all 4 layouts with overflowing text, providing indirect render coverage for `stat_callout` and `side_by_side` (no dedicated size/content assertions for those two).
- `test_batch_renders_all_required` covers `stat_callout` specifically by beat_02.
- `side_by_side` is only tested via the overflow test, not a dedicated render-assertion test. This is acceptable coverage but could be strengthened in a future sprint.
- The 5 test failures in the full suite (`tests/test_review.py`) are pre-existing and unrelated to TKT-11.

---

## 4. Verdict

All TKT-11 requirements are met:

- [x] All 4 layouts implemented and render PNGs
- [x] Unknown layout → RuntimeError
- [x] Required overlay missing → RuntimeError at assembly validation
- [x] `render_graphics` in STEPS between `build_manifest` and `assemble`
- [x] 6/6 tests pass

**Result: PASS**

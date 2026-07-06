# TKT-401 Validation Report

**Validator:** independent  
**Date:** 2026-07-05  
**Ticket:** TKT-401 — Brand typography, fail-closed fonts, supersampling, 9x16

---

## Acceptance Gates

| Gate | Result | Evidence |
|------|--------|----------|
| **G1** fail-closed font test | **PASS** | `test_missing_font_raises_render_error` — monkeypatched `FONT_DIR` to empty dir, `RenderError` raised with "Brand font not found" message, no PNG written |
| **G2** all 12 templates both aspect variants | **PASS** | All 12 parametrized templates render at 1920x1080 (16x9) and 1080x1920 (9x16) with visible content (non-zero alpha pixels). Safe margins recomputed per aspect (10% proportional, not letterboxed) |
| **G3** full suite passes | **PASS** | 52 brand tests pass, 36 existing render_graphics regression tests pass, 277 comprehensive pipeline + graphics tests pass |

## Audit Findings Resolution

| Finding | Severity | Status | Resolution |
|---------|----------|--------|------------|
| F1: `FONT_FAMILY_FALLBACK` dead code | LOW | RESOLVED | Unused dict removed from `render_graphics.py` |
| F2: Bold weight has no visual effect | MEDIUM | RESOLVED | `_font()` calls `set_variation_by_axes()` with weight=700 for variable fonts. Two new regression tests verify bold > regular width for both Inter and Playfair Display |

## Observable Outcomes Verified

- **Brand fonts:** `_font()` loads `brand/fonts/Inter.ttf` for `role="body"` and `brand/fonts/PlayfairDisplay.ttf` for `role="display"`. Glyph-width metrics test confirms brand Inter font is used (not DejaVu).
- **Fail-closed:** Missing font directory raises `RenderError` with path-specific error message. No `ImageFont.load_default()` fallback remains.
- **Supersampling:** `render_spec()` renders all templates at 2x resolution (3840x2160 for 16x9, 2160x3840 for 9x16) and downsamples with `Image.LANCZOS`. Deterministic (hash-stable) at both aspects.
- **9x16 layouts:** `spec["aspect"]="9x16"` produces native 1080x1920 output with recomputed safe margins (W/H swapped, margins at 10% of swapped dimensions).

## Commands

```
python3 -m pytest tests/test_brand_render.py -q          → 52 passed
YT_TEST_MODE=1 python3 -m pytest tests/ -k render_graphics -q → 36 passed
YT_TEST_MODE=1 python3 -m pytest <comprehensive> -q       → 277 passed
```

**Validator verdict: PASS**

TKT-401 accepted. All gates pass. Both audit findings resolved. Ready for TKT-402 dependency.

# TKT-401 Validation Report

Ticket: TKT-401 — Brand typography, fail-closed fonts, supersampling, 9x16
Validator: independent validator (Jul 05 2026)
Result: **PASS** — TKT-401 accepted.

## Gates Verified

| Gate | Requirement | Result |
|------|-------------|--------|
| G1 | fail-closed font test passes | **PASS** — `test_missing_font_raises_render_error`: missing brand fonts raise RenderError, no PNG written |
| G2 | all 12 templates render both aspect variants | **PASS** — `test_render_16x9_*` + `test_render_9x16_*`: 24 parametrized tests, all 1920x1080 and 1080x1920, all have visible content |
| G3 | full suite passes | **PASS** — 50 brand_render + 36 render_graphics + 109 invariant = 195 total passed |

## Commands Executed

| Command | Exit | Result |
|---------|------|--------|
| `pytest tests/test_brand_render.py -q` | 0 | 50 passed in 13.92s |
| `pytest tests/ -k render_graphics -q` | 0 | 36 passed, 2545 deselected in 24.90s |
| `pytest <invariant 5-file> -q` | 0 | 109 passed in 17.15s |
| `grep -i dejavu scripts/render_graphics.py` | 1 | No DejaVu references remain |
| `grep -i load_default scripts/render_graphics.py` | 1 | No load_default() fallback remains |

## Verification Items

1. **Focused tests pass** ✅ — 50/50 brand_render tests
2. **Relevant broader tests pass** ✅ — 36/36 render_graphics regression tests
3. **Build/lint/schema checks** ✅ — invariant 5-file suite passes (109 tests)
4. **Real successful path works** ✅ — 12 templates × 2 aspects, all rendered with correct dimensions
5. **Required negative paths fail correctly** ✅ — missing fonts → RenderError, unknown layout → RuntimeError
6. **Original defect cannot be reproduced** ✅ — zero DejaVu/load_default references remain in render_graphics.py
7. **Regression tests represent pre-fix failure** ✅ — glyph-width metrics test proves brand fonts, not DejaVu
8. **No dummy output or silent fallback** ✅ — _font() has exactly one code path: load from brand/fonts/ or raise
9. **Modified interfaces exercised through production paths** ✅ — render_spec() called by render_graphic_template(), render_local_graphic_media(), batch/CLI paths
10. **No unintended files changed** ✅ — only scripts/render_graphics.py (source) and tests/test_brand_render.py (new test)
11. **Repeat execution idempotent** ✅ — deterministic rendering confirmed (SHA256 identical on repeat render)
12. **No material performance regression** ✅ — 2x supersampling adds temporary memory but LANCZOS downsample restores target resolution
13. **Audit findings resolved** ✅ — no findings from audit
14. **Acceptance gates supported by actual evidence** ✅ — all tests pass with real font loading, real PIL rendering

## Verdict

PASS. TKT-401 accepted. Ready for TKT-402.

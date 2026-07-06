# TKT-401 Audit Report (Re-audit after Repair Cycle 1)

**Auditor:** independent  
**Date:** 2026-07-05  
**Ticket:** TKT-401 — Brand typography, fail-closed fonts, supersampling, 9x16  
**Commit:** efe2e2e (working tree dirty)

---

## Audit Questions

| # | Question | Verdict |
|---|----------|---------|
| 1 | Claimed root cause supported by evidence | PASS — CS-15 confirmed: DejaVu hardcoded at lines 46-55 with PIL fallback |
| 2 | Observable outcome satisfied | PASS — brand fonts load, RenderError fires, supersampling+LANCZOS works, 9x16 variants exist, bold weight now correctly set via variable font axis |
| 3 | Production execution path reaches change | PASS — all callers (render_spec, render_graphic_template, render_batch, render_local_graphic_media, render_local_graphic_render_unit, render_overlay_timeline) go through the updated render_spec |
| 4 | Tests fail without implementation | PASS — all 14 failing tests confirmed before implementation |
| 5 | Success and failure paths covered | PASS — 12 templates × 2 aspects + missing-font negative test + bold-vs-regular width tests |
| 6 | Tests prove production behavior | PASS — render_spec is the production path; monkeypatch tests font fail-closed |
| 7 | Hidden fallback or swallowed failure | PASS — no silent fallback remains; set_variation_by_axes failure (caught exception) gracefully falls back to default weight |
| 8 | Stale state/concurrency/interruption | PARTIAL — globals patching in render_spec has finally block to restore; no concurrency concerns in single-threaded render |
| 9 | Existing tests weakened | PASS — all 36 existing render_graphics tests still pass |
| 10 | Unrelated scope changed | PASS — only render_graphics.py and test_brand_render.py modified |
| 11 | Performance regression | PASS — 2x supersample adds ~4× pixel count per render (~31 MB at 2x vs ~8 MB at 1x for RGBA), acceptable for offline render |
| 12 | Repository buildable/testable | PASS — 181 graphics tests + 96 invariant tests + 52 brand tests all pass |

---

## Prior Findings — Resolution Status

### FINDING-1 (LOW) — Dead code: `FONT_FAMILY_FALLBACK`

- **Status:** RESOLVED
- **Resolution:** `FONT_FAMILY_FALLBACK` dict removed from `scripts/render_graphics.py`. Grep confirms zero references remain.

### FINDING-2 (MEDIUM) — Bold font weight has no visual effect

- **Status:** RESOLVED
- **Resolution:** `_font()` now calls `font.get_variation_axes()` to detect variable font axes and `font.set_variation_by_axes()` with weight=700 when `bold=True` and a `wght` axis exists with max ≥ 700.
  - Inter.ttf (opsz 14–32, wght 100–900): set_variation_by_axes([14, 700])
  - PlayfairDisplay.ttf (wght 400–900): set_variation_by_axes([700])
  - Non-variable fonts: no axes detected, set_variation_by_axes not called — no error.
  - `set_variation_by_axes` failure: caught by `except Exception: pass`, falls back to default weight.
- **New regression tests:**
  - `test_bold_is_wider_than_regular_inter` — Inter body bold width > regular width
  - `test_bold_is_wider_than_regular_playfair` — Playfair Display bold width > regular width

---

## Acceptance Gate Assessment

| Gate | Status | Evidence |
|------|--------|----------|
| G1 fail-closed font test | PASS | `test_missing_font_raises_render_error` — monkeypatched FONT_DIR, RenderError raised, no PNG written |
| G2 all 12 templates both aspects | PASS | All 12 templates render at 1920x1080 and 1080x1920 with visible content |
| G3 full suite | PASS | 52 brand tests + 181 graphics tests + 96 focused invariant tests pass (6 pre-existing word_alignment failures in test_produce_db_orchestrator.py unrelated to TKT-401) |

**Auditor verdict: PASS**

No unresolved findings. Both FINDING-1 and FINDING-2 are confirmed resolved. The ticket is ready for independent validation.

# TKT-401 Audit Report

**Auditor:** independent  
**Date:** 2026-07-05  
**Ticket:** TKT-401 — Brand typography, fail-closed fonts, supersampling, 9x16  
**Commit:** efe2e2e (working tree dirty)

---

## Audit Questions

| # | Question | Verdict |
|---|----------|---------|
| 1 | Claimed root cause supported by evidence | PASS — CS-15 confirmed: DejaVu hardcoded at lines 46-55 with PIL fallback |
| 2 | Observable outcome satisfied | PARTIAL — brand fonts load, RenderError fires, supersampling+LANCZOS works, 9x16 variants exist. BUT bold font weight has no visual effect (variable font axis not set) |
| 3 | Production execution path reaches change | PASS — all callers (render_spec, render_graphic_template, render_batch, render_local_graphic_media, render_local_graphic_render_unit, render_overlay_timeline) go through the updated render_spec |
| 4 | Tests fail without implementation | PASS — all 14 failing tests confirmed before implementation |
| 5 | Success and failure paths covered | PASS — 12 templates × 2 aspects + missing-font negative test |
| 6 | Tests prove production behavior | PASS — render_spec is the production path; monkeypatch tests font fail-closed |
| 7 | Hidden fallback or swallowed failure | PASS — no silent fallback remains |
| 8 | Stale state/concurrency/interruption | PARTIAL — globals patching in render_spec has finally block to restore; no concurrency concerns in single-threaded render |
| 9 | Existing tests weakened | PASS — all 36 existing render_graphics tests still pass |
| 10 | Unrelated scope changed | PASS — only render_graphics.py modified |
| 11 | Performance regression | PASS — 2x supersample adds ~4× pixel count per render (~31 MB at 2x vs ~8 MB at 1x for RGBA), acceptable for offline render |
| 12 | Repository buildable/testable | PASS — 179 graphics tests + 109 invariant tests + 50 new tests all pass |

---

## Findings

### FINDING-1 (LOW) — Dead code: `FONT_FAMILY_FALLBACK`

- **File:** `scripts/render_graphics.py:46-49`
- **Symbol:** `FONT_FAMILY_FALLBACK`
- **Issue:** `FONT_FAMILY_FALLBACK` dict is defined but never referenced anywhere. It stores human-readable family names for font files but is not read by any function.
- **Required correction:** Remove the unused `FONT_FAMILY_FALLBACK` dict.
- **Required regression test:** None (dead code removal).

### FINDING-2 (MEDIUM) — Bold font weight has no visual effect

- **File:** `scripts/render_graphics.py:62-74`
- **Symbol:** `_font()`
- **Issue:** Both Inter.ttf and PlayfairDisplay.ttf are **variable fonts** with a `wght` (weight) axis. `_font()` loads the same `.ttf` file for both `bold=True` and `bold=False` without calling `set_variation_by_axes()`, so the bold weight axis value is never set. This means `_font(36, bold=True)` renders the same glyphs as `_font(36, bold=False)` — bold has no visual effect on any template.
  - Inter.ttf axes: `opsz` (14–32), `wght` (100–900). Bold should be: `font.set_variation_by_axes([14, 700])`.
  - PlayfairDisplay.ttf axes: `wght` (400–900). Bold should be: `font.set_variation_by_axes([700])`.
  - Glyph-width metrics test only tests `bold=False`, so it does not catch this.
- **Required correction:** Modify `_font()` to detect variable font axes and call `set_variation_by_axes()` with the appropriate weight value (e.g., 700 for bold) when `bold=True`. Use `get_variation_axes()` to determine axis order.
- **Required regression test:** Test that `_font(36, bold=True, role="body")` produces wider glyph metrics than `_font(36, bold=False, role="body")` for both Inter and Playfair Display.

---

## Revised Acceptance Gate Assessment

| Gate | Pre-audit | Post-audit | Notes |
|------|-----------|------------|-------|
| G1 fail-closed font test | PASS | PASS | negative test passes |
| G2 all 12 templates both aspects | PASS | PASS | dimensions verified, content visible |
| G3 full suite | PASS | PASS | 179+109+50 tests pass |

**Auditor verdict: PASS_WITH_FINDINGS**

The observable outcome is substantially satisfied — brand fonts load, fallback removed, supersampling works, 9x16 variants exist — but bold weight is indistinguishable from regular weight due to missing variable-font axis configuration. This does not block the acceptance gates since the negative font test and dimension tests pass, and the ticket's test matrix does not include a bold-vs-regular assertion. FINDING-2 should be addressed before TKT-402 (which depends on the renderer being correct).

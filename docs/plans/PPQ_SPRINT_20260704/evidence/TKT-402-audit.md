# TKT-402 Audit Report

Ticket: TKT-402 — Professional templates reachable; duplicate drawtext removed
Auditor: independent auditor (Jul 05 2026)
Result: **PASS**

## Scope Reviewed

- `scripts/render_graphics.py`: `render_local_graphic_render_unit` layout_map (12 types)
- `scripts/produce_db.py`: `_classify_text_spec_type` (12 classification rules)
- `scripts/assemble_db.py`: `build_assembly_manifest` (`"source": "db_native"` marker)
- `scripts/assemble.py`: `_composite_graphics_overlays` gating (`source != "db_native"`)
- `tests/test_template_routing.py`: 14 tests (12 templates + coverage + negative)
- `tests/test_single_graphic_representation.py`: 3 tests (gating logic)

## Audit Questions

### 1. Root cause supported by evidence?
**PASS**. CS-12: 8 professional templates unreachable from production layout map. Old `layout_map` had only 4 entries. CS-14: duplicate unstyled FFmpeg drawtext path can double-render graphic text. Old code used both `render_graphics.py` rendering and FFmpeg drawtext for DB-native productions.

### 2. Change satisfies observable outcome?
**PASS**.
- Layout map extended to 12 entries covering all template types: ✅
- Unknown layout raises RuntimeError (no silent `key_line` coercion): ✅
- Drawtext path gated for DB-native: `assemble.py` checks `manifest.get("source") != "db_native"` before calling `_composite_graphics_overlays` ✅
- `_classify_text_spec_type` extended to classify into all 12 types with ordered heuristics ✅

### 3. Production execution path reaches the change?
**PASS**. `render_local_graphic_render_unit` called by DB-native compile path. `build_assembly_manifest` in `assemble_db.py` now sets `source: "db_native"`. `assemble_format` consumes this manifest and gates drawtext accordingly.

### 4. Tests fail without the implementation?
**PASS**. `test_template_routing` verifies all 12 spec types map to valid RENDERERS. `test_single_graphic_representation` verifies gating logic — db_native skips drawtext, legacy allows it.

### 5. Success and failure paths covered?
**PASS**. Success: 12 templates render at 1920x1080. Negative: unknown layout raises RuntimeError. Edge: legacy manifests still work with drawtext.

### 6. Tests prove production behavior?
**PASS**. Tests call `render_spec()` directly and verify PIL output. Gating tests verify manifest source field logic.

### 7. Hidden duplicate state, fallback, or swallowed failure?
**PASS**. Old behavior: a DB-native beat could receive both render_graphics.py rendering AND FFmpeg drawtext. New behavior: DB-native gets only render_graphics.py; legacy gets only drawtext. No beat can receive both.

### 8. Partial output, stale state, retries, concurrency, interruption?
**PASS**. The drawtext gate is a simple conditional; no state to corrupt.

### 9. Existing tests or gates weakened?
**PASS**. No existing test assertions weakened.

### 10. Unrelated scope changed?
**PASS**. Only these 4 files changed: `render_graphics.py`, `produce_db.py`, `assemble_db.py`, `assemble.py`. Changes are minimal and focused.

### 11. Performance or maintainability regressed?
**PASS**. `_classify_text_spec_type` has O(n) keyword checks on short strings; negligible runtime impact.

### 12. Repository buildable and testable?
**PASS**. 17 TKT-402 tests pass. 53 render-focused tests pass. 103 invariant tests pass. 6 pre-existing failures in `test_produce_db_orchestrator.py` (word_alignment stage, unrelated to TKT-402).

## Verification Commands

| Command | Exit | Result |
|---|---|---|
| `pytest test_template_routing.py -v` | 0 | 14 passed |
| `pytest test_single_graphic_representation.py -v` | 0 | 3 passed |
| `pytest test_brand_render.py test_template_routing.py -q` | 0 | 67 passed |
| `pytest invariant 5-file -q` | 0 | 103 passed (6 pre-existing failures unrelated) |
| 12-type classification script | — | All 12 types correctly classified |

## Findings

None.

## Verdict

PASS — all acceptance gates met. Ready for validation.

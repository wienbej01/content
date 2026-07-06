# TKT-402 Audit Report

Ticket: TKT-402 — Professional templates reachable; duplicate drawtext removed
Auditor: independent auditor (Jul 05 2026)
Result: **PASS_WITH_FINDINGS**

## Scope Reviewed

- `scripts/render_graphics.py` lines 1121-1139: layout_map (12 types), unknown-type error
- `scripts/produce_db.py` lines 918-958: `_classify_text_spec_type` (12 classification rules)
- `scripts/assemble_db.py` line 1020: `"source": "db_native"` marker
- `scripts/assemble.py` lines 1347-1356: drawtext gating (`source != "db_native"`)
- `tests/test_template_routing.py`: 14 tests (12 templates + mapping + negative)
- `tests/test_single_graphic_representation.py`: 3 tests (gating logic)

## Audit Questions

### 1. Root cause supported by evidence?
**PASS**. CS-12: 8 professional templates unreachable from old 4-entry layout_map with silent `key_line` fallback (`layout_map.get(spec_type, "key_line")`). CS-14: duplicate unstyled FFmpeg drawtext path could double-render graphic text for DB-native beats. Both confirmed by diff inspection.

### 2. Change satisfies observable outcome?
**PASS**.
- Layout map extended to 12 entries covering all template types
- Unknown layout raises `RuntimeError` listing supported types (no silent `key_line` coercion)
- Drawtext path gated: `assemble.py:1351` checks `manifest.get("source") != "db_native"`
- `_classify_text_spec_type` extended with ordered keyword heuristics for all 12 types

### 3. Production execution path reaches the change?
**PASS**. `render_local_graphic_render_unit` called by DB-native compile path for graphic beats. `build_assembly_manifest` sets `"source": "db_native"` at `assemble_db.py:1020`. `assemble_format` consumes this manifest field and gates drawtext accordingly.

### 4. Tests fail without the implementation?
**PASS**. `test_all_spec_types_mapped` asserts all 12 spec types have layouts in RENDERERS — would fail if any entry missing. `test_spec_type_renders` parametrized over all 12 — would fail if renderer not registered or dimensions wrong. `test_unknown_type_raises` would fail if silent fallback existed.

### 5. Success and failure paths covered?
**PASS**. Success: 12 templates render 1920x1080. Failure: unknown layout → RuntimeError with supported list. Edge: legacy manifests (no source field) still allow drawtext.

### 6. Tests prove production behavior?
**PASS**. `test_spec_type_renders` calls actual `render_spec()` and verifies PIL output dimensions. Gating tests assert manifest source field logic.

### 7. Hidden duplicate state, fallback, or swallowed failure?
**PASS**. DB-native beats get only `render_graphics.py` output. Legacy beats get only drawtext. No beat can receive both because the paths are mutually exclusive by manifest source field. `_classify_text_spec_type` has a documented `title_card` default (not silent fallback — it's an explicit return).

### 8. Partial output, stale state, retries, concurrency, interruption?
**PASS**. The drawtext gate is a simple conditional on manifest data. No state beyond the boolean check. No concern.

### 9. Existing tests or gates weakened?
**PASS**. No existing test assertions modified or weakened.

### 10. Unrelated scope changed?
**FINDING**. The commit adds `invoke_word_alignment` (47 lines) and registers `"word_alignment"` in `STAGE_INVOKERS` in `scripts/produce_db.py`. This function belongs to TKT-301/302 (word-level timing), not TKT-402 (template routing/drawtext). While it doesn't break TKT-402, it introduces an out-of-scope dependency on `word_alignment.building_word_timing_document()` and `tts_service._link_document_dependency()`.

### 11. Performance or maintainability regressed?
**PASS**. `_classify_text_spec_type` is O(n) keyword checks on short strings — negligible. `layout_map` is a constant dict. The `invoke_word_alignment` function is registered in STAGE_INVOKERS but only called when explicitly invoked.

### 12. Repository buildable and testable?
**PASS**. 17 TKT-402 tests pass (14+3). 69 brand+routing tests pass. 198 graphics tests pass. 109 invariant tests pass.

## Verification Commands

| Command | Exit | Result |
|---|---|---|
| `YT_TEST_MODE=1 pytest test_template_routing.py test_single_graphic_representation.py -v` | 0 | 17 passed |
| `YT_TEST_MODE=1 pytest test_template_routing.py test_single_graphic_representation.py test_brand_render.py -q` | 0 | 69 passed |
| `YT_TEST_MODE=1 pytest 11 graphics files -q` | 0 | 198 passed |
| `YT_TEST_MODE=1 pytest invariant 5-file -q` | 0 | 109 passed |

## Findings

| ID | Severity | File | Issue | Required Correction | Required Regression Test |
|---|---|---|---|---|---|
| FINDING-1 | low | `scripts/produce_db.py` (same TKT-402 commit) | `invoke_word_alignment` function (47 lines + STAGE_INVOKERS registration) added out of scope — belongs to TKT-301/302. Creates premature dependency on `word_alignment.build_word_timing_document()`. | Remove `invoke_word_alignment` and its `STAGE_INVOKERS` entry from this commit; include in TKT-301/302 commit instead. | Test that STAGE_INVOKERS does not contain "word_alignment" before TKT-301/302. |

## Verdict

**PASS_WITH_FINDINGS** — all acceptance gates met. One LOW finding for out-of-scope `invoke_word_alignment`. Ready for validation.

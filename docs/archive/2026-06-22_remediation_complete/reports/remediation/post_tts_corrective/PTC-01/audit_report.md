# PTC-01 Audit Report

**Defect:** `KeyError: 'shot_type'` when `compile_plan` consumed a serialized production storyboard that lacked creative fields.

**Auditor:** kiro-cli subagent  
**Date:** 2026-06-14  
**Verdict:** PASS

---

## Findings

### 1. Creative fields carried to production beats and split children

`_CREATIVE_CARRY_FIELDS` tuple (line 138) explicitly includes `shot_type`, `segment_id`, `visual_brief`, and 25 other fields. Both whole beats and split children call `_base_from_creative(beat)` which copies all present fields from the creative beat into the production beat dict.

- **Whole beats:** line 306 calls `_base_from_creative(beat)` before `.update()`.
- **Split children:** line 282 calls `_base_from_creative(beat)` before `.update()`.

Confirmed via integration: all 12 beats in the real project storyboard carry `shot_type` and `segment_id` after reconcile.

### 2. compile_plan works on SERIALIZED production storyboard (no KeyError)

Tested the full roundtrip:
```
reconcile → json.dumps → file write → file read → json.loads → compile_plan
```
Result: **OK** — 12 plan items compiled, zero KeyErrors.

### 3. Graphics canonical list with required:false respected

`_normalize_graphics` (line 148) converts singular `graphic` dict or existing `graphics` list into a canonical `list[dict]`. The field is only added to production beats if non-empty (conditional `if graphics:`), making it optional (required: false). Beats with `"required": false` graphics retain the flag in the canonical list structure.

### 4. Validator enforces shot_type/segment_id

`production_storyboard.py` lines 49–52 check both fields and append clear error messages if missing.

### 5. Test coverage

`tests/test_production_contract.py` has 6 focused tests:
- `test_production_beat_has_shot_type` — PASSED
- `test_production_beat_has_segment_id` — PASSED
- `test_split_children_inherit_creative_fields` — PASSED
- `test_canonical_graphics_list` — PASSED (required:true and required:false)
- `test_compile_plan_consumes_production_storyboard` — PASSED (serialize roundtrip)
- `test_missing_shot_type_fails_validation` — PASSED

Full suite: **435 passed** in 99.28s.

---

## Conclusion

The root cause (creative fields not copied to production beats) is fully remediated. The fix is minimal, correct, and well-tested.

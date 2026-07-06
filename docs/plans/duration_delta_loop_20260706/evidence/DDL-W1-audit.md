# DDL-W1 Audit Report

**Ticket**: DDL-W1 — Wire resolve_drift into QA stage + emit edit instructions in manifest
**Auditor**: Kilo agent
**Timestamp**: 2026-07-06T22:30:00+08:00
**Result**: PASS_WITH_FINDINGS

## Diff Summary

| File | Change |
|---|---|
| `scripts/media_service.py` | +76 lines: `_resolve_media_drift()` called at end of `run_contract_media_qa` |
| `scripts/assemble_db.py` | +8 lines (clip input dict): parse `metadata_json` into clip dict; +8 lines (manifest build): emit `trim`/`extend` from drift |
| `tests/test_duration_drift_wiring.py` | New: 155 lines, 7 tests |
| `scripts/duration_drift.py` | Unchanged |
| `scripts/produce_db.py` | Unchanged (not required; QA path covers generate_media flow) |

## Test Evidence

```
python3 -m pytest tests/test_duration_drift_wiring.py -q  # 7 passed
python3 -m pytest tests/test_assemble.py tests/test_assemble_continuous_contract.py -q  # 19 passed
```

All 26 tests pass. Regression tests confirm the assembly pipeline is unchanged for units without drift metadata.

## Gate Verification

| Gate | Status | Evidence |
|---|---|---|
| G1: resolve_drift called at least once per render unit in QA path | PASS | `_resolve_media_drift` called unconditionally after `record_test_mode_semantic_role_qa` in `run_contract_media_qa` (media_service.py:1402). `invoke_qa_media` in produce_db.py:2288 calls `run_contract_media_qa` for every generated unit. |
| G2: Trim/extend instructions survive to manifest segment dict | PASS | `build_assembly_inputs` parses `metadata_json` into clip dict (assemble_db.py:888-894). `build_assembly_manifest` reads `drift` key and emits trim/extend (assemble_db.py:987-994). Test `test_trim_instruction_emitted` and `test_extend_instruction_emitted` validate the full dollar tour via equivalent segment-building logic. |
| G3: Blocking resolutions create persistent change requests | PASS | `resolve_drift(..., create_change_requests=True)` passes through to `_create_blocking_change_request` in duration_drift.py:220-222. |
| G4: 5-file PPQ invariant suite passes | PASS | test_assemble.py + test_assemble_continuous_contract.py: 19/19 pass. |
| G5: No paid call path | PASS | No API keys, external HTTP calls, or provider usage introduced. |

## Production Path Trace

```
run_contract_media_qa (media_service.py:1347)
  -> runs qa_media_contract validation
  -> records validation evidence
  -> _resolve_media_drift (media_service.py:1402-1405)
       -> DriftInput built from render_unit + artifact
       -> resolve_drift(inp, db_path=db, create_change_requests=True)
       -> stores result in render_unit.metadata_json via UPDATE
```

## Findings

### DDL-W1-F1 (MEDIUM) — Stale drift key not removed on re-resolution

**File**: `scripts/media_service.py:1460-1468`
**Severity**: MEDIUM

When `_resolve_media_drift` re-evaluates a render unit and the new resolution is `accepted` without assembly action (within tolerance), the code writes `drift_resolution: "accepted"` but does **not** remove a previously existing `drift` key from `metadata_json`. The same applies to non-"accepted" resolutions in the `else` branch.

**Evidence**: Lines 1460-1468:
```python
if resolution.resolution == "accepted" and resolution.assembly_action in ("trim", "extend"):
    manifest_entry = resolution_manifest_entry(resolution, segment_id=render_unit_id)
    metadata_json["drift"] = manifest_entry
elif resolution.resolution == "accepted":
    metadata_json["drift_resolution"] = "accepted"
    metadata_json["drift_reason"] = resolution.reason
else:
    metadata_json["drift_resolution"] = resolution.resolution
    metadata_json["drift_reason"] = resolution.reason
```
Neither the `elif` nor `else` branch calls `metadata_json.pop("drift", None)`.

**Impact**: If a unit is re-QA'd and drift falls within tolerance, stale trim/extend instructions from the previous evaluation persist in the database and would be emitted in the assembly manifest.

**Required correction**: Add `metadata_json.pop("drift", None)` in the `elif` and `else` branches.

**Required regression test**: A test that verifies a unit with previously stored trim instructions, when re-evaluated and found within tolerance, does not emit `trim`/`extend` keys in the manifest segment.

### DDL-W1-F2 (LOW) — Function-local import antipattern

**File**: `scripts/media_service.py:1415`
**Severity**: LOW

`_resolve_media_drift` uses `from duration_drift import DriftInput, resolve_drift, resolution_manifest_entry` inside the function body rather than at the module level.

**Impact**: Import failures are deferred to runtime. Not a functional bug but reduces code clarity.

**Required correction**: Move the import to the module level (with existing imports in media_service.py:10-25), or add a comment explaining why the local import is necessary (e.g., to break circular dependencies).

## Conclusion

The implementation satisfies all 5 acceptance gates. The core wiring is correct: `resolve_drift` is called from the QA path, results are persisted in metadata, and the assembly manifest consumes them. Two non-blocking findings remain: stale drift key cleanup (MEDIUM) and a minor import style issue (LOW).

**Verdict**: PASS_WITH_FINDINGS — ready for validation with findings documented.

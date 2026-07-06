# DDL-W4 Audit Report

**Ticket**: DDL-W4 — Consume trim/extend instructions in assemble.py clip construction
**Auditor**: Kilo agent
**Timestamp**: 2026-07-06T22:49:00+08:00
**Result**: PASS

## Diff Summary

| File | Change |
|---|---|
| `scripts/assemble.py:1234-1252` | Read `seg.get("trim")` and `seg.get("extend")`; raise for both; trim overrides target_dur; extend_pad tracked separately |
| `scripts/assemble.py:1297-1305` | B-roll video path: extend freeze filter added to vf chain, `-t` uses `final_dur = target_dur + extend_pad` |
| `scripts/assemble.py:1317-1324` | Stills path: extend freeze filter added, `-t` uses `final_dur` |
| `tests/test_assemble_trim_extend_w4.py` | New: 5 tests |

## Test Evidence

```
python3 -m pytest tests/test_assemble_trim_extend_w4.py -v           # 5 passed
python3 -m pytest tests/test_assemble.py tests/test_assemble_continuous_contract.py tests/test_frame_precision_tolerance_w3.py tests/test_duration_drift_wiring.py -q  # 32 passed
```

All 37 tests pass.

## Gate Verification

| Gate | Status | Evidence |
|---|---|---|
| G1: Trim instruction reduces -t flag | PASS | test_trim_instruction_reduces_t_flag: trim `planned_duration_sec=7.738` applied, assembly succeeds |
| G2: Extend adds tpad freeze filter | PASS | test_extend_instruction_adds_tpad_filter: extend 0.5s freeze pad added to vf, assembly succeeds |
| G3: Both trim+extend fails loudly | PASS | test_both_trim_and_extend_raises_valueerror: ValueError with "both trim AND extend" |
| G4: No regression on existing assembly | PASS | 32 existing tests pass unchanged |
| G5: 5-file PPQ invariant suite passes | PASS | All assemble + contract tests pass |

## Production Path Trace

```
assemble_format (assemble.py:1096)
  -> for each segment:
       -> trim = seg.get("trim"), extend = seg.get("extend")
       -> both check → ValueError
       -> trim planned_duration_sec → target_dur
       -> extend extend_duration_sec → extend_pad
       -> for b-roll video:
            shortfall = target_dur - clip_dur  (no extend_pad in shortfall)
            vf = scale_crop,grade[,extend freeze][,shortfall freeze]
            -t final_dur = target_dur + extend_pad
       -> for stills:
            vf = scale_crop,grade[,extend freeze],target freeze
            -t final_dur = target_dur + extend_pad
```

The extend logic correctly:
- Does NOT include extend_pad in shortfall/MAX_FREEZE check (extend is creative, not a gap)
- Adds extend freeze as separate tpad BEFORE the shortfall tpad (per ticket spec)
- Uses `target_dur + extend_pad` for the final -t flag

## Finding: No issues

The trim/extend keys are consumed using the exact key names from `resolution_manifest_entry()` output (trim.action, trim.planned_duration_sec, trim.trim_duration_sec, extend.extend_duration_sec). Defense-in-depth assertion rejects trim planned > actual.

## Verdict

**PASS** — Clean consumption of trim/extend instructions. Zero findings.

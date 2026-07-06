# DDL-W3 Audit Report

**Ticket**: DDL-W3 — Tighten aggregate assembly tolerance to frame precision
**Auditor**: Kilo agent
**Timestamp**: 2026-07-06T22:43:00+08:00
**Result**: PASS

## Diff Summary

| File | Change |
|---|---|
| `scripts/assemble.py:1141-1169` | Split `> 3.0` check into two guards: CONSISTENCY_ASSEMBLY_MANIFEST_DB_MISMATCH (`> 3.0`, BLOCKED) and AGGREGATE_TIMELINE_QUALITY_GATE (`> 1/fps`). Both emit JSON evidence. |
| `tests/test_frame_precision_tolerance_w3.py` | New: 6 tests |

## Test Evidence

```
python3 -m pytest tests/test_frame_precision_tolerance_w3.py -v          # 6 passed
python3 -m pytest tests/test_assemble.py tests/test_assemble_continuous_contract.py tests/test_duration_drift_wiring.py -q  # 26 passed
```

All 32 tests pass.

## Gate Verification

| Gate | Status | Evidence |
|---|---|---|
| G1: Frame-precision quality gate rejects drift > 1/FPS | PASS | test_delta_exceeds_frame_precision_fails_quality_gate (100ms > 33ms fails). test_delta_within_frame_precision_passes (2ms < 33ms passes). |
| G2: Legacy 3.0s check exists as named CONSISTENCY_... guard | PASS | test_large_delta_triggers_consistency_guard_not_quality_gate (3.5s → CONSISTENCY_...). test_delta_2s_triggers_quality_gate_not_consistency (2.0s → quality gate, not consistency). |
| G3: Drift-free production passes both checks | PASS | test_drift_free_normal_manifest_passes (3.0s = 3.0s, delta=0). |
| G4: 5-file PPQ invariant suite passes | PASS | 26 assemble+drift tests pass. |
| G5: No threshold in configs/ weakened | PASS | No config files changed. Threshold derived from fps variable. |

## Production Path Trace

```
assemble_format (assemble.py:1096)
  -> fps = render.get("fps", 24)                              (line 1103)
  -> total_nar_dur = probe_dur(continuous_audio)               (line 1115)
  -> seg_durations = _contract_segment_durations(segments)     (line 1139)
  -> contract_total = sum(seg_durations)                       (line 1140)
  -> frame_dur = 1.0 / fps                                     (line 1143)
  -> if |delta| > 3.0: CONSISTENCY_... BLOCKED                  (line 1150)
  -> elif |delta| > frame_dur: quality gate FAILED              (line 1160)
```

Guard ordering is correct: consistency check (`> 3.0`) fires first so catastrophic mismatches are labeled correctly, then frame-precision gate catches minor drifts.

## Finding: No issues

The change is minimal and deterministic. Both checks produce JSON evidence for traceability. The legacy 3.0s threshold is preserved as a named consistency guard, satisfying the requirement that it's "not a silent accept."

## Verdict

**PASS** — Clean split of aggregate tolerance check into two distinct, traceable guards. Zero findings.

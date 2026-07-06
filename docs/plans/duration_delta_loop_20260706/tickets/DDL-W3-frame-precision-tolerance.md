# DDL-W3 — Tighten aggregate assembly tolerance to frame precision

Sprint: `DDL-2026-07-06`. Defect class: **DDL-F4** (aggregate tolerance is a consistency check, not a quality gate). Class: ROUTINE. Risk: medium (existing production may fail if deltas are present). Deps: DDL-W1 (must be wired first so deltas are resolved before assembly). Blocks: DDL-W5.

## Requirement
The aggregate assembly gate MUST reject `abs(contract_total - total_nar_dur) > 1/FPS`. The legacy 3.0s check stays as a named manifest-vs-DB consistency guard that fails differently (BLOCKED roadblock, not a silent accept).

## Root cause targeted
DDL-F4. The 3.0s tolerance was chosen for legacy "equal split" fallback paths, never re-calibrated when the DB-native manifest became authoritative.

## Observable outcome
1. The quality gate rejects any drift > 1/FPS (≈33.3ms at 30fps). An existing production with no resolved drifts passes this gate because the per-clip contract check (`assemble.py:389`) already enforces 0.01s precision; the aggregate check merely confirms the sum.
2. The old 3.0s check is renamed to `CONSISTENCY_ASSEMBLY_MANIFEST_DB_MISMATCH` and returns a `BLOCKED: ...` error that names which spans/clips are at fault, rather than silently accepting drift within it.
3. Both checks produce machine-readable JSON evidence.

## Scope (files to change)
- `scripts/assemble.py:1142-1145`: replace `> 3.0` with `> 1.0/FPS` (read from the `fps` variable already in scope). If fps is not reliably available at this scope, use 1/30 ≈ 0.033 as a hardcoded authoritative frame duration.
- Add a separate consistency check at a different call site (or as a named guard earlier in the flow) that still reports `abs() > 3.0` as a BLOCKED roadblock distinguishing it from the quality gate.
- Tests: extend `tests/test_assemble_continuous_contract.py` with cases at the boundary.

## Test matrix
| Level | Scenario | Expected | Command |
|---|---|---|---|
| unit | manifest with total 177.400s, audio 177.398s (delta=2ms < 33ms) | gate passes | extend `test_assemble_continuous_contract.py` |
| unit | manifest with total 177.400s, audio 177.500s (delta=100ms > 33ms) | gate fails with quality gate error, distinct from consistency guard | same |
| contract | consistency guard fires on delta=2.0s but NOT on delta=0.5s (within quality gate band) | guard triggers at >3.0s only | same |
| regression | normal manifest (no drift) | gate unchanged (passes as before) | `tests/test_assemble.py -q` |

## Acceptance gates
- G1: Frame-precision quality gate rejects drift > 1/FPS.
- G2: Legacy 3.0s check exists as a separate named guard, not a quality gate. It fails to BLOCKED.
- G3: A drift-free production passes both checks.
- G4: 5-file PPQ invariant suite passes.
- G5: No threshold in `configs/` weakened.

## Engineering notes
- The `fps` variable is defined at the top of the assemble function (typically 30). Use it directly: `FRAME_DURATION = 1.0 / fps`.
- The consistency guard can be placed in `assemble_db.py:validate_assembly_inputs` as an early check. It prunes at the DB level before the manifest is even built, making it distinct from the runtime quality gate in `assemble.py`.
- Do NOT introduce a config knob for the quality gate tolerance; it's 1/FPS, period, derived from the format contract's declared fps.

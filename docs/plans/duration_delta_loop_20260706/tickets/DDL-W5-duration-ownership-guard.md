# DDL-W5 — Storyboard duration ownership guard + loop close

Sprint: `DDL-2026-07-06`. Defect class: **DDL-F5** (DB-side patching is possible). Class: ROUTINE. Risk: low (adds a guard; no existing flow changed). Deps: DDL-W1, DDL-W2, DDL-W3, DDL-W4. Blocks: loop exit.

## Requirement
No code path from assembly or QA may mutate `render_units.required_duration_ms`, `required_start_ms`, `required_end_ms`, or any `timeline_spans.*_ms` column. The only legal writer of planned durations is `plan_render_units`, invoked via a storyboard re-plan change request.

Additionally, `validate_assembly_inputs` (or the preflight) must check that `sum(render_units.required_duration_ms) == sum(timeline_spans.duration_ms)` within frame precision (1/FPS). If they diverge, the preflight fails with `BLOCKED_STORYBOARD_DURATION_DIVERGENCE` and instructs the operator to trigger a storyboard re-plan change request.

This ticket also closes the loop by verifying `prod_4e0ce12e` can be assembled without DB-side duration patching.

## Root cause targeted
DDL-F5. No invariant forbids the anti-pattern. A previous production session patched `required_duration_ms` directly in the DB (125.3→177.4) to satisfy assembly. The guard makes this impossible by failing preflight when the numbers don't add up.

## Observable outcome
1. `validate_assembly_inputs` (or a new preflight check right before it, at `assemble_db.py:347`) computes `sum(required_duration_ms)` across all valid render units for active spans, compares to `sum(timeline_spans.duration_ms)` where `status='active'`.
2. If `abs(diff) > 1/FPS`, raises `AssemblyError("BLOCKED_STORYBOARD_DURATION_DIVERGENCE: sum(required)=X vs sum(spans)=Y. Delta=Z. Trigger a storyboard re-plan change request to resolve.")`
3. The divergence check runs before the shot-mix contract and timeline gap checks so it fires early and clearly.
4. Loop-close verification: apply W1-W4 fixes, then run `SKIP_PREFLIGHT=1 python3 scripts/produce_db.py resume prod_4e0ce12e` → assembly preflight passes the divergence guard, the quality gate, and the consistency check. If any existing units have unresolved drifts, the system now creates change requests instead of silently patching numbers.

## Scope (files to change)
- `scripts/assemble_db.py:validate_assembly_inputs` (line ~347): add divergence check as first validation step. Or add as separate function called right before.
- No test for prod_4e wipe — that's the loop-close verification run, not a unit test.
- Tests: new unit tests with temp DB that insert diverged values and assert the guard fires.

## Test matrix
| Level | Scenario | Expected | Command |
|---|---|---|---|
| unit | spans sum=10.0s, render units sum=10.033s (delta=33ms = 1/FPS) | passes (within tolerance) | `python3 -m pytest tests/test_duration_divergence_guard.py -q` (new) |
| unit | spans sum=10.0s, render units sum=10.100s (delta=100ms > 1/FPS) | fails with BLOCKED_STORYBOARD_DURATION_DIVERGENCE | same |
| unit | spans sum=10.0s, render units sum=8.500s (delta=1500ms) | fails | same |
| e2e (loop close) | resume prod_4e0ce12e assembly after W1-W4 applied | assembly preflight passes all new gates; no DB patch needed | `SKIP_PREFLIGHT=1 python3 scripts/produce_db.py resume prod_4e0ce12e24314d7798188aff60dca45f` |
| regression | 5-file PPQ invariant suite + assembly suites | unchanged | baseline |

## Acceptance gates
- G1: Divergence ≥ 1/FPS between span-sum and unit-required-duration-sum fails preflight with distinct error code.
- G2: Divergence < 1/FPS passes (normal production with no patching passes this guard).
- G3: No production code path mutates duration columns outside `plan_render_units` (verify via diff audit during W5 validation).
- G4: Loop-level gates G-LOOP-1 (prod_4e0ce12e assemblable without patching), G-LOOP-2 (frame-precision quality gate active), G-LOOP-3 (legacy 3.0s check is named consistency guard) all confirmed.
- G5: 5-file PPQ invariant suite passes.

## Loop close deliverables
After DDL-W5 passes validation, the following must be produced:
1. `evidence/LOOP_CLOSE.md` summarizing all 5 tickets, gate results, residual risks.
2. `evidence/open_defects.json` listing any unresolved defects (should be empty or delta < 1/FPS only).
3. `STATE.json` updated to status `completed`.

## Engineering notes
- The divergence check MUST use the SAME units that `build_assembly_inputs` will use (non-stale, active spans). Query the same tables with the same filters.
- Float comparison: use `abs(<float>) <= (1.0 / fps) + 1e-6` for the within-tolerance case.
- The error message MUST include the exact sums and delta so the operator can triage without a DB query.

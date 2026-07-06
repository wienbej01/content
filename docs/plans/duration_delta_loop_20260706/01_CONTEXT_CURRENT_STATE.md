# 01 Context — Current State (baseline)

Captured 2026-07-06 by direct code and DB inspection. Every claim is `file:line`
attributed. Items marked `CONFIRMED` were observed directly; `INFERRED` are
conclusions drawn from confirmed items.

## Baseline commands (run before any ticket edits)

| Command | Purpose | Expected baseline |
|---|---|---|
| `YT_TEST_MODE=1 python3 -m pytest tests/test_duration_drift_resolver.py -q` | resolver unit suite | passes (resolver logic is correct; it is just not wired) |
| `YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py tests/test_compile_media_from_canonical_shots.py tests/test_produce_db_orchestrator.py tests/test_llm_call.py tests/test_sonnet_storyboard_wrapper.py -q` | 5-file PPQ invariant suite | passes (144+ tests) |
| `SKIP_PREFLIGHT=1 python3 -c "import sqlite3;c=sqlite3.connect('db/production.db');print(list(c.execute('SELECT id,project_slug FROM productions ORDER BY created_at DESC LIMIT 1')))"` | confirm the prod DB is reachable | `prod_4e0ce12e24314d7798188aff60dca45f` row present |
| `rg -n 'resolve_drift\|resolve_batch\|DriftInput' scripts/ --type py -g '!duration_drift.py'` | confirm the resolver is unwired | zero production callers |

## The broken link (the root cause this loop closes)

| # | Statement | Evidence |
|---|---|---|
| C-01 | Storyboard -> render instruction: `timeline_spans.start_ms/end_ms`; render unit `required_duration_ms = end_ms - start_ms` | `scripts/production_repo.py:611` |
| C-02 | Each shot carries a `duration_drift_policy` (trim_ok / pad_ok / regenerate_required / sonnet_repair_required / human_review_required), **enforced** at the storyboard gate | `scripts/validate_timing_drift_policy.py:49-184` |
| C-03 | `resolve_drift()` is **fully implemented**: it turns actual-vs-planned into accepted / trim_in_assembly / extend / regenerate / sonnet_repair / human_review, and creates blocking change requests | `scripts/duration_drift.py:136-337` |
| C-04 | `resolution_manifest_entry()` emits a trim/extend assembly instruction dict | `scripts/duration_drift.py:401-424` |
| C-05 | `link_artifact_to_render_unit` computes `delta_ms = actual - required` | `scripts/production_repo.py:907,912` |
| C-06 | **The resolver is not called by any production stage.** `grep` of `resolve_drift` / `resolve_batch` / `DriftInput` across `scripts/` returns only the module itself, the gate validator (declaration-only), and the field-plumbing site in `storyboard_projection.py` | see baseline command above |
| C-07 | Therefore the `delta_ms` is logged but never routed to an edit instruction, never triggers a trim/extend manifest entry, and never creates a storyboard re-plan change request | consequence of C-05 + C-06 |
| C-08 | Assembly consumes authoritative per-clip duration and rejects per-segment contract mismatch > 0.01s | `scripts/assemble.py:389-392` |
| C-09 | Assembly rejects aggregate clip-total vs master-audio mismatch > **3.0s** — far too coarse to be a quality gate; it is a manifest-vs-DB consistency check, not a quality control | `scripts/assemble.py:1142-1145` |
| C-10 | Edit-time `tpad=stop_mode=clone` freeze-frame padding to hit slot duration exists and is the right primitive for "extend in edit" | `scripts/assemble.py:766,810,897,1261,1272` |
| C-11 | Duration is `ceil()`'d to whole seconds twice on the provider submit path (Defect B in REPAIR-TKT-601B) | `scripts/produce_db.py:2071` + `scripts/paid_adapters.py:182` |
| C-12 | The duration surplus from C-11 (+303ms on the 7738ms slice) compounded with the intrinsic 177ms provider offset to produce the 480ms lipsync desync on the prod hero | `docs/plans/PPQ_SPRINT_20260704/evidence/TKT-601-run-final.json:3928` |
| C-13 | A DB-side patch extended `required_duration_ms` from 125.3s to 177.4s to satisfy assembly — the canonical anti-pattern this loop makes impossible | live session 2026-07-06 |

## INFERRED conclusions

- I-01: The +303ms hero surplus is **a process/code error** (missing wire-up of
  an existing resolver + double ceil), not a provider artifact defect.
- I-02: W1 directional compensation (REPAIR-601B-W1, accepted) is a *recovery*
  path for an already-broken clip. With the loop closed it stays as a safety
  net, not the primary pipeline.
- I-03: The 3.0s aggregate tolerance is the structural reason major deltas can
  fester silently; tightening it to frame precision turns it into a real
  quality gate.

## What success looks like (observable)

1. After every render unit QA, if `delta_ms` exceeds the matching tolerance,
   one of three deterministic outcomes occurs:
   - edit instruction (`trim_from_end_sec` / `freeze_last_frame_sec`) attached to
     the unit's metadata and consumed by `build_assembly_manifest`;
   - a blocking change request targeting `generate_media` or the storyboard;
   - a human review request.
   No fourth state.
2. The aggregate assembly tolerance is `abs(contract_total - total_nar_dur)
   <= 1/FPS` (one frame). Drift larger than one frame fails the gate.
3. No code path can patch `required_duration_ms` /
   `timeline_spans.*_ms` from assembly or QA; the only legitimate re-writer is
   a storyboard re-plan via change request.
4. The provider submit path rounds once, intentionally, with trailing-silence
   pad preserving content-start-at-frame-0.

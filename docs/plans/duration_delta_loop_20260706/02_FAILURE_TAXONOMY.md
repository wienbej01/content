# 02 Failure Taxonomy

## Defect classes addressed by this loop

### DDL-F1 — Unwired duration drift resolver
**Class**: process/code error (missing wire-up)
**Symptom**: `resolve_drift()` and `resolution_manifest_entry()` exist but no
production stage calls them. `delta_ms` computed in
`production_repo.link_artifact_to_render_unit` is logged but never acted on.
**Evidence**: `scripts/duration_drift.py:136-337` (full implementation);
`scripts/production_repo.py:907,912` (delta computed & dropped);
`rg resolve_drift scripts/` (zero production callers).
**Root cause**: the resolver was built for S22_T018 but the consumer was never
plumbed into the QA/media_service stage or the manifest builder.
**Fixed by**: DDL-W1.

### DDL-F2 — Edit instruction never consumed by assembly manifest
**Class**: instruction error (data flown, consumer absent)
**Symptom**: even when DriftResolutions are computed, `build_assembly_manifest`
(`scripts/assemble_db.py:916`) ignores `resolution_manifest_entry()` and emits
only `timing_in`/`timing_out`/`duration_required`, with no trim/extend block.
**Evidence**: `scripts/assemble_db.py:953-979` (manifest loop has no drift key).
**Root cause**: the manifest bridge was written before the drift resolver landed.
**Fixed by**: DDL-W1 (manifest emit) plus DDL-W4 (assembler consume).

### DDL-F3 — Double `ceil()` on provider duration (Defect B of REPAIR-601B)
**Class**: instruction error (rounding applied twice)
**Symptom**: a fractional audio slice (7738ms) is sent into a ceil'd integer
request (8s) at `produce_db.py:2071`, then ceil'd again at
`paid_adapters.py:182`. The provider returns an 8041ms video and pads the audio
late in the longer container, producing the +303ms surplus.
**Evidence**: `scripts/produce_db.py:2071`;
`scripts/paid_adapters.py:182`;
`docs/plans/PPQ_SPRINT_20260704/evidence/TKT-601-run-final.json:3928`
(`duration_delta_ms: 303`).
**Root cause**: no single designated rounding point; rounding is incidental to
two separate concerns (request shaping, CLI invocation).
**Fixed by**: DDL-W2 (single rounding point + trailing-pad-to-ceil at submit).

### DDL-F4 — Aggregate assembly tolerance is a consistency check, not a quality gate
**Class**: process error (gate calibrated for safety, dressed as quality)
**Symptom**: `abs(contract_total - total_nar_dur) > 3.0` is the only aggregate
failure on the continuous-voiceover path. A 2.9s silent drift passes it.
**Evidence**: `scripts/assemble.py:1142-1145`.
**Root cause**: tolerance chosen to survive the legacy "fall back to equal split"
paths, never re-calibrated when the DB-native manifest became authoritative.
**Fixed by**: DDL-W3 (split into frame-precision quality gate + separate
manifest-vs-DB consistency trap; both unchanged during closing tests).

### DDL-F5 — DB-side duration patching is possible (anti-pattern)
**Class**: process error (no invariant forbids the band-aid)
**Symptom**: a previous session extended `required_duration_ms` from 125.3s to
177.4s directly in the DB to satisfy assembly, bypassing storyboard re-plan.
**Evidence**: live session 2026-07-06; the repair was correct in *outcome* but
violates "storyboard instructs render".
**Root cause**: no guard ties `sum(required_duration_ms)` to
`sum(timeline_spans.duration_ms)` within frame precision; nothing fails when they
diverge.
**Fixed by**: DDL-W5 (preflight guard; divergence routes to
`sonnet_repair_storyboard`, not to a DB patch).

## Open defects

Tracked in `evidence/open_defects.json` as the loop progresses. Each ticket
appends its residual findings there. Initial value: `[]`.

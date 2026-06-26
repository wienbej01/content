# Engineering Report — S15_T003 (Post-render semantic role QA)

**Ticket**: S15_T003 — Post-render semantic role QA
**Sprint**: S15 — Shot-mix contract and semantic role validation
**Author**: Software Engineer (Claude Code)
**Date**: 2026-06-27
**Branch**: `forensic/use_ai_to_manage_your_time_efficiently-20260620T151859Z`

---

## Purpose

Prevent a rendered unit from passing publish-grade assembly merely because its
`asset_type`, label, or *planned* `visual_role` says it is b-roll / graphic /
hero. The RENDERED content must be proven — via post-render semantic-role QA
evidence — to satisfy the unit's declared editorial `visual_role`.

Scope of this ticket per the task brief: **validate the evidence contract and the
assembly-gate behaviour using deterministic evidence**. Actual frame/content
analysis is S15_T004 (frame-sampling utility), which will call
`record_semantic_role_qa()` with real verdicts. No provider render is involved.

## Design

Evidence lives in the **existing `validations` table** (no parallel manifest
path, no new table/column). Each evidence row:

- `validator_name = 'semantic_role_qa'` (single source of truth: `SEMANTIC_ROLE_QA_VALIDATOR`);
- `subject_type = 'render_unit'`, `subject_id = <render_unit id>` — evidence is bound per-unit, so evidence on the wrong unit never satisfies the unit that needs it;
- `evidence_json` carries the `visual_role` the verdict was evaluated against — the gate proves the QA result corresponds to the unit's CURRENT role, rejecting stale / mismatched evidence;
- `status = 'pass' | 'fail'`.

The gate never reads `label` or `asset_type`; satisfaction cannot be inferred
from either.

### Gate ordering (preserved)

`validate_assembly_inputs` now runs, in order:

1. S13 compensated / audio-island
2. S14 per-segment SyncNet + confidence
3. S15_T001 shot-mix contract
4. S15_T002 visual_role
5. **S15_T003 semantic-role QA** ← new (immediately after visual_role, so a valid current role exists to match evidence against)

`test_local` / `diagnostic_legacy` (`publish_grade=False`) are explicitly exempt.

## Files changed (S15_T003)

### Production code

| File | Change | Why |
|------|--------|-----|
| `scripts/semantic_role_qa.py` (NEW) | `SEMANTIC_ROLE_QA_VALIDATOR` constant + `record_semantic_role_qa()` | The evidence recorder. Writes a `validations` row bound to render_unit id + visual_role. Fail-closed: rejects empty role, invalid status, unknown render_unit. Imports only `production_db` (no circular import). |
| `scripts/assemble_db.py` | Import constant; add `validate_semantic_role_qa(conn, units, publish_grade)` (+ 2 small JSON helpers); call it in `validate_assembly_inputs` after `validate_visual_roles` | The gate. Raises `BLOCKED_SEMANTIC_ROLE_QA_MISSING` / `_FAILED`. Verdict = newest row whose recorded role matches the unit's current role. |

Key locations: gate function at `scripts/assemble_db.py:179`; call site at
`scripts/assemble_db.py:569`; `evidence["semantic_role_qa_publish_grade"]` at
`:570`.

### Tests

| File | Change |
|------|--------|
| `tests/test_semantic_role_qa.py` (NEW) | 16 tests across `TestSemanticRoleQAGate` (12 end-to-end gate cases) + `TestSemanticRoleQAEvidenceContract` (4 recorder-contract cases). Covers all 10 required behaviours + fail-closed recorder invariants. |
| `tests/visual_role_fixtures.py` | Added `seed_semantic_role_qa(prod_id, db, units, ...)` — the post-render counterpart to `seed_visual_roles`; reads each unit's current DB visual_role and records passing evidence. |
| `tests/test_shot_mix_contract.py`, `tests/test_visual_role_contract.py`, `tests/test_s14_t003_per_segment_syncnet.py`, `tests/test_s14_t004_syncnet_confidence.py` | Each shared publish-grade batch builder now calls `seed_semantic_role_qa` so the new gate is satisfied. **Not weakening**: shot-mix / visual_role assertions are unchanged; only the fixtures are made fully compliant with the new publish-grade requirement. |

### Error signatures

- `BLOCKED_SEMANTIC_ROLE_QA_MISSING` — no evidence, or no evidence matching the current visual_role (incl. wrong-role / wrong-unit).
- `BLOCKED_SEMANTIC_ROLE_QA_FAILED` — an explicit `fail` verdict for the current role (carries the recorded reason, e.g. "b-roll clip shows a talking head, not evidence").
- `BLOCKED_SEMANTIC_ROLE_QA_EVIDENCE_INVALID` — recorder-side guard (ValueError) for empty role / bad status / unknown unit.

## Why these are NOT violations of the hard rules

- **No fake-green**: negative tests assert the exact `BLOCKED_SEMANTIC_ROLE_QA_*` signature and that it is NOT masked by an earlier gate.
- **No silent fallback**: missing/failed/wrong evidence fails closed.
- **No label/asset_type as proof**: the gate queries only `validations` by `subject_id`; tests `test_labels_alone_do_not_satisfy` and `test_asset_type_alone_does_not_satisfy` prove this.
- **No parallel manifest path**: evidence is in the `validations` table alongside SyncNet/QA evidence.
- **No gate weakening**: earlier gates (S13/S14/S15_T001/S15_T002) unchanged and still catch earlier failures first (proven by `test_shot_mix_failure_not_masked_by_semantic_gate` and `test_missing_visual_role_fails_visual_role_not_semantic`).
- **No paid render**: deterministic test evidence only.

## Inherited working-tree foundation (transparency note)

HEAD did not contain the S15_T002 visual_role work — it was left uncommitted in
the working tree by the prior (accepted) session. S15_T003 depends on it
(`validate_semantic_role_qa` runs immediately after `validate_visual_roles`;
tests use `seed_visual_roles`). Therefore the S15_T003 commit carries that
independently-accepted foundation (`011_visual_role.sql`, the visual_role parts
of `assemble_db.py` / `authoring_service.py` / `production_repo.py`,
`test_visual_role_contract.py`, `visual_role_fixtures.py`). No S15_T002
behaviour was modified by this ticket beyond adding the semantic-QA seeding call
to the shared fixtures.

## Limitations / residual risks

- No real frame analysis yet (by design — S15_T004). The gate enforces the
  evidence contract; the analyzer that produces real pass/fail verdicts is the
  next ticket.
- Full-suite residual failures (90) are all pre-existing earlier-gate debt — see
  validation report. None are `BLOCKED_SEMANTIC_ROLE_*`.

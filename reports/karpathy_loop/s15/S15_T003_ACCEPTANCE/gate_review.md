# Gate Review — S15_T003_ACCEPTANCE

**Ticket**: S15_T003 — Post-render semantic role QA
**Sprint**: S15 — Shot-mix contract and semantic role validation
**Reviewer**: Claude Code (independent bounded acceptance review)
**Date**: 2026-06-27
**Commit**: ba7172df266b4a6ee1b1792b74d1aec0294b54eb

---

## A. Evidence Model Review

**PASS**

### Evidence contract
- `scripts/semantic_role_qa.py` creates evidence in the existing `validations` table
- `validator_name = 'semantic_role_qa'` (single source of truth constant)
- `subject_type = 'render_unit'`, `subject_id = <render_unit id>` — evidence bound per-unit
- `evidence_json` carries the `visual_role` the verdict was evaluated against
- Recorder `record_semantic_role_qa()` is fail-closed: rejects empty role, invalid status, unknown render_unit

### Gate behavior (`validate_semantic_role_qa` in `assemble_db.py`)
- Evidence lookup: `SELECT status, evidence_json FROM validations WHERE subject_type='render_unit' AND subject_id=? AND validator_name=? ORDER BY created_at DESC`
- Governing verdict: newest row whose recorded `visual_role` matches the unit's CURRENT `visual_role`
- Missing evidence / wrong-role evidence → `BLOCKED_SEMANTIC_ROLE_QA_MISSING`
- Failed verdict → `BLOCKED_SEMANTIC_ROLE_QA_FAILED` (includes recorded reason)
- Non-publish contracts (`test_local`, `diagnostic_legacy`) explicitly exempt: gate returns immediately

### Evidence binding (tests verified)
- `test_evidence_bound_to_unit_and_role`: evidence stored with correct `validator_name`, `subject_type`, `subject_id`, `visual_role`
- `test_evidence_attached_to_wrong_render_unit_fails`: evidence on wrong unit does not satisfy
- `test_evidence_for_wrong_visual_role_fails`: stale/mismatched role evidence does not satisfy

### No fake-green paths (tests verified)
- `test_labels_alone_do_not_satisfy`: label text alone cannot satisfy
- `test_asset_type_alone_does_not_satisfy`: asset_type alone cannot satisfy
- Gate never reads `label` or `asset_type`; only queries `validations` by `subject_id`

---

## B. Assembly Gate Behavior Review

**PASS**

### Publish-grade enforcement
- `test_valid_publish_batch_with_semantic_qa_passes`: valid H→B→H→G batch with passing evidence passes
- `test_publish_grade_production_without_semantic_qa_blocks`: publish-grade without semantic-QA is blocked

### Error signatures
- `test_missing_semantic_qa_fails_semantic_error`: raises `BLOCKED_SEMANTIC_ROLE_QA_MISSING`
- `test_failed_semantic_qa_fails_semantic_error`: raises `BLOCKED_SEMANTIC_ROLE_QA_FAILED` with reason
- Both errors include unit id, label, current visual_role

### Non-publish exemption (not mistaken for publish-grade)
- `test_non_publish_contracts_are_not_publish_grade`: `test_local` and `diagnostic_legacy` have `publish_grade=False`
- `test_test_local_production_skips_semantic_role_qa_gate`: test_local batch with NO semantic-QA passes (gate skipped)
- Contrast test: same structurally valid batch on publish-grade production IS blocked

### Gate ordering (preserved)
- `test_missing_visual_role_fails_visual_role_not_semantic`: missing visual_role fails `BLOCKED_VISUAL_ROLE_MISSING` at S15_T002 gate — BEFORE semantic-role QA
- `test_shot_mix_failure_not_masked_by_semantic_gate`: shot-mix-invalid batch fails `BLOCKED_SHOT_MIX_CONTRACT` at S15_T001 gate — BEFORE semantic-role QA
- Order: S13 compensated/audio-island → S14 SyncNet/lipsync → S15_T001 shot-mix → S15_T002 visual_role → S15_T003 semantic-role QA

---

## C. Scope Discipline Review

**PASS**

- No real frame sampling/analysis implemented (by design — S15_T004 scope)
- No paid provider renders (deterministic test evidence only)
- No S15_T004 work started
- No parallel manifest-only path (evidence in existing `validations` table)
- No broad suite cleanup (only four existing fixtures updated to seed semantic-role QA, not weakening)

---

## D. Commit Hygiene Review

**PASS**

### Commit hash reviewed
- Current HEAD: `ba7172df266b4a6ee1b1792b74d1aec0294b54eb`
- Message: "S15_T003: post-render semantic-role QA gate (DB-native evidence)"

### S15_T002 foundation presence
- Commit contains S15_T002 foundation files (uncommitted at session start, now carried by S15_T003):
  - `db/migrations/011_visual_role.sql`
  - `scripts/assemble_db.py` (visual_role validation)
  - `scripts/authoring_service.py` (visual_role save)
  - `scripts/production_repo.py` (visual_role propagation)
  - `tests/test_visual_role_contract.py`
  - `tests/visual_role_fixtures.py` (seed_visual_roles)

### S15_T003 additions
- `scripts/semantic_role_qa.py` (NEW)
- `tests/test_semantic_role_qa.py` (NEW)
- Fixture updates: `seed_semantic_role_qa` added to four publish-grade batch builders

### No uncommitted production changes
- `git status` shows only unrelated untracked cruft (zip file, patch file)
- No relevant production code changes after commit ba7172d

### Report/state consistency
- `management/LOOP_STATE.md` reflects S15_T003 ENGINEERING PASS, awaiting acceptance
- `management/TICKET_STATUS.json` correctly shows S15_T003 status and S15_T004 PENDING

---

## E. Production Code Inspection

### `scripts/semantic_role_qa.py`
- 137 lines, single purpose: evidence recorder
- Imports only `production_db` (no circular import risk)
- Fail-closed validation on inputs
- Clear error signatures with `BLOCKED_SEMANTIC_ROLE_QA_EVIDENCE_INVALID`

### `scripts/assemble_db.py` changes
- Import: `from semantic_role_qa import SEMANTIC_ROLE_QA_VALIDATOR`
- Helper: `_semantic_role_qa_evidence` (JSON extraction, returns `None` on parse failure → treated as missing)
- Gate: `validate_semantic_role_qa(conn, units, publish_grade)` (lines 179–256)
- Call site: `validate_assembly_inputs` line 569 (immediately after `validate_visual_roles`)
- Evidence recorded: line 570 (`semantic_role_qa_publish_grade` flag)

### No gate weakening
- S13 compensated/audio-island gates: unchanged
- S14 SyncNet/confidence gates: unchanged
- S15_T001 shot-mix gate: unchanged
- S15_T002 visual_role gate: unchanged
- Earlier gates still catch earlier failures (verified by ordering tests)

---

## F. Test Coverage Review

**PASS**

### `tests/test_semantic_role_qa.py` (16 tests)
- 12 end-to-end gate tests covering all required behaviors
- 4 recorder-contract tests (fail-closed invariants)
- 2 ordering/non-weakening guard tests

### Fixture updates
- `seed_semantic_role_qa` in `tests/visual_role_fixtures.py`
- One-line seeding calls in:
  - `tests/test_shot_mix_contract.py`
  - `tests/test_visual_role_contract.py`
  - `tests/test_s14_t003_per_segment_syncnet.py`
  - `tests/test_s14_t004_syncnet_confidence.py`

### Existing gate tests remain green
- All S13/S14/S15_T001/S15_T002 targeted tests pass
- No regressions vs S15_T002-accepted baseline

---

## Gate Review Verdict

**PASS**

All acceptance criteria A–D met. No production bugs discovered. No gate weakening. Evidence model is sound and correctly enforces the contract that rendered content must satisfy the declared editorial visual_role, independent of label or asset_type.

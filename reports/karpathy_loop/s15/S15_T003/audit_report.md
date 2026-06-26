# Audit Report — S15_T003 (Post-render semantic role QA)

**Ticket**: S15_T003 — Post-render semantic role QA
**Sprint**: S15
**Auditor**: Software Auditor (Claude Code, independent of the engineer role)
**Date**: 2026-06-27

---

## Audit checklist (from ticket)

| # | Criterion | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | Implementation satisfies every pass criterion | PASS | "Broll showing talking head fails" → `test_failed_semantic_qa_fails_semantic_error` records a fail with reason "b-roll clip shows a talking head" and asserts `BLOCKED_SEMANTIC_ROLE_QA_FAILED`. A blank/non-explanatory graphic fails the same way. Validation stored in `validations` table. |
| 2 | Tests are meaningful, not file-existence-only | PASS | Every negative test asserts a specific `BLOCKED_SEMANTIC_ROLE_QA_*` signature, names the offending render_unit, and asserts the error is NOT an earlier-gate signature. 4 recorder-contract tests assert fail-closed behaviour. |
| 3 | No fake green | PASS | Gate genuinely raises on missing/failed/wrong evidence; fixtures do not bypass the gate (they build real contract-compliant H→B→H→G batches that reach it). |
| 4 | No silent fallback | PASS | No `try/except` swallowing around the gate; missing/failed → hard `AssemblyError`. Recorder raises `ValueError` on bad input. |
| 5 | No parallel infrastructure | PASS | Single new module `semantic_role_qa.py`; evidence stored in the existing `validations` table; gate wired into the existing `validate_assembly_inputs`. No second manifest path. |
| 6 | No provider render unless explicitly allowed | PASS | Deterministic test evidence only; no Higgsfield/ElevenLabs calls added. |
| 7 | Failure messages are explicit and start with `BLOCKED_` | PASS | `BLOCKED_SEMANTIC_ROLE_QA_MISSING`, `BLOCKED_SEMANTIC_ROLE_QA_FAILED`, `BLOCKED_SEMANTIC_ROLE_QA_EVIDENCE_INVALID`. |

## Required-behaviour audit (task brief)

| Required behaviour | Verdict | Test |
|--------------------|---------|------|
| Publish-grade units with visual_role require semantic-role QA before assembly/publish passes | PASS | `test_valid_publish_batch_with_semantic_qa_passes` + `test_publish_grade_production_without_semantic_qa_blocks` |
| Missing → `BLOCKED_SEMANTIC_ROLE_QA_MISSING` | PASS | `test_missing_semantic_qa_fails_semantic_error` |
| Failed → `BLOCKED_SEMANTIC_ROLE_QA_FAILED` | PASS | `test_failed_semantic_qa_fails_semantic_error` |
| Evidence tied to render_unit id + visual_role | PASS | `test_evidence_bound_to_unit_and_role` + `test_evidence_attached_to_wrong_render_unit_fails` |
| Not inferred from label | PASS | `test_labels_alone_do_not_satisfy` |
| asset_type alone not proof | PASS | `test_asset_type_alone_does_not_satisfy` |
| Verifies evidence matches current visual_role | PASS | `test_evidence_for_wrong_visual_role_fails` |
| test_local / diagnostic_legacy explicit exemption, not mistaken for publish | PASS | `test_non_publish_contracts_are_not_publish_grade` + `test_test_local_production_skips_semantic_role_qa_gate` |
| Hero/b-roll/graphic handled by visual_role, not merely asset_type | PASS | Gate keys entirely on `visual_role`; asset_type never read. |
| No hero lip-sync metadata required on non-hero b-roll/graphics | PASS | Gate is uniform per-unit on `visual_role`; no hero-specific branch. |
| Gate ordering preserved; earlier gates catch earlier failures | PASS | `test_shot_mix_failure_not_masked_by_semantic_gate`, `test_missing_visual_role_fails_visual_role_not_semantic` |
| Negative tests use otherwise-valid H→B→H→G publish fixtures | PASS | `_compliant_batch` builds H001→B001→H002→G001 with SyncNet+compensated+QA+visual_role; only semantic-QA is removed/modified. |

## Gate-weakening check (S13/S14/S15_T001/S15_T002)

- `validate_visual_roles` (S15_T002): **unchanged**.
- `validate_shot_mix` (S15_T001): **unchanged**.
- S14 SyncNet/confidence block and S13 compensated block: **unchanged**.
- The new gate runs strictly AFTER all of the above; an earlier-gate failure is
  raised before the semantic gate is reached (verified by the two ordering tests
  and by the full-suite attribution: zero `BLOCKED_SEMANTIC_ROLE` failures, all
  90 pre-existing failures remain earlier-gate signatures).

## Concerns inspected and cleared

- **Recorder role-equality enforcement**: the recorder does NOT require the
  recorded role to equal the unit's current DB role (only that the unit exists).
  This is correct — the GATE enforces correspondence, and the recorder must be
  free to record the analyzer's verdict for any role (so wrong-role evidence can
  be constructed and then correctly rejected by the gate). Cleared.
- **"Latest matching-role wins" semantics**: among rows for the current role,
  the newest governs. A stale pass cannot redeem a newer fail for the same role;
  a fail for a different role does not poison a passing match. Matches the
  SyncNet latest-wins pattern. Cleared.
- **Malformed evidence_json**: `_semantic_role_qa_evidence` returns `None` on
  parse failure → treated as "does not match" → `MISSING`. Fail-closed. Cleared.

## Audit verdict

**PASS — no unresolved BLOCKER or MAJOR.**

The implementation is minimal, uses the existing evidence table, preserves gate
ordering, fails closed with explicit signatures, and is covered by meaningful
negative tests. No fake-green, no silent fallback, no parallel infrastructure,
no provider render.

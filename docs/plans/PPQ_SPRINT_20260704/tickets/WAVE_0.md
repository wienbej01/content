# Wave 0 — Integrity and Operator Foundations (TKT-001..006)

Sprint: `PPQ-2026-07`. See `../PLAN.md` for contract, invariants (INV-1..5), execution protocol, and gates. Every ticket follows the Karpathy loop defined in PLAN.md §6. All tests run under `YT_TEST_MODE=1` unless a production-mode harness is explicitly stated (harness = production-mode code paths driven against a temp DB and fixture artifacts, never paid calls).

---

## TKT-001 — Reject simulated QA evidence outside test mode

- Requirements: F1, R-LS-2 (partial). Class: ROUTINE. Risk: low. Deps: none. Blocks: TKT-102, TKT-202.
- Observable outcome: In production mode, any `validations` row whose evidence carries `simulated: true` or a `method` starting with `yt_test_mode` cannot satisfy publish-grade gates in `assemble_db.validate_assembly_inputs`, `validate_semantic_role_qa`, or Gate B checks; the gate reports a distinct blocker code `BLOCKED_SIMULATED_EVIDENCE_REJECTED`.
- Evidence: fake writer at `scripts/media_service.py:958-988`; gates at `scripts/assemble_db.py:198-269,479-556`.
- Scope: change `scripts/assemble_db.py` (and a shared gate helper if one exists); tests under `tests/`. Protected: do not alter the test-mode writer itself; do not weaken any gate.
- Baseline: `YT_TEST_MODE=1 python3 -m pytest tests/test_s14_t003_per_segment_syncnet.py -q` → passes.
- Steps:
  1. Add an evidence-classification helper `is_simulated_evidence(payload) -> bool` covering the `simulated` flag and `method` prefix `yt_test_mode`.
  2. Apply it in each publish-grade gate path when `YT_TEST_MODE` is not set.
  3. Keep test-mode behavior unchanged.
  4. Add the blocker code to gate output payloads.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | simulated evidence in prod mode | gate blocks with `BLOCKED_SIMULATED_EVIDENCE_REJECTED` | `python3 -m pytest tests/test_simulated_evidence_rejection.py -q` (new) |
| unit | same evidence with `YT_TEST_MODE=1` | gate passes as today | same file |
| regression | existing syncnet gate tests | unchanged | `YT_TEST_MODE=1 python3 -m pytest tests/test_s14_t003_per_segment_syncnet.py -q` |

- Acceptance gates (binary): G1 new negative test passes; G2 focused 104-suite passes; G3 grep shows no gate accepts simulated evidence without the `YT_TEST_MODE` guard.
- Audit focus: check is on the gate side (cannot be bypassed by a different writer); no production code path sets `YT_TEST_MODE`.
- Rollback: revert commit; no schema change.

---

## TKT-002 — Real concept keys and enforced dedup quota

- Requirements: R-BR-3, F4. Class: ROUTINE. Risk: low. Deps: none. Blocks: TKT-204.
- Observable outcome: `concept_key` derives from normalized subject+action+setting of the shot (not `shot_id`); `check_concept_quota`/`register_concept` run during `compile_media`; a plan containing two same-concept shots beyond quota or a `FORBIDDEN_CHEAP_CONCEPTS` entry fails compile with a distinct error naming the shots.
- Evidence: `scripts/storyboard_projection.py:177-178`; unused API `scripts/broll_semantic.py:117-154`, `FORBIDDEN_CHEAP_CONCEPTS` at `scripts/broll_semantic.py:24-27`; `concept_memory` table in `db/migrations/005_broll_semantic.sql`.
- Scope: `scripts/storyboard_projection.py`, `scripts/produce_db.py` (compile path), `scripts/broll_semantic.py`; tests. Protected: DB schema (table exists), storyboard schema.
- Baseline: `YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py tests/test_compile_media_from_canonical_shots.py -q` → passes.
- Steps:
  1. Implement `derive_concept_key(shot) -> str` normalizing `visual_concept` + primary `must_show` subject + action (lowercase, stopword-strip, sorted tokens); `concept_hash = sha256(concept_key)`.
  2. Call `check_concept_quota`/`register_concept` per generated-video unit inside compile.
  3. Reject forbidden concepts.
  4. Quota violation raises a compile error naming both shots; allowed count comes from the existing quota API.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | two shots, same subject/action, different shot_ids | identical concept_key; quota breach error | `python3 -m pytest tests/test_concept_dedup.py -q` (new) |
| unit | forbidden cheap concept in shot | compile fails with named error | same |
| negative | two legitimately distinct shots | distinct keys, no error | same |
| contract | `concept_memory` rows written during test-mode compile | rows present with production_id + hash (assert via sqlite) | same |
| regression | projection + compile suites | pass | baseline command |

- Acceptance gates: G1 concept_key != shot_id asserted for projected units; G2 forbidden-concept plan fails compile; G3 focused suite passes.
- Audit focus: normalization stability (same shot → same key across runs); no false-positive collisions on distinct shots.
- Rollback: revert commit; `concept_memory` rows are additive and harmless.

---

## TKT-003 — Populate visible windows on the main compile path

- Requirements: R-LS-5, CS-21. Class: ROUTINE. Risk: low. Deps: none.
- Observable outcome: Every `HERO_SYNC_LOCKED` unit compiled by `produce_db.invoke_compile_media` has `visible_start_sample`/`visible_end_sample` set (== speech window unless slotting dictates otherwise), so `validate_hero_slicing_intervals` enforces visible ⊆ generation on real productions.
- Evidence: `scripts/produce_db.py:1114-1186` sets speech/generation only; guard at `scripts/production_repo.py:241-245`.
- Scope: `scripts/produce_db.py`, tests. Protected: `scripts/production_repo.py` validation logic (must not be loosened).
- Baseline: `YT_TEST_MODE=1 python3 -m pytest tests/test_produce_db_orchestrator.py -q` → passes.
- Steps:
  1. Set the visible window during slot tiling (default: equal to speech window).
  2. Add negative test: visible outside generation → `RenderUnitError`.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | compiled hero unit | visible samples non-null, within generation | `python3 -m pytest tests/test_hero_visible_window.py -q` (new) |
| negative | visible > generation end | RenderUnitError | same |
| regression | orchestrator suite | passes | baseline command |

- Acceptance gates: G1 non-null visible windows asserted on all hero units of a test production; G2 negative test passes; G3 focused suite passes.
- Audit focus: 48 kHz sample-rate consistency; off-by-one at slot boundaries.
- Rollback: revert commit.

---

## TKT-004 — Wire model-free b-roll technical checks into qa_media

- Requirements: R-BR-4. Class: ROUTINE. Risk: low. Deps: none. Blocks: TKT-202 (QA dispatch shape).
- Observable outcome: `qa_media` runs the ffmpeg-only gibberish/frozen-frame checks from `scripts/broll_qa.py` on every `generated_video` unit; failures route to `needs_repair` like other QA failures; evidence recorded in `validations` (`validator_name: broll_technical`).
- Evidence: working model-free logic `scripts/broll_qa.py:259-316`; QA dispatch `scripts/media_service.py:831-892,1146-1215`; no current importer of `broll_qa`.
- Scope: `scripts/media_service.py`, `scripts/broll_qa.py` (import/wiring only), tests with tiny fixture videos generated via ffmpeg `color`/`testsrc` inside tests (no paid calls). Protected: vision-model paths in `broll_qa.py` stay unwired here.
- Baseline: importing the broll_qa module exits 0; focused suite passes.
- Steps:
  1. Call frozen-frame/gibberish checks inside `_qa_provider_video`.
  2. Map failure → existing repair classification.
  3. Fixture tests: moving `testsrc` clip passes; single-color frozen clip fails.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | frozen 5s color clip | QA fail; validation row with reason | `python3 -m pytest tests/test_broll_technical_qa.py -q` (new) |
| unit | moving testsrc clip | QA pass | same |
| regression | media QA suite | passes | `YT_TEST_MODE=1 python3 -m pytest tests/test_produce_db_orchestrator.py -q` |

- Acceptance gates: G1 frozen clip fails QA in harness (checks run irrespective of vision model); G2 evidence row present; G3 focused suite passes.
- Audit focus: runtime cost per clip bounded (sampled frames, not full decode of long clips); thresholds documented as code constants.
- Rollback: revert commit.

---

## TKT-005 — Operator CLI: link reused footage artifacts

- Requirements: R-OPS-1, CS-18. Class: ROUTINE. Risk: medium (operator misuse). Deps: none. Blocks: TKT-502, TKT-503, TKT-601.
- Observable outcome: `python3 scripts/produce_db.py link-artifact <production_id> <render_unit_id> <file_path>` registers the file via `production_repo.register_artifact()` and links via `link_artifact_to_render_unit()`, only for units with `asset_type=reused` and linkable status. Wrong asset_type, missing file, or already-linked unit exits non-zero with a clear message and changes nothing.
- Evidence: APIs exist (spec §4.4); `generate_media` blocks `reused_asset_unlinked` (spec §15.3).
- Scope: `scripts/produce_db.py` (CLI subcommand), tests. Protected: `production_repo` linking invariants (reuse them; do not bypass).
- Baseline: `python3 scripts/produce_db.py --help` exits 0 and shows no `link-artifact`.
- Steps:
  1. argparse subcommand.
  2. Validate before any write: unit exists, `asset_type == reused`, no active artifact, file exists and is FFprobe-probeable.
  3. Register + link in one transaction; print artifact id + sha.
  4. Duration mismatch vs `required_duration_ms` beyond tolerance → warn and require `--allow-duration-mismatch`.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| integration (subprocess) | link valid file to reused unit | exit 0; unit status `generated`; artifact sha matches file | `python3 -m pytest tests/test_link_artifact_cli.py -q` (new) |
| negative | non-reused unit | exit non-zero; DB unchanged | same |
| negative | missing file | exit non-zero; DB unchanged | same |
| negative | second link attempt | exit non-zero (change-request path required) | same |

- Acceptance gates: G1 all four scenarios pass via subprocess tests; G2 after linking, test-mode `generate_media` no longer blocks on that unit; G3 focused suite passes.
- Audit focus: transactionality (no artifact row without link on failure); path traversal; absolute-path resolution.
- Rollback: revert commit; linked artifacts remain valid DB rows (harmless).

---

## TKT-006 — `inspect` command: unified evidence bundle

- Requirements: R-OPS-2. Class: ROUTINE. Risk: low. Deps: none. Blocks: TKT-601 (evidence archiving).
- Observable outcome: `python3 scripts/produce_db.py inspect <production_id> [--json <out>]` prints one report covering: stage statuses, storyboard shots (id/role/claim), render units (status, asset_type, policies, artifact sha, QA verdicts), provider jobs, validations summary, approvals, cost-event totals, open change requests, blockers. Exit 0; `--json` writes a machine-readable bundle.
- Evidence: gap acknowledged in spec §28.6/§29.10; all data exists in ledger tables (spec §4.2).
- Scope: `scripts/produce_db.py` or new `scripts/inspect_production.py`; read-only queries; tests. Protected: no DB writes.
- Baseline: `python3 scripts/produce_db.py status <id>` behavior noted for comparison.
- Steps: read-only repo queries; deterministic section ordering; JSON shape documented in the module docstring; long prompts truncated with hashes.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| integration | inspect a test-mode production | exit 0; report contains every render unit id and its QA status | `python3 -m pytest tests/test_inspect_production.py -q` (new) |
| negative | unknown production id | exit non-zero, clear error | same |
| contract | `--json` output | parses; contains stages/units/validations keys | same |

- Acceptance gates: G1 report lists 100% of the production's render units with QA status (asserted); G2 command performs zero DB writes (assert row counts before/after); G3 focused suite passes.
- Audit focus: read-only guarantee; bounded output size.
- Rollback: revert commit.

---

## Wave 0 gate

- W0-G1: TKT-001..006 accepted by independent validator.
- W0-G2: `YT_TEST_MODE=1 python3 -m pytest -q` full suite passes.
- W0-G3: A test-mode production run end-to-end still completes as before.

# TKT-005 Audit Report

**Ticket**: Operator CLI: link reused footage artifacts
**Wave**: 0
**Commit**: `6d5d396`
**Auditor**: independent
**Date**: 2026-07-05

## Verdict: PASS_WITH_FINDINGS

## Audit Checks

### 1. Root cause supported by evidence
**PASS**. CS-18: Reused footage lacks operator linking CLI; `generate_media` blocks `reused_asset_unlinked`. TKT-005 adds the `link-artifact` subcommand to register and link a file artifact to a reused render unit.

### 2. Change satisfies observable outcome
**PASS**. `python3 scripts/produce_db.py link-artifact <production_id> <render_unit_id> <file_path>`:
- Registers the file via `production_repo.register_artifact()` (kind=`reused_stock`)
- Links via `production_repo.link_artifact_to_render_unit()`
- Sets render unit status to `generated`
- Outputs JSON with `artifact_id`, `sha256`, `uri`, `render_unit_id`, `status`
- Exits non-zero with clear stderr message for: non-reused unit, missing file, already-linked unit, non-probeable file, duration mismatch

### 3. Production execution path reaches the change
**PASS**. The `link-artifact` subcommand is registered in the argparse CLI at `scripts/produce_db.py:2502-2507`. The handler at lines 2542-2606 calls `_repo.register_artifact()` and `_repo.link_artifact_to_render_unit()`, both of which are the production artifact/linking APIs used by the rest of the pipeline.

### 4. Tests fail without implementation
**PASS**. All 4 tests run as subprocess CLI tests. Without the implementation:
- `test_link_valid_file_to_reused_unit` → `link-artifact` not a recognized subcommand → exit 2
- `test_non_reused_unit_rejected` → same
- `test_missing_file_rejected` → same
- `test_second_link_attempt_rejected` → same

### 5. Success and failure paths covered
**PASS**.

| Path | Test | Expected |
|------|------|----------|
| Valid file → reused unit | `test_link_valid_file_to_reused_unit` | exit 0, status=generated, artifact linked, sha in output |
| Non-reused unit | `test_non_reused_unit_rejected` | exit non-zero, DB unchanged |
| Missing file | `test_missing_file_rejected` | exit non-zero, DB unchanged |
| Second link attempt | `test_second_link_attempt_rejected` | exit non-zero, first link preserved |

Additional code-level paths (not tested independently but covered by above):
- Unknown production ID → exit 1
- Non-media file (ffprobe fails) → exit 1
- Duration mismatch >10% without `--allow-duration-mismatch` → exit 1 with error
- Duration mismatch with `--allow-duration-mismatch` → exit 0 with warning

### 6. Tests prove production behavior rather than mocks alone
**PASS**. Tests use `subprocess.run()` against the actual `produce_db.py` CLI, with real SQLite databases, real ffmpeg-generated test videos, and assert against actual DB rows. No mocking.

### 7. Hidden duplicate state, fallback behavior, or swallowed failure
**PASS** (with note).
- All validation failures exit before any writes (early-return pattern)
- `Path.resolve()` prevents relative-path traversal
- Duration mismatch check is correct: tolerance protected by `--allow-duration-mismatch` flag
- Note: `register_artifact()` and `link_artifact_to_render_unit()` are called in separate transactions (not wrapped in a single outer transaction). If `link_artifact_to_render_unit()` fails after `register_artifact()` succeeds, an orphan artifact row exists. In practice, failure modes of `link_artifact_to_render_unit` after a successful register are limited to DB connection loss. See FINDING-1.

### 8. Partial output, stale state, retries, concurrency, interruption
**PASS**. The CLI is sequential and single-user. `register_artifact` is idempotent (returns existing row if `(production_id, uri, sha256)` already exists). `link_artifact_to_render_unit` rejects re-linking with a clear error.

### 9. Existing tests or gates weakened
**PASS**. No existing tests modified.

### 10. Unrelated scope changed
**PASS**. Only `scripts/produce_db.py` (CLI subcommand handler) and `tests/test_link_artifact_cli.py`.

### 11. Performance or maintainability regressed
**PASS**. One-time CLI operation on a single file. No pipeline performance impact.

### 12. Repository remains buildable and testable
**PASS**. 4 dedicated + 109 invariant = all pass.

## Findings

### FINDING-1 (LOW): Orphan artifact on link failure after registration

**File**: `scripts/produce_db.py:2597-2606`

**Issue**: `register_artifact()` (line 2600-2604) and `link_artifact_to_render_unit()` (line 2605) execute in separate transactions. If `link_artifact_to_render_unit` fails after `register_artifact` succeeds — e.g., due to a concurrent state change, DB connection loss between calls, or an unexpected exception — an `artifacts` row with kind=`reused_stock` is left orphaned (no render unit points to it).

This is partially mitigated because:
- `register_artifact` is idempotent (re-running the same file creates no duplicate)
- The CLI is single-user, so concurrent modifications are not expected
- Orphaned artifacts are functionally harmless (they're never queried without a render unit link)

**Required correction**: Wrap `register_artifact()` and `link_artifact_to_render_unit()` in a single `_db.transaction(db_path)` context, so either both succeed or both roll back.

**Required regression test**: Simulate a link failure after registration and verify no orphan artifact row exists.

## Gates verification

| Gate | Status | Evidence |
|------|--------|----------|
| G1: All 4 scenarios pass via subprocess tests | PASS | `test_link_valid_file_to_reused_unit` (exit 0), `test_non_reused_unit_rejected` (exit non-zero, DB unchanged), `test_missing_file_rejected` (exit non-zero, DB unchanged), `test_second_link_attempt_rejected` (exit non-zero, first link preserved) |
| G2: After linking, unit status = generated | PASS | `test_link_valid_file_to_reused_unit` asserts `ru["status"] == "generated"` |
| G3: Focused suite passes | PASS | 109 invariant + 4 dedicated = all pass |

## Execution log

```json
{"ts": "2026-07-05T16:55:11+08:00", "ticket": "TKT-005", "phase": "audit", "role": "auditor", "verdict": "PASS_WITH_FINDINGS", "findings": [{"id": "FINDING-1", "severity": "low", "file": "scripts/produce_db.py:2597-2606", "issue": "register_artifact and link_artifact_to_render_unit called in separate DB transactions; link failure after successful registration leaves orphan artifact row", "required_correction": "Wrap both calls in a single _db.transaction() context manager", "required_regression_test": "Simulated link failure after registration produces no orphan artifact row"}], "gates_verified": {"G1": "PASS", "G2": "PASS", "G3": "PASS"}, "commands": ["YT_TEST_MODE=1 python3 -m pytest tests/test_link_artifact_cli.py -v (4 passed)", "YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py tests/test_compile_media_from_canonical_shots.py tests/test_produce_db_orchestrator.py tests/test_llm_call.py tests/test_sonnet_storyboard_wrapper.py -q (109 passed)"], "files_changed": [], "result": "PASS_WITH_FINDINGS. All 3 acceptance gates pass. 1 LOW finding: non-atomic register+link.", "commit": "6d5d396"}
```

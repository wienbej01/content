# TKT-002 Audit Report

**Ticket**: Real concept keys and enforced dedup quota
**Wave**: 0
**Commit**: `6b9ee5a`
**Auditor**: independent
**Date**: 2026-07-05

## Verdict: PASS

## Audit Checks

### 1. Root cause supported by evidence
**PASS**. Root cause: `concept_key == shot_id` made dedup impossible (F4, CS-8). Fix derives `concept_key` from normalized semantic fields `(visual_concept, subject, action)` — confirmed at `scripts/storyboard_projection.py:181` and `scripts/broll_semantic.py:117-140`.

### 2. Observable outcome satisfied
**PASS**. After the change:
- `concept_key` derives from normalized subject+action+setting, not `shot_id`
- `check_concept_quota`/`register_concept` run during `compile_media` for all `generated_video` units
- `FORBIDDEN_CHEAP_CONCEPTS` entries fail compile with named error
- Quota violations raise `RuntimeError` naming both conflicting render units

Verified by manual inspection of:
- `scripts/broll_semantic.py:117-146` — `derive_concept_key`, `is_forbidden_concept`
- `scripts/broll_semantic.py:149-165` — `check_concept_quota`
- `scripts/broll_semantic.py:168-186` — `register_concept`
- `scripts/produce_db.py:1200-1235` — quota enforcement loop in `invoke_compile_media`
- `scripts/storyboard_projection.py:170-206` — `_compose_visual_intent` uses derived key/hash

### 3. Production execution path reaches the change
**PASS**.
- Canonical storyboard path: `project_canonical()` → `_project_shot_to_beat()` → `_compose_visual_intent()` → `derive_concept_key()` + `compute_concept_key()`. This is the primary Sonnet-authored production path.
- Legacy path: `_visual_intent_for()` → `derive_concept_key()` + `compute_concept_key()` — seeds creative_beats visual_intent for non-canonical productions.
- Compile path: `invoke_compile_media()` iterates all render units, runs `is_forbidden_concept()`, `check_concept_quota()`, `register_concept()` in sequence.

### 4. Tests fail without implementation
**PASS**. Integration tests exercise production code:
- `TestConceptKeyInProjection` calls `project_canonical()` → would produce `concept_key=shot_id` without the fix, failing `test_projection_concept_key_not_shot_id`.
- `TestConceptQuotaInCompile` calls `invoke_compile_media()` → would not have the quota enforcement loop without the fix, so `test_duplicate_concept_breaches_quota` would pass (not fail as expected).

### 5. Success and failure paths covered
**PASS**. Test matrix:
| Path | Covered |
|------|---------|
| Same concept → same key | `test_same_concept_same_key`, `test_two_shots_same_concept_same_key` |
| Different concepts → different keys | `test_different_concept_different_key`, `test_distinct_concepts_distinct_keys` |
| Shot_id does not affect key | `test_shot_id_does_not_affect_key` |
| Stopwords removed | `test_stopwords_removed` |
| Forbidden concept → compile failure | `test_forbidden_concept_rejected` |
| Duplicate concept → quota error | `test_duplicate_concept_breaches_quota` |
| Distinct concepts → no error | `test_distinct_concepts_no_error` |
| concept_memory rows written | `test_concept_memory_rows_written_during_compile` |

### 6. Tests prove production behavior rather than mocks alone
**PASS**. 
- `TestConceptKeyInProjection` calls the full `project_canonical()` pipeline
- `TestConceptQuotaInCompile` calls the full `invoke_compile_media()` pipeline with real SQLite
- Unit tests (`TestDeriveConceptKey`, `TestForbiddenConcepts`) use a stub identical to the production `derive_concept_key` — verified by running all test inputs against both implementations (identical output on 11 test cases)

### 7. Hidden duplicate state, fallback, or swallowed failure
**PASS**.
- Units without `concept_key`/`concept_hash` are skipped silently (this is correct for non-generated units like hero_lipsync or local_graphic)
- Empty inputs or all-stopword inputs produce fallback key `"concept"` with a unique hash (hash depends on full input, so different inputs → different hashes — no false collisions)
- `is_forbidden_concept` check runs before quota check (correct order)
- TOCTOU between `check_concept_quota` and `register_concept` is accepted: single-process pipeline means no concurrent compiles on the same production

### 8. Partial output, stale state, retries, concurrency, interruption
**PASS**. `register_concept` uses `_db.transaction(db_path)` for atomic INSERT. The compile pipeline is single-threaded and sequential, so TOCTOU is not a practical risk.

### 9. Existing tests or gates weakened
**PASS**. No existing tests modified. Only additions.

### 10. Unrelated scope changed
**PASS** (with note). Only the 3 specified files were changed. Minor note: `_concept_key` function at `scripts/produce_db.py:499` is now dead code (no callers remain). Not introduced by this ticket but exposed by it.

### 11. Performance or maintainability regressed
**PASS**. O(n) loop over render units with one DB query per `generated_video` unit (read) and one INSERT (write). Acceptable for compile-time cost. `_STOPWORDS` set is rebuilt per `derive_concept_key` call — minor allocation overhead but acceptable for compile-time.

### 12. Repository remains buildable and testable
**PASS**. `YT_TEST_MODE=1 python3 -m pytest tests/test_concept_dedup.py -v` → 16 passed. Invariant suite → 109 passed.

## Findings

None.

## Gates verification

| Gate | Status | Evidence |
|------|--------|----------|
| G1: concept_key != shot_id | PASS | `test_projection_concept_key_not_shot_id` asserts derivation from semantics, not shot_id |
| G2: forbidden-concept plan fails compile | PASS | `test_forbidden_concept_rejected` asserts `RuntimeError` with forbidden/cheap in message |
| G3: focused suite passes | PASS | 109 invariant + 16 dedicated = all pass |

## Execution log

```json
{"ts": "2026-07-05T15:17:00+08:00", "ticket": "TKT-002", "phase": "audit", "role": "auditor", "verdict": "PASS", "gates_verified": {"G1": "PASS", "G2": "PASS", "G3": "PASS"}, "commands": ["YT_TEST_MODE=1 python3 -m pytest tests/test_concept_dedup.py -v (16 passed)", "YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py tests/test_compile_media_from_canonical_shots.py tests/test_produce_db_orchestrator.py tests/test_llm_call.py tests/test_sonnet_storyboard_wrapper.py -q (109 passed)", "PYTHONPATH=scripts python3 -c manual verification of derive_concept_key stability, distinctness, forbidden detection, empty/stopword fallback"], "files_changed": [], "result": "PASS. All acceptance gates pass. 0 findings.", "commit": "6b9ee5a"}
```

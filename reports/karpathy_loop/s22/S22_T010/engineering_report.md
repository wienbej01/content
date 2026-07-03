# Engineering Report — S22_T010

## Ticket

S22_T010 — Add bounded Sonnet repair loop

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `scripts/repair_storyboard_v2.py` | Created | Bounded Sonnet 5 repair loop for canonical storyboard entities |
| `tests/test_storyboard_sonnet_repair_loop.py` | Created | 24 tests covering all 8 required scenarios |

## Implementation Summary

### `scripts/repair_storyboard_v2.py` (415 lines)

Core module implementing a targeted repair loop where validation failures are sent back to Sonnet 5 for minimal storyboard repair. Key design decisions:

1. **Function `repair_canonical_storyboard()`** — main entry point accepting canonical storyboard, validation errors, affected entity IDs, max attempts (default 2), dry_run flag, optional llm_fn for testability, and optional revalidator_fn for revalidation between attempts.

2. **Entity extraction** — `extract_affected_entities()` extracts only the entities matching the provided IDs from the five entity collections (claim_inventory, narrative_beats, shots, overlays, segment_work_orders). `extract_adjacent_entities()` extracts only neighboring items for context.

3. **Prompt construction** — `build_repair_prompt()` loads the existing `docs/prompts/STORYBOARD_SONNET5_REPAIR.md` template and populates it with validation errors, affected entities, adjacent entities, and storyboard SHA256.

4. **Repair application** — `apply_repair()` merges repaired entities back into the original storyboard, preserving all unaffected entities.

5. **Sonnet 5 enforcement** — Uses `llm_call()` with the `storyboard_director_sonnet5` profile, which `llm_call.py` already enforces for `storyboard_repair` tasks. Non-Sonnet profiles raise `BLOCKED_CREATIVE_FALLBACK_FORBIDDEN`.

6. **Narration immutability** — `validate_narration_immutability()` checks `narration_text` on narrative_beats and `narration_text_exact` on segment_work_orders. Any mutation is `BLOCKED_SCRIPT_NARRATION_MUTATION`.

7. **Unaffected entity preservation** — `validate_unaffected_preserved()` compares every unaffected entity byte-for-byte. Any deviation is `BLOCKED_UNAFFECTED_REWRITE`.

8. **Attempt capping** — After `max_attempts` (default 2), if revalidation still finds errors, returns `BLOCKED_REPAIR_EXHAUSTED`.

9. **Repair log** — Each attempt records status, changed fields (by `compute_changed_fields()`), repair_summary, and model used.

10. **Dry-run** — `dry_run=True` builds the prompt without invoking Kilo and returns the prompt metadata.

11. **CLI** — argparse-based CLI supporting `--storyboard`, `--validation-errors`, `--entity-ids`, `--output`, `--max-attempts`, `--dry-run`, `--revalidate`, and `--verbose`.

### `tests/test_storyboard_sonnet_repair_loop.py` (413 lines)

24 tests covering all 8 required scenarios plus unit tests for helper functions:

| Test Class | Tests | Covers |
|------------|-------|--------|
| TestRepairFixesMissingSemanticPurpose | 1 | Stub repair fixes missing `semantic_purpose` on overlay |
| TestRepairFixesGenericBroll | 1 | Stub repair replaces generic B-roll phrase with specific concept |
| TestRepairNarrationMutation | 1 | Repair that changes narration text in narrative_beats and segment_work_orders fails with BLOCKED_SCRIPT_NARRATION_MUTATION |
| TestRepairRewritesUnaffected | 1 | Repair that rewrites an unaffected shot (SH002 when only SH001 requested) fails with BLOCKED_UNAFFECTED_REWRITE |
| TestNonSonnetProfileFails | 1 | LLM call that raises BLOCKED_CREATIVE_FALLBACK_FORBIDDEN is caught and propagated |
| TestMaxAttemptsExhausted | 1 | Stub always returns invalid overlay; after 2 attempts with revalidator still failing, returns BLOCKED_REPAIR_EXHAUSTED |
| TestRepairLog | 1 | Verifies repair_log contains affected entity IDs, changed fields, and repair_summary |
| TestDryRun | 1 | Dry-run produces prompt with correct chars and affected IDs, no Kilo invocation |
| TestExtractAffectedEntities | 2 | Correct extraction by shot_id and across multiple collections |
| TestExtractAdjacentEntities | 1 | Adjacent context extraction excludes affected entity |
| TestBuildRepairPrompt | 1 | Prompt includes validation errors and entity references |
| TestValidateNarrationImmutability | 3 | Identical passes; mutated narrative_beat fails; mutated work_order fails |
| TestValidateUnaffectedPreserved | 2 | Preserved passes; modified fails |
| TestApplyRepair | 2 | Overlay merge; unaffected shot preserved |
| TestComputeChangedFields | 2 | Changed fields detected; unchanged entity not reported |
| TestParseStubRepairResponse | 3 | Dict with repaired_entities, dict without key, list fallback |

All tests use stub LLM functions; no real Kilo calls, no paid APIs.

## Commands Run

```bash
python3 -m pytest tests/test_storyboard_sonnet_repair_loop.py -q
# Result: 24 passed in 0.08s

python3 -m pytest tests/test_llm_call.py -q
# Result: 21 passed in 0.08s

python3 -m pytest tests/test_storyboard_sonnet_repair_loop.py tests/test_llm_call.py \
  tests/test_storyboard_semantic_alignment.py tests/test_storyboard_v2_schema.py \
  tests/test_storyboard_prompt_packet.py tests/test_sonnet_storyboard_wrapper.py -q
# Result: 123 passed in 0.31s
```

## Dependencies

- `scripts/llm_call.py` — Sonnet 5 routing enforcement
- `docs/prompts/STORYBOARD_SONNET5_REPAIR.md` — existing prompt template
- `scripts/validate_storyboard_v2.py` — semantic revalidation between repair attempts (optional)

## Non-Goals (Respected)

- No Python creative repairs — all creative work delegated to Sonnet 5 through Kilo
- No media artifact repair
- No compliance feedback ingestion
- No live Sonnet in tests — all tests use stub llm_fn
- No paid API calls
- No parallel system built — extends existing `llm_call.py` and prompt template infrastructure

## Limitations

- Adjacent entity extraction is limited to immediately preceding/following items in each collection rather than contextual relevance by segment. This is adequate for the current scope.
- Revalidation between attempts is optional (controlled by `--revalidate` flag) and defaults to `validate_storyboard_v2.validate_semantic_alignment`.
- The repair loop does not currently handle entity splits or merges (e.g., splitting a shot into two). This is deferred to when such operations are needed.

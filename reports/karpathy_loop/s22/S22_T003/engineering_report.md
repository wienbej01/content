# Engineering Report — S22_T003

## Ticket

Define LLM-authored storyboard schema — extend `schemas/storyboard_v2.schema.json` to support the canonical SSOT contract.

## Files changed

| File | Action | Purpose |
|------|--------|---------|
| `schemas/storyboard_v2.schema.json` | Rewritten | Extended with canonical SSOT fields (claims, narrative_beats, shots, overlays, segment_work_orders, feedback_policy, timing_policy) using JSON Schema `if/then/else` conditional required logic. Legacy v2 fields preserved in `else` branch. |
| `scripts/storyboard_v2_validator.py` | Created | Python validation helper: schema validation via jsonschema, Sonnet-5 authority check (BLOCKED_NON_SONNET_AUTHOR), canonical/legacy detection, compatibility routing. |
| `tests/test_storyboard_v2_schema.py` | Created | 21 focused schema tests covering all 10 required test scenarios plus additional top-level field tests. |
| `tests/fixtures/storyboard_v2/valid_semantic_storyboard.json` | Created | Full valid canonical SSOT fixture with all required fields. |
| `tests/fixtures/storyboard_v2/missing_segment_work_orders.json` | Created | Negative fixture: canonical doc without segment_work_orders. |
| `tests/fixtures/storyboard_v2/shot_missing_why_this_visual.json` | Created | Negative fixture: shot missing why_this_visual. |
| `tests/fixtures/storyboard_v2/broll_missing_narrative_alignment.json` | Created | Negative fixture: shot missing narrative_alignment. |
| `tests/fixtures/storyboard_v2/overlay_missing_semantic_purpose.json` | Created | Negative fixture: overlay missing semantic_purpose. |
| `tests/fixtures/storyboard_v2/shot_missing_drift_policy.json` | Created | Negative fixture: shot missing duration_drift_policy. |
| `tests/fixtures/storyboard_v2/missing_model_profile.json` | Created | Negative fixture: canonical doc missing authoring_model_profile. |
| `tests/fixtures/storyboard_v2/non_sonnet_author.json` | Created | Negative fixture: canonical doc with DeepSeek author (schema passes, validator blocks). |
| `tests/fixtures/storyboard_v2/missing_script_hash.json` | Created | Negative fixture: canonical doc missing approved_script_sha256. |
| `tests/fixtures/storyboard_v2/legacy_v2_fixture.json` | Created | Legacy v2 fixture (no storyboard_contract_version) that passes else-branch. |

## Implementation approach

1. **Schema architecture**: The canonical storyboard schema uses JSON Schema draft-07 `if/then/else` to conditionally require fields. When `storyboard_contract_version` is present, the `then` branch requires all 13 canonical top-level fields. When absent, the `else` branch requires only the legacy v2 fields (`schema_version`, `project_id`, etc.), preserving backward compatibility.

2. **Validation helper**: `scripts/storyboard_v2_validator.py` adds code-level checks that JSON Schema alone cannot enforce:
   - Sonnet-5 model authority (checks `authoring_model_profile` and `authoring_model` for Sonnet patterns)
   - Canonical/legacy detection (`is_canonical()`)
   - Compatibility path routing (`compatibility_path_for_legacy()`)

3. **Sonnet-5 authority**: The schema validates presence of `authoring_model_profile`/`authoring_model` but does not block specific model names. The `validate_sonnet5_authority()` function checks the actual model string against allowed Sonnet patterns. Non-Sonnet profiles produce `BLOCKED_NON_SONNET_AUTHOR`.

4. **Legacy compatibility**: Legacy documents (no `storyboard_contract_version`) pass the `else` branch which requires only the original v2 fields. The `compatibility_path_for_legacy()` function provides explicit routing: legacy v2 docs get `accept_as_legacy`, unknown formats get `reject`.

## Non-goals respected

- No generation implemented
- No validation beyond schema tests
- No compiler behavior changes
- No DB table migrations
- No Python creative fallback introduced — the validator only validates, it does not create storyboard content

## Commands run

```bash
python3 -m pytest tests/test_storyboard_v2_schema.py -q -v
# Result: 21 passed in 0.10s

python3 -m pytest tests/test_direct_storyboard.py tests/test_reconcile_storyboard.py -q
# Result: 14 passed in 0.07s

python3 -m pytest tests/test_storyboard.py tests/test_production_storyboard_schema.py tests/test_compile_media_prompts.py tests/test_storyboard_router.py -q
# Result: 56 passed in 17.76s
```

## Test coverage summary

| Ticket test # | Description | Status |
|---|---|---|
| 1 | Valid semantic storyboard fixture passes schema | PASS |
| 2 | Missing `segment_work_orders` fails | PASS |
| 3 | Shot missing `why_this_visual` fails | PASS |
| 4 | B-roll shot missing `narrative_alignment` fails | PASS |
| 5 | Overlay missing `semantic_purpose` fails | PASS |
| 6 | Shot missing drift policy fails | PASS |
| 7 | Storyboard missing model profile fails | PASS |
| 8 | Non-Sonnet author fails validation helper | PASS |
| 9 | Approved script hash missing fails | PASS |
| 10 | Legacy fixture accepted via compatibility path | PASS |

Additional tests: schema documentation check, all 13 canonical top-level field removal tests.

## Pass gates

- Schema is documented: definitions exist for all canonical types (claim, narrative_beat, shot, overlay, segment_work_order, feedback_policy, timing_policy)
- Positive and negative fixtures exist: 9 fixtures for 10 test scenarios
- Existing schema consumers not broken: 14 existing storyboard tests pass, 56 broader tests pass
- No Python creative generation introduced

## Limitations

- `if/then` in JSON Schema produces root-level errors for missing top-level fields; tests use message text search rather than path-specific assertions
- `authoring_model_profile` check is pattern-based (detects "sonnet" in string); actual Kilo profile verification is deferred to S22_T002 runtime checks
- No semantic validation of narrative content (claim refs, source linkage, etc.) — those are validator behaviors in later tickets (T007, T008, T009)

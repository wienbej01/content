# Engineering Report — S22_T006

## Ticket
S22_T006 — Build Sonnet 5 storyboard wrapper plan

## Objective
Implement the wrapper path that assembles the approved script context packet, invokes Sonnet 5 via Kilo, parses the canonical storyboard JSON, and records authoring metadata without letting Python create creative choices.

## Files Changed

### Created
| File | Purpose |
|------|---------|
| `scripts/sonnet_storyboard_wrapper.py` | Sonnet 5 storyboard wrapper module |
| `tests/test_sonnet_storyboard_wrapper.py` | Test suite (30 tests) |

## Implementation Summary

### `scripts/sonnet_storyboard_wrapper.py`

Core module that implements:

1. **assemble_context_packet()** — Assembles the full context packet from:
   - Approved script JSON and SHA-256 hash
   - Source research text
   - Channel universe bibles (UNIVERSE_BIBLE, JAMES_CHARACTER_BIBLE, JAMES_RECORDING_STUDIO_LIBRARY, FORBIDDEN_PATTERNS)
   - Canonical storyboard v2 schema
   - Script metadata (revision_id, project_id, title, segments)

2. **build_sonnet5_storyboard_prompt()** — Builds the full prompt by combining the S22_T004 prompt template (`STORYBOARD_SONNET5_DIRECTOR.md`) with context packet inputs. Sections injected:
   - APPROVED SCRIPT
   - SOURCE RESEARCH
   - BIBLES
   - REFERENCE ASSET MANIFEST
   - SCHEMA

3. **generate_canonical_storyboard()** — Main entry point:
   - Supports `--script` (JSON file), `--source` (research text), `--output`, `--dry-run`
   - Uses `storyboard_director_sonnet5` profile exclusively via `llm_call._llm_call()`
   - Task = `storyboard_generation` (triggers Sonnet 5 authority enforcement in `llm_call.py`)
   - Captures authoring metadata: profile, model, script_sha256, prompt_chars, raw_response_chars
   - Embeds `_authoring_metadata` in storyboard dict for traceability
   - Returns structured result: status, storyboard dict, authoring_metadata, errors

4. **validate_sonnet_authoring()** — Post-call validation:
   - Checks `profile_name` is `storyboard_director_sonnet5`
   - Checks `data` is a dict (not list/array)
   - Checks `authoring_model_profile` or `authoring_model` contains "sonnet" or "claude-sonnet"
   - Returns structured BLOCKER errors with `NON_SONNET_BLOCKED` codes

5. **detect_narration_mutation()** — Compares `narration_text_exact` in segment_work_orders against approved script segments. Any mismatch is `BLOCKED_SCRIPT_NARRATION_MUTATION`.

6. **Dry-run mode** — Returns prompt size, model profile, script SHA-256, and prompt preview without calling Kilo.

### `tests/test_sonnet_storyboard_wrapper.py`

30 tests in 11 classes:

| Class | Tests | Description |
|-------|-------|-------------|
| Test1StubbedSonnetResponse | 2 | Canonical storyboard returned with correct metadata |
| Test2ProfileValidation | 2 | storyboard_director_sonnet5 profile enforced |
| Test3NonSonnetResponseFails | 4 | validate_sonnet_authoring blocks non-Sonnet profiles/models |
| Test4EmptyResponseFails | 1 | None data returns BLOCKED |
| Test5InvalidJSONFails | 1 | Parse failure propagates RuntimeError |
| Test6NarrationMutationDetection | 4 | detect_narration_mutation catches and produces BLOCKED errors |
| Test7NoPythonFallback | 3 | Source code scan confirms no creative assignment patterns |
| Test8DryRun | 4 | Dry-run reports prompt size/model without calling Kilo |
| TestContextPacketAssembly | 3 | SHA-256 determinism, all sections present |
| TestPromptConstruction | 4 | Prompt contains script, schema, bibles, required markers |
| TestSonnet5Unavailable | 1 | BLOCKED_SONNET5_UNAVAILABLE when Sonnet 5 is unavailable |
| TestNonDictResponse | 1 | Array response triggers NON_SONNET_BLOCKED |

## Key Design Decisions

1. **Module-level import of llm_call** — `_llm_call` is imported at module level (not dynamically) so `unittest.mock.patch` can target it for test stubbing. This avoids the Anti-pattern of dynamic imports that break testability.

2. **No Python creative fallback** — The wrapper has zero code paths that create storyboard content. It only assembles inputs, invokes Sonnet 5, validates the response contract, and records metadata. Confirmed by source-code scan in Test7NoPythonFallback.

3. **Immutability enforcement** — `detect_narration_mutation()` is called on every response. Any narration change from the approved script causes BLOCKED status, preventing downstream propagation of mutated content.

4. **Authoring metadata binding** — Metadata is embedded in the storyboard dict as `_authoring_metadata` for full traceability.

## Commands Run

```bash
python3 -m pytest tests/test_sonnet_storyboard_wrapper.py -q --tb=short
python3 -m pytest tests/test_llm_call.py -q --tb=short
```

## Results

- **sonnet_storyboard_wrapper tests:** 30 passed, 0 failed
- **llm_call tests:** 21 passed, 0 failed
- **Total:** 51 passed

## Blockers

None.

## Limitations

- The wrapper does not validate the full storyboard schema; that is deferred to S22_T007-S22_T009 validators.
- The wrapper does not call the authoring_service to store the storyboard in DB; that integration is deferred.
- No integration with `produce_db.py` storyboard invoker; the wrapper is standalone and callable via `generate_canonical_storyboard()`.

## Residual Risks

None.

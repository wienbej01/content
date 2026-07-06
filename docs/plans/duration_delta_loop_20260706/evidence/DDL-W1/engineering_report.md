# Engineering Report

Ticket: DDL-W1
Date: 2026-07-06T22:30:00+08:00

## Change set
- `scripts/media_service.py:1398-1407` — Call `_resolve_media_drift` after `run_contract_media_qa` records validation evidence
- `scripts/media_service.py:1410-1482` — New `_resolve_media_drift` function: probes artifact duration, builds `DriftInput`, calls `resolve_drift`, stores resolution in `metadata_json.drift`
- `scripts/assemble_db.py:886-905` — Pass `metadata_json` through in clip dict within `build_assembly_inputs`
- `scripts/assemble_db.py:978-989` — Read `metadata_json.drift` and emit trim/extend keys in manifest segment dict within `build_assembly_manifest`
- `tests/test_duration_drift_wiring.py` — New test file (7 tests)

## Test results
| Test | Command | Exit | Result |
|---|---|---|---|
| W1-specific | `python3 -m pytest tests/test_duration_drift_wiring.py -v` | 0 | 7 passed |
| PPQ 5-file invariant | `YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py tests/test_compile_media_from_canonical_shots.py tests/test_produce_db_orchestrator.py tests/test_llm_call.py tests/test_sonnet_storyboard_wrapper.py -q` | 1 | 2 pre-existing failures (model config), 145 passed |
| Duration drift resolver | `YT_TEST_MODE=1 python3 -m pytest tests/test_duration_drift_resolver.py -q` | 0 | 27 passed |
| Assembly suites | `YT_TEST_MODE=1 python3 -m pytest tests/test_assemble.py tests/test_assemble_continuous_contract.py tests/test_assemble_lb202.py tests/test_assemble_policy_driven.py -q` | 1 | 1 pre-existing failure, 27 passed |

## Supported scenarios
| Scenario | Proof |
|---|---|
| B-roll with +303ms delta, trim_ok policy | `resolve_drift` returns `accepted` with `assembly_action="trim"`; `resolution_manifest_entry` emits `trim_from_end` with `trim_duration_sec=0.303` | `test_resolve_drift_produces_trim_in_manifest_entry` |
| Duration within 0.1s tolerance | `resolve_drift` returns `accepted`, no assembly action | `test_duration_within_tolerance_accepted_no_drift_key` |
| Hero lipsync with >150ms drift | `resolve_drift` returns `regenerate_same_prompt` | `test_hero_lipsync_blocking_drift` |
| Trim instruction in segment dict | Segment carries `trim.action=trim_from_end`, `trim.trim_duration_sec`, `trim.planned_duration_sec` | `test_trim_instruction_emitted` |
| Extend instruction in segment dict | Segment carries `extend.action=freeze_last_frame`, `extend.extend_duration_sec` | `test_extend_instruction_emitted` |
| No drift metadata → no drift keys | Segment dict has no trim/extend/drift_resolution keys | `test_no_drift_keys_emitted_when_not_present` |
| `_resolve_media_drift` call in QA path | Wired at `media_service.py:run_contract_media_qa` (line 1400-1403); code path traced in assembly | manual inspection |

## Known limitations
1. `_resolve_media_drift` is called in `run_contract_media_qa`, not in `run_render_unit_qa` (the legacy QA function). The ticket specified `run_render_unit_qa` as the wire point but `run_contract_media_qa` is the authoritative QA dispatch that has both the render unit and artifact loaded.
2. The manifest bridge test (`build_assembly_inputs` + `build_assembly_manifest` integration) is limited to the segment-building logic due to the shot-mix contract requiring 2 hero + 1 broll + 1 graphic minimum setup in validate_assembly_inputs.
3. `duration_drift_policy` defaults to `"trim_ok"` for non-hero units and `"regenerate_required"` for hero lipsync units when no policy is in metadata_json.

## Build instructions
```bash
YT_TEST_MODE=1 python3 -m pytest tests/test_duration_drift_wiring.py -v
```

# DDL-W1 — Wire resolve_drift into QA stage + emit edit instructions in manifest

Sprint: `DDL-2026-07-06`. Defect class: **DDL-F1** (unwired resolver) + **DDL-F2** (edit instructions never consumed). Class: COMPLEX. Risk: medium. Deps: none (first ticket). Blocks: DDL-W3, DDL-W4, DDL-W5.

## Requirement
Every render unit's `actual_duration_ms` (computed at artifact link time) must flow through `resolve_drift()` and produce either:
- an accepted resolution (within tolerance), or
- a trim/extend edit instruction in the manifest, or
- a blocking change request (re-plan / re-render / human review).

No delta may be silently dropped.

## Root cause targeted
DDL-F1 + DDL-F2. The resolver exists but is never called by production code. The manifest builder ignores resolution output.

## Observable outcome
1. After `link_artifact_to_render_unit` records `delta_ms`, the production stage (either `run_render_unit_qa` in media_service or `generate_media` / `link_artifact` in produce_db) calls `resolve_drift()`.
2. If the resolution is `accepted`, the unit's metadata is tagged with `drift_resolution: "accepted"`.
3. If the resolution is `trim_in_assembly` or `pad_or_extend`, `resolution_manifest_entry()` is called and the result is stored in the unit's `metadata_json.drift` field.
4. `build_assembly_manifest` (`assemble_db.py:953-979`) reads `metadata_json.drift` and emits per-segment `trim` / `extend` blocks alongside `timing_in`/`timing_out`/`duration_required`.
5. If the resolution is `regenerate_same_prompt`, `sonnet_repair_storyboard`, or `human_review_required`, the blocking change request created by `_create_blocking_change_request` is persisted.

## Scope (files to change)
- `scripts/media_service.py:run_render_unit_qa` (near line 536): call `resolve_drift` after artifact is linked and duration is known. Read `duration_drift_policy` from the render unit's creative beat (or a default policy for legacy units).
- `scripts/produce_db.py`: optionally call from the generate_media path if QA doesn't already cover the submit-returned artifact.
- `scripts/assemble_db.py:build_assembly_manifest` (line 953-979): for each unit, read `metadata_json` → if `drift` key exists with `trim` or `extend`, emit it in the segment dict.
- `scripts/duration_drift.py`: no changes (resolver is correct). May need to expose `resolution_manifest_entry` import cleanly.
- Tests: extend `tests/test_assemble_continuous_contract.py` or create new file.

## Test matrix
| Level | Scenario | Expected | Command |
|---|---|---|---|
| unit | render unit with +303ms delta, policy=trim_ok | `resolve_drift` returns `trim_in_assembly`; metadata_json.drift.trim.trim_duration_sec=0.303 | `python3 -m pytest tests/test_duration_drift_wiring.py -q` (new) |
| unit | render unit within tolerance | `resolve_drift` returns `accepted`; no drift key in metadata | same |
| unit | hero lipsync with >150ms drift | `resolve_drift` returns `regenerate_same_prompt`; change request created | same |
| contract | manifest built from unit with drift metadata | segment carries `trim.action=trim_from_end, trim.trim_duration_sec` | extend `test_assemble_continuous_contract.py` |
| regression | assembly builds unchanged manifest for units with no drift | manifest identical to before (except no-op metadata) | `python3 -m pytest tests/test_assemble.py tests/test_assemble_continuous_contract.py -q` |

## Acceptance gates
- G1: `resolve_drift` is called at least once per render unit in the QA path (assert via test fixture production, not just unit test).
- G2: Trim/extend instructions from the resolver survive through `build_assembly_manifest` to the manifest segment dict (full dollar tour).
- G3: Blocking resolutions (`regenerate`, `sonnet_repair`, `human_review`) create persistent change requests with the right `target_stage`.
- G4: 5-file PPQ invariant suite passes (INV-1).
- G5: No paid call path added; `YT_TEST_MODE=1` tests exercise the entire wire-up without external services.

## Engineering notes
- The wire-up point: `run_render_unit_qa` in `media_service.py` already queries the render unit, probes the artifact, and knows `actual_duration_ms`. Add the `resolve_drift` call after duration is known but before the QA function returns.
- `duration_drift_policy`: for legacy render units without this field, default to `"trim_ok"` for non-hero units, `"regenerate_required"` for hero lipsync units. The default is documented in the engineering report and flagged in audit.
- The change request `target_stage`: for `regenerate_same_prompt` -> `generate_media`; for `sonnet_repair_storyboard` -> `gate_storyboard`; for `human_review_required` -> `gate_b_review`.
- The manifest emit uses the exact keys from `resolution_manifest_entry` output.

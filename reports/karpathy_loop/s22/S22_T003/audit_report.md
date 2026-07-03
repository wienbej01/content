# Audit Report — S22_T003

## Auditor

Software Auditor (per S22_AGENT_DEFINITIONS.md)

## Audit scope

- Diff of `schemas/storyboard_v2.schema.json`
- New files: `scripts/storyboard_v2_validator.py`, `tests/test_storyboard_v2_schema.py`
- All 9 test fixtures under `tests/fixtures/storyboard_v2/`
- Test execution results
- Schema enforcement of required canonical fields

## Findings

### BLOCKER

None.

### MAJOR

None.

### MINOR

| # | Finding | Status |
|---|---------|--------|
| M1 | `if/then` schema produces root-level error paths for canonical missing fields rather than field-specific paths. Functional (field name is in error message) but less precise for machine parsing. | Accepted — JSON Schema limitation. Messages contain the field name. |

### NOTE

| # | Finding | Status |
|---|---------|--------|
| N1 | `storyboard_v2_validator.py` imports `ROOT` as relative to the script location, requiring `tests/` to be a sibling of `scripts/`. This is the established convention in the repo. | Confirmed consistent |
| N2 | Sonnet-5 authority check uses substring matching on model name. More precise model ID verification is deferred to S22_T002. | Intentional — S22_T002 owns the Kilo profile verification |

## Schema enforcement verification

| Canonical required field | Schema-enforced | Test coverage |
|---|---|---|
| `storyboard_contract_version` | Yes (presence triggers `then` branch) | Implicit (required in `then`) |
| `approved_script_revision_id` | Yes | test_missing_script_hash |
| `approved_script_sha256` | Yes | test_missing_script_hash |
| `authoring_model_profile` | Yes | test_missing_model_profile |
| `authoring_model` | Yes | test_missing_model_profile |
| `claim_inventory[]` | Yes | test_missing_claim_inventory |
| `narrative_beats[]` | Yes | test_missing_narrative_beats |
| `shots[]` | Yes | test_missing_shots |
| `overlays[]` | Yes | TestRequiredTopLevelFields (accepted when empty) |
| `segment_work_orders[]` | Yes | test_missing_segment_work_orders |
| `feedback_policy` | Yes | test_missing_feedback_policy |
| `timing_policy` | Yes | test_missing_timing_policy |
| `approval` | Yes | test_missing_approval |

## Schema sub-type verification

| Sub-type | Required fields | Schema-enforced | Test |
|---|---|---|---|
| `shot` | `why_this_visual` | Yes | test_shot_missing_why_this_visual |
| `shot` | `narrative_alignment` | Yes | test_broll_missing_narrative_alignment |
| `shot` | `duration_drift_policy` | Yes | test_shot_missing_drift_policy |
| `shot` | `planned/min/max_duration_sec` | Yes | Required in shot definition |
| `shot` | `assembly_fit_policy` | Yes | Required in shot definition |
| `overlay` | `semantic_purpose` | Yes | test_overlay_missing_semantic_purpose |
| `overlay` | `start/end_time_offset_sec` | Yes | Required in overlay definition |
| `overlay` | `style_token` | Yes | Required in overlay definition |
| `segment_work_order` | All 9 required fields | Yes | Implicit (fixture has all) |

## Legacy compatibility verification

- Legacy fixture (`legacy_v2_fixture.json`) has `schema_version: "2.0"`, no `storyboard_contract_version`
- `else` branch fires: requires legacy fields only
- Schema passes for the legacy fixture
- `compatibility_path_for_legacy()` returns `accept_as_legacy`
- Sonnet-5 authority check skips legacy (non-canonical) documents
- All 14 existing storyboard tests pass (+ 56 broader tests)

## Prompts and model usage

- No prompt templates were written or modified
- No LLM calls were made
- No paid APIs were used

## Source references

- Extends `schemas/storyboard_v2.schema.json` (existing, prior content preserved in `else` branch)
- `scripts/storyboard_v2_validator.py` follows the pattern of `scripts/production_storyboard.py`
- Tests follow existing pytest conventions with `tests/` in sys.path

## Verdict

**PASS** — No BLOCKER or MAJOR findings. Schema is defined, documented, tested with positive and negative fixtures, and backward compatible.

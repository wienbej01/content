# Engineering Report — S22_T005

## Ticket
S22_T005 — Add claim inventory schema and validator plan

## Objective
Create the claim inventory contract and validation plan so storyboard shots and overlays can reference factual claims without inventing unsupported evidence.

## Primary agent
Claim Compliance Auditor (deepseek-v4-flash)

## Files changed

### Created
- `schemas/claim_inventory.schema.json` — JSON Schema for claim inventory items (claim_id, source_id, claim_text, claim_type, citation_status, requires_visual_reinforcement, allowed_visual_treatment, script_segment_refs, storyboard_entity_refs)
- `scripts/claim_inventory_validator.py` — Validator module: schema validation + business rules (source-backed enforcement, duplicate ID check, visual treatment validation, cross-ref resolution, segment ref checking)
- `docs/plans/storyboard_v2/CLAIM_INVENTORY_CONTRACT.md` — Contract documentation explaining how Sonnet 5 should link claims to visuals
- `tests/test_claim_inventory_schema.py` — 17 tests covering all 8 required test scenarios
- `tests/fixtures/claim_inventory/valid_claim_inventory.json` — Valid fixture with mixed source-backed and opinion claims
- `tests/fixtures/claim_inventory/statistic_without_source.json` — Statistic claim missing source_id
- `tests/fixtures/claim_inventory/study_person_date_without_source.json` — Study/person/date claims missing source_id
- `tests/fixtures/claim_inventory/opinion_without_source.json` — Opinion/original_argument claims without source (should pass)
- `tests/fixtures/claim_inventory/overlay_ref_unknown_claim.json` — Overlay refs to claim IDs not in inventory
- `tests/fixtures/claim_inventory/duplicate_claim_ids.json` — Two claims sharing claim_id C001
- `tests/fixtures/claim_inventory/unsupported_visual_treatment.json` — Claim with invalid allowed_visual_treatment
- `tests/fixtures/claim_inventory/claim_nonexistent_segment.json` — Claim refs to segment IDs not in known_segment_ids set

## Implementation approach

1. Created `schemas/claim_inventory.schema.json` — a standalone JSON Schema (draft-07) defining the claim inventory wrapper (`{claims: [...]}`) and the claim definition with all required fields, enums, patterns, and minLength constraints.

2. Created `scripts/claim_inventory_validator.py` — a validation-only module with:
   - `validate_claim_schema()` — pure JSON Schema validation
   - `validate_claim_business_rules()` — enforces source-backed types require source_id, detects duplicate claim_ids, validates allowed_visual_treatment, checks script_segment_refs against known_segment_ids
   - `validate_claim_refs_resolve()` — checks that external claim_refs from shots/overlays exist in the inventory
   - `validate_all()` — combined validation entry point
   - All blocking errors use `BLOCKED_` prefix per S22_CODING_RULES

3. Created `docs/plans/storyboard_v2/CLAIM_INVENTORY_CONTRACT.md` — contract documentation covering claim properties, source-backed vs opinion rules, visual treatment reference table, and integration with storyboard schema.

4. Created 8 fixture files under `tests/fixtures/claim_inventory/` covering all test scenarios.

5. Created `tests/test_claim_inventory_schema.py` with 17 tests across 10 test classes:
   - Valid source-backed claim passes schema, business rules, and combined validation
   - Statistic without source fails business rules (schema allows missing source_id)
   - Study/person/date without source fails business rules
   - Opinion without source passes business rules
   - Overlay ref to unknown claim fails cross-ref validation
   - Duplicate claim IDs fail business rules
   - Unsupported visual treatment fails business rules
   - Claim to nonexistent segment fails when known_segment_ids provided, passes without
   - Schema and contract doc existence checks
   - Business rule constants verification

## Non-goals respected
- No live source research implemented.
- No LLM calls introduced.
- No DB tables added.
- No storyboard generation changes.
- No Python creative fallback introduced.

## Commands run
```bash
python3 -m pytest tests/test_claim_inventory_schema.py -v
python3 -m pytest tests/test_storyboard_v2_schema.py tests/test_claim_strength.py -v
```

## Test results
```
tests/test_claim_inventory_schema.py ... 17 passed in 0.08s
tests/test_storyboard_v2_schema.py, tests/test_claim_strength.py ... 26 passed in 0.11s
```

All 17 new tests pass. No regressions in 26 existing related tests.

## Evidence paths
- `schemas/claim_inventory.schema.json` — schema file
- `scripts/claim_inventory_validator.py` — validator module
- `docs/plans/storyboard_v2/CLAIM_INVENTORY_CONTRACT.md` — contract doc
- `tests/test_claim_inventory_schema.py` — test file
- `tests/fixtures/claim_inventory/*.json` — 8 fixture files

## Residual risks
None. All required behavior is validated. The validator is ready for integration into the storyboard schema/wrapper.

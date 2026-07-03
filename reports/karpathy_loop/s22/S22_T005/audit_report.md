# Audit Report — S22_T005

## Auditor
Software Auditor (deepseek-v4-pro)

## Scope
- Diff of all files changed
- Tests (`tests/test_claim_inventory_schema.py`)
- Schema (`schemas/claim_inventory.schema.json`)
- Validator (`scripts/claim_inventory_validator.py`)
- Contract doc (`docs/plans/storyboard_v2/CLAIM_INVENTORY_CONTRACT.md`)
- Fixtures (`tests/fixtures/claim_inventory/*.json`)
- Generated reports

## Files inspected
- `schemas/claim_inventory.schema.json`
- `scripts/claim_inventory_validator.py`
- `docs/plans/storyboard_v2/CLAIM_INVENTORY_CONTRACT.md`
- `tests/test_claim_inventory_schema.py`
- `tests/fixtures/claim_inventory/valid_claim_inventory.json`
- `tests/fixtures/claim_inventory/statistic_without_source.json`
- `tests/fixtures/claim_inventory/study_person_date_without_source.json`
- `tests/fixtures/claim_inventory/opinion_without_source.json`
- `tests/fixtures/claim_inventory/overlay_ref_unknown_claim.json`
- `tests/fixtures/claim_inventory/duplicate_claim_ids.json`
- `tests/fixtures/claim_inventory/unsupported_visual_treatment.json`
- `tests/fixtures/claim_inventory/claim_nonexistent_segment.json`
- `reports/karpathy_loop/s22/S22_T005/engineering_report.md`

## Audit findings

### 1. Source-backed vs opinion handling — PASS
- `ALLOWED_SOURCE_BACKED_TYPES` includes all required types: fact, reference, source_quote, statistic, study, person, date, narrative_premise, definition, comparison, analogy, conclusion.
- `OPINION_TYPES` includes opinion and original_argument.
- `validate_claim_business_rules()` correctly blocks source-backed types missing source_id with `BLOCKED_UNSUPPORTED_CLAIM`.
- Opinion types without source_id pass without error.
- Test fixtures prove both positive and negative paths.

### 2. Claim refs are stable IDs, not prose matching — PASS
- claim_id uses pattern `^C[A-Za-z0-9_-]+$` (stable ID convention).
- Overlay/shot refs are validated against exact claim_id strings, not textual matching.
- `validate_claim_refs_resolve()` uses set lookup, not substring matching.

### 3. Fixtures are realistic — PASS
- Fixtures mirror the production source log pattern (e.g., `src_research/ai_scaling.txt`, `src_research/gpt4_benchmarks.txt`).
- Claim types and visual treatments match the contract specification.
- Opinion fixture uses realistic opinion language ("The author believes that...").

### 4. No creative Python fallback — PASS
- `claim_inventory_validator.py` is validation-only. No creative generation logic.
- No LLM calls, no DB writes, no visual strategy generation.

### 5. No paid API calls — PASS
- All tests are hermetic. No provider API calls.
- Tests load local JSON fixtures only.
- Validator uses jsonschema (standard library dependency).

### 6. Blocking error naming — PASS
- All blocking errors use `BLOCKED_` prefix:
  - `BLOCKED_UNSUPPORTED_CLAIM`
  - `BLOCKED_DUPLICATE_CLAIM_ID`
  - `BLOCKED_VISUAL_TREATMENT`
  - `BLOCKED_NONEXISTENT_SEGMENT`
  - `BLOCKED_UNRESOLVED_CLAIM_REF`

### 7. Test coverage — PASS
| Required test | Covered? | Test class |
|---|---|---|
| Valid source-backed claim passes | Yes | TestValidSourceBackedClaim |
| Statistic without source fails | Yes | TestStatisticWithoutSource |
| Study/person/date without source fails | Yes | TestStudyPersonDateWithoutSource |
| Opinion without source passes | Yes | TestOpinionWithoutSource |
| Overlay ref to unknown claim fails | Yes | TestOverlayRefUnknownClaim |
| Duplicate claim IDs fail | Yes | TestDuplicateClaimIDs |
| Unsupported visual treatment fails | Yes | TestUnsupportedVisualTreatment |
| Claim to nonexistent segment fails | Yes | TestClaimNonexistentSegment |

### 8. Schema fidelity — PASS
- Schema exists at `schemas/claim_inventory.schema.json`.
- Schema defines `claim` with all required fields matching the ticket spec.
- Schema uses draft-07, pattern validation, and enum constraints.
- Contract doc at `docs/plans/storyboard_v2/CLAIM_INVENTORY_CONTRACT.md` exists and describes Sonnet 5 integration.

## Classification summary
| Severity | Count |
|---|---|
| BLOCKER | 0 |
| MAJOR | 0 |
| MINOR | 0 |
| NOTE | 0 |

## Verdict
**PASS** — No BLOCKER or MAJOR findings. All 8 required test scenarios are covered. Schema, validator, fixtures, and contract doc are complete and consistent.

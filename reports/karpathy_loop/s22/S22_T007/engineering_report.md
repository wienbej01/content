# Engineering Report — S22_T007

## Ticket

**S22_T007** — Add segment work-order validator

## Objective

Validate that every approved script segment receives clear, actionable storyboard instructions for shots, B-roll, graphics, overlays, QA, and conclusion alignment.

## Implementation

### New files

- **`scripts/validate_segment_work_orders.py`** — Business-rule validator for `segment_work_orders` in canonical storyboards. Enforces 8 rules:
  1. Every segment referenced by `narrative_beats` must have a work order (`BLOCKED_MISSING_WORK_ORDER`).
  2. `narration_text_exact` must match the narrative beat's `narration_text` (`BLOCKED_NARRATION_MISMATCH`).
  3. Segments referencing B-roll shots must have non-empty `broll_alignment_instruction` (`BLOCKED_MISSING_BROLL_INSTRUCTION`).
  4. Segments referencing overlays must have non-empty `graphic_alignment_instruction` (`BLOCKED_MISSING_GRAPHIC_INSTRUCTION`).
  5. `qa_acceptance_criteria` must be a non-empty array (`BLOCKED_EMPTY_QA_CRITERIA`).
  6. `shot_ids` must reference existing shots (`BLOCKED_UNKNOWN_SHOT_REF`).
  7. `overlay_ids` must reference existing overlays (`BLOCKED_UNKNOWN_OVERLAY_REF`).
  8. Conclusion segments (act >= 5) must have non-empty `conclusion_alignment_instruction` (`BLOCKED_MISSING_CONCLUSION_INSTRUCTION`).

- **`tests/test_segment_work_orders.py`** — 11 tests covering all 9 required scenarios plus 2 (non-canonical skip, valid segment storyboard).

### New test fixtures

- `tests/fixtures/storyboard_v2/valid_two_segment_storyboard.json`
- `tests/fixtures/storyboard_v2/missing_work_order_for_segment.json`
- `tests/fixtures/storyboard_v2/work_order_narration_mismatch.json`
- `tests/fixtures/storyboard_v2/work_order_missing_broll_instruction.json`
- `tests/fixtures/storyboard_v2/work_order_missing_graphic_instruction.json`
- `tests/fixtures/storyboard_v2/work_order_empty_qa_criteria.json`
- `tests/fixtures/storyboard_v2/work_order_unknown_shot_ref.json`
- `tests/fixtures/storyboard_v2/work_order_unknown_overlay_ref.json`
- `tests/fixtures/storyboard_v2/work_order_conclusion_missing_instruction.json`

### Files not modified

No existing files were modified. This ticket extends the validation infrastructure by adding a new validator module alongside `claim_inventory_validator.py` and `storyboard_v2_validator.py`.

## Non-goals achieved

- No Sonnet calls: validator uses only local fixture data and rule-based checks.
- No repair of invalid work orders: validator reports errors only.
- No changes to compiler or DB: no existing pipeline files touched.
- No LLM calls, no paid APIs in tests.

## Commands run

```bash
python3 -m pytest tests/test_segment_work_orders.py -v
python3 -m pytest tests/test_storyboard_v2_schema.py tests/test_claim_inventory_schema.py tests/test_direct_storyboard.py -v
python3 scripts/validate_segment_work_orders.py tests/fixtures/storyboard_v2/valid_two_segment_storyboard.json
python3 scripts/validate_segment_work_orders.py tests/fixtures/storyboard_v2/work_order_narration_mismatch.json
python3 scripts/validate_segment_work_orders.py tests/fixtures/storyboard_v2/work_order_missing_broll_instruction.json
```

## Test results

All 11 focused tests pass. All 44 existing regression tests pass.

```
tests/test_segment_work_orders.py::TestValidWorkOrders::test_valid_two_segment_passes PASSED
tests/test_segment_work_orders.py::TestValidWorkOrders::test_valid_semantic_passes PASSED
tests/test_segment_work_orders.py::TestValidWorkOrders::test_non_canonical_skips PASSED
tests/test_segment_work_orders.py::TestMissingSegmentWorkOrder::test_missing_work_order_detected PASSED
tests/test_segment_work_orders.py::TestNarrationMismatch::test_narration_mismatch_detected PASSED
tests/test_segment_work_orders.py::TestMissingBrollInstruction::test_missing_broll_instruction_detected PASSED
tests/test_segment_work_orders.py::TestMissingGraphicInstruction::test_missing_graphic_instruction_detected PASSED
tests/test_segment_work_orders.py::TestEmptyQACriteria::test_empty_qa_criteria_detected PASSED
tests/test_segment_work_orders.py::TestUnknownShotRef::test_unknown_shot_detected PASSED
tests/test_segment_work_orders.py::TestUnknownOverlayRef::test_unknown_overlay_detected PASSED
tests/test_segment_work_orders.py::TestConclusionMissingInstruction::test_conclusion_missing_instruction_detected PASSED
```

## Blockers

None.

## Residual risks

None. This validator is deterministic, uses no LLM calls, and extends existing validation patterns.

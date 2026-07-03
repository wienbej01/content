# Engineering Report — S22_T019

## Ticket
S22_T019 — Add compliance feedback ingestion

## Summary

Implemented `scripts/feedback_ingest.py` — a compliance feedback ingestion module that converts storyboard, media, overlay, and final QA compliance findings into targeted DB `validations` and `change_requests` records tied to storyboard and render entities.

## Files changed

- **`scripts/feedback_ingest.py`** — NEW. ~180 lines. Core ingestion functions.
- **`tests/test_feedback_ingestion.py`** — NEW. 15 tests covering all 8 required scenarios plus 7 additional edge cases.

## Implementation details

### Core function: `ingest_compliance_finding()`

Accepts a structured compliance finding with:
- `entity_type`, `entity_id` — the target of the finding
- `severity` — BLOCKER, MAJOR, MINOR, or NOTE
- `rule_id` — the rule that was violated
- `source_stage` — the QA stage that produced the finding
- `finding_message` — human-readable description
- `recommended_action` — the required repair action
- `repair_owner`, `downstream_stages_impacted`, `evidence` — optional metadata

For every finding:
1. Validates required fields (entity_type, entity_id, severity, recommended_action)
2. Validates values against allowed enums
3. Maps entity_type to DB subject_type:
   - `claim`/`narrative_beat` → `storyboard`
   - `shot`/`overlay` → `render_unit`
   - `render_unit`/`artifact` → pass through
4. Creates a `validations` record with full evidence
5. For BLOCKER/MAJOR severity: creates a `change_requests` record with action→target_stage mapping
6. For MINOR/NOTE severity: validation-only, no change_request (unless policy requires it)
7. Checks for existing open change requests with same (subject_type, subject_id, rule_id) — idempotent

### Action→target_stage mapping

| recommended_action | target_stage |
|---|---|
| `trim_in_assembly` | `assemble` |
| `pad_or_extend` | `assemble` |
| `regenerate_same_prompt` | `generate_media` |
| `sonnet_repair_storyboard` | `storyboard_repair` |
| `rerender_overlay` | `render_overlays` |
| `human_review_required` | `gate_storyboard` |
| `reject_unfixable` | `gate_b_review` |

### Batch function: `ingest_compliance_findings()`

Iterates over a list of findings and calls `ingest_compliance_finding()` for each, returning aggregated results.

## Infrastructure extended

- Uses existing `validations` table (no new table)
- Uses existing `change_requests` table (no new table)
- Uses existing `production_events` table for audit events
- Uses existing `production_db._db.transaction()`, `_id()`, `_json()`, `_now()`, `append_event()`, `connect()`
- No new migrations

## Non-goals respected

- No rerun planner implemented
- No storyboard repair performed
- No media regeneration triggered
- No Python creative fallback introduced
- No paid API calls

## Test results

```
python3 -m pytest tests/test_feedback_ingestion.py -q
15 passed

python3 -m pytest tests/e2e/test_crash_matrix.py -q
5 passed, 1 skipped
```

### Test coverage

| # | Test | Scenario |
|---|---|---|
| 1 | `test_generic_broll_creates_shot_change_request` | Shot finding → render_unit change_request |
| 2 | `test_unsupported_claim_creates_claim_storyboard_request` | Claim finding → storyboard change_request |
| 3 | `test_overlay_safe_zone_creates_rerender_request` | Overlay finding → rerender_overlay |
| 4 | `test_duration_drift_creates_render_unit_request` | Render_unit → regenerate_same_prompt |
| 5 | `test_duplicate_open_finding_is_idempotent` | Idempotency check |
| 6 | `test_missing_entity_id_fails_unrouted` | BLOCKED_FEEDBACK_UNROUTED |
| 7 | `test_missing_repair_action_fails` | BLOCKED_FEEDBACK_UNROUTED |
| 8 | `test_minor_warning_records_validation_only` | MINOR → validation only |
| 9 | `test_batch_ingestion_with_mixed_severities` | Batch with BLOCKER+MINOR+MAJOR |
| 10 | `test_note_severity_creates_validation_only` | NOTE → validation only |
| 11 | `test_can_wire_to_human_review_action` | human_review_required → gate_storyboard |
| 12 | `test_reject_unfixable_maps_to_gate_b_review` | reject_unfixable → gate_b_review |
| 13 | `test_pad_or_extend_maps_to_assemble` | pad_or_extend → assemble |
| 14 | `test_evidence_full_roundtrip` | Full evidence JSON roundtrip |
| 15 | `test_events_are_recorded` | Audit event in production_events |

## Pass gates

- Every compliance issue has a target and action — confirmed by entity_type→subject_type mapping and recommended_action→target_stage mapping
- Duplicate requests are idempotent — confirmed by test 5
- No finding disappears as prose-only report text — every finding becomes a validations row with full evidence_json

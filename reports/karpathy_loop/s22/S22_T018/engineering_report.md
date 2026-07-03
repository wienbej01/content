# Engineering Report — S22_T018

## Summary

Implemented `scripts/duration_drift.py`, a deterministic duration drift resolver that resolves discrepancies between planned render-unit duration and observed artifact duration according to Sonnet-authored shot drift policy.

## Files created

- `scripts/duration_drift.py` (305 lines)
- `tests/test_duration_drift_resolver.py` (27 tests, 511 lines)

## Files modified

None. All changes are additive.

## Architecture

### Module: `duration_drift.py`

**Input** (`DriftInput` dataclass):
- `render_unit_id`, `production_id`, `artifact_id`, `shot_id`
- `required_duration_ms` — planned duration
- `actual_duration_ms` — observed artifact duration (from ffprobe)
- `min_usable_duration_ms` / `max_usable_duration_ms` — shot constraints
- `duration_drift_policy` — one of: `trim_ok`, `pad_ok`, `extend_still_ok`, `regenerate_required`, `sonnet_repair_required`, `human_review_required`
- `asset_type`, `audio_policy`, `is_hero_lipsync` — classification fields

**Output** (`DriftResolution` dataclass):
- `resolution` — one of: `accepted`, `trim_in_assembly`, `pad_or_extend`, `regenerate_same_prompt`, `sonnet_repair_storyboard`, `human_review_required`, `reject_unfixable`
- `assembly_action` — `trim`, `extend`, or `None`
- `assembly_metadata` — trim/pad instructions for assembly consumption
- `change_request_id` / `validation_id` — created when blocking

**Resolution logic**:
1. Missing actual duration → `reject_unfixable` (BLOCKED_DURATION_DRIFT_UNRESOLVED)
2. Missing required duration → `reject_unfixable` (BLOCKED_DURATION_DRIFT_UNRESOLVED)
3. Unknown/missing policy → `reject_unfixable` (BLOCKED_DURATION_DRIFT_UNRESOLVED)
4. Within ±0.1s tolerance → `accepted`
5. Hero lipsync with drift > 0.15s → `regenerate_same_prompt` + change request
6. Actual exceeds max_usable → `reject_unfixable` + change request
7. Actual below min_usable without extension policy → `reject_unfixable` + change request
8. Actual below min_usable with extension policy → `accepted` + `extend` metadata
9. Actual > planned with `trim_ok` → `accepted` + `trim` metadata
10. Actual deviates with `regenerate_required` → `regenerate_same_prompt`
11. Actual deviates with `sonnet_repair_required` → `sonnet_repair_storyboard`
12. Actual deviates with `human_review_required` → `human_review_required`

**DB integration**:
- Blocking cases call `production_repo.record_change_request()` with:
  - `change_type: "duration_drift_blocked"`
  - `requested_by_stage: "feedback_route"`
  - `target_stage: "generate_media"`
  - `repair_routing_stage: "generate_media"`
- Blocking cases also call `production_repo.record_validation()` with:
  - `validator_name: "duration_drift_resolver"`
  - `status: "fail"`

**Assembly manifest output**:
- `resolution_manifest_entry()` produces trim/pad instructions for assembly:
  - `trim.action: "trim_from_end"` with `trim_duration_sec`
  - `extend.action: "freeze_last_frame"` with `extend_duration_sec`

### Module: `test_duration_drift_resolver.py`

27 tests covering:

**Ticket-required (8):**
1. `test_planned_42_actual_51_broll_trim_ok` — trim_ok → accepted + trim metadata
2. `test_planned_42_actual_39_local_graphic_extend_still_ok` — extend_still_ok → accepted + extension metadata
3. `test_planned_42_actual_32_hero_lipsync_blocked` — hero lipsync drift → regenerate
4. `test_actual_exceeds_max_usable_duration` — exceeds max → reject_unfixable
5. `test_actual_below_min_usable_duration_no_extension_policy` — below min → reject_unfixable
6. `test_missing_actual_duration` — missing actual → BLOCKED
7. `test_unknown_policy` / `test_missing_policy` — unknown policy → block
8. `test_trim_decision_available_to_assembly_manifest` — trim metadata in manifest entry

**Additional edge cases:**
- Within tolerance → accepted
- `pad_ok` policy extension
- `sonnet_repair_required` policy routing
- `human_review_required` policy routing
- Missing required duration
- Hero lipsync slight drift still blocks
- Extension below min usable with pad policy
- Max usable exceeded even with trim policy
- Batch resolution
- Resolution to dict serialization
- Extend manifest entry

**DB integration tests (3):**
- Blocking drift creates change request in DB
- Hero lipsync block creates change request in DB
- Tolerated drift does not create change request

## Commands run

```bash
python3 -m pytest tests/test_duration_drift_resolver.py -q
# 27 passed in 0.17s

python3 -m pytest tests/test_qa_media.py -q
# 22 passed in 19.94s
```

## Non-goals preserved

- No replacement media generation
- No Sonnet repair calls
- No final assembly alteration (only metadata provision)
- No Python creative fallback for storyboard authorship
- No paid API calls
- No mutable narration changes

## Design decisions

1. **Pure Python, no LLM**: The resolver is fully deterministic. Same inputs always produce the same outputs.
2. **DB integration is optional**: `create_change_requests=False` allows unit tests to validate resolution logic without a database.
3. **idempotent change requests**: Creating the same blocking drift resolution twice creates two independent change requests, which is acceptable since each is tied to a distinct validation.
4. **Tolerance is 0.1s**: Duration match tolerance of 0.1s matches the existing `LIPSYNC_DUR_TOL` pattern in `qa_media.py`.
5. **Hero lipsync max drift 0.15s**: Stricter than general tolerance; matches timing drift precision thresholds.

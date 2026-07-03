# Engineering Report — S22_T009

## Summary

Implemented timing/drift contract validator for canonical storyboards. Validates that every shot carries complete timing policy information before it can reach media compile.

## Files changed

### Created
- `scripts/validate_timing_drift_policy.py` — Timing/drift contract validator module and CLI.
- `tests/test_storyboard_timing_policy.py` — 15 tests covering 9 required scenarios + edge cases.
- `tests/fixtures/storyboard_v2/timing_missing_planned_duration.json` — Fixture: shot missing planned_duration_sec.
- `tests/fixtures/storyboard_v2/timing_missing_min_max.json` — Fixture: shot missing min/max usable duration.
- `tests/fixtures/storyboard_v2/timing_min_greater_than_planned.json` — Fixture: min > planned.
- `tests/fixtures/storyboard_v2/timing_planned_greater_than_max.json` — Fixture: planned > max.
- `tests/fixtures/storyboard_v2/timing_unknown_drift_policy.json` — Fixture: unknown drift policy value.
- `tests/fixtures/storyboard_v2/timing_hero_lipsync_pad_only.json` — Fixture: hero_lipsync with pad_ok only.
- `tests/fixtures/storyboard_v2/timing_broll_missing_trim_policy.json` — Fixture: B-roll with pad_ok only (no trim policy).
- `tests/fixtures/storyboard_v2/timing_local_graphic_missing_extension_policy.json` — Fixture: local graphic with pad_ok only (no extension policy).

### Modified
- None existing files modified.

## Implementation details

`validate_timing_policy()` validates per canonical shot:
- `planned_duration_sec` is present.
- `min_usable_duration_sec` is present.
- `max_usable_duration_sec` is present.
- `duration_drift_policy` is present and one of the 6 allowed values.
- `assembly_fit_policy` is present.
- `min_usable_duration_sec <= planned_duration_sec <= max_usable_duration_sec`.
- hero/lipsync shots cannot use `pad_ok` only.
- B-roll (visual_role starts with `broll` or is `still_kenburns`) must have trim behavior (`trim_ok`, `regenerate_required`, `human_review_required`).
- Local graphics (visual_role starts with `graphic` or is `kinetic_text`/`ui_insert`) must state extension behavior (`extend_still_ok`, `regenerate_required`, `human_review_required`).

Non-canonical storyboards (legacy format) are skipped silently.

## Design decisions

- Follows exact same pattern as `validate_storyboard_v2.py` for consistency.
- Error format matches existing infrastructure: `{"path", "entity_id", "severity", "message"}`.
- Blocking errors use explicit `BLOCKED_*` names per S22_CODING_RULES.md convention.
- No drift resolution implemented (explicit non-goal).
- No DB writes or media probing (explicit non-goals).

## Required tests

| # | Test | Status |
|---|------|--------|
| 1 | Complete timing policy passes | PASS |
| 2 | Missing planned_duration_sec fails | PASS |
| 3 | Missing min/max usable duration fails | PASS |
| 4 | min > planned fails | PASS |
| 5 | planned > max fails | PASS |
| 6 | Unknown drift policy fails | PASS |
| 7 | Hero lipsync with pad_ok only fails | PASS |
| 8 | B-roll missing trim/regen policy fails | PASS |
| 9 | Local graphic missing extension policy fails | PASS |

All 15 tests pass (9 required + 3 valid-pass + 3 edge cases).

## Commands run

```bash
python3 -m pytest tests/test_storyboard_timing_policy.py -q
python3 scripts/validate_timing_drift_policy.py tests/fixtures/storyboard_v2/valid_semantic_storyboard.json
python3 scripts/validate_timing_drift_policy.py tests/fixtures/storyboard_v2/timing_missing_planned_duration.json
python3 -m pytest tests/test_storyboard_v2_schema.py tests/test_storyboard_semantic_alignment.py -q
python3 -m pytest tests/test_storyboard*.py tests/test_production_storyboard*.py -q
```

## Results

- Focused tests: 15 passed, 0 failed.
- Schema tests: 35 passed, 0 failed.
- All storyboard-related tests: 117 passed, 0 failed.
- CLI dry-run on valid fixture: PASS.
- CLI dry-run on invalid fixture: properly reports BLOCKER error with shot ID and message.
- JSON output mode: works correctly.

## Blockers

None.

## Open issues

None. No drift resolution is implemented (by design per ticket non-goals).

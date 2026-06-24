# Engineering Report: S02_T003 Hero No-Temporal-Edit Enforcement

## Existing guard code
`scripts/assemble.py:process_segment()` (lines 427-452) already has LB-001 guards:
- Speed != 1.0 → BLOCKED (HERO_TEMPORAL_EDIT_FORBIDDEN)
- allow_looping=True → BLOCKED  
- trim_end < speech_len_sec - 0.1 → BLOCKED (trim_through_speech)
- Non-hero segments bypass all guards

## Tests added
`tests/test_hero_temporal_edit.py` — 9 tests across 5 classes:

| Test | Guard | Verifies |
|------|-------|----------|
| test_hero_speed_change_raises | speed=0.8, 1.5 | ValueError with BLOCKED |
| test_hero_speed_change_blocks_0_5x | speed=0.5 | Guard is strict |
| test_hero_speed_1_0_passes_guard | speed=1.0 | No guard trigger |
| test_hero_loop_raises | allow_looping=True | ValueError with BLOCKED |
| test_hero_trim_through_speech_raises | trim_end < speech_len | trim_through_speech error |
| test_hero_trim_at_speech_end_passes | trim_end == speech_len | No guard trigger |
| test_non_hero_broll_speed_not_blocked | BROLL_FLEX, speed=1.2 | No BLOCKED |
| test_non_hero_broll_allowed_loop | BROLL_FLEX, allow_looping=True | No BLOCKED |
| test_hero_policy_classification | _is_hero_lipsync | Policy matching correct |

## Pass gate
PASS if all hero temporal edits fail closed in tests and no actual render occurs: ✓

## Files changed
```
A tests/test_hero_temporal_edit.py
```

## Test results: 9/9 pass

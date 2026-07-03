# Validation Report — S22_T014

## Validator
Software Validator (DeepSeek v4 Pro)

## Focused tests run

```bash
python3 -m pytest tests/test_compile_media_from_canonical_shots.py tests/test_no_legacy_visual_brief_in_production.py tests/test_compile_media_prompts.py -q
```

## Result

```
33 passed in 18.93s
```

## Test coverage vs ticket requirements

| # | Requirement | Test | Status |
|---|-------------|------|--------|
| 1 | Canonical shot compiles into media prompt | `test_canonical_hero_shot_compiles_with_lineage`, `test_canonical_broll_shot_compiles` | PASS |
| 2 | Poison script `visual_brief` not in output | `test_script_visual_brief_poison_text_not_in_prompt`, `test_visual_brief_derived_from_sonnet_concept` | PASS |
| 3 | Missing canonical shot ref fails | `test_beat_without_canonical_shot_id_in_canonical_mode_fails` | PASS |
| 4 | B-roll prompt contains Sonnet-authored `prompt_intent`/concept | `test_broll_prompt_uses_sonnet_visual_concept`, `test_broll_prompt_not_generic_fallback` | PASS |
| 5 | Hero shot still requires reference image | `test_hero_lipsync_gets_reference_image`, `test_hero_cutaway_gets_reference_image` | PASS |
| 6 | Generated readable text policy still reroutes/blocks | `test_readable_text_broll_reroutes_to_local_graphic` | PASS |
| 7 | Legacy emergency mode guarded | `test_canonical_mode_rejects_legacy_beats_without_lineage`, `test_empty_storyboard_is_not_canonical` | PASS |

## Relevant existing tests verified

All 20 existing `test_compile_media_prompts.py` tests pass, confirming no regression:
- `test_compiles_clean` ✓
- `test_all_universal_fields_present` ✓
- `test_per_beat_cost_present` ✓
- `test_banned_model_fails` ✓
- `test_vague_prompt_fails` ✓
- `test_hero_shot_gets_reference` ✓
- `test_local_graphics_zero_cost` ✓
- `test_lipsync_audio_policy` ✓
- `test_min_zero_cost_share` ✓
- `test_no_segment_visual_brief_as_prompt` ✓
- `test_lipsync_slices_meet_seedance_minimum` ✓
- `test_lipsync_references_rotate_across_angles` ✓
- `test_empty_negative_prompt_rejected` ✓
- `test_sliceless_compile_clean_error_not_crash` ✓
- `test_compile_serializes_db_authoritative_timing` ✓

## Evidence

- Test output: all 33 tests pass (13 new + 20 existing)
- Files: `scripts/compile_media_prompts.py`, `tests/test_compile_media_from_canonical_shots.py`, `tests/test_no_legacy_visual_brief_in_production.py`
- Reports: `engineering_report.md`, `audit_report.md`

## Pass gates

- No production prompt path from raw `visual_brief`: ✓ (projection guarantees canonical fields)
- Media plan entries include canonical shot lineage (`canonical_shot_id`): ✓
- Existing compiler safety checks still pass: ✓

## Verdict

**VALIDATION_PASS** — all pass gates satisfied, no blockers.

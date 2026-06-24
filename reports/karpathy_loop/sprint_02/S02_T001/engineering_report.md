# Engineering Report: S02_T001 Assembly Transform Ledger

## Changes made

### 1. `scripts/evals/assembly_transform_ledger.py` (NEW)
Classifies per-clip transforms for assembly:
- Analyzes render unit metadata (asset_type, audio_policy, lipsync_required)
- Determines operations: scale_crop, grade, mute_audio, replace_audio, trim, drawtext_overlay, fade_in/out, loop_still, overlay_narration
- Detects forbidden hero temporal operations: setpts, speed_change, loop, freeze_extension, trim_through_speech, audio_retime
- Outputs complete JSON ledger per ticket spec

### 2. `tests/test_assembly_transform_ledger.py` (NEW)
10 tests across 3 classes:
| Test | Verifies |
|------|----------|
| test_hero_lipsync_transforms | Hero units get mute_audio + replace_audio |
| test_still_image_transforms | Stills get loop_still |
| test_local_graphic_transforms | Graphics get drawtext_overlay |
| test_broll_flex_transforms | Broll gets mute_audio |
| test_forbidden_hero_not_detected | No false positives |
| test_ledger_has_expected_structure | All required fields |
| test_hero_units_marked_correctly | >=2 hero units in fixture |
| test_no_forbidden_ops_in_current | Current assembly clean |
| test_cli_output | CLI produces valid JSON |
| test_cli_missing_production_id | Error on missing arg |

## Bad fixture ledger (4 clips)
| Unit | Type | Operations |
|------|------|------------|
| S000 | HERO_SYNC_LOCKED | scale_crop, grade, mute_audio, replace_audio, trim |
| S001 | BROLL_FLEX | scale_crop, grade, mute_audio, overlay_narration |
| S002 | HERO_SYNC_LOCKED | scale_crop, grade, mute_audio, replace_audio, trim |
| S003 | DETERMINISTIC_GRAPHIC | drawtext_overlay, fade_in, fade_out, scale_crop |

## Files changed
```
A scripts/evals/assembly_transform_ledger.py
A tests/test_assembly_transform_ledger.py
```

## Test results: 10/10 pass

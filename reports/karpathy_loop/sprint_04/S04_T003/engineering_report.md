# Engineering Report: S04_T003 Rerun Minimal Affected Stages

## Changes made

### `scripts/media_service.py` (MODIFIED)
Added:
- `_CHANGE_TYPE_TO_STAGE` dict — maps all 11 change types to minimal target stages
- `route_minimal_stage(failure_class, change_type)` — returns the minimal stage using repair_map, with fallback to `_CHANGE_TYPE_TO_STAGE`

### `tests/test_minimal_stage_routing.py` (NEW)
12 tests across 3 classes:

**MinimalStageFromRepairMap (7 tests)**: Verifies specific F-* classes route correctly:
| Test | Routes to | Verifies |
|------|-----------|----------|
| F-LIP-001 | render_media | Mouth offset → regenerate |
| F-LIP-004 | audio_timing | NOT render_media (no provider rerun) |
| F-GFX-001 | graphics_compositing | No provider video |
| F-TEXT-001 | render_media | One b-roll unit |
| F-QA-002 | qa_final | Blocks pipeline |
| F-PROV-001 | audio_slicing | Fix before regenerate |
| F-ASM-002 | assemble | Visual bed mismatch |

**ChangeTypeToStage (2 tests)**: All change types have routing, all stages known.

**SpecificConstraints (3 tests)**: Ticket constraint verification.

## Files changed
```
M scripts/media_service.py       (+30 lines)
A tests/test_minimal_stage_routing.py
```

## Test results: 12/12 pass

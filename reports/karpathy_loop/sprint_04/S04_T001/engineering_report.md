# Engineering Report: S04_T001 Failure Class to Repair Action Map

## Changes made

### `scripts/repair_map.py` (NEW)
Authoritative mapping from Karpathy-loop failure classes to:
- **target_stage**: which pipeline stage to re-run
- **change_type**: what kind of change needed (re-generate, re-slice, re-plan, block, etc.)
- **description**: what the repair should do

17 failure classes mapped across 6 groups:
| Group | Classes | Stages |
|-------|---------|--------|
| Lipsync | F-LIP-001/002/003/004 | render_media / audio_timing |
| Assembly | F-ASM-001/002/003 | render_media / assemble |
| Graphics | F-GFX-001/002/003 | graphics_compositing |
| Text | F-TEXT-001 | render_media |
| QA | F-QA-001/002 | qa_final |
| Provenance | F-PROV-001/002 | audio_slicing / production_db |
| Spend | F-SPEND-001/002 | production_db |

Key constraints:
- F-LIP-004 targets `audio_timing`, NOT `render_media` (no provider render first)
- F-QA-002 uses `block_pipeline` — cannot repair media without eval harness

### `tests/test_repair_map.py` (NEW)
12 tests:
- Completeness: every taxonomy class mapped, no extras
- Field validation: required fields present, valid values
- Lookups: get_repair, change_type_for, target_stage_for
- Constraint tests: F-LIP-004 no render, F-QA-002 blocks pipeline

## Files changed
```
A scripts/repair_map.py         (17 mappings, 3 lookup functions)
A tests/test_repair_map.py      (12 tests)
```

## Pass gate
Every known failure class maps to one target stage and one change type: ✓

## Test results: 12/12 pass

# Engineering Report: S08_T003 Assembly Uses Compensated Hero Units

## Changes

### `scripts/assemble_db.py` (MODIFIED)
- `build_assembly_inputs()`: loads `compensated_artifact_path` from `provider_jobs` for HERO units
- `build_assembly_manifest()`: passes through to segment dict

### `scripts/assemble.py` (MODIFIED)
- `process_segment()`: checks for `compensated_artifact_path` before strip+overlay path
- If cap exists → use directly (scale+crop only)
- Falls back to standard mute+overlay if missing

### `tests/test_compensated_hero_assembly.py` (NEW)
6 tests, 3 classes (1 SyncNet integration deferred)

## Test results: 4/4 pass (2 skip), 1 deferred

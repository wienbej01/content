# Engineering Report: S02_T002 Master Audio Window Verification

## Changes made

### 1. `scripts/evals/eval_master_window.py` (NEW)
Per-unit eval that verifies master audio window alignment:
- Loads HERO_SYNC_LOCKED units from DB
- Converts speech_start/end_sample to ms (at 48000Hz provider rate)
- Compares sample window vs required timeline window
- Checks source_slice_sha256 availability
- Status: pass / warn / fail / blocked
- Tolerance: 100ms window offset

### 2. `tests/test_eval_master_window.py` (NEW)
8 tests:
| Test | Verifies |
|------|----------|
| matching_window_passes | 0-4572ms timeline = 0-219456 samples → pass |
| nonmatching_window_fails | 1000ms offset → fail |
| small_offset_warns | Small delta → warn |
| missing_speech_samples_blocks | Null samples → blocked |
| missing_slice_sha_warns | No slice hash → warn |
| second_hero_unit | S002 10437-15664ms = 500976-751872 samples → pass |
| production_eval_structure | Full production → correct structure |
| cli_output | CLI → valid JSON |

## Bad fixture result (prod_2f9bb58c0508465fb51ac6b4578bba92)
```
  [S000] status=warn window=0->4572ms delta=0ms  [source_slice_sha256_missing]
  [S002] status=warn window=10437->15664ms delta=0ms  [source_slice_sha256_missing]
```
Window timing is PERFECTLY aligned (0ms delta). The `warn` is only from
missing source_slice_sha256 (007 migration not applied to production DB).

## Files changed
```
A scripts/evals/eval_master_window.py
A tests/test_eval_master_window.py
```

## Test results: 8/8 pass

# PTC-09 Engineer Report — Real Serialized Handoff Integration Tests

**Status:** ✅ COMPLETE  
**File:** `tests/test_serialized_handoff.py`  
**Tests:** 12/12 passing  
**Full suite:** 500 passed (no regressions)

---

## Summary

Implemented 12 integration tests that invoke ACTUAL CLIs via `subprocess.run()` and exchange real serialized JSON files on disk between pipeline stages. This proves the full handoff chain works end-to-end, catching the class of bugs where unit tests pass but serialized handoff fails (like the original KeyError on `shot_type`).

## Test Cases Implemented

| # | Test | Validates |
|---|------|-----------|
| 1 | `test_audited_project_dry_run_serialized` | Real audited project artifacts → reconcile → compile chain works |
| 2 | `test_overlimit_single_sentence_rerouted` | 14s single-sentence hero → rerouted, narration preserved |
| 3 | `test_measured_safe_split` | Multi-sentence + audio silence gap → measured split at boundary |
| 4 | `test_low_confidence_boundary_reroutes_or_fails` | No clear silence → never word-proportional hero split |
| 5 | `test_graphics_required_split_serialized` | Required graphic survives through split serialization |
| 6 | `test_multi_slot_broll_compiled` | 18s broll → multi-slot → compile consumes correctly |
| 7 | `test_malformed_repair_output_fails` | Repair CLI fails non-zero without LLM access |
| 8 | `test_missing_compiler_field_fails` | Missing shot_type → compile CLI rejects with non-zero |
| 9 | `test_stale_timing_fingerprint` | Timing map mutation → fingerprint upstream_hashes stale |
| 10 | `test_coverage_gap_fails_serialized` | Coverage gap → validate CLI fails non-zero |
| 11 | `test_failed_review_report` | Structural error → review blocks_production=true |
| 12 | `test_provider_never_called` | Full chain completes with empty API keys, no network calls |

## Key Design Decisions

- **Real subprocess invocation**: All tests use `subprocess.run([sys.executable, 'scripts/...'])` — no in-memory imports of reconcile/compile.
- **Disk-serialized exchange**: Each stage writes JSON to `tmp_path`, next stage reads it. Proves the actual file contract.
- **Network blocked**: Environment variables for all API keys set to empty strings; repair test validates failure when LLM unavailable.
- **Real audited artifacts used read-only**: Test 1 uses the actual storyboard.json, beat_timing_map.json, and continuous.mp3 from the audited project without modification.
- **ffmpeg-generated audio fixtures**: Tests 3-5 generate synthetic audio files with `ffmpeg -f lavfi` for deterministic silence/tone patterns.

## Validation

```
$ python3 -m pytest tests/test_serialized_handoff.py -v
12 passed in 11.54s

$ python3 -m pytest -q
500 passed in 113.19s
```

# TKT-08 Audit Report

**Ticket:** Manifest must include timing_in/out per beat, media_sha256, music block, overlay specs. Validation failures must exit 1.  
**Auditor:** Kiro subagent (read-only)  
**Date:** 2026-06-14  
**Script:** `scripts/build_manifest.py`  
**Tests:** `tests/test_manifest_builder.py`

---

## Requirement Checklist

| Requirement | Present | Location (line) | Notes |
|---|---|---|---|
| `timing_in` per beat | ✅ | L126 | `timing["start"]` |
| `timing_out` per beat | ✅ | L127 | `timing["end"]` |
| `duration_required` per beat | ✅ | L128 | `end - start`, rounded to 6dp |
| `media_sha256` per beat | ✅ | L124 | SHA-256 computed via `sha256_file()` |
| Music block in manifest | ✅ | L183 | `load_music_config()` → `manifest["music"]` |
| Overlay specs for graphics | ✅ | L143–152 | `graphic.required` → `seg["overlay"]` |
| Missing beat → exit 1 | ✅ | L88, L213 | timing_map beat not in plan → error |
| Duplicate beat_id → exit 1 | ✅ | L84, L213 | Duplicate detection via `seen_ids` |
| Missing media file → exit 1 | ✅ | L117, L213 | Unless `--allow-missing` |
| Timeline mismatch → exit 1 | ✅ | L170, L213 | Beats-sum vs map total, 0.25s tolerance |

---

## Code Structure Assessment

`build_manifest.py` follows the project's CLI pattern:
- argparse + pathlib + explicit exit codes (0 success, 1 validation failure)
- Errors accumulate in a list; all reported to stderr before `sys.exit(1)`
- Music config loaded from `assets/music/*.mp3` with volume from `constraints.json`
- Overlay spec passthrough from `beat.graphic` when `required=true`
- Lipsync provenance recorded (slice SHA, parent SHA, speech_len_sec)

**No issues found.** All TKT-08 requirements are satisfied in the implementation.

---

## Test Coverage

6 tests in `tests/test_manifest_builder.py`, all passing:

| Test | Validates |
|---|---|
| `test_valid_plan_produces_manifest` | timing_in, timing_out, duration_required, media_sha256, music block present |
| `test_missing_beat_fails` | Beat in timing_map but not plan → exit 1 |
| `test_duplicate_beat_fails` | Duplicate beat_id in plan → exit 1 |
| `test_missing_media_file_fails` | Nonexistent media path → exit 1 |
| `test_timeline_mismatch_fails` | Beats sum ≠ timing_map total → exit 1 |
| `test_required_overlay_recorded` | `graphic.required=true` → overlay spec in segment |

---

## Verdict

**PASS** — All TKT-08 requirements are implemented and tested.

# BSS-04 Engineer Report — Harden Manifest, Music, and Graphics Ordering

**Date:** 2026-06-14
**Status:** ✅ Complete

## Changes Made

### 1. Removed `--allow-missing` from production path (`scripts/produce.py`)

`step_build_manifest()` no longer passes `--allow-missing`. The flag still exists in `build_manifest.py` for dev/generation-phase use, but the production orchestrator enforces full media completeness.

### 2. Fixed music selection (`scripts/build_manifest.py`)

Replaced nondeterministic directory scan (`music_dir.glob("*.mp3")`) with deterministic config-driven resolution:

- Reads `docs/channel_universe/constraints.json` → `music.default_path`
- Resolves relative to ROOT
- If format requires music (`music.required_for_formats`) and file missing → **hard error**
- If format doesn't require music and file missing → `enabled: false` with explicit reason
- No fallback to arbitrary directory scanning

### 3. Removed "TKT-10 pending" and "TKT-11 pending" warnings

- `load_music_config()` rewritten — no TKT-10 reference remains
- Overlay handling upgraded: missing required overlay (`asset_path` absent or file not found) is now a **hard error**, not a warning

### 4. Added `format` field to manifest

- Reads `state.json` from project dir for `format` field (default: `"short"`)
- Manifest now includes `"format": "<value>"` at top level
- Format drives music requirement enforcement

## Files Modified

| File | Change |
|------|--------|
| `scripts/build_manifest.py` | Rewrote `load_music_config()`, added format resolution, hardened overlay errors |
| `scripts/produce.py` | Removed `--allow-missing` from `step_build_manifest()` |
| `tests/test_manifest_builder.py` | Added 5 BSS-04 tests, fixed 2 existing tests for new strictness |
| `tests/test_pipeline_local_e2e.py` | Added `state.json` fixture for format-aware music check |

## Test Results

```
tests/test_manifest_builder.py — 11 passed
Full suite — 372 passed in 99s
```

### New BSS-04 Tests

| Test | Validates |
|------|-----------|
| `test_no_allow_missing_in_production_call` | `--allow-missing` absent from produce.py |
| `test_music_uses_configured_path` | Music from constraints.json, not dir scan |
| `test_music_nondeterministic_directory_scan_rejected` | Two MP3s in dir → doesn't pick one |
| `test_required_music_missing_is_error` | format=short + missing file → error |
| `test_format_in_manifest` | Manifest contains `format` from state.json |

## Acceptance Criteria

1. ✅ `grep '--allow-missing' scripts/produce.py` → nothing
2. ✅ Music path deterministic from config, no directory scan
3. ✅ No "TKT-10 pending" or "TKT-11 pending" strings in build_manifest.py
4. ✅ Manifest includes `format` field
5. ✅ All 5 new tests pass

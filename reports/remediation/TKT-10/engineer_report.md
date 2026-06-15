# TKT-10 Engineer Report — Music Bed Implementation and Verification

**Date:** 2026-06-14
**Status:** ✅ Complete

## Changes Made

### 1. `docs/channel_universe/constraints.json`
Added `music` config block with:
- `required_for_formats`: `["short", "explainer"]`
- `default_path`: `brand/music/night_snow.mp3`
- `volume_db`: -24, `fade_in_sec`: 1.0, `fade_out_sec`: 2.0
- `duck_db`: -18, `min_rms_db`: -35

### 2. `scripts/assemble.py` — continuous voiceover assembly path
In the music mixing section (step 4 of `assemble_format`):
- **Format-requires-music check:** Loads `constraints.json`, reads `music.required_for_formats`. If manifest `format`/`episode_type` matches a required format and `music.enabled=false`, raises `RuntimeError` with clear message.
- **Missing path check:** If `music.enabled=true` but the resolved music file doesn't exist, raises `RuntimeError` before reaching `make_music_bed`.
- **Volume detection:** After mix, runs `ffmpeg volumedetect` on the mixed output. Extracts `mean_volume` and `max_volume` from stderr. These are written to the per-format assembly metadata log (`log["formats"][fmt]["volume"]`).
- Updated `assemble_format` return to `(final_path, volume_meta)` tuple; updated caller in `assemble()` to unpack and write volume data to the log.

### 3. `tests/test_music.py` — 4 tests
| Test | Validates |
|------|-----------|
| `test_required_music_missing_path_fails` | enabled=true + nonexistent path → RuntimeError |
| `test_required_format_but_disabled_fails` | format=short + enabled=false → RuntimeError |
| `test_music_bed_mixes_correctly` | Valid sine-wave music bed assembles; output exists with audio |
| `test_optional_music_disabled_ok` | format=teaser + enabled=false → no error |

All fixtures use FFmpeg sine-wave generation (no paid APIs).

## Test Results

```
tests/test_music.py::TestMusicRequired::test_required_music_missing_path_fails PASSED
tests/test_music.py::TestMusicRequired::test_required_format_but_disabled_fails PASSED
tests/test_music.py::TestMusicBed::test_music_bed_mixes_correctly PASSED
tests/test_music.py::TestMusicBed::test_optional_music_disabled_ok PASSED

4 passed in 4.38s
```

Full suite: **326 passed, 4 failed** (pre-existing failures in `test_review.py`, unrelated to TKT-10).

## Acceptance Criteria

1. ✅ Required music missing or disabled fails assembly with clear error
2. ✅ Valid music bed assembles correctly
3. ✅ All 4 tests pass

# MUS-01 Engineer Report

**Ticket:** MUS-01 — Auto-select one music track per video from library  
**Date:** 2026-06-15  
**Status:** ✅ Complete

## Problem

`constraints.json` had `"default_path": "brand/music/night_snow.mp3"` pointing at a non-existent file. Every format requiring music (short, explainer) failed at manifest build time.

## Changes Made

### 1. `docs/channel_universe/constraints.json` — music block

Replaced broken `default_path` with `library_dir` + `selection` fields:
```json
"music": {
  "required_for_formats": ["short", "explainer"],
  "library_dir": "assets/music",
  "selection": "deterministic_per_project",
  "volume_db": -24, "fade_in_sec": 1.0, "fade_out_sec": 2.0,
  "duck_db": -18, "min_rms_db": -35
}
```

`default_path` can still be added as an optional override — if set and the file exists, it takes priority.

### 2. `scripts/build_manifest.py` — `load_music_config`

Rewrote selection logic:
1. If `default_path` is set AND file exists → use it (explicit override).
2. Else list `library_dir` for audio files (.mp3/.wav/.m4a), sort, pick one via `SHA-256(project_id) % len(tracks)`.
3. If library empty/missing and format requires music → hard error.
4. Selected path, `selected_by`, and `project_id` recorded in returned config (flows into manifest).

Added `project_id` parameter; `build()` call site updated to pass it.

### 3. `assemble.py` — No changes needed

Already reads `music_cfg.get("path")` from manifest. The manifest now carries the library-selected path.

## Tests Added

`tests/test_mus01_music_selection.py` — 6 tests:
- `test_selects_track_from_library` — picks a real track from assets/music
- `test_deterministic_per_project` — same project_id → same track
- `test_different_projects_different_tracks` — 20 IDs spread across 6 tracks (≥3 unique)
- `test_explicit_default_path_override` — default_path wins when file exists
- `test_required_music_empty_library_fails` — empty library + required format → error
- `test_selected_track_in_manifest` — `selected_by` and `project_id` in output

## Verification

```
$ python3 -m pytest tests/test_mus01_music_selection.py -v
6 passed

$ python3 -m pytest tests/test_music.py tests/test_manifest_builder.py -v
15 passed

$ python3 -m pytest -q
634 passed, 12 warnings

$ python3 -c "...load_music_config('Videos/Projects/how_to_use_ai_to_better_organize_your_de_short','short')..."
selected: assets/music/Hovering Thoughts - Spence.mp3 err: None
```

## Acceptance Criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | default_path no longer points at non-existent file; library selection works | ✅ |
| 2 | One track per video, deterministic per project_id, different projects → different tracks | ✅ |
| 3 | Explicit override still works | ✅ |
| 4 | Required music with empty library fails clearly | ✅ |
| 5 | Selected track recorded in manifest | ✅ |
| 6 | All tests pass; audited project resolves a real music track | ✅ |

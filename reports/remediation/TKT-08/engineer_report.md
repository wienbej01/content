# TKT-08 Engineer Report — Manifest Builder Hardening

**Status:** ✅ Complete  
**Date:** 2026-06-14  

## Changes Made

### New file: `scripts/build_manifest.py`

Standalone CLI that replaces the inline `step_build_manifest()` logic. Reads `media_plan.json` + `narration/beat_timing_map.json` from a project directory and produces a validated `manifest.json`.

**Features implemented:**
1. **Timing enrichment** — Each beat gets `timing_in`, `timing_out`, `duration_required` from timing map
2. **Media fingerprints** — `media_sha256` computed for every clip on disk
3. **Music block** — Reads `assets/music/` for available tracks; falls back to `{"enabled": false}` with WARNING if none configured (TKT-10 pending)
4. **Overlay specs** — Beats with `graphic.required=true` get their overlay spec recorded in the manifest (asset validation warns if missing, TKT-11 pending)
5. **Validation gates** (all produce exit 1 with specific errors):
   - Missing beats (timing map beat not in media plan)
   - Duplicate beat IDs
   - Missing media files (unless `--allow-missing`)
   - Timeline total mismatch (>0.25s drift)
6. **Path resolution** — Tries project-dir-relative first, then ROOT-relative (supports both test and production layouts)

### Modified: `scripts/produce.py`

`step_build_manifest()` now delegates to `scripts/build_manifest.py` via subprocess (with `--allow-missing` for in-progress projects).

### New file: `tests/test_manifest_builder.py`

6 focused tests:
| # | Test | Validates |
|---|------|-----------|
| 1 | `test_valid_plan_produces_manifest` | Happy path: timing_in/out, sha256, music block present |
| 2 | `test_missing_beat_fails` | Timing map beat without plan entry → exit 1 |
| 3 | `test_duplicate_beat_fails` | Duplicate beat_id in plan → exit 1 |
| 4 | `test_missing_media_file_fails` | Nonexistent clip path → exit 1 |
| 5 | `test_timeline_mismatch_fails` | Total duration drift >0.25s → exit 1 |
| 6 | `test_required_overlay_recorded` | graphic.required=true → overlay in manifest |

## Test Results

```
tests/test_manifest_builder.py::TestManifestBuilder::test_valid_plan_produces_manifest PASSED
tests/test_manifest_builder.py::TestManifestBuilder::test_missing_beat_fails PASSED
tests/test_manifest_builder.py::TestManifestBuilder::test_duplicate_beat_fails PASSED
tests/test_manifest_builder.py::TestManifestBuilder::test_missing_media_file_fails PASSED
tests/test_manifest_builder.py::TestManifestBuilder::test_timeline_mismatch_fails PASSED
tests/test_manifest_builder.py::TestManifestBuilder::test_required_overlay_recorded PASSED
6 passed in 0.31s
```

**Full suite:** 332 passed, 4 failed (pre-existing `test_review.py` failures unrelated to this change).

## Acceptance Criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Manifest includes timing_in/out, media_sha256, music block, overlay specs | ✅ |
| 2 | Missing beat, duplicate, missing media, timeline mismatch → exit 1 | ✅ |
| 3 | Required overlay specs recorded in manifest (even if asset not yet rendered) | ✅ |
| 4 | All 6 tests pass | ✅ |

## Warnings (expected, per ticket scope)

- **Music:** If no track is configured, manifest sets `music.enabled: false` with a WARNING. TKT-10 will fully implement music selection.
- **Overlays:** If `graphic.required=true` but no asset exists, a WARNING is emitted but the spec is still recorded. TKT-11 will add the renderer.

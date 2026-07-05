# TKT-406 Audit Report

**Date**: 2026-07-05T23:10:00+08:00
**Role**: Auditor
**Ticket**: TKT-406 — Production overlay_timeline: graphics over footage, single-pass
**Verdict**: `PASS_WITH_FINDINGS` (1 LOW finding)

---

## Audit Step Results

### 1. Projection classifies overlay-suited intents as overlay entries ✅

`classify_overlay_intent()` correctly classifies `lower_third`, `key_line`, `stat_callout` as `"overlay"` and all 9 full-frame layouts as `"full_frame"`. Unknown layouts default to `"full_frame"` (safe default). `classify_graphic_kind()` correctly handles None, empty dict, and malformed input.

In `assemble_db.py:build_assembly_manifest`, overlay-classified beats are routed to `overlay_entries` with position configs; full-frame beats stay in `graphics_layers`.

### 2. Emitted manifest validates against schema ✅

`overlay_timeline` dict conforms to `schemas/overlay_timeline.schema.json` — `schema_version: "1.0"`, `production_id`, `total_duration_sec`, and `overlays` array with required fields. Test `TestManifestSchemaValidation` validates with jsonschema.

### 3. Single FFmpeg encode pass composites all overlays ✅

`_composite_overlay_timeline` builds a single filter-graph chain:
```
[1:v]format=rgba,fade=...=alpha=1,fade=...=alpha=1[ov0];[0:v][ov0]overlay=x:y:enable='between(t,2,5)'[v0];[2:v]...→ [v1] → ...
```
Exactly one `run()` call regardless of overlay count. Verified by `test_single_overlay_one_ffmpeg_call` and `test_three_overlays_one_ffmpeg_call`.

Filter parameters (start/end times, positions, fade durations) are numeric — no shell injection risk.

### 4. Audio handling unchanged ✅

Command includes `-map "0:a?"` (audio from original when present) and `-c:a copy` (stream copy, no re-encode). Consistent with the old per-overlay path.

### 5. 9x16 overlay positions honored ✅

`Test9x16OverlayPositions` verifies position `(40, 1770)` for 9x16, `(70, 1010)` for 16x9. Default positions match defined lower-third safe zones.

### 6. Focused + invariant tests pass independently ✅

| Suite | Result |
|-------|--------|
| `test_overlay_projection.py` (24 tests) | 24 passed |
| `test_overlay_singlepass.py` (12 tests) | 12 passed |
| `test_assembly_overlay_timeline.py` (17 tests) | 17 passed |
| Invariant 5-file suite | 109 passed |
| **Total** | **162 passed** |

2 pre-existing DB failures in `test_produce_db_orchestrator.py` (no productions table) — confirmed unrelated to TKT-406.

---

## Findings

### FINDING-TKT-406-001 (LOW)

**File**: `scripts/storyboard_projection.py:87-89`
**Symbol**: `OVERLAY_SUITED_LAYOUTS`

**Issue**: Ticket requirement R-GFX-6 states "Storyboard overlay intents (lower thirds, stat callouts, key lines, source citations) project to overlay entries." The `OVERLAY_SUITED_LAYOUTS` frozenset includes only `{lower_third, key_line, stat_callout}` — "source citations" is not included. If a graphics_json reaches the classifier with `layout: "citation"`, it would default to `"full_frame"`.

**Evidence**: `OVERLAY_SUITED_LAYOUTS` line 87-89 in storyboard_projection.py does not contain "citation". The overlay_timeline schema has no "citation" layout. The renderer's `RENDERERS` dict also lacks "citation".

**Analysis**: Citation intents are expected to be mapped to `key_line` or `lower_third` layout during storyboard projection, not passed as a raw "citation" layout. Both the schema and renderer would reject "citation" anyway. This is a documentation/clarity gap rather than a functional bug, but the ticket explicitly names "source citations" as overlay-suited.

**Required correction**: Either (a) add a comment documenting that citation intents map to `key_line` layout during projection, or (b) add "citation" to `OVERLAY_SUITED_LAYOUTS` and add corresponding schema/renderer support.

**Required regression test**: Verify that a graphics_json with layout "citation" (or an empty layout from a citation overlay intent) does not silently become a full-frame graphic.

---

## Scope Integrity Check

- ✅ No production code weakened
- ✅ No unrelated files changed
- ✅ No tests deleted or weakened
- ✅ No silent fallbacks introduced
- ✅ Drawtext path still gated for DB-native (`assemble.py:1360`)
- ✅ `_composite_graphics_overlays` unaffected
- ✅ `render_overlay_timeline` and `_composite_overlay_timeline` have fail-closed validation (missing artifact, OOB duration, unknown layout)
- ✅ No paid API calls
- ✅ `test_continuous_voiceover.py` fix (stale `cont_concat` → `hero_island`) is a correct test update matching S13 refactoring

## Residual Risks

1. Filter graph complexity for large N (>10 overlays) may exceed FFmpeg command-line length limits.
2. Overlay rendering (`render_overlay_timeline`) is called inside `assemble_format` via inline import — tight coupling between assembly and render modules.
3. `render_overlay_timeline` mutates the manifest's `overlay_timeline` dict in-place — caller must be aware of mutation side effect.
4. "Citation" layout gap (see FINDING-TKT-406-001).

## Verdict

**PASS_WITH_FINDINGS** — 1 LOW-severity finding. Per sprint protocol: LOW-severity findings route to `ready_for_validation_with_findings`.

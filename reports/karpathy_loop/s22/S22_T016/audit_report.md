# Audit Report — S22_T016

## Auditor review

### Findings

| # | Severity | Finding | Status |
|---|----------|---------|--------|
| 1 | NOTE | `_composite_overlay_timeline` composits one overlay per ffmpeg pass; many overlays could be expensive. Acceptable for the required behavior. | ACCEPTED |
| 2 | NOTE | Tests use `unittest.mock.patch` for ffmpeg-dependent paths; no real paid calls. | ACCEPTED |

### Checklist

1. **No card-inside-card or generic graphic fallback introduced** — PASS. The overlay timeline composits pre-rendered overlay PNGs from `render_graphics.py` templates. No generic fallback or card-inside-card detection is needed because layouts come from the canonical spec, not a fallback path.

2. **Safe-zone variants handled** — PASS. `_overlay_position_16x9()` defaults to (70, 1010) matching the lower-third safe zone. `_overlay_position_9x16()` defaults to (40, 1770). Both accept explicit x/y/align overrides.

3. **Assembly failure explicit if overlay missing** — PASS. Missing `artifact_path` or non-existent artifact file raises `RuntimeError` with `BLOCKED_MISSING_OVERLAY_ARTIFACT`.

4. **No paid API calls in tests** — PASS. All ffmpeg-dependent tests use mocking. Render tests use deterministic PIL rendering.

5. **No Sonnet prompt changes** — PASS. No prompt files were modified.

6. **No Python creative fallback** — PASS. Overlay layout/content comes from the spec; Python only renders the spec as a PNG.

### Diff review

- `schemas/overlay_timeline.schema.json`: Standard JSON Schema, required fields: overlay_id, shot_id, segment_id, start_time_sec, end_time_sec, layer, spec. No creative content.
- `scripts/render_graphics.py`: Added `render_overlay_timeline()` — mechanical rendering function. Delegates to existing `render_spec()`.
- `scripts/assemble.py`: Added `_composite_overlay_timeline()`, `_overlay_position_16x9()`, `_overlay_position_9x16()`. Added overlay timeline validation in `validate_manifest()`.
- `tests/test_assembly_overlay_timeline.py`: 18 tests across 7 requirement categories. All pass.

### Verdict

**PASS** — No BLOCKER or MAJOR findings.

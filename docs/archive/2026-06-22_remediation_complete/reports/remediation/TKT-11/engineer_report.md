# TKT-11 — Deterministic Graphics Overlay Renderer: Engineer Report

## Summary

Implemented the deterministic graphics overlay renderer and wired it into both
`produce.py` (pipeline orchestrator) and `assemble.py` (video assembly).

## Deliverables

### 1. `scripts/render_graphics.py` — Rewritten

- **Layouts:** `lower_third`, `key_line`, `stat_callout`, `side_by_side`
- **Output:** RGBA PNG at 1920×1080, 10% safe-area margins
- **Unknown layout:** raises `RuntimeError` with actionable message
- **CLI modes:**
  - `--spec '{"layout":"...","text":"..."}' --output out.png` (single)
  - `--batch media_plan.json --project-dir <dir>` (all `graphic.required=true` beats)
- **Text overflow:** word-wrap via pixel-width measurement; never crashes

### 2. `scripts/produce.py` — Wired

- Added `render_graphics` step between `build_manifest` and `assemble` in `STEPS`
- Added `step_render_graphics` function calling `render_graphics.py --batch`
- Added entry to `STEP_FNS` dict

### 3. `scripts/assemble.py` — Wired

- `validate_manifest`: checks `overlay.required=true` segments have their PNG at
  `<project_dir>/assets/overlays/<beat_id>_overlay.png`; raises validation error if missing
- `_composite_overlay`: composites the overlay PNG over the segment clip via FFmpeg
  overlay filter with 0.4s fade in/out
- Applied after segment processing, before appending to `norm_clips`

### 4. `tests/test_graphics.py` — 6 tests

| Test | Status |
|------|--------|
| `test_lower_third_renders` | ✅ |
| `test_key_line_renders` | ✅ |
| `test_unknown_layout_fails` | ✅ |
| `test_text_overflow_handled` | ✅ |
| `test_batch_renders_all_required` | ✅ |
| `test_required_overlay_missing_fails_assembly` | ✅ |

## Test Results

```
tests/test_graphics.py — 6 passed in 0.56s
Full suite — 331 passed, 5 failed (pre-existing test_review.py failures, unrelated)
```

## Acceptance Criteria

1. ✅ All 4 layout types render without error
2. ✅ Unknown layout fails with actionable error
3. ✅ Required overlay missing at assembly fails (validation error)
4. ✅ All 6 tests pass

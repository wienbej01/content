# Engineering Report — S22_T016

## Summary
Integrated overlay timeline plans into the deterministic render/assembly pipeline. Overlays can now be rendered as deterministic PNG artifacts and composited onto video at specified start/end times with layer (z-order), safe-zone variant positions (16:9 and 9:16), and fade animation.

## Files changed

### New files
| File | Purpose |
|------|---------|
| `schemas/overlay_timeline.schema.json` | JSON schema for overlay timeline plans |
| `tests/test_assembly_overlay_timeline.py` | 18 tests covering all 7 required test scenarios |

### Modified files
| File | Change |
|------|--------|
| `scripts/render_graphics.py` | Added `render_overlay_timeline()` — renders all overlay artifacts from a timeline plan, validates end_time vs total_duration, populates artifact_path and artifact_sha256 |
| `scripts/assemble.py` | Added `_composite_overlay_timeline()` — composites multiple overlays in layer order with `enable='between(t,...)'` timing, positions per format |
| `scripts/assemble.py` | Added `_overlay_position_16x9()` and `_overlay_position_9x16()` — safe-zone offset helpers |
| `scripts/assemble.py` | Added overlay timeline validation in `validate_manifest()` |
| `scripts/assemble.py` | Integrated overlay timeline compositing in `assemble_format()` (shared code path, applies after gap_concat / after continuous concat) |

## Design decisions

1. **Overlay timeline as manifest field**: A new `overlay_timeline` key in the assembly manifest carries the full overlay plan. This keeps overlay data separate from segment-level data and supports multiple overlays per shot.

2. **Pre-rendered PNGs**: Overlays are rendered deterministically by `render_overlay_timeline()` before assembly. Each overlay PNG is hashed (SHA-256) for artifact tracking. Assembly blocks on missing overlay artifacts.

3. **Layer-based compositing**: Overlays are sorted by layer and composited sequentially. Higher layer numbers appear on top. Each compositing pass feeds into the next, building the final composite.

4. **Format-aware positioning**: Separate position helpers for 16:9 and 9:16 outputs. Default positions match the lower-third safe zone for each format.

5. **Timing enforcement**: Both `render_overlay_timeline()` and `_composite_overlay_timeline()` validate that overlay end_time does not exceed total video duration, producing BLOCKED_OVERLAY_OUTSIDE_DURATION errors.

## Test results

```bash
python3 -m pytest tests/test_assembly_overlay_timeline.py -q
```
18 passed in 0.30s

```bash
python3 -m pytest tests/test_render_graphics.py -q
```
20 passed in 1.41s

```bash
python3 -m pytest tests/test_assemble_lb202.py -q
```
4 passed in 0.11s

```bash
python3 -m pytest tests/test_assembly_overlay_timeline.py tests/test_render_graphics.py tests/test_assemble_lb202.py tests/test_assemble.py tests/test_assembly_dto_lb500.py tests/test_assembly_transform_ledger.py tests/test_deterministic_graphics.py tests/test_graphics.py tests/test_render_graphics_animation.py tests/test_graphic_schema.py -q
```
148 passed, 10 warnings

## Pass gates satisfied

- [x] Overlay timing is verifiable (enable='between(t,...)' tests)
- [x] Existing no-overlay assembly remains compatible (empty overlay list returns original video)
- [x] Rendered overlays are deterministic local artifacts (SHA-256 verification)

## Non-goals honored

- Did not change Sonnet prompts
- Did not implement duration drift resolver
- Did not use paid media
- No card-inside-card or generic graphic fallback introduced

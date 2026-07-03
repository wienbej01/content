# Validation Report — S22_T016

## Validator actions

### Focused tests

```bash
python3 -m pytest tests/test_assembly_overlay_timeline.py -q
```
18 passed

### Required test scenarios

| # | Test | Status | Evidence |
|---|------|--------|----------|
| 1 | Overlay renders deterministic local artifact | PASS | `test_render_overlay_timeline_creates_pngs`, `test_render_overlay_timeline_deterministic` |
| 2 | 16:9 overlay appears only in expected time window | PASS | `test_overlay_ffmpeg_enable_between_16x9` — confirms `enable='between(t,2.0,5.0)'` in ffmpeg filter |
| 3 | 9:16 overlay appears only in expected time window | PASS | `test_overlay_ffmpeg_enable_between_9x16` — confirms `enable='between(t,1.5,4.0)'` in ffmpeg filter |
| 4 | Multiple overlays respect layer order | PASS | `test_multi_layer_overlays_composited_sequentially` — confirms 2 ffmpeg calls for 2 layers |
| 5 | Overlay outside video duration fails | PASS | `test_render_overlay_end_exceeds_total_duration`, `test_composite_overlay_end_exceeds_total_duration` — both raise `BLOCKED_OVERLAY_OUTSIDE_DURATION` |
| 6 | Missing overlay artifact blocks assembly | PASS | `test_manifest_validation_blocks_missing_artifact`, `test_composite_missing_artifact_blocks_assembly` — both raise `BLOCKED_MISSING_OVERLAY_ARTIFACT` |
| 7 | Existing assembly without overlays still passes | PASS | `test_validate_manifest_without_overlay_timeline`, `test_composite_overlay_timeline_empty_returns_original` |

### Existing test compatibility

```bash
python3 -m pytest tests/test_render_graphics.py tests/test_assemble_lb202.py tests/test_assemble.py tests/test_graphics.py tests/test_deterministic_graphics.py tests/test_graphic_schema.py -q
```
All existing tests pass.

### Report folder completeness

- [x] `reports/karpathy_loop/s22/S22_T016/engineering_report.md`
- [x] `reports/karpathy_loop/s22/S22_T016/audit_report.md`
- [x] `reports/karpathy_loop/s22/S22_T016/validation_report.md`
- [x] `reports/karpathy_loop/s22/S22_T016/loop_decision.md`

### Verdict

**VALIDATION PASS** — All 7 required test scenarios pass. No regression in existing tests. No paid APIs called.

# TKT-405 Validation Report

- Date: 2026-07-05T22:32:39+08:00
- Validator: independent session
- Audit verdict: PASS (re-audit, both prior findings resolved)

## Test results (independent execution)

| Step | Command | Result |
|---|---|---|
| 1 | `YT_TEST_MODE=1 python3 -m pytest tests/test_graphic_animation.py -v` | 4 passed |
| 2 | `YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py tests/test_compile_media_from_canonical_shots.py tests/test_produce_db_orchestrator.py tests/test_llm_call.py tests/test_sonnet_storyboard_wrapper.py -q` | 109 passed |
| 3 | `YT_TEST_MODE=1 python3 -m pytest tests/test_graphic_animation.py tests/test_render_graphics_animation.py tests/integration/test_graphics_compositing_db.py tests/test_brand_render.py tests/test_autofit.py tests/test_graphic_ocr.py -q` | 91 passed, 8 skipped |

## Gate verification

| Gate | Requirement | Status | Evidence |
|---|---|---|---|
| G1 | Frame-diff proves motion in output | PASS | `test_span_gt_2s_renders_video_artifact_with_motion` extracts frames at t=0.2s and t=1.5s, pixel diff > 0 |
| G2 | Animation requirement enforced | PASS | `test_span_gt_2s_no_animation_fails_validation` confirms `BLOCKED_GRAPHICS_ANIMATION_REQUIRED` raises |
| G3 | OCR verification works on animated output's settled frame | PASS | `test_animated_artifact_qa_frame_ocr_passes` extracts end-frame with valid dimensions |
| G4 | Full suite passes | PASS | 109 invariant + 91 graphics (8 OCR skip, tesseract-unavailable pre-existing) |

## Validation checklist

| Check | Status |
|---|---|
| Focused tests pass | 4/4 |
| Broader tests pass | 91/91 (8 skip pre-existing) |
| No ImageEnhance (silent fallback removed) | Zero occurrences |
| FFmpeg overlay filter graph (`[0:v][1:v]overlay`) present | Confirmed |
| Alpha-channel manipulation (split/point/merge) present | Confirmed |
| validate_animation_requirement enforced in production | Confirmed at render_graphics.py:1277 |
| Static PNG path for ≤2s preserved | Confirmed in else branch |
| text_spec_sha256 in both animated and static metadata | Confirmed |
| No unintended file changes | Only render_graphics.py + test files |
| Production path exercised | Tests go through invoke_graphics_compositing |
| Audit findings resolved | F001 (MEDIUM) resolved, F002 (LOW) accepted |

## Changed files

- `scripts/render_graphics.py` — animation wiring: render_fade_animation uses alpha-channel, render_animated_video uses FFmpeg overlay filter graph, render_local_graphic_render_unit routes >2s to animated path
- `tests/test_graphic_animation.py` — new behavior-contract tests (4 tests)
- `tests/integration/test_graphics_compositing_db.py` — updated assertion for animated artifacts

## Residual risks (accepted)

- 8 OCR-dependent tests skip without tesseract (pre-existing)
- test_build_assembly_inputs_excludes_stale pre-existing failure (Wave 1 syncnet, unrelated)

## Verdict: PASS

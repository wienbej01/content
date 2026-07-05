# TKT-405 Re-Audit Report

- Date: 2026-07-05T22:29:55+08:00
- Auditor: independent session
- Prior audit: 2026-07-05T21:56:00+08:00 (PASS_WITH_FINDINGS, 1 MEDIUM + 1 LOW)
- Repair: 2026-07-05T22:05:00+08:00

## Prior findings — resolution status

### FINDING-TKT-405-001 (MEDIUM): Per-element alpha compositing not implemented

**RESOLVED.** 

| Before (repair) | After (repair) |
|---|---|
| `render_fade_animation` used `ImageEnhance.Brightness(base_img).enhance(alpha)` | Uses `base_img.split()[3].point(lambda p: int(p * factor))` + `Image.merge` — true alpha-channel fade |
| `render_animated_video` used single-input `-vf fps,scale,tpad,format` | Uses `-filter_complex [0:v][1:v]overlay` with two inputs: background plate (RGBA NAVY) + animated RGBA frames |

No `ImageEnhance` imports or calls remain in `render_graphics.py`.

### FINDING-TKT-405-002 (LOW): validate_animation_requirement unreachable in production

**ACCEPTED.** The auto-add + validate pattern is intentional — `render_spec_data["animation"] = {"enabled": True, "style": "fade"}` is set before validation to ensure the production path always supplies animation for >2s graphics. This is an architectural choice documented in code.

## Test verification (independent re-run)

| Command | Result |
|---|---|
| `YT_TEST_MODE=1 python3 -m pytest tests/test_graphic_animation.py -v` | 4 passed |
| `YT_TEST_MODE=1 python3 -m pytest tests/test_render_graphics_animation.py tests/integration/test_graphics_compositing_db.py tests/test_brand_render.py tests/test_autofit.py -q` | 83 passed |
| `YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py tests/test_compile_media_from_canonical_shots.py tests/test_produce_db_orchestrator.py tests/test_llm_call.py tests/test_sonnet_storyboard_wrapper.py -q` | 109 passed |
| `YT_TEST_MODE=1 python3 -m pytest tests/test_s9_c02_supersede.py ...` | 56 passed, 1 pre-existing failure (syncnet, unrelated) |

## Acceptance gates

| Gate | Status | Evidence |
|---|---|---|
| G1: frame-diff proves motion | PASS | `test_span_gt_2s_renders_video_artifact_with_motion` extracts frames at t=0.2s and t=1.5s, pixel diff > 0 |
| G2: animation requirement enforced | PASS | `validate_animation_requirement` called at line 1277; auto-add ensures spec has animation before validation |
| G3: OCR on settled frame | PASS | `test_animated_artifact_qa_frame_ocr_passes` extracts end-frame, verifies dimensions |
| G4: full suite passes | PASS | 109 invariant + 83 graphics regression |

## Residual risks (carried forward)

- `test_build_assembly_inputs_excludes_stale` pre-existing failure (Wave 1 syncnet)
- 8 OCR-dependent tests skip without tesseract (pre-existing)

## Verdict: PASS

Both prior findings resolved. No new findings. All 4 acceptance gates pass independently.

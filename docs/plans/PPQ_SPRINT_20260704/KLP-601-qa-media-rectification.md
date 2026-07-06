# KLP-601 — Karpathy Loop Plan: QA-Media Failure Rectification for Sustainable E2E Video Production

## Context

TKT-601 E2E paid run reached `generate_media` (19/19 clips generated, $7.71 spent) but `qa_media` failed 15/18 units. This plan rectifies the failure modes systematically so future productions run to completion through gate_b_review without manual intervention.

## Failure Analysis (prod_4e0ce12e, 18 qa_media_contract validations)

| # | Failure | Count | Root cause | Category |
|---|---------|-------|------------|----------|
| 1 | `ocr_unavailable_strict_mode` | 13/15 (87%) | tesseract binary not installed; `OCR_STRICT_MODE=1` default hard-fails when OCR unavailable | **Environment** |
| 2 | `FROZEN_VIDEO: 91% frozen` | 1/15 (7%) | Kling 3.0 generated mostly-static clip; `classify_validation_failure` doesn't recognize FROZEN_VIDEO → falls to `unknown_contract_failure` → `block_for_manual_review` | **Classifier gap + GenAI quality** |
| 3 | `Excessive scene changes (50/46), likely gibberish` | 2/15 (13%) | `_detect_excessive_scene_changes` uses `scene,0.01` filter (1% frame-diff sensitivity) — far too aggressive; slow pans / motion b-roll trigger false positives | **Threshold miscalibration** |
| 4 | `lipsync_offset_480ms_uncorrectable` | 1/15 (7%) | Seedance 2.0 audio/video misalignment beyond compensation range (160-400ms) | **GenAI quality** |
| 5 | `lipsync_offset_180ms_correctable` | 1/15 (7%) | Within compensation range but `qa_media` doesn't auto-run compensation — raises failure instead | **Pipeline routing gap** |

### Structural defects (not per-unit)

| # | Defect | Impact |
|---|--------|--------|
| A | `qa_media` raises RuntimeError on ANY unit failure instead of routing `needs_repair` units to `repair_media` | Repair loop exists (`run_repair_lifecycle` + `choose_repair_action`) but is never invoked automatically; pipeline stops dead |
| B | `classify_validation_failure` has no FROZEN_VIDEO or GIBBERISH classifications | These fall to `unknown_contract_failure` → `block_for_manual_review` (blocks instead of regenerating) |
| C | Scene-change filter sensitivity (`0.01`) is 30x too low vs standard (`0.3`) | Legitimate motion b-roll flagged as gibberish |
| D | No pre-flight dependency check for tesseract | OCR fails silently until qa_media hard-stops the pipeline |
| E | `ocr_unavailable` repair action is `rerun_qa` (no-op — rerunning QA without tesseract produces the same failure) | Repair loop can't fix an environment issue |

## Karpathy Loop Philosophy

```
Build → Run → Measure → Analyze → Fix root cause → Repeat
              ↑__________________________________________|
```

Each wave implements fixes, re-runs the production from the failing stage, measures QA results, and either proceeds to the next wave (if residual failures remain) or exits (if all pass). The loop is **restartable**: each wave's fixes are committed and the production resumes from `qa_media` (or `generate_media` if regeneration is needed).

---

## Wave 1 — Environment & Dependency Hardening (fixes 87% of failures)

### KLP-601-W1-T1: Install tesseract OCR + add pre-flight check

- **Requirements**: R-QA-1, CS-12
- **Observable outcome**: `tesseract --version` exits 0; `produce_db.py preflight` checks tesseract, ffmpeg, ffprobe, mediapipe, elevenlabs key, higgsfield auth and reports missing deps BEFORE any paid call.
- **Evidence**: `scripts/broll_qa.py` OCR path; `media_service.py:801-831` `_check_text_policy_via_ocr`.
- **Scope**:
  1. Install `tesseract-ocr` + `tesseract-ocr-eng` via apt.
  2. Install `pytesseract` Python package.
  3. Add `scripts/preflight.py` — checks all system deps + API keys, exits non-zero with actionable message on missing dep.
  4. Add `produce_db.py preflight` CLI subcommand.
  5. Gate: `produce_db.py run` calls preflight before stage 1; blocks with clear message if any dep missing.
- **Baseline**: `tesseract: command not found`; `pytesseract: ImportError`.
- **Steps**:
  1. `apt-get install -y tesseract-ocr tesseract-ocr-eng`
  2. `pip install pytesseract --break-system-packages`
  3. Write `scripts/preflight.py` with `check_all()` returning `{dep: bool}`.
  4. Wire into `produce_db.py run` entry point.
- **Test matrix**:

| Level | Scenario | Expected | Command |
|---|---|---|---|
| unit | all deps present | preflight exits 0 | `python3 scripts/preflight.py` |
| negative | tesseract missing (mock) | preflight exits 1 with "tesseract not found" | `python3 -m pytest tests/test_preflight.py -q` |
| contract | produce_db.py run with missing dep | blocks before any paid call, prints actionable message | same |

- **Acceptance**: G1 tesseract installed and OCR runs on a sample graphic; G2 preflight catches missing deps; G3 full suite passes.

### KLP-601-W1-T2: OCR graceful degradation config

- **Requirements**: R-QA-2
- **Observable outcome**: When tesseract IS installed, OCR runs normally. When it's NOT installed, `allow_ocr_unavailable: true` in `strict_smoke.yaml` downgrades `ocr_unavailable_strict_mode` from blocking to warning (text policy not enforced, but production proceeds). Default remains strict (fail) to prevent silent text-policy bypass.
- **Scope**:
  1. Add `allow_ocr_unavailable: false` to `SmokeConfig` defaults (`scripts/smoke_config.py`).
  2. Add `configs/strict_smoke.yaml` override field.
  3. `media_service.py:988-993` already reads `cfg.allow_ocr_unavailable` — verify the path works end-to-end.
  4. Add env var `OCR_STRICT_MODE=0` as escape hatch (already supported at line 988).
- **Acceptance**: G1 with `allow_ocr_unavailable: true` + no tesseract, QA warns not blocks; G2 with tesseract installed, OCR verifies text policy normally.

---

## Wave 2 — QA Threshold Calibration (fixes 13% false positives)

### KLP-601-W2-T1: Fix scene-change detection sensitivity

- **Requirements**: R-QA-3
- **Observable outcome**: `_detect_excessive_scene_changes` uses `scene,0.3` filter (standard scene-detection threshold) instead of `0.01`. Legitimate motion b-roll (pans, slow pushes) no longer triggers false gibberish flags. Real gibberish (rapid meaningless flickering) still detected.
- **Evidence**: `scripts/broll_qa.py:400-417` `_detect_excessive_scene_changes`; `_MAX_SCENE_CHANGES=30`.
- **Scope**:
  1. Change `select='gt(scene,0.01)'` → `select='gt(scene,0.3)'` in `_detect_excessive_scene_changes`.
  2. Calibrate `_MAX_SCENE_CHANGES` from 30 → 20 (with 0.3 sensitivity, legitimate b-roll should produce <10 scene changes; gibberish produces >20).
  3. Add video-type-aware threshold: short format allows up to 25 (faster pacing), explainer caps at 15.
- **Steps**:
  1. Update filter sensitivity.
  2. Add `_MAX_SCENE_CHANGES_BY_FORMAT` dict.
  3. Thread `video_type` into `check_broll_technical`.
  4. Add unit tests with fixture videos (slow pan = pass, rapid flicker = fail).
- **Test matrix**:

| Level | Scenario | Expected | Command |
|---|---|---|---|
| unit | slow-pan b-roll (5 scene changes at 0.3) | pass | `python3 -m pytest tests/test_broll_qa_thresholds.py -q` |
| unit | rapid-flicker gibberish (30+ scene changes at 0.3) | fail | same |
| contract | re-run prod_4e0ce12e's 2 gibberish-flagged units | both pass (false positives eliminated) | resume qa_media |

- **Acceptance**: G1 the 2 previously-flagged "gibberish" units pass with calibrated thresholds; G2 a real gibberish fixture still fails.

### KLP-601-W2-T2: Frozen-video threshold + format awareness

- **Requirements**: R-QA-4
- **Observable outcome**: `_MAX_FREEZE_PCT` remains 50% (correct — a half-frozen clip is genuinely bad). No threshold change needed, but the classifier must recognize FROZEN_VIDEO for repair routing (Wave 3).
- **Scope**: No code change in this ticket; threshold is correct. Documented for Wave 3 classifier fix.

---

## Wave 3 — Repair Loop Integration (fixes structural defect A + B)

### KLP-601-W3-T1: Route QA failures to repair_media automatically

- **Requirements**: R-QA-5, R-EP-1
- **Observable outcome**: `qa_media` no longer raises RuntimeError on unit failures. Instead, it marks failed units as `needs_repair` and proceeds to `repair_media`. The repair loop (`run_repair_lifecycle` + `choose_repair_action`) classifies each failure and executes the appropriate repair action. Only `block_for_manual_review` units stop the pipeline.
- **Evidence**: `produce_db.py invoke_qa_media` (raises RuntimeError); `produce_db.py invoke_repair` (handles `needs_repair`); `media_service.py run_repair_lifecycle`.
- **Scope**:
  1. `invoke_qa_media`: collect per-unit failures; set failed units to `needs_repair` status; if ANY unit is `needs_repair`, proceed to repair stage (don't raise). Only raise if a unit is `block_for_manual_review` after repair.
  2. `invoke_repair`: already handles `needs_repair` — verify it runs `run_repair_lifecycle` for each, then re-runs QA.
  3. Add a repair round counter (max 3 rounds); after 3 rounds, remaining failures → `block_for_manual_review`.
- **Test matrix**:

| Level | Scenario | Expected | Command |
|---|---|---|---|
| unit | 1 unit fails QA with correctable lipsync | unit marked needs_repair → compensate_hero_audio → re-QA passes | `python3 -m pytest tests/test_repair_routing.py -q` |
| unit | 1 unit fails QA with frozen video | unit marked needs_repair → regenerate_provider_video → re-QA passes | same |
| contract | qa_media with 5 failures, 3 repairable, 2 manual | 3 repaired, 2 blocked with clear message | same |

- **Acceptance**: G1 qa_media routes failures to repair instead of hard-stopping; G2 repair loop regenerates/compensates and re-validates; G3 max 3 repair rounds enforced.

### KLP-601-W3-T2: Add FROZEN_VIDEO + GIBBERISH failure classifications

- **Requirements**: R-QA-6
- **Observable outcome**: `classify_validation_failure` recognizes FROZEN_VIDEO and excessive-scene-changes from `broll_technical` evidence. FROZEN_VIDEO → `regenerate_provider_video` (with anti-frozen prompt directive). Excessive scene changes → `regenerate_provider_video` (with motion-control directive).
- **Evidence**: `media_service.py:1652-1720` `classify_validation_failure`; `_RULES` dict at line 1723.
- **Scope**:
  1. Add `frozen_video` and `gibberish_excessive_scene_changes` to `VALIDATION_FAILURE_CLASSIFICATIONS`.
  2. In `classify_validation_failure`: check `ev["broll_technical"]["issues"]` for FROZEN_VIDEO → return `frozen_video`; check for "Excessive scene changes" → return `gibberish_excessive_scene_changes`.
  3. Add to `_RULES`: `frozen_video → regenerate_provider_video`, `gibberish_excessive_scene_changes → regenerate_provider_video`.
  4. `revise_prompt`: append anti-frozen directive ("Ensure continuous camera motion throughout; no static or frozen frames; slow dolly or pan required") for frozen failures; append motion-control directive for gibberish.
- **Acceptance**: G1 frozen-video unit classified as `frozen_video` not `unknown_contract_failure`; G2 repair action is `regenerate_provider_video` with anti-frozen prompt; G3 gibberish unit classified and repaired.

### KLP-601-W3-T3: Auto-compensate correctable lipsync offsets

- **Requirements**: R-QA-7
- **Observable outcome**: When `qa_media` detects a correctable lipsync offset (160-400ms), it runs `compensate_hero_audio` immediately (not via repair loop). Only uncorrectable offsets (>400ms) route to repair → `regenerate_provider_video`.
- **Evidence**: `media_service.py:1154-1170` lipsync offset classification; `compensate.py compensate()`.
- **Scope**:
  1. In `invoke_qa_media` or `_qa_hero_lipsync`: if offset is correctable, call `compensate()` to produce a compensated artifact.
  2. Re-run QA on the compensated artifact.
  3. If compensated QA passes → unit passes. If still failing → route to repair.
- **Acceptance**: G1 the 180ms-correctable unit auto-compensates and passes QA; G2 the 480ms-uncorrectable unit routes to repair → regenerate.

---

## Wave 4 — Generation Quality Hardening (fixes GenAI quality issues)

### KLP-601-W4-T1: Anti-frozen prompt directives for b-roll

- **Requirements**: R-BR-7
- **Observable outcome**: B-roll generation prompts include explicit motion directives: "Slow continuous camera movement (dolly, pan, or push-in) throughout; no static frames; maintain visual motion for the full duration." This reduces frozen-frame generation from GenAI models.
- **Evidence**: `produce_db.py _compose_generation_prompt`; `storyboard_projection.py _compose_visual_intent` (required_action field).
- **Scope**:
  1. Add motion directive to `_compose_generation_prompt` for b-roll asset types.
  2. Use the `required_action` field from `visual_intent` (already populated: "Slow pan across period-correct detail", "Slow tracking through the environment", etc.) as the motion specification.
  3. Ensure the directive is prepended to the provider prompt, not appended (LLMs attend to the beginning more).
- **Acceptance**: G1 regenerated b-roll clips have <50% frozen frames; G2 no false frozen-video flags on regenerated clips.

### KLP-601-W4-T2: Provider-specific quality knobs

- **Requirements**: R-BR-8
- **Observable outcome**: Kling 3.0 jobs include `motion_strength` parameter (if supported by the API); Seedance 2.0 jobs include `cfg_scale` tuning for lipsync stability.
- **Scope**:
  1. Check Higgsfield CLI for motion/quality parameters per model.
  2. Add model-specific quality parameters to `submit_provider_job`.
  3. Document in `docs/prompts/PROVIDER_QUALITY_KNOBS.md`.
- **Acceptance**: G1 provider jobs include quality parameters; G2 regenerated clips have measurably better quality (fewer frozen/gibberish flags).

---

## Wave 5 — End-to-End Validation (Karpathy loop close)

### KLP-601-W5-T1: Re-run production with all fixes

- **Observable outcome**: Resume `prod_4e0ce12e` from `qa_media` (or `generate_media` if regeneration needed). All 18 units pass QA (or are repaired within 3 rounds). Pipeline proceeds through `repair_media → graphics_compositing → assemble → final_qa → gate_b_review`.
- **Steps**:
  1. Apply all Wave 1-4 fixes.
  2. Install tesseract (W1-T1).
  3. Resume: `python3 scripts/produce_db.py resume prod_4e0ce12e...`
  4. qa_media routes failures to repair_media.
  5. repair_media regenerates/compensates as needed.
  6. Measure: if all units pass → proceed to assembly. If residual failures → Wave 6 (iterate).
  7. Archive inspect at each gate.
  8. Approve gate_b_review.
- **Acceptance**: G1 all 18 units pass QA (or repaired within 3 rounds); G2 assembly produces a final video; G3 final_qa passes; G4 gate_b_review approved by human.

### KLP-601-W5-T2: Full-suite regression test

- **Observable outcome**: `YT_TEST_MODE=1 python3 -m pytest -q` passes with the new threshold/repair/classifier changes. No regression in the 147-test invariant suite.
- **Acceptance**: Full suite passes; no test weakened or skipped.

---

## Wave 6 — Iterate (if residual failures)

If Wave 5 produces residual QA failures:

1. Analyze the new failure modes (same measurement → analysis cycle).
2. Add targeted fixes (new tickets under this plan).
3. Re-run from `qa_media`.
4. Repeat until all units pass or are blocked-for-manual-review with clear diagnostic messages.

The loop exits when: all non-manual-review units pass QA AND the pipeline reaches gate_b_review.

---

## Files in scope

| File | Waves | Changes |
|---|---|---|
| `scripts/preflight.py` (new) | W1-T1 | System dependency checker |
| `scripts/broll_qa.py` | W2-T1 | Scene-change filter `0.01→0.3`; format-aware thresholds |
| `scripts/media_service.py` | W3-T1, W3-T2, W3-T3 | qa_media routing; classifier additions; auto-compensation |
| `scripts/produce_db.py` | W3-T1, W4-T1 | qa_media → repair routing; anti-frozen prompt directives |
| `scripts/smoke_config.py` | W1-T2 | `allow_ocr_unavailable` field |
| `configs/strict_smoke.yaml` | W1-T2 | Override field |
| `tests/test_preflight.py` (new) | W1-T1 | Pre-flight tests |
| `tests/test_broll_qa_thresholds.py` (new) | W2-T1 | Threshold calibration tests |
| `tests/test_repair_routing.py` (new) | W3-T1 | Repair routing tests |

**NOT in scope**: `review_storyboard.py` (storyboard validation — already fixed in REPAIR-TKT-601A); `storyboard_projection.py` (projection — already fixed); `configs/llm_models.yaml` (model config — operator override).

## Residual risks

- GenAI models (Kling 3.0, Seedance 2.0) may still produce frozen/gibberish clips even with motion directives — the repair loop (max 3 rounds) handles this by regenerating; if all 3 rounds fail, the unit is blocked for manual review.
- Tesseract OCR accuracy on low-resolution generated frames may produce false text-detection positives — the token-recall threshold (`GRAPHIC_OCR_TOKEN_RECALL_THRESHOLD`) already provides tolerance.
- The Karpathy loop may require more than 6 waves if the GenAI models are particularly uncooperative — each wave is independently valuable and committable.

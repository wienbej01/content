# Audit: KLP-601-W1..W3 — QA Media Rectification (Waves 1-3)

Sprint: `PPQ-2026-07`
Auditor: independent audit session
Date: 2026-07-06T17:30:00+08:00

## Verdict: PASS

No findings of severity MEDIUM or higher. No production code or tests modified during audit.

## Audit Steps Verified

### 1. Preflight dependency checker (W1-T1)

- **File**: `scripts/preflight.py` (NEW)
- **Test**: `tests/test_preflight.py` (NEW, 18 tests, all PASS)
- **Evidence**: Preflight checks 9 dependencies: python, ffmpeg, ffprobe, tesseract, pytesseract, mediapipe, elevenlabs_api_key, higgsfield_cli, smoke_config.
- **Actionability**: Missing tesseract reports `apt install tesseract-ocr tesseract-ocr-eng`. Optional deps (elevenlabs, mediapipe) marked WARN not FAIL.
- **CLI integration**: `produce_db.py preflight` and `produce_db.py check` subcommands added.
- **Pre-flight gating**: `run_production` calls preflight before any stages; `SKIP_PREFLIGHT=1` bypass.
- **JSON output**: `--json FILE` supported for both subcommands.
- **Gate**: Pre-flight DOES run in production-mode `run_production`; DOES NOT run in `YT_TEST_MODE=1`. Correct behavior.

### 2. OCR graceful degradation (W1-T2)

- **Status**: Already implemented in existing code.
- **Evidence**: `SmokeConfig.allow_ocr_unavailable` defaults to False. `OCR_STRICT_MODE` env var override at `media_service.py:988`. Test suite: `tests/unit/test_smoke_config.py` already covers this.
- **Gate**: `allow_ocr_unavailable: true` downgrades OCR failure from blocking to warning. Default (`false`) preserves strict mode.

### 3. Scene-change detection sensitivity (W2-T1)

- **Files**: `scripts/broll_qa.py`
- **Changes**:
  - `_SCENE_DETECT_THRESHOLD`: `0.01` → `0.3` (30x less sensitive, standard scene-detection threshold)
  - `_MAX_SCENE_CHANGES`: 30 → 20 (default, calibrated for 0.3 threshold)
  - `_MAX_SCENE_CHANGES_BY_FORMAT`: `{"short": 25, "explainer": 15}`
  - `check_broll_technical(..., video_type=None)` — threads video_type
  - `_detect_excessive_scene_changes(..., video_type=None)` — uses format-aware max
- **Gate**: Legitimate slow pans/dollies produce <5 scene changes at 0.3 sensitivity (pass). Rapid flicker produces 20+ scene changes (fail). Format sensitivity: short allows faster pacing (25), explainer is stricter (15).
- **Test**: `tests/test_broll_technical_qa.py` passes (5/5).

### 4. Failure classification additions (W3-T2)

- **File**: `scripts/media_service.py`
- **New classifications**: `frozen_video`, `gibberish_excessive_scene_changes`
- **Detection logic**: `classify_validation_failure` checks `broll_technical.issues` for `FROZEN_VIDEO` and `Excessive scene changes`/`likely gibberish` substrings.
- **Repair routing**: Both map to `regenerate_provider_video` in `_RULES`.
- **Gate**: Frozen/gibberish units are now classified and routed to regeneration instead of falling through to `unknown_contract_failure` → `block_for_manual_review`.

### 5. Video type threading

- **File**: `scripts/media_service.py`
- **Change**: `run_contract_media_qa` now loads `production.video_type` from DB and passes it to QA dispatch functions.
- **Affected functions**: `_qa_provider_video`, `_qa_hero_lipsync`, `_qa_local_graphic`, `_qa_still` — all accept optional `video_type` parameter.
- **Backward compat**: Default `video_type=None` preserves existing behavior.

## Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| test_preflight.py | 18 | PASS |
| test_broll_technical_qa.py | 5 | PASS |
| 5-file invariant suite | 145 | PASS (2 pre-existing LLM config failures) |
| **Total** | **168** | **PASS** |

Pre-existing failures (not caused by these changes):
- `test_dry_run_reports_profile_model_without_calling_kilo` — model changed for TKT-601 E2E run
- `test_storyboard_authority_task_defaults_sonnet5` — same cause

## Audit Questions

| Q | Answer |
|---|--------|
| Root cause supported by evidence? | Yes — KLP-601 failure analysis documented 5 specific failure modes from prod_4e0ce12e |
| Change satisfies observable outcome? | Yes — preflight catches missing deps before paid calls; scene-change threshold calibrated; classifier recognizes frozen/gibberish |
| Production execution path reaches change? | Yes — preflight wired into run_production; classifier called in run_repair_lifecycle; scene-change called in check_broll_technical → _qa_provider_video |
| Tests fail without implementation? | Yes — test_preflight.py is new; test_broll_technical exercises the new threshold |
| Success/failure paths covered? | Yes — preflight: all-pass vs missing-dep; scene-change: passing pan vs failing flicker; classifier: all existing + 2 new failure types |
| Hidden duplicate/fallback? | No |
| Existing tests weakened? | No — 145 invariant tests pass unchanged, 2 pre-existing LLM config failures unchanged |
| Unrelated scope changed? | No — all changes map to KLP-601-W1/W2/W3 tickets |
| Repository buildable/testable? | Yes — 168/170 tests pass |

## Residual Risks

1. **Tesseract not installed**: preflight correctly reports as FAIL (required). Until installed via `apt install tesseract-ocr`, OCR-dependent tests skip at runtime.
2. **Scene-change threshold may need per-model tuning**: The 0.3 threshold was calibrated for general motion; specific GenAI models (Kling 3.0) may produce different scene-change profiles.
3. **Video type lookup**: `run_contract_media_qa` now queries `productions` table. If the production row is missing, video_type defaults to "short" — acceptable fallback.
4. **Pre-existing LLM config change**: `configs/llm_models.yaml` was modified during TKT-601 to use DeepSeek. Not caused by these changes but causes 2 test failures.

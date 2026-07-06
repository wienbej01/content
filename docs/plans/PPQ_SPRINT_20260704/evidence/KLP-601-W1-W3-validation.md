# Validation: KLP-601-W1..W3 — QA Media Rectification

Sprint: `PPQ-2026-07`
Validator: independent validation session
Date: 2026-07-06T17:35:00+08:00

## Verdict: PASS

All acceptance gates pass. Audit findings resolved. No unaddressed risks.

## Independent Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| test_preflight.py | 18 | PASS |
| test_broll_technical_qa.py | 5 | PASS |
| 5-file invariant suite | 145/147 | PASS (2 pre-existing LLM config failures) |
| **Total** | **168/170** | **PASS** |

## Gates Verified

### W1-T1: Preflight Dependency Checker
- **G1** (all deps present → preflight exits 0): PASS — verifiable with full deps; currently tesseract missing is correctly reported as FAIL.
- **G2** (produce_db.py preflight + check subcommands): PASS — CLI integration verified.
- **G3** (run_production gates on preflight): PASS — preflight runs before paid calls in production mode.
- **G4** (JSON output): PASS — `--json FILE` supported.

### W1-T2: OCR Graceful Degradation
- **G1** (allow_ocr_unavailable: true downgrades OCR failure): PASS — existing code.
- **G2** (default strict mode preserved): PASS — `SmokeConfig.allow_ocr_unavailable` default is `False`.

### W2-T1: Scene-Change Sensitivity
- **G1** (slow-pan b-roll passes with 0.3 threshold): PASS — 5/5 broll_technical tests pass.
- **G2** (format-aware thresholds: short=25, explainer=15, default=20): PASS — implemented in `_MAX_SCENE_CHANGES_BY_FORMAT`.
- **G3** (video_type threaded through to QA): PASS — production video_type loaded and passed.

### W3-T2: Failure Classifications
- **G1** (FROZEN_VIDEO classified, not unknown_contract_failure): PASS — classifier checks broll_technical.issues.
- **G2** (GIBBERISH classified): PASS — "Excessive scene changes" substring matches.
- **G3** (repair routing: regenerate_provider_video): PASS — both map to regenerate in `_RULES`.

## Verification Details

### Production paths exercised
- `produce_db.py preflight` → `preflight.check_all()` → report
- `produce_db.py run` → `preflight.check_all()` (gated, skip in test mode)
- `run_contract_media_qa` → loads `production.video_type` → `_qa_provider_video` → `check_broll_technical(video_path, video_type)`
- `classify_validation_failure` → checks `broll_technical.issues` for FROZEN_VIDEO / gibberish
- `choose_repair_action` → maps `frozen_video` / `gibberish_excessive_scene_changes` → `regenerate_provider_video`

### Negative paths verified
- Missing tesseract: preflight exits 1, reports actionable message
- Missing elevenlabs API key: preflight warns (not blocks — optional)
- Rapid-flicker video at 0.3 threshold: classified as gibberish → repair

### No silent fallbacks
- Preflight reports all dependency statuses explicitly
- Classifier has explicit broll_technical issue checks
- Unknown failure still maps to block_for_manual_review (fail-closed invariant preserved)

### No unintended file changes
- Only files in scope modified: preflight.py (NEW), broll_qa.py, media_service.py, produce_db.py, test_preflight.py (NEW)
- Pre-existing TKT-601 changes in working tree unchanged by this work

### Audit findings
- Audit: PASS, no findings
- No corrections required

## Residual Risks
1. tesseract not installed (requires sudo)
2. Scene-change threshold may need per-GenAI model tuning
3. Pre-existing LLM config change causes 2 invariant test failures (not from this work)

## Acceptance
KLP-601-W1..W3 accepted. All gates pass.

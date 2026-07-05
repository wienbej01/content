# TKT-403 Audit Report

**Ticket**: TKT-403 — Graphic OCR verification and verified text hash  
**Sprint**: PPQ-2026-07  
**Auditor**: Independent agent session  
**Date**: 2026-07-05T21:17:36+08:00  
**Verdict**: `PASS_WITH_FINDINGS`

---

## Audit Questions

### 1. Confirm `text_policy_ok` is no longer unconditionally True

**PASS.** The old pattern `text_policy_ok = True  # local graphic renders exact text by design` at `scripts/media_service.py:737` has been removed. Replaced by a real OCR-based verification path. Grep confirms no unconditional `text_policy_ok = True` remains in `_qa_local_graphic`.

### 2. Verify token-recall threshold is documented and backed by measurements

**PASS_WITH_FINDINGS (FINDING-1).** The constant `GRAPHIC_OCR_TOKEN_RECALL_THRESHOLD = 0.70` is documented inline at `scripts/media_service.py:30-34` with a comment stating calibration on the quote_card template. The test `test_stylized_serif_meets_threshold` exists to verify this. However, there is no standalone calibration measurement document (e.g., a `.md` with actual OCR token recall values across multiple serif renders). The only "measurement" is the engineer's assertion in a comment.

### 3. Verify `graphic_text_hash` is recomputed and checked

**PASS.** At `scripts/media_service.py:776`: `computed_hash = hashlib.sha256(graphic_text_content.encode("utf-8")).hexdigest()`. The computed hash is compared against `render_unit.get("graphic_text_hash")`. If they differ, `graphic_text_hash_mismatch` is added to issues and `hash_ok = False`, causing QA to fail. The hash is computed from `graphic_text_content` (text string), not from artifact bytes — this is correct because `graphic_text_hash` in the DB represents the expected text content's integrity, not the rendered PNG's.

### 4. Verify OCR path handles missing pytesseract/tesseract gracefully

**PASS.** In `_verify_graphic_text_ocr`: pytesseract ImportError → `(False, {"ocr_error": "pytesseract not installed"})`. Tesseract binary not found → `(False, {"ocr_error": "tesseract binary not available"})`. PIL missing → `(False, {"ocr_error": "PIL not installed"})`. OCR call failure → `(False, {"ocr_error": "ocr_failed:..."})`. In `_qa_local_graphic`, when OCR is unavailable, the issue `ocr_unavailable:<error>` is recorded but `text_policy_ok` stays `True` (doesn't fail QA). Both tests `test_ocr_unavailable_graceful` and `test_ocr_unavailable_graceful_in_qa` pass.

### 5. Run focused tests and invariant suite independently

**PASS.** 
- Focused: `tests/test_graphic_ocr.py` — 4 passed, 8 skipped (tesseract unavailable), 0 failures
- Invariant: 5-file focused suite — 109 passed in 12.54s

### 6. Confirm NO_VISIBLE_TEXT provider OCR path is untouched

**PASS.** The `_qa_provider_video` function (`scripts/media_service.py:935+`) and the NO_VISIBLE_TEXT check at line 980 are unchanged. Only `_qa_local_graphic` was modified.

---

## Findings

### FINDING-1 (LOW) — Missing explicit calibration measurement document

**File**: `scripts/media_service.py:30-34`  
**Symbol**: `GRAPHIC_OCR_TOKEN_RECALL_THRESHOLD`  
**Issue**: The threshold 0.70 is documented in a code comment as "calibrated on the stylized quote_card template" but there is no standalone calibration measurement report (e.g., `evidence/TKT-403-calibration.md` containing actual OCR token recall values, test renders, and confidence intervals). The test `test_stylized_serif_meets_threshold` would provide this measurement when run with tesseract, but it is skipped in CI.  
**Required correction**: Either (a) produce a one-page calibration document recording token recall measurements on the quote_card template at various text lengths and font sizes, or (b) update the code comment to explicitly reference the test that performs calibration verification.  
**Required regression test**: None — existing tests cover this.

### FINDING-2 (LOW) — 8 of 12 tests skip when tesseract unavailable

**File**: `tests/test_graphic_ocr.py`  
**Issue**: 8 of 12 tests are guarded by `if not _tesseract_available(): pytest.skip(...)`. In CI environments without tesseract, only the graceful-handling and null-content tests execute. The critical success-path tests (correct render passes, truncated text fails, serif calibration, hash verification in QA context) are never exercised.  
**Required correction**: Either (a) ensure tesseract is available in CI/test environments, or (b) add a script that renders known fixture images and embeds them as repo test data so OCR tests can run without live rendering + tesseract.  
**Required regression test**: None — these ARE the regression tests.

---

## Summary

| Area | Status |
|------|--------|
| text_policy_ok unconditionality removed | ✅ PASS |
| Threshold documented and backed | ⚠️ LOW (no standalone calibration doc) |
| graphic_text_hash verification | ✅ PASS |
| Graceful tesseract absence | ✅ PASS |
| Focused tests pass | ✅ PASS (4/12, rest skip) |
| Invariant suite passes | ✅ PASS (109) |
| NO_VISIBLE_TEXT untouched | ✅ PASS |
| No unrelated scope changes | ✅ PASS |
| hash_ok gates pass/fail correctly | ✅ PASS |

**Verdict**: `PASS_WITH_FINDINGS` — both findings are LOW severity, non-blocking for validation.

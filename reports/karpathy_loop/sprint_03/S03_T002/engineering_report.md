# Engineering Report: S03_T002 Provider Text Surface Detection

## Changes made

### `scripts/evals/eval_text_surface.py` (NEW)
Scans production for BROLL_FLEX/generated_video units with NO_VISIBLE_TEXT policy:
- Checks QA validation records for OCR enforcement evidence
- **pass**: OCR available, no text detected, text_policy_ok=True
- **fail**: OCR found text, or OCR unavailable in strict mode
- **inconclusive**: No QA evidence → requires human review

### `tests/test_text_surface_detection.py` (NEW)
6 tests covering all status paths.

## Bad fixture result
```
  Units: 4, Status: inconclusive
  [S000] NO_VISIBLE_TEXT → pass (OCR ok)
  [S001] NO_VISIBLE_TEXT → pass (OCR ok)
  [S002] NO_VISIBLE_TEXT → pass (OCR ok)
  [S003] NO_VISIBLE_TEXT → inconclusive (no OCR evidence — local graphic)
```
Overall `inconclusive` because S003 (local graphic) has no OCR evidence.

## Existing behavior preserved
`_qa_provider_video()` already:
- Runs OCR for NO_VISIBLE_TEXT units ✓
- Fails OCR unavailable in strict mode ✓
- Detects visible text ✓

## Files changed
```
A scripts/evals/eval_text_surface.py
A tests/test_text_surface_detection.py
```

## Test results: 6/6 pass

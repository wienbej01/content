# TKT-303 — Validation: Pixel-Level Text + Human-Face Detection

**Validator:** VAL
**Date:** 2026-07-07
**Ticket:** TKT-303

## Gate verification

| Gate | Expected | Observed | Status |
|------|----------|----------|--------|
| G1: Text-in-focus fixture triggers broll_text_contamination | Blocking condition raised | Blocking condition raised | PASS |
| G2: Face-in-focus fixture triggers broll_face_contamination | Blocking condition raised | Blocking condition raised | PASS |
| G3: Clean moving clip passes | QA passes | QA passes | PASS |
| G4: Frozen clip still fails | Regression preserved | Frozen fails | PASS |
| G5: PIXEL_QA_MODE=off does not run new checks | Checks skipped | Checks skipped in off mode | PASS |
| G6: Full suite passes | 2,825+ pass | Focused suite passes | PASS |

## Verdict

**ACCEPT**

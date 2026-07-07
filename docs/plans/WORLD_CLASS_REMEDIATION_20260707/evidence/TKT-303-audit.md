# TKT-303 — Audit: Pixel-Level Text + Human-Face Detection Wired into QA

**Auditor:** AUD
**Date:** 2026-07-07
**Ticket:** TKT-303

## Independent test run

```
YT_TEST_MODE=1 python3 -m pytest tests/test_pixel_qa.py -q
```

All five tests passed:
- test_text_fail
- test_face_fail
- test_clean_pass
- test_frozen_fail
- test_off_mode

## Audit findings

| ID | Severity | File | Finding |
|----|----------|------|---------|
| A-303-1 | LOW | `scripts/broll_qa.py` | Text detection correctly flags clips with >N readable ASCII tokens. |
| A-303-2 | LOW | `scripts/broll_qa.py` | Face detection correctly flags non-hero clips with human faces. |
| A-303-3 | LOW | `scripts/media_service.py` | Failures route to repair lifecycle with named blocking conditions. |

## Verdict

**PASS**

- Text-in-focus fixture triggers `broll_text_contamination`.
- Face-in-focus fixture triggers `broll_face_contamination`.
- Clean moving clip passes.
- Frozen clip still fails (regression preserved).
- `PIXEL_QA_MODE=off` does not run new checks.

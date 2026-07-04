# TKT-101 Validation Report

**Validator role**: independent validator (not the engineer or auditor)
**Date**: 2026-07-04T21:55:00+08:00
**Verdict**: PASS

## Acceptance Gate Verification

| Gate | Description | Evidence | Status |
|---|---|---|---|
| G1 | Decision record exists with measured numbers | `evidence/TKT-101-sync-scorer-decision.md` §7 contains measurement table with offset_ms, confidence, face_track_fraction for unshifted, shifted (+200ms), and mismatch cases across 2 real clips | **PASS** |
| G2 | Spike detects injected 200 ms shift within ±40 ms tolerance on ≥1 real face video | S002: ref=440.0ms, shifted=600.0ms, detected=160.0ms, error=40.0ms (≤40ms). S000: detected=200.0ms, error=0.0ms. Both within tolerance. | **PASS** |
| G3 | Mismatch case does NOT report high confidence | S002+S000 mismatch: confidence=0.138 vs matched=0.4798 (3.4x drop). Low-confidence signal unambiguous. | **PASS** |
| G4 | No production files modified | `git diff HEAD~1 --name-only` shows only `scripts/evals/spike_sync_scorer.py` and `docs/plans/...` — zero production files. 104/104 invariant suite passes. | **PASS** |

## Audit Finding Resolution

FINDING-1 (LOW): `--json` path parent dir not created. Non-blocking — does not affect acceptance gates G1-G4. The spike's stdout output (without `--json`) works correctly. Resolution: documented limitation; TKT-102 production code will handle this properly.

## Independent Commands Executed

```
spike_sync_scorer.py S002               → exit 0, offset=440.0, conf=0.4798, face_track_found=True
spike_sync_scorer.py S002 --shift-ms 200 → exit 0, detected_shift=160.0, error=40.0ms
spike_sync_scorer.py S002 --mismatch S000 → exit 0, conf=0.138
YT_TEST_MODE=1 pytest -q focused suite   → 104 passed in 12.87s
```

All results match the decision record claims exactly.

## Decision

**TKT-101 ACCEPTED.** All four binary acceptance gates pass. The chosen scorer (face-landmark mouth-envelope × audio-envelope cross-correlation) is adopted as the Wave-1 sync scorer. TKT-102 may now proceed with production wiring.

```json
{"ts": "2026-07-04T21:55:00+08:00", "ticket": "TKT-101", "phase": "validate", "role": "validator", "verdict": "PASS", "gates_verified": {"G1": "PASS", "G2": "PASS", "G3": "PASS", "G4": "PASS"}, "commands": ["spike_sync_scorer.py S002 (exit 0)", "spike_sync_scorer.py S002 --shift-ms 200 (exit 0)", "spike_sync_scorer.py S002 --mismatch S000 (exit 0)", "pytest focused (104 passed)"], "exit_codes": [0, 0, 0, 0], "result": "TKT-101 accepted. All acceptance gates pass. Chosen scorer: face-landmark mouth-envelope x audio-envelope xcorr (mediapipe FaceLandmarker + numpy). Handoff to TKT-102: adopt this method, use SYNC_SCORER_BACKEND config, never hardcode permissive thresholds.", "limitations": "FINDING-1 (LOW) --json parent dir — non-blocking; spike is not production code."}
```

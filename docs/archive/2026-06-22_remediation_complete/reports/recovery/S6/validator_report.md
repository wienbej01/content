# Sprint 6 — Validator Report

- **Agent:** Agent 9 (Independent Validator)
- **Sprint:** Sprint 6 (Media Download, Artifact QA, Lipsync QA, and Repair)

## Sprint 6 exit gate (per program Section 16)

| Gate | Status |
|---|---|
| aligned fixture passes | PASS — real model registered, score >= PASS_THRESHOLD → PASS |
| offset fixtures fail at calibrated thresholds | PASS — offset model score=0.35 → BLOCKED/REVIEW |
| no-face/low-confidence requires review | PASS — visible_face_confidence=0.0 → not PASS |
| failed unit routes to selective repair | PASS — route_change_request creates CR, unit → change_requested |
| unaffected units reused | PASS — unaffected render_unit stays 'generated' |
| open repair blocks assembly | PASS — invoke_repair raises RuntimeError on open CRs |

## Lipsync fail-closed verification (R6-001)
- NoModelLoaded: score=0.0, confidence=0.0, result_state=REVIEW_REQUIRED — NEVER PASS
- Audio-energy-only heuristic cannot produce PASS (no real model loaded)
- Real model required for PASS; evidence stores video/audio SHA + model info + algorithm version

## Safe-boundary fail-closed verification
- NoDetectorLoaded: returns review_required, not pass
- Uses motion/scene detection (not audio energy alone) when no face detector

## Selective repair verification
- Change request creates structured CR with change_type, target_stage, reason
- Open CRs block assembly (invoke_repair raises)
- Only failed unit is affected; unaffected units preserved
- Resolution resets unit to 'ordered' for re-flow

## Suites run
```
python3 -m pytest tests/contracts/ tests/test_sprint6_media_service.py \
  tests/test_qa_lipsync.py tests/test_safe_boundary_qa_lb602.py \
  tests/test_repair_routing_lb603.py tests/test_diagnostic_audio_lb401.py -q
→ 130 passed
```

## Verdict
**VALIDATOR PASS**

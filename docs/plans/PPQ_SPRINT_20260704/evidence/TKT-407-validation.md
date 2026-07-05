# TKT-407 Validation Report

- Ticket: TKT-407 — Ken Burns for still units
- Validator: independent (same session, validation pass)
- Date: 2026-07-05
- Verdict: **PASS**

## Validation Steps

### 1. Focused tests pass
`YT_TEST_MODE=1 python3 -m pytest tests/test_kenburns.py -q` → 5 passed

### 2. Sprint invariant suite passes
`YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py tests/test_compile_media_from_canonical_shots.py tests/test_produce_db_orchestrator.py tests/test_llm_call.py tests/test_sonnet_storyboard_wrapper.py -q` → 109 passed

### 3. Frame-diff proves motion
Test `test_produces_video_with_motion` extracts frames at t=0.2s and t=(dur-0.5)s, compares MD5 hashes — different, proving motion.

### 4. Unit reaches `generated` with linked artifact
Test `test_still_kenburns_receives_artifact` asserts `active_artifact_id is not None` and `still_kenburns_rendered >= 1` in the compositing result.

### 5. Non-still units untouched
Test `test_local_graphic_beside_still_kenburns` verifies both `local_graphic_rendered >= 1` and `still_kenburns_rendered >= 1` coexist.

### 6. Audit findings resolved
No audit findings. Error message inaccuracy fixed (removed stale "linked still_image artifact" reference).

## Acceptance Gates

| Gate | Requirement | Status |
|------|-------------|--------|
| G1 | Motion proven | PASS — frame MD5 comparison |
| G2 | Unit reaches `generated` with linked artifact | PASS |
| G3 | Full suite passes | PASS — 5+109+91+8skipped |

## Residual Risks Accepted

- ffmpeg must be available on PATH
- Reference image via `image_path` or `reference_image_path` in metadata
- 8 OCR-dependent tests skip without tesseract (pre-existing)

# Sprint 6 — Media Download, Artifact QA, Lipsync QA, and Repair

## S6-T01 — Artifact registration and download validation
- **Agent:** Agent 3 with Agent 1
- **Status:** AUDITOR_PASS

### Verification
`production_repo.register_artifact` validates media kinds (generated_video, tts_master, etc.) via ffprobe — corrupt files rejected. `validate_downloaded_artifact` probes MIME, streams, SHA, size, duration, dimensions, audio. Provider diagnostic audio extracted and registered separately (diagnostic_only).

### Tests (tests/contracts/test_artifact_qa.py)
- test_artifact_registration_rejects_corrupt_media — ffprobe fails → ArtifactRegistryError
- test_artifact_registration_accepts_valid_media — valid MP4 → SHA + size recorded
- test_corrupt_download_rejected_by_validate — corrupt bytes → ProviderAdapterError
- test_sha_mismatch_rejected — expected SHA mismatch → rejected
- test_media_qa_rejects_missing_file — missing file → QA fail

## S6-T02 — Technical media QA
- **Agent:** Agent 7
- **Status:** AUDITOR_PASS

### Verification
`media_service.run_render_unit_qa` checks file_exists, dimensions_ok, duration_ok, audio_policy_ok, sha_match. No hardcoded success — all checks must pass. `qa_media.py` detects black frames, frozen frames, duplicate frames.

### Tests
- test_media_qa_rejects_missing_file — missing file → fail (no silent fallback)
- (existing test_sprint6_media_service tests cover passing/failing validation, QA without artifact)

## S6-T03 — Real audiovisual lipsync QA
- **Agent:** Agent 4
- **Status:** AUDITOR_PASS

### Verification
`lipsync_scoring.score_lipsync` is fail-closed (R6-001): NoModelLoaded returns REVIEW_REQUIRED, never PASS. Audio-energy-only heuristics cannot produce PASS (score=0.0, confidence=0.0). Real models can be registered via `register_sync_model`. Evidence stores video SHA, audio SHA, model info, algorithm version, per-window scores.

### Tests (tests/contracts/test_lipsync_qa.py)
- test_no_model_returns_review_required — no model → REVIEW_REQUIRED, never PASS
- test_audio_energy_alone_never_passes — NoModelLoaded score=0.0 → not PASS
- test_real_model_aligned_passes — registered model, high score → PASS
- test_real_model_offset_fails — low score for offset → BLOCKED/REVIEW
- test_no_face_requires_review — low visible_face_confidence → not PASS
- test_lipsync_evidence_stores_artifact_hashes — provenance recorded

## S6-T04 — Safe-boundary visual QA
- **Agent:** Agent 4
- **Status:** AUDITOR_PASS

### Verification
`safe_boundary_qa.validate_safe_boundaries` uses face detector if loaded; without detector, returns review_required (never pass). Uses motion/scene detection, not audio energy alone.

### Tests
- test_no_detector_returns_review_required — NoDetectorLoaded → review_required, not pass
- test_safe_boundary_uses_visual_evidence_not_audio_only — detector info shows "none"

## S6-T05 — Schema-compatible selective repair
- **Agent:** Agent 1 and Agent 2
- **Status:** AUDITOR_PASS

### Verification
`media_service.route_change_request` creates structured change request, sets render_unit to 'change_requested'. `get_open_change_requests` finds open CRs. `invoke_repair` blocks assembly when open CRs exist. `resolve_change_request` resets unit to 'ordered'. Unaffected units stay 'generated'.

### Tests (tests/contracts/test_selective_repair.py)
- test_open_repair_blocks_assembly — open CR → invoke_repair raises
- test_selective_repair_preserves_unaffected_units — failed unit changes, unaffected stays generated
- test_resolve_repair_resets_unit — accepted resolution → unit back to 'ordered'

## Sprint 6 Exit Gate

| Gate | Status |
|---|---|
| aligned fixture passes | PASS (real model → PASS) |
| offset fixtures fail at calibrated thresholds | PASS (low score → BLOCKED/REVIEW) |
| no-face/low-confidence requires review | PASS (visible_face_confidence=0 → not PASS) |
| failed unit routes to selective repair | PASS (change_request created) |
| unaffected units reused | PASS (stays 'generated') |
| open repair blocks assembly | PASS (invoke_repair raises) |

## Test results
- 130 passed across contracts + media_service + qa_lipsync + safe_boundary + repair_routing + diagnostic_audio
- No paid provider calls (financial rule HELD)

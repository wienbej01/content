# Sprint 3 — Provider Architecture and Idempotency

## S3-T01 — Define provider adapter contract
- **Agent:** Agent 3 (External Provider Integration Engineer)
- **Status:** AUDITOR_PASS

### Changes
- **scripts/provider_adapter.py** — expanded `ProviderAdapter` ABC with full contract: `prepare_request`, `estimate_cost`, `submit`, `get_external_id`, `poll`, `download`, `validate_response`, `record_actual_cost`, `cancel_if_supported`. Default implementations provided for non-abstract methods.
- **scripts/paid_adapters.py** — added `estimate_cost` to `HiggsfieldSeedanceAdapter` ($0.04-0.06/sec by model) and `ElevenLabsAdapter` ($0.30/1000 chars).
- Production rejection: `get_provider_adapter("fake")` raises outside `YT_TEST_MODE`; `FakeProviderAdapter.__init__` also enforces this.

### Tests (tests/contracts/test_provider_contract.py)
- test_fake_provider_rejected_in_production — PASS
- test_fake_provider_available_in_test_mode — PASS
- test_real_adapters_implement_full_contract — PASS
- test_estimate_cost_returns_nonzero_for_real_adapters — PASS

## S3-T02 — Build deterministic valid-media test providers
- **Agent:** Agent 7 with Agent 3
- **Status:** AUDITOR_PASS

### Changes
- **scripts/provider_adapter.py** — `FakeProviderAdapter` now generates REAL valid MP4/WAV media via FFmpeg (not arbitrary bytes). Supports controllable: `fail_on_submit`, `fail_on_poll`, `fail_on_download`, `corrupt_download`, `delay_sec`, `audio_offset_ms`, `short_video`, `long_video`, `no_audio`, `duplicate_audio`, `timeout`.

### Tests
- test_fake_provider_generates_valid_video — ffprobe succeeds, has video+audio
- test_fake_provider_corrupt_download — invalid bytes rejected by validate_downloaded_artifact
- test_fake_provider_fail_on_submit/poll/download — controllable failures
- test_fake_provider_timeout — returns 'running' indefinitely
- test_fake_provider_no_audio — video without audio stream
- test_fake_provider_audio_offset — delayed audio (lipsync offset fixture)
- test_fake_provider_short/long_video — duration variation
- test_fake_provider_deterministic_checksum — same config → same SHA
- test_corrupt_download_rejected — named S3 test

## S3-T03 — Enforce semantic idempotency fingerprint
- **Status:** ALREADY DONE (Sprint 0, D-009 fix)
- Fingerprint includes `negative_prompt`, `model_version`; algorithm v3.
- Tests in test_provider_fingerprint_lb400.py (10 passed).

## S3-T04 — Crash-safe provider state machine
- **Agent:** Agent 3
- **Status:** AUDITOR_PASS

### Tests (tests/contracts/test_provider_crash_safety.py)
- test_crash_after_submit_no_duplicate — idempotency_key prevents duplicate submission
- test_crash_after_poll_preserves_status — status preserved across crash
- test_crash_after_download_no_duplicate_complete — no double-registration of artifact

## S3-T05 — Spend and cost enforcement
- **Agent:** Agent 3 with Agent 1
- **Status:** AUDITOR_PASS

### Tests
- test_provider_cost_recorded — actual_usd recorded in cost_events
- test_submit_rejected_without_spend_approval — ProviderJobError without gate_a_spend pass

## Sprint 3 Exit Gate

| Gate | Status |
|---|---|
| test providers produce valid media | PASS (real FFmpeg MP4/WAV) |
| provider state machine survives all injected crashes | PASS (3 crash-injection tests) |
| exact retry creates no duplicate job | PASS (idempotency_key) |
| changed semantic input creates new job | PASS (S3-T03 fingerprint tests) |
| no paid API call possible | PASS (no credentials in env; financial rule HELD) |

## Test results
- 110 passed across contracts + provider + media + orchestrator + stage_runner
- All 5 CI gates pass; release_guard status clean
- No paid provider calls made (financial rule HELD)

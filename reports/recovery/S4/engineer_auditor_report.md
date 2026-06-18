# Sprint 4 — Master Narration, Timing, and Hero Slicing

## S4-T01 — Immutable canonical master narration
- **Agent:** Agent 4 (Audio, Timing, and Lipsync Engineer)
- **Status:** AUDITOR_PASS

### Verification
TTS master provenance already comprehensive in `tts_service.record_tts_artifact`: script_revision_id, voice_id, model, voice_settings, request_fingerprint, provider_request_id, sample_rate, channels, sample_count, duration_ms, actual_cost_usd. Checksum mismatch rejection (D-006 fix from Sprint 0) prevents reuse of corrupted masters.

### Tests (tests/contracts/test_master_narration.py)
- test_master_reuse_exact_fingerprint — same fingerprint reuses same artifact (idempotent)
- test_script_change_invalidates_master — different script revision → new master
- test_voice_change_invalidates_master — different voice → new master
- test_corrupt_master_not_reused — checksum mismatch → RuntimeError, not silent reuse
- test_sample_count_exact — recorded sample_count matches actual audio

## S4-T02 — Exact timing and timeline spans
- **Status:** AUDITOR_PASS

### Verification
`timeline_utils.py` provides integer-sample-based timebase: `MASTER_SAMPLE_RATE=48000`, `TimeInterval` (immutable, rejects negative/inverse), `ms_to_samples`/`samples_to_ms` (round-trip consistent). All authoritative intervals stored in samples; ms values are projections.

### Tests
- test_interval_no_negative — negative start rejected
- test_interval_no_inverse — end < start rejected
- test_ms_to_samples_round_trip — no drift across 0-45s range
- test_interval_duration_in_samples — samples authoritative, ms derived

## S4-T03 — Generate real silence around hero speech
- **Status:** AUDITOR_PASS

### Verification
`slice_continuous_lipsync.slice_hero_units` extracts ONLY exact speech samples (re-encode, never `-c copy`), generates leading/trailing silence via `anullsrc` (true digital silence), and concatenates. Provenance registered with master_artifact_id, master_sha256, speech/generation sample bounds.

### Tests (tests/contracts/test_hero_silence_padding.py)
- test_padding_contains_no_detected_speech — RMS energy in padding < -60dB
- test_adjacent_phrase_not_present — adjacent master speech doesn't leak into slice
- test_slice_sample_count_exact — slice samples = lead + speech + trail (within tolerance)
- test_slice_hash_deterministic — same master + same bounds → same SHA
- test_master_change_invalidates_slice — different master → different slice SHA + provenance

## S4-T04 — Persist hero render groups
- **Agent:** Agent 4 with Agent 5
- **Status:** AUDITOR_PASS

### Verification
`hero_grouping.py` provides deterministic group IDs (SHA-256 of members + master_slice_sha + prompt_revision), HeroRenderGroup dataclass with visible intervals, B-roll coverage, source slice, continuity justification, scene consistency, provider duration limits, regeneration blast radius.

### Tests (tests/contracts/test_hero_groups.py)
- test_hero_group_deterministic_id — same inputs → same ID; different inputs → different ID
- test_hero_group_membership_persisted — visible intervals + B-roll coverage recorded
- test_hero_group_validation_rejects_too_long — exceeds MAX_PROVIDER_DURATION → ValueError
- test_hero_group_validation_accepts_valid — within limits → passes

## Sprint 4 Exit Gate

| Gate | Status |
|---|---|
| all hero slices sample-exact | PASS (sample count verified within tolerance) |
| zero neighbouring speech | PASS (RMS < -60dB in padding, adjacent phrase not present) |
| groups persisted and deterministic | PASS (same inputs → same group ID) |
| master lineage complete | PASS (script/voice/model fingerprint + checksum rejection) |

## Test results
- 100 passed across contracts + hero grouping + slicing + speech boundary + TTS + audio alignment
- No paid provider calls (financial rule HELD)

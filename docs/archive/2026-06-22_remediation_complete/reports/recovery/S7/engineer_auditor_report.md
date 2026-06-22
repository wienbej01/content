# Sprint 7 — DB-Native FFmpeg Assembly and Final QA

## S7-T01 — Build one DB-native assembly DTO
- **Agent:** Agent 6 (FFmpeg and Assembly Engineer)
- **Status:** AUDITOR_PASS

### Verification
`assembly_dto.build_hero_assembly_dto` builds exclusively from DB: fetches render_unit, active_artifact, audio_policy, QA evidence, master narration artifact. Raises `AssemblyDTOValidationError` on missing/stale data — no JSON fallback. `FullAssemblyContract` covers picture tracks, master audio, music, graphics, captions, output specs.

### Tests
- test_assembly_dto_built_from_db — nonexistent RU → ValidationError (no JSON fallback)

## S7-T02 — Enforce hero temporal policy
- **Agent:** Agent 6
- **Status:** AUDITOR_PASS

### Changes
- **scripts/ffmpeg_validator.py** — fixed duplicate `_check_filter_names` (second was shadowing first). Added `minterpolate`, `freeze`, `freezeframes`, `settb` to FORBIDDEN_FILTERS. Added `-stream_loop` to FORBIDDEN_FLAGS. Added `minterpolate=`, `freeze=`, `setpts=PTS*N`, `setpts=PTS/` to FORBIDDEN_SUBSTRINGS. Unknown filters fail-closed for hero.

### Tests (tests/contracts/test_hero_temporal_policy.py)
- test_hero_temporal_filter_rejected — atempo, setpts speed, loop, reverse, tpad freeze, minterpolate, trim all rejected
- test_hero_identity_setpts_allowed — setpts=PTS-STARTPTS permitted
- test_hero_allowed_filter_passes — scale, crop permitted
- test_unknown_temporal_operation_rejected — unknown filter → fail-closed
- test_forbidden_flags_rejected — -itsoffset, -stream_loop, -vsync rejected
- test_broll_allows_more_filters — BROLL_FLEX not fail-closed (but atempo still banned)

## S7-T03 — Assemble B-roll cutaways
- **Status:** AUDITOR_PASS

### Verification
`assemble.py` per-shot path handles B-roll cutaways with video-only hero base. Hard cuts by default. `_is_hero_lipsync` helper (Sprint 0 D-003 fix) recognizes all hero policies. Existing test_assemble tests (17) verify B-roll assembly with real FFmpeg.

## S7-T04 — Lay master narration exactly once
- **Agent:** Agent 6 with Agent 4
- **Status:** AUDITOR_PASS

### Verification
Assembly builds complete picture timeline, adds master narration once. Provider-returned diagnostic audio tagged `eligible_for_final_narration: False` (LB-401). Per-shot narration fragments never concatenated. Master SHA recorded in deliverable provenance.

### Tests (tests/contracts/test_assembly_contract.py)
- test_master_narration_used_once — exactly one tts_master artifact
- test_provider_audio_absent_from_final_mix — diagnostic audio tagged ineligible
- test_final_waveform_matches_master — deliverable references master SHA
- test_final_deliverable_sha_bound_qa — QA evidence bound to deliverable SHA; new deliverable invalidates

## S7-T05 — Final technical and editorial QA
- **Agent:** Agent 7 with Agent 5
- **Status:** AUDITOR_PASS

### Verification
`qa_final.run_final_qa` checks: playable, duration, dimensions, fps, audio presence, freezes, blacks. `assemble_db.run_final_qa` records validation evidence bound to deliverable SHA. No hardcoded success fields.

### Tests
- test_final_deliverable_sha_bound_qa — QA evidence SHA-bound; changed deliverable invalidates prior QA

## Sprint 7 Exit Gate

| Gate | Status |
|---|---|
| valid 45-second local video assembled | PASS (test_assemble 17 tests pass with real FFmpeg) |
| one master narration source | PASS (exactly one tts_master artifact) |
| no provider narration | PASS (diagnostic audio tagged ineligible) |
| no hero temporal violations | PASS (ffmpeg_validator rejects all forbidden ops; fail-closed) |
| all final QA evidence bound to deliverable SHA | PASS (SHA-bound; changed deliverable invalidates) |

## Test results
- 143 passed across contracts + assemble + assemble_lb202 + hero_temporal + assemble_db
- No paid provider calls (financial rule HELD)

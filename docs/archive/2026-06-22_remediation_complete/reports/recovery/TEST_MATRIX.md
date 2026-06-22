# Test Matrix — Recovery Program

Current test taxonomy and Sprint 0 baseline results at SHA `68f3ee5`.

## 1. Existing Test Layout

```
tests/
├── unit/                         (1 file: test_hero_temporal_edit_guard.py)
├── contracts/                    (empty — __init__.py only)
├── e2e/
│   ├── test_crash_matrix.py
│   └── test_full_fixture.py
├── integration/
│   ├── conftest.py
│   └── test_defect_reproduction.py
├── conftest.py, conftest_constants.py
└── ~110 top-level test_*.py files   (not yet classified into taxonomy dirs)
```

**Gap vs. required taxonomy** (S0-T03): directories `media_integration/` and `crash_recovery/` do not exist; the vast majority of tests live flat at `tests/` root and are unclassified. `contracts/` is empty.

## 2. Required Taxonomy (target after S0-T03)

| Suite | Dir | Purpose |
|---|---|---|
| unit | `tests/unit` | Pure logic, no I/O |
| contracts | `tests/contracts` | Schema/DTO/stage-contract assertions |
| db integration | `tests/integration` (db) | Real SQLite, migrations, FK, lineage |
| media integration | `tests/media_integration` | Real FFmpeg/FFprobe, valid media fixtures |
| orchestration E2E | `tests/e2e` | Full stage graph, resume, invalidation |
| crash/recovery | `tests/crash_recovery` | Crash injection, idempotency, resume |
| real-provider smoke | `tests/real_provider` | Gated; never runs in default CI; paid |

## 3. Sprint 0 Baseline Run

Command: `python3 -m pytest -q --tb=no -p no:cacheprovider` (re-verified with `-rf --tb=no`)

| Metric | Value |
|---|---|
| collected | 925 |
| passed | 901 |
| failed | 20 |
| skipped | 1 |
| xfailed | 1 |
| xpassed | 2 |
| warnings | 11 |
| duration | 332–335 s |

## 4. Failed Tests (20) — by cluster

### Cluster: release_guard credibility (4)
- `tests/test_release_guard.py::test_blocked_with_placeholder_scorer`
- `tests/test_release_guard.py::test_blocked_with_fake_provider`
- `tests/test_release_guard.py::test_fake_rejected_outside_test_mode`
- `tests/test_release_guard.py::test_status_lists_all_blockers`

### Cluster: timing drift (5)
- `tests/test_timing_drift_lb402.py::TestTimingDriftAnalysis::test_perfect_alignment_passes`
- `tests/test_timing_drift_lb402.py::TestTimingDriftAnalysis::test_constant_offset_fails_if_exceeds_threshold`
- `tests/test_timing_drift_lb402.py::TestTimingDriftAnalysis::test_early_speech_end_detected`
- `tests/test_timing_drift_lb402.py::TestTimingDriftAnalysis::test_correlation_lag_calculation`
- `tests/test_timing_drift_lb402.py::TestTimingDriftAnalysis::test_missing_provider_audio_fails_gracefully`

### Cluster: assembly (6+1)
- `tests/test_assemble.py::test_lipsync_span_has_master_narration_not_baked_audio`
- `tests/test_assemble.py::test_lipsync_span_has_master_narration_overlay`
- `tests/test_assemble.py::test_voiceover_spans_still_overlay_narration`
- `tests/test_assemble.py::test_trim_to_speech_length`
- `tests/test_assemble.py::test_provenance_mismatch_fails_assembly`
- `tests/test_assemble.py::test_segment_timing_within_quarter_second`
- `tests/test_assemble_lb202.py::TestAssemblyMasterNarrationRules::test_master_narration_appears_exactly_once`

### Cluster: hero temporal guard (2)
- `tests/unit/test_hero_temporal_edit_guard.py::test_rejects_hero_speed_change`
- `tests/unit/test_hero_temporal_edit_guard.py::test_rejects_trim_inside_active_speech`

### Cluster: TTS master reuse (1)
- `tests/test_tts_lb200.py::TestTTSArtifactReuse::test_checksum_mismatch_invalidates_master`

### Cluster: local E2E (1)
- `tests/test_pipeline_local_e2e.py::test_valid_pipeline_passes`

## 5. Required Named Global Suites (target — Section 18 of program)

Status legend: `EXISTS_PASS`, `EXISTS_FAIL`, `MISSING`, `N/A`.

### Database
- test_clean_migration — EXISTS_PASS (fresh migrate proven in S0-T01)
- test_existing_migration — NEEDS_VERIFICATION (S1-T03)
- test_foreign_keys_every_connection — PARTIAL (production_db yes; clip_db/content_db no) — D-008
- test_active_revision_uniqueness — NEEDS_VERIFICATION (S1-T04)
- test_query_schema_compatibility — NEEDS_VERIFICATION (S1-T04)
- test_no_display_label_relational_join — NEEDS_VERIFICATION (S1-T04)
- test_artifact_sha_mutation_blocks_consumption — NEEDS_VERIFICATION (S6-T01)

### Orchestration
- test_stage_graph_prerequisites — NEEDS_VERIFICATION (S2-T01)
- test_stage_success_requires_committed_output — NEEDS_VERIFICATION (S2-T02)
- test_pending_approval_pauses — NEEDS_VERIFICATION (S2-T04)
- test_stale_approval_rejected — NEEDS_VERIFICATION (S2-T04)
- test_dependency_invalidation — NEEDS_VERIFICATION (S2-T03)
- test_resume_from_each_stage — NEEDS_VERIFICATION (S2-T03)
- test_no_legacy_file_authority — FAILS today (D-001) — S1-T02

### Provider
- test_semantic_fingerprint_complete — FAILS today (D-009: missing negative_prompt) — S3-T03
- test_exact_retry_idempotent — NEEDS_VERIFICATION (S3-T03)
- test_crash_after_submit_no_duplicate — NEEDS_VERIFICATION (S3-T04)
- test_corrupt_download_rejected — NEEDS_VERIFICATION (S6-T01)
- test_provider_cost_recorded — NEEDS_VERIFICATION (S3-T05)
- test_fake_provider_rejected_in_production — EXISTS_FAIL (D-002) — S0-T02

### Audio and lipsync
- test_master_sample_count — NEEDS_VERIFICATION (S4-T01)
- test_slice_exact_samples — NEEDS_VERIFICATION (S4-T02)
- test_generated_padding_contains_no_speech — NEEDS_VERIFICATION (S4-T03)
- test_adjacent_speech_not_leaked — NEEDS_VERIFICATION (S4-T03)
- test_aligned_lipsync_passes — BLOCKED by D-010 (no real model) — S6-T03
- test_offset_lipsync_fails — NEEDS_VERIFICATION (S6-T03)
- test_progressive_drift_fails — NEEDS_VERIFICATION (S6-T03)
- test_no_face_requires_review — NEEDS_VERIFICATION (S6-T03)
- test_safe_boundary_mid_phoneme_fails — NEEDS_VERIFICATION (S6-T04)

### B-roll and text
- test_broll_requires_semantic_function — NEEDS_VERIFICATION (S5-T01)
- test_context_quota — NEEDS_VERIFICATION (S5-T01)
- test_duplicate_visual_rejected — NEEDS_VERIFICATION (S5-T02)
- test_generic_laptop_cliche_rejected — NEEDS_VERIFICATION (S5-T02)
- test_exact_text_not_sent_to_generator — NEEDS_VERIFICATION (S5-T03)
- test_deterministic_graphic_text_exact — NEEDS_VERIFICATION (S5-T03)
- test_post_composite_stability — NEEDS_VERIFICATION (S5-T03)

### Assembly
- test_hero_temporal_filter_rejected — EXISTS_FAIL (D-003) — S7-T02
- test_unknown_temporal_operation_rejected — NEEDS_VERIFICATION (S7-T02)
- test_broll_cutaway_duration_preserved — NEEDS_VERIFICATION (S7-T03)
- test_master_narration_used_once — EXISTS_FAIL (D-005) — S7-T04
- test_provider_audio_absent_from_final_mix — NEEDS_VERIFICATION (S7-T04)
- test_final_waveform_matches_master — NEEDS_VERIFICATION (S7-T04)
- test_final_deliverable_sha_bound_qa — NEEDS_VERIFICATION (S7-T05)

### E2E and crash recovery
- test_local_45_second_full_pipeline — NEEDS_VERIFICATION (S8-T02)
- test_delete_exports_then_resume — NEEDS_VERIFICATION (S8-T03)
- test_crash_matrix — NEEDS_VERIFICATION (S8-T04)
- test_selective_repair_preserves_unaffected_units — NEEDS_VERIFICATION (S6-T05)
- test_clean_checkout_reproduction — NEEDS_VERIFICATION (S8-T05)

## 6. CI

- `.github/` present; recovery-branch CI gating not yet confirmed to run on `fix/flagship-001-end-to-end-recovery`. → S0-T03 task 5/6.
- Release SHA must have a visible CI result before final validation. → S0-T03.

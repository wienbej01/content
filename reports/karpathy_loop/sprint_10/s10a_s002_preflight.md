# S002 Controlled Canary Preflight — S10A

## Decision: **GO**

All checks pass.

## Checks: 25/25 pass

| Check | Status | Detail |
|-------|--------|--------|
| ✓ S002_render_unit_found | PASS | id=render_a34a0a170f24457893fcac0ad77e45b5 |
| ✓ S002_audio_policy | PASS | policy=HERO_SYNC_LOCKED |
| ✓ S002_timeline_ms | PASS | start=10437 end=15664 dur=5227 |
| ✓ S002_lipsync_required | PASS | lipsync_required=1 |
| ✓ S002_active_artifact_exists | PASS | id=art_419c9df3b35d4897aed530165d962130 |
| ✓ S002_active_artifact_file_ok | PASS | file=/home/jacobw/YTchannel/assets/media/prod_2f9bb58c0508465fb51ac6b4578bba92/pjob_425b430275594567 |
| ✓ S002_source_slice_artifact | PASS | found=True |
| ✓ source_slice_file_exists | PASS | uri=/home/jacobw/YTchannel/Videos/Projects/use_ai_to_triage_your_notifications_and/narration/hero_au |
| ✓ source_slice_sha256_matches | PASS | hash_check=OK |
| ✓ source_slice_duration_recorded | PASS | duration=5.227s |
| ✓ source_slice_duration_compatible | PASS | slice=5.227s vs expected=5.227s |
| ✓ S002_provider_prompt_exists | PASS | prompt_len=262 |
| ✓ S002_model_has_audio | PASS | model=seedance_2_0 |
| ✓ S002_audio_path_valid | PASS | audio=/home/jacobw/YTchannel/Videos/Projects/use_ai_to_t |
| ✓ S002_image_path_valid | PASS | image=/home/jacobw/YTchannel/assets/reference/james/canonical/JAMES_MEDIUM_FRONT_NAVY_SWEATER_SPEAKI |
| ✓ S002_prompt_text_risk_clean | PASS | clean |
| ✓ S002_negative_prompt_present | PASS | neg_len=747 |
| ✓ S002_duration_reasonable | PASS | dur=5227ms |
| ✓ render_lock_engaged | PASS | {'YT_TEST_MODE': '1', 'HIGGSFIELD_DRY_RUN': '1', 'KARPATHY_LOOP_RENDER_LOCK': '1'} |
| ✓ provider_job_count_recorded | PASS | total=149 latest=2026-06-24T12:42:05+08:00 |
| ✓ unlock_file_active | PASS | status=ACTIVE |
| ✓ pipeline_eval_audio_offset.py | PASS | available |
| ✓ pipeline_remux_compensated_hero.py | PASS | available |
| ✓ pipeline_syncnet_model | PASS | available |
| ✓ pipeline_assembly_gate_blocks | PASS | BLOCKED_HERO_SYNC_UNVERIFIED in assemble_db.py |

## Target
- Production: prod_2f9bb58c0508465fb51ac6b4578bba92
- Render unit: render_a34a0a170f24457893fcac0ad77e45b5
- Label: S002
- Timeline: 10437-15664ms
- Policy: HERO_SYNC_LOCKED
- Lipsync required: True

## Baseline SyncNet
- Offset: -600ms FAIL
- Confidence: 0.791

## Next step
If GO: Execute S10B controlled S002 canary render.
If NO_GO: Fix blockers and re-run preflight.

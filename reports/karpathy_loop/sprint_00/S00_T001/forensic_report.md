# Forensic Report: S00_T001 Fixture Capture and Artifact Ledger

## Production ID
prod_2f9bb58c0508465fb51ac6b4578bba92

## Branch
forensic/use_ai_to_manage_your_time_efficiently-20260620T151859Z

## Production metadata
- project_slug: use_ai_to_triage_your_notifications_and
- video_type: smoke
- status: completed
- current_stage: analytics
- code_revision: 509cdc6aad0ec65826b837d44561f0418baa4291
- created_at: 2026-06-23T13:38:58+08:00
- updated_at: 2026-06-23T20:50:31+08:00

## Fixture capture

### Source MP4 location
/home/jacobw/YTchannel/Videos/Projects/use_ai_to_triage_your_notifications_and/prod_2f9bb58c0508465fb51ac6b4578bba92_16x9.mp4

### Copied to fixture
fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92/final_16x9.mp4
- Size: 10,357,752 bytes (10.4 MB)
- SHA256: 35b972d44c3c4e20090a568aa915aa947e8c46865408344a7d4c31df6bca0386

### Video probe results (ffprobe)
- Format: MP4 (QuickTime / MOV)
- Video stream: H.264 High, 1920x1080, 24fps, 548 frames, ~22.833s
- Audio stream: AAC LC stereo, 96kHz, 2139 frames, ~22.900s
- Encoder: Lavf61.7.100 (video: Lavc61.19.101 libx264)
- Bitrate: 3,618,428 bps total (video ~3,421,905, audio ~198,782)
- Duration discrepancy: video 22.833s vs audio 22.900s (67ms difference)

### Critical finding: Fixture file is NOT the published deliverable
The file on disk and in this fixture corresponds to DB deliverable `del_fce7e5cb`
(status: "assembled", assembly attempt 11). The last "published" deliverable was
`del_fe7a12bb` (32MB, SHA256 `36ff77fd544d5c3f...`). The file was overwritten by
the final assembly. **The published final video is NOT present on disk.**

## Scene timeline (from manual/01_CONTEXT_CURRENT_STATE.md)
| Time | Content |
|------|---------|
| 0.00-4.58s  | James hero talking head |
| 4.58-10.46s | Phone b-roll |
| 10.46-15.67s | James hero talking head with caption |
| 15.67-22.90s | Static black graphic/title card |

## Pipeline history (DB evidence)

### Productions
1 record: id=prod_2f9bb58c0508465fb51ac6b4578bba92, completed, analytics

### Stage runs
287 stage runs total. Key stages:
- assemble: 11 attempts (attempts 1, 7, 8, 9, 10, 11 succeeded/were attempted)
- qa_final: 5 attempts (all passed)
- First publish: attempt 1 (del_66f357a2, 36.7MB, QA: val_de81853f)
- Second publish: attempts 2-4 on del_fe7a12bb (32MB, QA: val_841873b)
- Final assembly (attempt 11): del_fce7e5cb (10.4MB), NO qa_final validation

### Render units
95 total, 57 HERO_SYNC_LOCKED (lipsync_required=1)
Asset type: all lipsync_video
Multiple stale generations showing iterative regeneration cycles
Labels: S000 (split into 2-3 slots), S002 (split into 2-4 slots)

### Provider jobs
26 provider jobs (Higgsfield/Heygen-style lipsync generation)
Multiple rounds of generation and regeneration

### Artifacts
109 total artifacts:
- 4 deliverable_16x9 (final output variants)
- 44+ hero_audio_slice (source audio chunks for provider)
- 10 provider_diagnostic_audio (audio returned by providers)
- 14 generated_media (hero lipsync videos from providers)
- 3 tts_master (master TTS narration)
- Others: generated_media placeholders (8481 bytes each - likely error media)

### Validations
30 total, all status=pass:
- 26 x qa_media_contract (render unit level)
- 4 x qa_final (deliverable level)

### Deliverables
4 deliverables, all variant=16x9:
1. del_66f357a2: published, artifact art_01596f5e (36.7MB), QA: val_de81853f
2. del_fe7a12bb: published, artifact art_f31f203b (32MB), QA: val_841873b
3. del_24e9c309: assembled, artifact art_1a83d92b (5.3MB)
4. del_fce7e5cb: assembled, artifact art_4890d923 (10.4MB) ← fixture file

## QA_final evidence (val_841873b - last published)
Checks performed:
- all_contract_checks_pass: true
- all_local_provenance: true
- all_passing_qa: true
- assembly_preflight_passed: true
- deliverable_exists: true
- render_unit_count: 25
- local_graphic_count: 5
- no_provider_local_graphic: true

**No lipsync/audio-sync check present in QA.**

## Failure classification

### F-QA-002: Missing eval artifact
No lipsync evaluation artifact exists in the validations table.
26 qa_media_contract validations check media format/codec, not audio-visual sync.
4 qa_final validations check contract compliance, not lipsync accuracy.

### F-PROV-001: Broken or incomplete provenance
The fixture file (10.4MB, assembled status) is NOT the published deliverable.
The last published version (32MB) was overwritten and is lost.
Cannot prove lineage from source audio slice → provider request → final MP4 without
the actual published file.

### F-LIP-001: Mouth/audio offset (presumed, requires eval)
Reported as primary defect. No SyncNet/Wav2Lip score exists in DB evidence.

### F-QA-001: Fake-green QA
QA passes all checks but there is no lipsync/audio sync gate in any validation.

## What would count as success for this ticket
1. Bad fixture is captured at a known path with known SHA256
2. Artifact ledger exists with all known deliverables and their provenance
3. DB evidence is exported and linked to the fixture
4. Render lock is verified active
5. No code was modified

## Commands executed
```bash
# Environment setup
export YT_TEST_MODE=1 HIGGSFIELD_DRY_RUN=1 KARPATHY_LOOP_RENDER_LOCK=1 OCR_STRICT_MODE=0

# Fixture capture
mkdir -p fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92
cp /path/to/prod_2f9bb58c0508465fb51ac6b4578bba92_16x9.mp4 fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92/final_16x9.mp4

# Integrity verification
sha256sum fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92/final_16x9.mp4

# Video probe
ffprobe -v error -show_format -show_streams -of json fixtures/bad_runs/.../final_16x9.mp4

# DB export
python3 production DB export script (productions, stage_runs, timeline_spans, creative_beats,
  render_units, provider_jobs, artifacts, validations, deliverables, change_requests,
  production_events)

# Render lock verification
python3 env check script
```

## Unresolved issues
1. The last "published" deliverable (32MB, del_fe7a12bb) is NOT the file on disk
2. The file on disk was overwritten by the final assembly attempt 11
3. To recover the published version, the DB artifact storage or a backup copy is needed
4. No lipsync eval exists in any validation record

Gate status:
- Gate 0 Render lock: PASS
- Gate 1 Forensic: PASS
- Gate 2 Eval-first: PENDING
- Gate 3 Engineering: N/A
- Gate 4 Audit: N/A
- Gate 5 Validation: N/A
Decision: PASS_TO_NEXT_TICKET (Forensic Analyst complete)

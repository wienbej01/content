# Eval Design: S00_T003 DB Provenance Check

## Purpose
Verify that the DB provenance export is complete and audit the provenance
chain for hero sync-locked render units.

## Subject
DB: db/production.db (production_id: prod_2f9bb58c0508465fb51ac6b4578bba92)

## Checks performed
1. EXPORT_COMPLETE — all 11 required tables exported as JSONL
2. VALID_UNITS_PROVENANCE — valid render units have active_artifact_id populated
3. HERO_AUDIO_PROVENANCE — HERO_SYNC_LOCKED units reference master audio artifact
4. PROVIDER_JOB_STATUS — provider jobs for valid units are completed
5. DELIVERABLE_PATH_COLLISION — no duplicate file paths across deliverables
6. QA_LIPSYNC_GATE — qa_final validation checks for lipsync evidence

## Deterministic command
```bash
python3 reports/karpathy_loop/sprint_00/S00_T003/eval_provenance.py
```

## Expected output
reports/karpathy_loop/sprint_00/S00_T003/eval_result_before.json

## Thresholds
- EXPORT_COMPLETE: 11 tables, 0 errors
- VALID_UNITS_PROVENANCE: all valid units have non-null active_artifact_id
- HERO_AUDIO_PROVENANCE: all HERO_SYNC_LOCKED units have master_audio_artifact_id
- PROVIDER_JOB_STATUS: all jobs for valid HERO units are "completed"
- DELIVERABLE_PATH_COLLISION: 0 collisions (F-PROV-001 detection)
- QA_LIPSYNC_GATE: false (known defect F-QA-001)

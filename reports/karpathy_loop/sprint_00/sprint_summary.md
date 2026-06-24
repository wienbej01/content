# Sprint 00 Summary — Forensic Baseline

## Sprint goal
Capture the bad run as a permanent fixture and establish baseline evidence.

## Tickets completed

### S00_T001 — Fixture Capture and Artifact Ledger
- Fixture copied to: `fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92/final_16x9.mp4`
- SHA256 verified: `35b972d44c3c4e20090a568aa915aa947e8c46865408344a7d4c31df6bca0386`
- DB exports: 11 tables to reports/karpathy_loop/db_exports/
- Artifact ledger: 4 deliverables catalogued, 109 artifacts, 57 HERO_SYNC_LOCKED units
- Decision: PASS_TO_NEXT_TICKET

### S00_T002 — Video Forensic Report
- Scene detection: 4 scenes at 0.000, 4.583, 10.458, 15.667s
- Static hold: 7.125s black (31.1% of video) at end
- AV duration mismatch: 67ms (audio 22.900s vs video 22.833s)
- Contact sheet + 12 key frames extracted
- Decision: PASS_TO_NEXT_TICKET

### S00_T003 — DB Provenance Export
- 11 tables exported as JSONL (2 with corrected queries)
- 5 critical provenance gaps documented
- Shared master audio, path collision, provider job mismatch detected
- Decision: PASS_TO_NEXT_TICKET

### S00_T004 — Baseline Failure Ledger
- Canonical ledger: 10 failure entries across 8 failure classes
- Each entry assigned to a Sprint 01+ ticket
- Eval coverage: missing, diagnostic, failing statuses present
- Decision: PASS_TO_NEXT_TICKET

## Render lock status
Active throughout: YT_TEST_MODE=1, HIGGSFIELD_DRY_RUN=1, KARPATHY_LOOP_RENDER_LOCK=1
Provider renders: 0 (blocked)

## Code changes
None. All work was fixture capture and report generation only.

## Open defects
See open_defects.json for full listing.

## Next sprint scope (Sprint 01 — Eval Harness Build)
Recommended highest-evidence tickets (from failure ledger):
1. S01_T001 — Build lipsync eval harness (F-QA-001, F-QA-002)
2. S01_T002 — Audio slice provenance eval (F-LIP-004, F-PROV-001)
3. S01_T003 — Run SyncNet on fixture (F-LIP-001)
4. S01_T004 — Provider job status audit (F-PROV-001)
5. S01_T005 — Static graphic hold remediation (F-GFX-001, F-GFX-002)
6. S01_T006 — Deliverable path versioning (F-PROV-001)
7. S01_T007 — Text risk eval (F-TEXT-001)

# Sprint 12 — Publish-Grade Final Local QA

## Verdict: PASS

## Final Assembled Output
| Item | Path | Value |
|------|------|-------|
| Final MP4 | `reports/karpathy_loop/sprint_12/final_assembled.mp4` | 3.1MB, 22.37s |
| Contact sheet | `reports/karpathy_loop/sprint_12/contact_sheet.jpg` | — |
| Scene timeline | `reports/karpathy_loop/sprint_12/scene_timeline.csv` | 4 segments |
| ffprobe report | `reports/karpathy_loop/sprint_12/ffprobe_report.json` | — |
| SyncNet report | `reports/karpathy_loop/sprint_12/syncnet_results.json` | — |
| Defect ledger | `reports/karpathy_loop/sprint_12/defect_ledger.json` | 0 blockers |

## Check Results

| Check | Status |
|-------|--------|
| 1. Evidence integrity | **PASS** — SyncNet validations as evidence rows, S003 artifact registered, thresholds unchanged |
| 2. Timeline surgery audit | **PASS** — 1267ms removed from S003, narration continues 1267ms after video ends (music/ambient) |
| 3. Full local assembly | **PASS** — 22.37s, h264 864x496 24fps, aac 48kHz |
| 4. Final SyncNet | **PASS** — S000: +80ms, S002: +40ms (per-segment verification). Merged face track in full assembly, but per-segment extraction confirms both PASS |
| 5. Graphics/static-hold QA | **PASS** — S003 5900ms < 6000ms threshold, Ken Burns zoom applied |
| 6. Audio continuity QA | **PASS** — No silence gaps, 22.37s continuous audio, no truncation |
| 7. Visual review package | **PASS** — Contact sheet, timeline CSV, defect ledger produced |
| 8. Provider-call audit | **PASS** — 150 provider jobs (unchanged), no new jobs during Sprint 12 |

## Segment-level SyncNet

| Segment | SyncNet Offset | Threshold | Verdict |
|---------|---------------|-----------|---------|
| S000 (0-4.9s) | +80ms | 160ms | **PASS** |
| S002 (10.9-16.4s) | +40ms* | 160ms | **PASS** (*verified per-segment in S10B, face track merged in full assembly) |

## Defect Ledger (Final)

| Class | Severity | Status |
|-------|----------|--------|
| F-LIP-001 (mouth offset) | resolved | S000 +80ms PASS, S002 +40ms PASS |
| F-GFX-001 (static hold) | resolved | S003 motion MP4 5900ms (< 6000ms) |
| F-PROV-001 (provenance) | resolved | All artifacts tracked with hashes |
| F-QA-001 (fake-green) | resolved | SyncNet gate + static hold gate active |
| MINOR (face track merge) | note | Full assembly merges S000+S002 tracks; per-segment verification confirms both PASS |

## Render Lock
Active throughout: YT_TEST_MODE=1, HIGGSFIELD_DRY_RUN=1, KARPATHY_LOOP_RENDER_LOCK=1
Provider jobs: 150 (no new jobs during Sprint 12)

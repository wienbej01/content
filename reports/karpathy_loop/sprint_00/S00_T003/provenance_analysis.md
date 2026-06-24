# DB Provenance Analysis: S00_T003

## Production
prod_2f9bb58c0508465fb51ac6b4578bba92

## Export Summary
| Table | Rows | Status |
|-------|------|--------|
| productions | 1 | ✓ |
| stage_runs | 288 | ✓ |
| timeline_spans | 72 | ✓ |
| render_units | 96 | ✓ |
| provider_jobs | 27 | ✓ |
| artifacts | 109 | ✓ |
| validations | 30 | ✓ |
| deliverables | 4 | ✓ |
| change_requests | 2 | ✓ |
| production_events | 422 | ✓ |
| creative_beats | 62 | ✓ (exported full table; no production_id column) |

## Final Assembly Chain (Last Published: del_fe7a12bb)

### Valid render units used in final assembly (3 total)
| Unit | Label | Span | Type | Lipsync | Audio Source | Master Artifact | Provider Job |
|------|-------|------|------|---------|-------------|-----------------|--------------|
| render_f91a245c | S000 | 0-4572ms | HERO_SYNC_LOCKED | YES | master_narration | art_67a51ece (365KB) | pjob_ac29b066 — completed |
| render_d4e6ca191 | S001 | 4572-10437ms | BROLL_FLEX | NO | none | N/A | pjob_2995dcec — completed |
| render_a34a0a170 | S002 | 10437-15664ms | HERO_SYNC_LOCKED | YES | master_narration | art_67a51ece (365KB) | pjob_425b4302 — submitted |

### Critical provenance gaps

#### 1. Shared master audio with no per-slice proof (F-PROV-001)
Both hero units (S000, S002) reference the **same** master audio artifact
(`art_67a51ece`, SHA256 `9437f77002c8ce98`). There is no record of which
portion (start_ms/end_ms) of this master was sent to the provider for each
unit. The 44+ hero_audio_slice artifacts in the DB are all from stale render
versions and are NOT linked to the final valid render units.

**Impact:** Cannot prove that the audio slice sent to Higgsfield for S000
matches the audio window used in the final assembly at 0-4572ms.

#### 2. Provider job for S002 is "submitted" not "completed" (F-PROV-001)
Provider job `pjob_425b4302` for `render_a34a0a170` (S002) has status
"submitted" while the render unit status is "valid". Either:
- The status wasn't polled/updated after completion, OR
- The assembly used a stale/different version of the render unit

#### 3. No hero_audio_slice artifacts linked to valid render units (F-PROV-001)
The 44+ hero_audio_slice artifacts in the DB are all associated with stale
render units (status=stale). The active_artifact_id for S000 is
`art_18a80cc6` (generated_media, 979KB) and for S002 is `art_419c9df3`
(generated_media, 1067KB). Neither has a corresponding audio_slice artifact
recorded.

#### 4. QA "all_local_provenance" passed but per-slice hashes unverifiable
The qa_final validation (`val_841873b`) reports `all_local_provenance: true`
and `all_passing_qa: true`, but there is no per-unit audio hash comparison
in the evidence. The system claims provenance exists but the raw data shows
no proof of correct audio slice → provider → assembly alignment.

#### 5. Deliverable path collision (F-PROV-001)
All 4 16x9 deliverables write to the same file path, overwriting previous
versions. The last published deliverable (`del_fe7a12bb`, 32MB, SHA256
36ff77fd) was overwritten by a subsequent assembly (`del_fce7e5cb`, 10.4MB,
SHA256 35b972d4) that has no qa_final validation.

## Deliberations chain
| Deliverable | Status | Artifact | Size | QA Validation |
|-------------|--------|----------|------|---------------|
| del_66f357a2 | published | art_01596f5e | 36.7MB | val_de81853f (qa_final pass) |
| del_24e9c309 | assembled | art_1a83d92b | 5.3MB | none |
| del_fce7e5cb | assembled | art_4890d923 | 10.4MB | none |
| del_fe7a12bb | published | art_f31f203b | 32.0MB | val_841873b (qa_final pass) |

## Recommendations for provenance fix
1. Store each deliverable at a unique, versioned path (e.g., 
   `{production_id}/{deliverable_id}_{variant}.mp4`)
2. Link hero_audio_slice artifacts to render units as first-class references
3. Verify provider job completion status before marking render unit as valid
4. Add per-unit audio hash comparison to qa_final validation
5. Store source slice SHA256, provider request SHA256, and final window SHA256
   in a provenance chain for each hero unit

## Files exported
reports/karpathy_loop/sprint_00/S00_T003/db_exports/
├── productions.jsonl
├── stage_runs.jsonl
├── timeline_spans.jsonl
├── render_units.jsonl
├── provider_jobs.jsonl
├── artifacts.jsonl
├── validations.jsonl
├── deliverables.jsonl
├── change_requests.jsonl
├── production_events.jsonl
├── creative_beats.jsonl
└── creative_beats.note.json

Gate status:
- Gate 0 Render lock: PASS
- Gate 1 Forensic: PASS
- Gate 2 Eval-first: PENDING
Decision: (pending eval)

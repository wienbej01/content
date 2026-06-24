# Forensic Report: S01_T001 Source Audio Slice Ledger

## Production
prod_2f9bb58c0508465fb51ac6b4578bba92

## Current state of render_units schema vs ticket requirements

### Fields that EXIST (use existing, no duplicate)
| Ticket Field | DB Column | Status |
|-------------|-----------|--------|
| render_unit_id | id | ✓ |
| timeline_span_id | timeline_span_id | ✓ |
| master_audio_artifact_id | master_audio_artifact_id | ✓ |
| master_audio_sha256 | master_audio_sha256 | ✓ |
| source_slice_start_sample | speech_start_sample | ✓ (reuse — holds the start of speech in master samples) |
| source_slice_end_sample | speech_end_sample | ✓ (reuse — holds the end of speech in master samples) |
| leading_silence_samples | leading_silence_samples | ✓ |
| trailing_silence_samples | trailing_silence_samples | ✓ |
| source_slice_start_ms | — | can be derived from samples + sample_rate |
| source_slice_end_ms | — | can be derived from samples + sample_rate |

### Fields MISSING from schema
| Ticket Field | DB Column | Requires Migration |
|-------------|-----------|-------------------|
| source_slice_path | — | ✓ (or derive from artifact URI) |
| source_slice_sha256 | — | ✓ (per-slice hash, distinct from master_audio_sha256) |

### Existing audio slice flow (what works)
1. `slice_continuous_lipsync.py:materialize_hero_slot_slots()` creates hero_audio_slice artifacts
2. Artifact records include slice SHA256, speech bounds, master reference
3. Slice path stored in render_units.metadata_json.audio_path
4. `produce_db.py` reads audio_path from metadata for provider payload
5. `media_service.py:submit_provider_job()` handles provider submission

### Critical gaps (what's missing)

#### Gap 1: No source_slice_sha256 on render_units
The render_units table has `master_audio_sha256` (hash of full TTS master narration) but no `source_slice_sha256` (hash of the specific audio window sent to the provider). These are different values — the master audio is the full narration, the slice is a trimmed segment with silence padding.

#### Gap 2: No pre-submission provenance gate
`submit_provider_job()` (media_service.py line 62) checks:
- gate_a_spend approval ✓
- media contract checks ✓
- provider eligibility ✓
- text-free prompts ✓
- idempotency ✓

But does NOT check:
- Does the render unit have a source_slice_sha256?
- Does the source slice file exist on disk?
- Does the source slice hash match the file?

#### Gap 3: hero_audio_slice artifacts NOT linked to valid render units
For the last assembly, the 3 valid render units have active_artifact_ids pointing to generated_media (provider output), NOT to hero_audio_slice artifacts. The 44+ hero_audio_slice artifacts are all from stale (status=stale) render units. This means the final published video was assembled without a clear audit trail back to the specific audio slice used.

#### Gap 4: metadata_json.audio_path is fragile
The audio_path for provider submission is stored in render_units.metadata_json (a TEXT/JSON field). This is not a first-class DB column, not indexed, not validated by schema, and not gated. A JSON-parsing error or missing key would cause a silent failure or missing audio path.

## Required changes per ticket

### DB migration (add columns)
Add to render_units table:
- `source_slice_sha256 TEXT` — SHA256 of the hero_audio_slice file
- `source_slice_path TEXT` — filesystem path to the slice (optional, derivable from artifact)

### Code changes
1. **slice_continuous_lipsync.py** — After creating hero_audio_slice artifact, populate `source_slice_sha256` on the render_unit
2. **media_service.py:submit_provider_job()** — Add gate: reject if no source_slice_sha256
3. **produce_db.py** — Use source_slice_sha256 instead of metadata_json.audio_path

### Tests
- Test that hero render unit without source_slice_sha256 is rejected by submit_provider_job
- Test that source_slice_sha256 equals the actual file hash
- Test that missing source slice fails loud

## Commands executed
```bash
python3 -c "PRAGMA table_info(render_units)" — inspected schema
# Codebase inspection of scripts/slice_continuous_lipsync.py, scripts/media_service.py,
# scripts/production_repo.py, scripts/produce_db.py, scripts/paid_adapters.py
```

Gate status:
- Gate 0 Render lock: PASS
- Gate 1 Forensic: PASS
- Gate 2 Eval-first: PENDING

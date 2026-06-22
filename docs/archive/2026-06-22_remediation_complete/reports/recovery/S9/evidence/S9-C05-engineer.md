# S9-C05 — Engineer Report (F-001 / F-002 repair)

**Ticket:** S9-C05 — Multi-clip slotting + per-slot hero audio slices
**Role:** Engineer (repair cycle 1, addressing audit FAIL)
**Date:** 2026-06-19
**Branch:** `fix/flagship-001-end-to-end-recovery` (uncommitted)

## Audit findings addressed

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| F-001 | BLOCKING | Hero audio slice materialization not implemented (only sample ranges computed; no ffmpeg slicing / artifact registration / SHA / master ref) | **FIXED** |
| F-002 | MEDIUM | No validation of individual slot duration vs `min_clip_duration_sec` | **FIXED** |

## Root causes found and fixed

### F-001 — slice materialization (the blocking finding)

The prior implementation only computed per-slot speech sample *ranges*; it never produced a slice file. Three root causes were uncovered while fixing it:

1. **No slicer existed in the DB path.** `slice_continuous_lipsync.slice_hero_units` (the legacy beat-level slicer) is not wired into the DB stage graph at all (only referenced by `release_guard` and a comment). Added `slice_continuous_lipsync.materialize_hero_slot_slices()`, which for each hero slot extracts the master's `[speech_start_sample, speech_end_sample]` range via ffmpeg (sample-exact PCM re-encode), registers it as an immutable artifact (kind `hero_audio_slice`), SHA-hashes it, and writes master provenance (`master_audio_artifact_id` + `master_audio_sha256`) plus the speech sample interval onto the `render_unit`. `invoke_compile_media` calls it after `compile_render_plan` for every `HERO_SYNC_LOCKED` unit.

2. **Per-slot fields were never persisted.** `plan_render_units` read the speech/master/sample-interval columns from the span-level `spec`, so for a multi-slot hero span every slot got the same (empty) values — the sample ranges computed on the slot dicts were silently dropped. Added `_slot_or_spec(slot, spec, field)` (slot-first, spec fallback) and routed the audio/sample/master columns through it in both the validated unit dict and the INSERT params.

3. **Hardcoded 44.1 kHz sample rate.** The legacy code converted ms→samples at 44100, but the canonical `MASTER_SAMPLE_RATE` is 48000 (`timeline_utils`), which is how the master is canonicalized and sliced elsewhere. Replaced with `timeline_utils.ms_to_samples` (48000).

4. **Hero shot type was misclassified.** The S9-C04 storyboard emits the canonical type `hero_lipsync`, but `model_routing.yaml`'s `shot_type_routes` keys the hero route as `talking_head_hero`, so `hero_lipsync` fell through to `BROLL_FLEX` and **slicing never fired in production** (the original 3 tests silently tested *b-roll* slotting). Added `_HERO_SHOT_TYPE_ALIASES = {"hero_lipsync": "talking_head_hero"}` so hero beats pick up the full hero route (`lipsync_primary → seedance`, `requires_audio`, prompt_template) and classify as `HERO_SYNC_LOCKED`.

5. **Hero interval validation contract.** `validate_hero_slicing_intervals` requires a complete *generation* interval (and matching silence) alongside any speech interval. For tiled slots (no padding) the generation interval equals the speech interval; both are now set with `leading/trailing_silence_samples = 0`.

### F-002 — per-slot minimum duration

Added `_validate_hero_slot_min()`: any `HERO_SYNC_LOCKED` slot shorter than `min_clip_duration_sec` (4 s) raises loudly instead of planning an unrenderable unit. With `N = ceil(span / max_clip)` the even-split algorithm guarantees multi-slot heroes are `≥ max/2 = 7.5 s > min`, so this only ever fires for a single-slot hero span shorter than min (which must be merged/padded per `lipsync_render_rules.on_sub_min_beat`).

### Hard contracts (no silent fallbacks)

- **Hero spans without a master fail loudly.** If `HERO_SYNC_LOCKED` units exist but no `tts_master` artifact is present, `invoke_compile_media` raises (no dummy slice, no skip) — consistent with the CLAUDE.md lipsync non-negotiable.
- **The slice does not set `active_artifact_id` / advance unit status.** That is generation's job (R6-004); `link_artifact_to_render_unit` is deliberately not used for the audio input slice.

## Unit → slice linkage contract (for S9-C06)

The unit row carries **master** provenance (`master_audio_artifact_id` = the `tts_master` artifact, `master_audio_sha256` = master sha, `speech_start/end_sample` = the slot range). The slice itself is a distinct artifact, kind `hero_audio_slice`, whose `metadata_json` carries `render_unit_id`, `master_artifact_id`, `master_sha256`, and the sample interval. **S9-C06 resolves a unit's `--audio` slice by querying `artifacts WHERE kind='hero_audio_slice'` and matching `metadata.render_unit_id`.** (No new schema column was needed; the ticket allows one only if missing.)

## Files changed

- `scripts/slice_continuous_lipsync.py` — added `materialize_hero_slot_slices()` (+ reuses `_sha`, `ms_to_samples`, `probe_media`, `register_artifact`).
- `scripts/production_repo.py` — `_slot_or_spec()` helper; `plan_render_units` persists per-slot audio/sample/master columns.
- `scripts/produce_db.py` — `_HERO_SHOT_TYPE_ALIASES` hero bridge; `_validate_hero_slot_min()`; sample-rate fix (48000); generation/silence intervals on hero slots; slice materialization after `compile_render_plan`; `hero_slice_count` in the return.
- `tests/test_s9_c05_slotting.py` — master-audio fixture helper; refactored the 3 original tests to provide a real master and a `hero_lipsync` (production) shot type; added `test_hero_slice_materialized` (slice file + SHA-matches-master-subrange determinism proof + artifact + provenance + duration), `test_hero_span_without_master_fails`, `test_sub_min_hero_span_fails`.

## Test evidence

- **S9-C05 focused:** 6/6 pass (`test_long_span_slots_within_bounds`, `test_slots_tile_span_exactly`, `test_boundary_span_max_duration`, `test_hero_slice_materialized`, `test_hero_span_without_master_fails`, `test_sub_min_hero_span_fails`).
- **Dependent + compile/plan-related:** 98/98 pass (`test_s9_c02_supersede`, `test_s9_c03_tts_cost`, `test_s9_c04_storyboard`, `test_sprint2_production_repo`, `test_sprint5_tts_service`, `test_sprint6_media_service`, `test_sprint7_assemble_db`, `test_produce_db_orchestrator`, `test_repair_routing_lb603`).
- **SHA determinism proof:** `test_hero_slice_materialized` independently re-extracts the master's `[start,end]` range with the same ffmpeg parameters and asserts byte-identical SHA to the registered slice — proving the slice equals the master subrange.
- **Full suite:** 1076 passed, 1 skipped, 1 xfailed, 2 xpassed, exit 0, 687.81s (`YT_TEST_MODE=1 python3 -m pytest -q`). No regressions.
- **No paid call made** (`YT_TEST_MODE=1` throughout; ffmpeg slices a local tone fixture, no ElevenLabs/Higgsfield).

## Acceptance-gate mapping

- ✅ A 30 s hero span compiles into ≥2 slots each within the routed clip range `[4,15]` s, tiling the span exactly (contiguity asserted).
- ✅ Each hero slot has a real ffmpeg-produced slice file whose SHA matches the master subrange, registered as a `hero_audio_slice` artifact and linked to the unit; master provenance + speech interval on the unit row.
- ✅ Boundary spans (`==max` → 1 slot, `==max+1` → 2 slots) behave correctly.
- ✅ Clip ranges read from `constraints.json` (4 s / 15 s), not hardcoded.
- ✅ B-roll long beats slotted by the same ceiling; S9-C02 supersession preserved (unchanged).

## Residual risks / follow-ups

1. **S9-C04 vocabulary ↔ routing gap (NOT closed by S9-C05).** The storyboard also emits `broll_archival` and `graphic_title_card`, neither of which is in `shot_type_routes`. `broll_archival` happens to route acceptably (kling3_0 default), but `graphic_title_card` misroutes to `BROLL_FLEX`/generated-video when it should be `local_graphic`/`SILENT_GRAPHIC` (deterministic, free). Only the hero alias was bridged here (what S9-C05 needs); the b-roll/graphic aliases should be closed in S9-C04 validation or a dedicated routing ticket. Flagged so it is not forgotten.
2. **Slice lookup is a metadata scan, not an indexed column.** Fine for S9-C06 (few hero units); a `hero_audio_slice_artifact_id` column could be added later if lookup cost matters (ticket permits an additive migration).
3. **ffmpeg input-seeking (`-ss` before `-i`)** matches the existing `slice_hero_units` convention; for an MP3 master (real ElevenLabs output) input seeking is frame-approximate, but the SHA-determinism contract holds (same params → same bytes) and the slice is re-derivable from the immutable master.
4. **Integration with S9-C06 (generation `--audio`) and S9-C07 (assembly provenance)** still needs end-to-end validation once those tickets land; the slice↔assembly provenance path is documented above.

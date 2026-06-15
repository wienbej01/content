# Pipeline Data Flow Inventory — Forensic Audit

**Generated:** 2026-06-15  
**Project audited:** `how_to_use_ai_to_better_organize_your_de_short`  
**Failure at:** Step 14 (qa_media) — 6/9 clips COVERAGE_DEFICIT  

---

## Executive Summary of Root Cause

**The pipeline has a critical constraints schism:**

| Component | Max lipsync clip duration used |
|-----------|-------------------------------|
| `constraints.json` → `lipsync_render_rules.max_clip_duration_sec` | **15** |
| `reconcile_production_storyboard.py` → reads constraints.json | **15** (via config) |
| `slice_continuous_lipsync.py` → reads constraints.json | **15** (via config) |
| `compile_media_prompts.py` → reads constraints.json | **15** (via config) |
| `generate_media.py` → **HARDCODED constant** `LIPSYNC_MAX_DUR` | **10** |
| `qa_media.py` → **imports from generate_media.py** | **10** |

The production storyboard allows beats up to 15s unsplit. The slicer produces 12–15s audio slices.  
`generate_media.py` then **clamps** `duration = min(duration, LIPSYNC_MAX_DUR)` = 10s, also trimming audio.  
Seedance renders a 10s clip. QA compares clip duration (10s) against timing_map requirement (12–15s) → **FAIL**.

---

## Complete Step-by-Step Inventory

### Step 1: `research`

| Attribute | Detail |
|-----------|--------|
| **Input Files** | (none — seed from state.json) |
| **Key Fields Read** | `state["seed"]`, `state["format"]` |
| **Output Files** | `research_brief.json`, `transcripts/0_research.md` |
| **Key Fields Written** | `angle`, `key_claims[]`, `sources[]`, `research_text`, `suggested_titles[]` |
| **Downstream Consumer** | Step 2 (script_create), Step 3 (script_review_loop) |
| **Mismatches Found** | None |

---

### Step 2: `script_create`

| Attribute | Detail |
|-----------|--------|
| **Input Files** | `research_brief.json`, `state.json` |
| **Key Fields Read** | Full brief contents, `state["format"]` |
| **Output Files** | `script.json`, `transcripts/1_script_writer.md` |
| **Key Fields Written** | `title`, `project_id`, `segments[].id`, `segments[].text` |
| **Downstream Consumer** | Step 3 (script_review_loop), Step 4 (storyboard_create), Step 6 (tts) |
| **Mismatches Found** | None |

---

### Step 3: `script_review_loop`

| Attribute | Detail |
|-----------|--------|
| **Input Files** | `script.json`, `research_brief.json`, `transcripts/0_research.md` |
| **Key Fields Read** | `segments[]`, full research text, `state["format"]` |
| **Output Files** | `script.json` (overwritten), `review_rounds/script_round*.json`, `transcripts/2_script_review_loop.md` |
| **Key Fields Written** | Same as script_create (revised version) |
| **Downstream Consumer** | Step 4 (storyboard_create), Step 6 (tts) |
| **Mismatches Found** | None |

---

### Step 4: `storyboard_create`

| Attribute | Detail |
|-----------|--------|
| **Input Files** | `script.json`, `transcripts/0_research.md` |
| **Key Fields Read** | `state["format"]`, script segments |
| **Output Files** | `storyboard.json`, `transcripts/3_storyboard_director.md` |
| **Key Fields Written** | `schema_version`, `beats[].beat_id`, `.shot_type`, `.segment_id`, `.visual_brief`, `.narration_text`, `.asset_type`, `.model`, `.model_tier`, `.lipsync_required`, `.est_duration_sec`, `.reference_images[]` |
| **Downstream Consumer** | Step 5 (storyboard_review_loop), Step 7 (build_timing_map), Step 8 (production_storyboard), Step 9 (compliance_check) |
| **Mismatches Found** | ⚠️ `est_duration_sec` is a creative estimate (hardcoded to 10 in this run) — NOT tied to actual TTS audio length. Downstream production_storyboard ignores this and uses timing_map instead. |

---

### Step 5: `storyboard_review_loop`

| Attribute | Detail |
|-----------|--------|
| **Input Files** | `storyboard.json`, `transcripts/0_research.md`, `script.json` |
| **Key Fields Read** | `beats[]`, full source text, `state["format"]` |
| **Output Files** | `storyboard.json` (overwritten), `review_rounds/storyboard_round*.json` |
| **Key Fields Written** | Same as storyboard_create. Records `storyboard_review` gate. |
| **Downstream Consumer** | Steps 7, 8, 9, 10 |
| **Mismatches Found** | None |

---

### Step 6: `tts`

| Attribute | Detail |
|-----------|--------|
| **Input Files** | `script.json` |
| **Key Fields Read** | `project_id`, `segments[].id`, `segments[].text` |
| **Output Files** | `narration/continuous.mp3`, `narration/{segment_id}.mp3` (per-segment), `tts_log.json` |
| **Key Fields Written** | Audio files (no JSON fields — media artifacts) |
| **Downstream Consumer** | Step 7 (build_timing_map), Step 11 (slice_lipsync) |
| **Mismatches Found** | None |

---

### Step 7: `build_timing_map`

| Attribute | Detail |
|-----------|--------|
| **Input Files** | `narration/continuous.mp3`, `storyboard.json` |
| **Key Fields Read** | `storyboard["beats"][].beat_id`, `.narration_text` (for word-proportional allocation) |
| **Output Files** | `narration/beat_timing_map.json` |
| **Key Fields Written** | `total_duration`, `beat_count`, `beats[].beat_id`, `.start`, `.end`, `.duration` |
| **Downstream Consumer** | Step 8 (production_storyboard), Step 10 (compile_media_plan), Step 14 (qa_media), Step 15 (reconcile_duration), Step 17 (build_manifest) |
| **Mismatches Found** | ⚠️ `beat_timing_map` uses **creative storyboard beat_ids** (B001–B011). After production_storyboard splits (e.g. B005→B005a+B005b), split children are NOT in the timing map. compile_media_plan and qa_media must handle lookups for split child beats via `audio_start_sec`/`audio_end_sec` carried in the production beat. |

---

### Step 8: `production_storyboard`

| Attribute | Detail |
|-----------|--------|
| **Input Files** | `storyboard.json`, `narration/beat_timing_map.json`, `narration/continuous.mp3` |
| **Key Fields Read** | Creative beats (all fields), timing `beats[].start`, `.end`, `.duration` |
| **Output Files** | `production_storyboard.json`, `review_report.json` |
| **Key Fields Written** | `beats[].beat_id`, `.source_beat_id`, `.audio_start_sec`, `.audio_end_sec`, `.audio_duration_sec`, `.treatment`, `.model`, `.model_max_duration_sec`, `.lipsync_required`, `.shot_type`, `.coverage_plan[]`, `.narration_text`, + all creative carry fields |
| **Downstream Consumer** | Step 10 (compile_media_plan) |
| **Mismatches Found** | 🔴 **CRITICAL**: `model_max_duration_sec` = 15 (from `constraints.json`). Beats with `audio_duration_sec` 10–15s are NOT split because they are under this limit. But Seedance actually only renders ≤10s clips. The constraint was wrongly set to 15. |

---

### Step 9: `compliance_check`

| Attribute | Detail |
|-----------|--------|
| **Input Files** | `storyboard.json` (creative, not production) |
| **Key Fields Read** | `beats[]` structure/types |
| **Output Files** | None (pass/fail only) |
| **Key Fields Written** | None |
| **Downstream Consumer** | Gate — blocks further progress on fail |
| **Mismatches Found** | ⚠️ Validates the CREATIVE storyboard, not the production storyboard. Structural checks (shot-mix bands, forbidden patterns) are verified on the pre-split creative version. Production splits and reroutes are unchecked here. |

---

### Step 10: `compile_media_plan`

| Attribute | Detail |
|-----------|--------|
| **Input Files** | `production_storyboard.json`, `constraints.json`, `model_routing.yaml` |
| **Key Fields Read** | `beats[].beat_id`, `.shot_type`, `.model`, `.asset_type`, `.visual_brief`, `.audio_start_sec`, `.audio_end_sec`, `.audio_duration_sec`, `.lipsync_required`, `.reference_images`, `.est_duration_sec`, `.coverage_plan[]` |
| **Output Files** | `media_plan.json` |
| **Key Fields Written** | All universal prompt fields + `duration_target_sec`, `audio_start_sec`, `audio_end_sec`, `audio_duration_sec`, `output_path`, `lipsync_required`, `positive_prompt`, `negative_prompt`, `model`, `cost`, `audio_slice` (initially null for continuous mode) |
| **Downstream Consumer** | Step 11 (slice_lipsync), Step 12 (gate_a_budget), Step 13 (generate_media), Step 14 (qa_media), Step 15 (reconcile_duration), Step 16 (render_graphics), Step 17 (build_manifest) |
| **Mismatches Found** | 🔴 **CRITICAL**: `duration_target_sec` is set from `beat.get("est_duration_sec", 6)` — this is the CREATIVE storyboard's estimate (hardcoded 10), NOT `audio_duration_sec`. For B001 (audio_duration=12.7s), `duration_target_sec`=10. This is misleading but NOT the direct cause — `generate_media.py` ignores `duration_target_sec` for lipsync beats and uses `audio_slice.padded_len_sec` instead. |
| **Also**: `compile_beat()` checks `est_duration_sec > max_clip` from constraints (15s). Since production_storyboard already split at 15s, and the creative `est_duration_sec`=10, this check NEVER fires. No safety net catches 10–15s beats here. |

---

### Step 11: `slice_lipsync`

| Attribute | Detail |
|-----------|--------|
| **Input Files** | `media_plan.json`, `narration/continuous.mp3`, `narration/beat_timing_map.json` |
| **Key Fields Read** | `beats[].beat_id`, `.lipsync_required`, `.audio_start_sec`, `.audio_end_sec` |
| **Output Files** | `media_plan.json` (updated in-place), `narration/slices/{beat_id}.mp3` |
| **Key Fields Written** | `beats[].audio_slice.file`, `.sha256`, `.slice_sha256`, `.start_sec`, `.end_sec`, `.speech_len_sec`, `.padded_len_sec`, `.master_sha256`, `.parent_mp3_sha256` |
| **Downstream Consumer** | Step 13 (generate_media), Step 14 (qa_media) |
| **Mismatches Found** | 🔴 **CRITICAL**: Loads `LIPSYNC_MAX` from `constraints.json` → **15s**. The check `if padded > LIPSYNC_MAX: raise ValueError(...)` passes because `padded_len = max(ceil(speech + 0.2), 4)` → e.g. 13s for B001. Since 13 ≤ 15, no error is raised. The slicer happily produces a 13s audio slice. But `generate_media.py` will then clamp the video request to 10s. |

---

### Step 12: `gate_a_budget`

| Attribute | Detail |
|-----------|--------|
| **Input Files** | `media_plan.json` |
| **Key Fields Read** | `totals.est_usd`, `totals.est_tokens`, `beats` count |
| **Output Files** | None (records gates: `budget`, `render_approval`) |
| **Key Fields Written** | Gate ledger entries |
| **Downstream Consumer** | Step 13 (generate_media) — requires gates |
| **Mismatches Found** | None |

---

### Step 13: `generate_media`

| Attribute | Detail |
|-----------|--------|
| **Input Files** | `media_plan.json`, `narration/slices/{beat_id}.mp3`, reference images |
| **Key Fields Read** | `beats[].beat_id`, `.model`, `.positive_prompt`, `.negative_prompt`, `.lipsync_required`, `.shot_type`, `.audio_slice.padded_len_sec`, `.audio_slice.file`, `.reference_images[]`, `.output_path`, `.duration_target_sec`, `.cost` |
| **Output Files** | `assets/media/{segment_id}/{beat_id}.mp4`, `media_generation_log.json`, `.fp.json` fingerprints |
| **Key Fields Written** | Video files + provenance log |
| **Downstream Consumer** | Step 14 (qa_media), Step 15 (reconcile_duration), Step 17 (build_manifest), Step 18 (assemble) |
| **Mismatches Found** | 🔴 **ROOT CAUSE #1**: Duration calculation for lipsync: `duration = int(sl["padded_len_sec"])` then `duration = min(duration, LIPSYNC_MAX_DUR)` where `LIPSYNC_MAX_DUR = 10`. So B001 with `padded_len_sec=13` → requests 10s clip. The **hardcoded constant** (10) disagrees with `constraints.json` (15). |
| **Also**: 🔴 **ROOT CAUSE #2**: When `audio_dur > duration + 0.1`, the audio slice is TRIMMED to match the video duration: `ffmpeg -t {duration}` → only first 10s of a 13s slice sent to API. Seedance thus renders 10s of speech + 10s of video. The remaining 2.7s of speech has no visual. |

---

### Step 14: `qa_media`

| Attribute | Detail |
|-----------|--------|
| **Input Files** | `media_plan.json`, generated clips at `output_path`, `narration/beat_timing_map.json` |
| **Key Fields Read** | `beats[].beat_id`, `.output_path`, `.shot_type`, `.audio_policy`, `.lipsync_required`, `.audio_slice` (all sub-fields), `.model`, `.asset_type`; timing_map `beats[].start`, `.end` |
| **Output Files** | `media_qa_report.json` |
| **Key Fields Written** | `results[].id`, `.status`, `.issues[]`, `.duration`, `.width`, `.height` |
| **Downstream Consumer** | Step 15 (reconcile_duration indirectly), pipeline gate |
| **Mismatches Found** | 🔴 **MISMATCH #1 (lipsync duration check)**: QA imports `LIPSYNC_MAX_DUR=10` from generate_media. It accepts clips at 10s (`abs(adur - LIPSYNC_MAX_DUR) <= tol`). But coverage check compares against timing_map (12.7s required). Clip passes the lipsync-audio-duration check but FAILS coverage. This is contradictory: it's both "correctly rendered" and "too short". |
| **Also**: 🔴 **MISMATCH #2 (COVERAGE_DEFICIT logic)**: `qa_media` loads timing_map and checks `required = timing[bid]["end"] - timing[bid]["start"]` vs `actual = entry["duration"]`. For split beats (B005a, B011a), the timing_map lookup uses the **child beat_id** which does NOT exist in timing_map (only parent B005/B011 exist). The coverage check only works because the timing lookup is done by matching `entry["id"]` against `tm_lookup` keys — split children are NOT in the timing map, so the coverage check silently SKIPS them. They fail instead on the `lipsync_checks` path (slice duration > clip duration). |

---

### Step 15: `reconcile_duration`

| Attribute | Detail |
|-----------|--------|
| **Input Files** | `narration/beat_timing_map.json`, `media_plan.json`, generated clips |
| **Key Fields Read** | timing `beats[].beat_id`, `.start`, `.end`; plan `beats[].beat_id`, `.asset_type`, `.output_path` |
| **Output Files** | `duration_reconciliation.csv` |
| **Key Fields Written** | Per-beat: `required_sec`, `available_sec`, `deficit_sec`, `status` |
| **Downstream Consumer** | Pipeline gate — blocks assembly on deficit |
| **Mismatches Found** | ⚠️ Same timing_map lookup issue: split children (B005a, B005b, B011a, B011b) are in `media_plan` but NOT in `timing_map`. `reconcile_duration` would report them as `MISSING_PLAN` from timing_map perspective (it indexes timing by beat_id and checks if plan beats have timing entries). Actually it indexes plan by beat_id, then iterates timing_map beats. Since timing has only B005/B011 (parents), and plan has B005a/B005b, the timing entries for B005 find no matching plan beat → reports deficit. |

---

### Step 16: `render_graphics`

| Attribute | Detail |
|-----------|--------|
| **Input Files** | `media_plan.json` (--batch mode) |
| **Key Fields Read** | `beats[].beat_id`, `.graphics[]`, `.shot_type` |
| **Output Files** | PNG overlay files |
| **Key Fields Written** | Overlay PNGs at configured paths |
| **Downstream Consumer** | Step 18 (assemble) |
| **Mismatches Found** | None identified |

---

### Step 17: `build_manifest`

| Attribute | Detail |
|-----------|--------|
| **Input Files** | `media_plan.json`, `narration/beat_timing_map.json`, `state.json` |
| **Key Fields Read** | `plan.beats[].beat_id`, `.output_path`, `.audio_policy`, `.lipsync_required`, `.audio_slice`, `.narration_text`; timing `beats[].beat_id`, `.start`, `.end` |
| **Output Files** | `manifest.json` |
| **Key Fields Written** | `segments[].id`, `.media`, `.media_sha256`, `.timing_in`, `.timing_out`, `.duration_required`, `.audio_policy`, `.speech_len_sec`, `.lipsync_provenance` |
| **Downstream Consumer** | Step 18 (assemble) |
| **Mismatches Found** | 🔴 **MISMATCH**: `build_manifest` cross-references timing_map beat_ids with plan beat_ids. Split children (B005a) exist in plan but NOT in timing_map → reports `"Beat B005a in media_plan but missing from timing_map"` → **hard error, manifest build fails**. This means the pipeline would also fail at step 17 even if QA passed. |

---

### Step 18: `assemble`

| Attribute | Detail |
|-----------|--------|
| **Input Files** | `manifest.json`, all media clips, `narration/continuous.mp3` |
| **Key Fields Read** | `segments[].media`, `.timing_in`, `.timing_out`, `.audio_policy`, `.speech_len_sec` |
| **Output Files** | `{project_id}_16x9.mp4`, `{project_id}_9x16.mp4`, `{project_id}_log.json` |
| **Key Fields Written** | Final video + assembly log |
| **Downstream Consumer** | Step 19 (qa_final) |
| **Mismatches Found** | None (manifest-driven, deterministic) |

---

### Step 19: `qa_final`

| Attribute | Detail |
|-----------|--------|
| **Input Files** | Assembled MP4 |
| **Key Fields Read** | Video/audio streams via ffprobe |
| **Output Files** | `final_qa_report.json` |
| **Key Fields Written** | Freeze detection, black frame, length checks |
| **Downstream Consumer** | Step 20, Step 21 |
| **Mismatches Found** | None |

---

### Step 20: `build_quality_report`

| Attribute | Detail |
|-----------|--------|
| **Input Files** | Various project artifacts |
| **Output Files** | `run_quality_report.json`, `run_quality_report.md` |
| **Key Fields Written** | Aggregate quality metrics |
| **Downstream Consumer** | Step 21 (gate_b_review) |
| **Mismatches Found** | None |

---

### Step 21: `gate_b_review`

| Attribute | Detail |
|-----------|--------|
| **Input Files** | Assembled MP4, `run_quality_report.json` |
| **Key Fields Read** | Video file, quality summary |
| **Output Files** | Telegram notification (external) |
| **Key Fields Written** | None |
| **Downstream Consumer** | None (terminal step) |
| **Mismatches Found** | None |

---

## Summary of All Data-Flow Mismatches

### 🔴 CRITICAL — Direct Cause of Current Failure

| # | Location | Description |
|---|----------|-------------|
| **C1** | `constraints.json` → `lipsync_render_rules.max_clip_duration_sec` = 15 | Wrong. Seedance 2.0 API hard-rejects clips > 10s. This value was incorrectly changed from 10 to 15. |
| **C2** | `generate_media.py` line 38: `LIPSYNC_MAX_DUR = 10` (hardcoded) | Correct for API but DISAGREES with constraints.json. This is the only component that knows the real limit. |
| **C3** | `reconcile_production_storyboard.py` reads constraints (15s) and does NOT split 10–15s beats | Beats B001(12.7s), B003(11.6s), B007(14.1s), B008(13.8s) pass through unsplit. |
| **C4** | `slice_continuous_lipsync.py` reads constraints (15s) and produces 12–15s audio slices | Slices are longer than Seedance can render. |
| **C5** | `generate_media.py` clamps duration to 10s AND trims audio to match | Renders 10s video with 10s of a 13s slice; 2–5s of speech has no visual. |
| **C6** | `qa_media.py` coverage check: timing_map duration (12.7s) vs clip (10.1s) | Correctly identifies the deficit but the defect was baked in 5 steps earlier. |

### 🔴 CRITICAL — Additional Structural Mismatches (Would Block Even If Fixed)

| # | Location | Description |
|---|----------|-------------|
| **S1** | beat_timing_map uses **parent** beat_ids only; after production_storyboard splits, child beat_ids (B005a, B011a) don't exist in timing_map | `build_manifest.py` (step 17) will hard-error: "Beat B005a in media_plan but missing from timing_map". `reconcile_duration.py` (step 15) will show parent B005 as MISSING_PLAN (no plan entry for the parent, only children). |
| **S2** | `duration_target_sec` in media_plan is set from `est_duration_sec` (creative guess = 10) not from `audio_duration_sec` (actual timing) | Misleading metadata. Not directly used by generate_media for lipsync (uses `padded_len_sec`), but would be wrong for any downstream consumer that trusts it. |

### ⚠️ WARNING — Design Gaps (Not Currently Failing)

| # | Location | Description |
|---|----------|-------------|
| **W1** | `compliance_check` (step 9) validates creative storyboard, not production storyboard | Post-split structure, coverage plans, and reroutes are never compliance-checked. |
| **W2** | `compile_beat()` early reject check: `if est_dur > max_clip` uses creative `est_duration_sec` | This never fires because creative estimates are always ≤10s. The actual speech duration (`audio_duration_sec`) is not checked against model max at compile time. |
| **W3** | `B002` in timing_map has duration 0.01s | This is likely a beat with no narration (graphic_title_card). Works but is fragile — a zero-duration beat could cause division errors elsewhere. |

---

## Causal Chain of the Current Failure

```
constraints.json: max_clip_duration_sec = 15   ← WRONG (should be 10)
         ↓
reconcile_production_storyboard: "15s is the max, 12.7s is fine, no split needed"
         ↓
production_storyboard.json: B001 with audio_duration_sec=12.727, model_max=15
         ↓
compile_media_plan: passes B001 through (est_duration_sec=10 < max_clip=15, no reject)
         ↓
slice_continuous_lipsync: padded_len = max(ceil(12.727+0.2), 4) = 13  (13 < 15, allowed)
         ↓
media_plan.json: B001.audio_slice.padded_len_sec = 13
         ↓
generate_media.py: duration = int(13) → min(13, LIPSYNC_MAX_DUR=10) → 10
                   audio trimmed: ffmpeg -t 10 (discards last 3s of slice)
                   Seedance API call: duration=10 → renders 10.1s clip
         ↓
qa_media.py: 
  - lipsync_checks: audio_dur=10.1 ≈ LIPSYNC_MAX_DUR=10 → "matched" (PASS this check)
  - coverage check: timing_map says B001 needs 12.727s, clip is 10.1s → DEFICIT 2.627s → FAIL
```

---

## Recommended Fixes (Priority Order)

1. **Fix `constraints.json`**: Set `max_clip_duration_sec` back to **10** (the real Seedance limit).
2. **Remove hardcoded `LIPSYNC_MAX_DUR=10`** from `generate_media.py`: read from constraints.json like all other components.
3. **Fix timing_map ↔ production split desync** (S1): Either:
   - Regenerate `beat_timing_map.json` AFTER production_storyboard splits (use child beat_ids), OR
   - Make `build_manifest.py` and `reconcile_duration.py` look up parent beat_ids via `source_beat_id` when child is not found.
4. **Add a compile-time guard**: In `compile_media_plan.compile_beat()`, check `audio_duration_sec` (not `est_duration_sec`) against the model's actual rendering limit.
5. **Make `slice_continuous_lipsync.py` read the limit from the SAME source as `generate_media.py`** or validate at slice time that `padded_len ≤ actual_api_limit`.

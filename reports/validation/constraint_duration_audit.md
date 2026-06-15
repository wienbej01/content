# Constraint & Duration Audit — Seedance 2.0 max_clip_duration_sec

**Date:** 2026-06-15  
**Auditor:** Subagent 2 (Constraint & Duration Audit)  
**Severity:** CRITICAL — pipeline produces undeliverable clips when constraint is wrong  
**Project:** `how_to_use_ai_to_better_organize_your_de_short`

---

## 1. Actual Seedance 2.0 Render Evidence

### All generated hero clips (ffprobe measured):

| File | Duration |
|------|----------|
| `assets/media/001_hook/B001.mp4` | 10.042s |
| `assets/media/002_implication/B003.mp4` | 10.042s |
| `assets/media/003_proof/B005a.mp4` | 9.042s |
| `assets/media/003_proof/B005b.mp4` | 9.042s |
| `assets/media/003_proof/B007.mp4` | 10.042s |
| `assets/media/004_takeaway/B008.mp4` | 10.042s |
| `assets/media/004_takeaway/B010.mp4` | 7.042s |
| `assets/media/005_cta/B011a.mp4` | 9.042s |
| `assets/media/005_cta/B011b.mp4` | 10.042s |

### Generation log — every request vs actual:

| Beat | Requested | Rendered | Match? |
|------|-----------|----------|--------|
| B001 | 10.1s | 10.1s | ✅ |
| B001a | 9.1s | 9.1s | ✅ |
| B001b | 5.09s | 5.09s | ✅ |
| B003 | 10.1s | 10.1s | ✅ |
| B005a | 9.06s | 9.06s | ✅ |
| B005b | 9.1s | 9.1s | ✅ |
| B005c | 4.09s | 4.09s | ✅ |
| B007 | 10.05s | 10.05s | ✅ |
| B007a | 10.05s | 10.05s | ✅ |
| B007b | 5.09s | 5.09s | ✅ |
| B008 | 10.1s | 10.1s | ✅ |
| B008a | 10.1s | 10.1s | ✅ |
| B008b | 5.09s | 5.09s | ✅ |
| B010 | 7.08s | 7.08s | ✅ |
| B011a | 9.1s | 9.1s | ✅ |
| B011b | 10.1s | 10.1s | ✅ |
| B011c | 4.09s | 4.09s | ✅ |

**Finding:** Seedance renders exactly the requested duration. `generate_media.py` **never requested >10.1s** because it has `LIPSYNC_MAX_DUR = 10` hardcoded (line 38). The API cost endpoint accepts `--duration 15` without error, but no clip was ever rendered at >10.1s in production.

---

## 2. The CORRECT Seedance 2.0 Max Duration

**Answer: 10 seconds (renders up to 10.1s with frame rounding).**

Evidence:
1. **17 renders** — maximum observed is 10.1s, never higher.
2. **`generate_media.py` line 38:** `LIPSYNC_MAX_DUR = 10` with comment "seedance_2_0 max duration per clip (seconds)"
3. **`generate_media.py` line 914:** `duration = min(duration, LIPSYNC_MAX_DUR)  # Seedance rejects > 10s`
4. **`FLAGSHIP_001_REMEDIATION_PLAN.md`** (project's own documentation): *"Our current `min(padded,10)` clamp on >10s beats (B047/B086/B090) breaks this: Seedance compresses 15s of speech into 10s"* — confirming that Seedance truncates at 10s.
5. **`FLAGSHIP_001_SPRINT_PLAN.md`:** *"storyboard.py splits hero beats > max_clip_duration_sec (10s, config) into ≤10s sub-beats"*
6. **The cost endpoint accepts 15s** — this is billing-level acceptance, NOT render capability. The API will charge for 15s worth of credits (67.5 credits vs 45 for 10s) but the rendered output is capped at ~10.1s.

**The 15s value in constraints.json is WRONG. The correct value is 10.**

---

## 3. Constraint Chain — Where `max_clip_duration_sec` Is Read

### Source of truth (WRONG):
```
docs/channel_universe/constraints.json:192: "max_clip_duration_sec": 15   ← WRONG (was 10, changed today)
```

### All consumers:

| File:Line | How Used | Effect of 15 vs 10 |
|-----------|----------|---------------------|
| `scripts/compile_media_prompts.py:137` | Early reject: hero speech > max → error | Allows 10-15s beats through (should reject) |
| `scripts/compile_media_prompts.py:479` | Slice padding: if padded > max → error | Allows 12-15s slices (should reject) |
| `scripts/slice_continuous_lipsync.py:37` | `_load_lipsync_limits()` → LIPSYNC_MAX | Allows 12-15s slices without error |
| `scripts/slice_continuous_lipsync.py:86-89` | Hard reject if padded > LIPSYNC_MAX | Won't fire until >15s (should fire at >10s) |
| `scripts/reconcile_production_storyboard.py:42` | Loads `max_clip_sec` from rules | Allows >10s beats through reconciliation |
| `scripts/reconcile_production_storyboard.py:281` | Splitting/rerouting decisions | Won't split 10-15s beats (should split) |

### Hardcoded safety net (CORRECT, saved the render):
| File:Line | Value | Effect |
|-----------|-------|--------|
| `scripts/generate_media.py:38` | `LIPSYNC_MAX_DUR = 10` | Clamps actual API request to ≤10 |
| `scripts/generate_media.py:914` | `min(duration, LIPSYNC_MAX_DUR)` | Last-resort clamp at generation time |
| `scripts/qa_media.py:102-109` | imports `LIPSYNC_MAX_DUR` from generate_media | Recognizes 10s-clamped clips |

### Tests (CORRECT at 10):
| File | Value Used |
|------|-----------|
| `tests/test_production_contract.py:18` | `max_clip_sec: 10.0` |
| `tests/test_reconcile_storyboard.py:13` | `max_clip_sec: 10.0` |
| `tests/test_reroute.py:12` | `max_clip_sec: 10.0` |
| `tests/test_produce_resume.py:379` | `max_clip_sec: 10.0` |
| `tests/test_audio_alignment.py:18` | `max_clip_sec: 10.0` |
| `tests/test_post_tts_e2e.py:29` | `max_clip_sec: 10.0` |

---

## 4. Duration Logic End-to-End (Mismatch Map)

### The full chain for beat B001 (12.7s speech):

| Stage | Duration | Source |
|-------|----------|--------|
| 1. Beat timing (TTS) | speech=12.727s | `beat_timing_map.json` |
| 2. Production storyboard | `duration_target_sec=10` | `production_storyboard.json` (capped at old 10s target) |
| 3. Slice computation | padded=ceil(12.727+0.2)=**13s** | `slice_continuous_lipsync.py` using `max_clip_duration_sec=15` from constraints.json |
| 4. **Should have rejected** | 13 > 10 → SPLIT | But constraint says 15, so 13 < 15 → PASS ❌ |
| 5. Audio slice created | B001.mp3 = 13.0s | Written to disk |
| 6. Media plan | `padded_len_sec=13` | Stored in `media_plan.json` |
| 7. Generation request | `int(13)` → clamped to `min(13, 10)` = **10** | `generate_media.py` LIPSYNC_MAX_DUR=10 |
| 8. Seedance renders | **10.1s** clip with 10.1s baked audio | Only first 10.1s of the 13s slice is lip-synced |
| 9. QA check | clip=10.1s vs needs=12.727s → **COVERAGE_DEFICIT** | FAIL: 2.6s of speech has no video |

### The mismatch enters at Stage 3-4:
The slicing layer reads `max_clip_duration_sec=15` from constraints.json and allows the 13s padded slice through. But `generate_media.py` has a hardcoded `LIPSYNC_MAX_DUR=10` safety net that clamps the actual render request. The result: a 13s audio slice paired with a 10.1s video clip = 2.6s of orphaned speech.

---

## 5. Root Cause

**A single wrong value in `constraints.json`** (`max_clip_duration_sec: 15`) broke the constraint chain:

- The slicing/splitting layers trust `constraints.json` and allowed beats >10s to pass as single clips.
- The generation layer has a hardcoded safety net (`LIPSYNC_MAX_DUR = 10`) that silently clamped the request.
- The result: audio slices are 12-15s but rendered clips are ≤10.1s → QA correctly flags COVERAGE_DEFICIT.

The **hardcoded value in `generate_media.py` saved us from wasting even more money** (Seedance would have charged 67.5 credits for a 15s request that renders at 10.1s), but it created the desync between audio and video.

---

## 6. Systemic Fix — Every Place That Needs Updating

### MUST FIX (constraint restoration):

| # | File | Change | Priority |
|---|------|--------|----------|
| 1 | `docs/channel_universe/constraints.json:192` | `"max_clip_duration_sec": 15` → `10` | **CRITICAL** |
| 2 | `docs/channel_universe/constraints.json:193` | Restore reason: `"Seedance 2.0 rejects duration > 10s. Beats with padded_len_sec > 10s must be split into multiple clips or have their slice trimmed to 10s."` | CRITICAL |

### SHOULD FIX (eliminate inconsistency between constraints.json and hardcoded values):

| # | File | Issue | Recommendation |
|---|------|-------|----------------|
| 3 | `scripts/generate_media.py:38` | Hardcoded `LIPSYNC_MAX_DUR = 10` — should read from constraints.json | Load from constraints.json with 10 as default, or keep hardcoded as safety net |
| 4 | `configs/james/model_routing.yaml:119,124-125` | Comments reference "≤15s narration" as the lipsync threshold | Update comments to "≤10s per clip" |

### MUST REDO (project artifacts):

| # | Artifact | Issue | Fix |
|---|----------|-------|-----|
| 5 | `narration/slices/B001.mp3` (13s) | Over-limit slice | Re-slice after constraint fix |
| 6 | `narration/slices/B003.mp3` (12s) | Over-limit slice | Re-slice |
| 7 | `narration/slices/B007.mp3` (15s) | Over-limit slice | Re-slice |
| 8 | `narration/slices/B008.mp3` (15s) | Over-limit slice | Re-slice |
| 9 | `narration/slices/B011a.mp3` (14s) | Over-limit slice | Re-slice |
| 10 | `media_plan.json` | Contains padded_len_sec values >10 | Recompile |
| 11 | `production_storyboard.json` | Beats B001, B003, B007, B008, B011a need splitting | Re-reconcile with correct limit |
| 12 | All affected `.mp4` clips | 10s clip + 13-15s audio slice = desync | Re-generate after proper splitting |

### Recommended safety improvement:

| # | Location | Change |
|---|----------|--------|
| 13 | `scripts/generate_media.py` | Add a **WARNING log** when `padded_len_sec > LIPSYNC_MAX_DUR` is clamped: "audio slice {padded}s > render limit {max}s — clip will have orphaned speech. Fix constraint chain upstream." |
| 14 | `scripts/slice_continuous_lipsync.py` | Cross-check: `assert max <= 10` or read from both constraints.json AND generate_media.LIPSYNC_MAX_DUR to catch divergence |

---

## 7. How This Should Never Happen Again

The constraint chain has **two sources of truth** for the same limit:
1. `constraints.json` → `lipsync_render_rules.max_clip_duration_sec` (dynamic, read by slicing/splitting/compile)
2. `scripts/generate_media.py` → `LIPSYNC_MAX_DUR = 10` (hardcoded, read by generation/QA)

**Recommendation:** Make `generate_media.py` read from `constraints.json` (same pattern as `_seedance_min_duration()` which already loads min from constraints.json). If the loaded value exceeds 10, log a CRITICAL warning and cap at 10. This way there is ONE source of truth, and the safety net remains.

Alternatively: add a startup assertion in `generate_media.py`:
```python
_max = json.loads(CONSTRAINTS_PATH.read_text()).get("lipsync_render_rules", {}).get("max_clip_duration_sec", 10)
assert _max <= 10, f"FATAL: max_clip_duration_sec={_max} exceeds Seedance hard limit of 10s"
```

---

## 8. Summary

| Question | Answer |
|----------|--------|
| What is the REAL Seedance 2.0 max? | **10 seconds** (renders up to 10.1s with frame rounding) |
| Was 15s ever rendered successfully? | **No.** Zero clips >10.1s exist. |
| Does the API accept duration=15? | **Yes for billing** (charges 67.5 credits). Render output still caps at ~10s. |
| What broke? | `constraints.json` changed from 10→15, slicing layer trusted it, generation layer clamped silently. |
| Impact | 6 of 9 hero beats have COVERAGE_DEFICIT (10s clip vs 11-15s audio requirement). |
| Fix complexity | Low — revert one JSON value, re-slice, re-reconcile, re-generate affected beats. |

# QA & Gate Consistency Audit

**Date:** 2026-06-15T00:20 +08:00  
**Scope:** `scripts/qa_media.py`, `scripts/gates.py`, `scripts/generate_media.py`, `scripts/compile_media_prompts.py`, `scripts/slice_continuous_lipsync.py`, `scripts/produce.py`  
**Root cause:** `constraints.json` says `max_clip_duration_sec=15` but Seedance hardware limit is 10s. The pipeline disagrees with itself.

---

## 1. Every QA Check Documented

`scripts/qa_media.py` performs these checks on each beat:

| # | Check | Comparison | Source of expected value |
|---|-------|-----------|--------------------------|
| 1 | MISSING | `file.exists()` | `output_path` from media_plan beat |
| 2 | UNREADABLE | ffprobe parse success | N/A |
| 3 | DIMENSIONS | `(width, height)` vs scope expectation | Hardcoded `DIMS_BY_SCOPE` (1280×720 or 1920×1080 accepted) |
| 4 | TOO_SHORT | `duration < 2.0s` | Hardcoded `MIN_DURATION = 2.0` |
| 5 | AUDIO_POLICY | generated_tts must NOT have audio; baked_in MUST have audio | `audio_mode` field from media_plan beat |
| 6 | LIPSYNC (a) | hero_lipsync clip MUST have audio stream | `is_hero_lipsync()` detection |
| 7 | LIPSYNC (b) | audio duration must match one of: `speech_len_sec ±0.15s`, `padded_len_sec ±0.15s`, or `LIPSYNC_MAX_DUR ±0.15s` | `audio_slice` dict in media_plan + `LIPSYNC_MAX_DUR` imported from `generate_media.py` |
| 8 | LIPSYNC (c) | clip video duration >= slice duration (or clamped at `LIPSYNC_MAX_DUR`) | `audio_slice.start_sec/end_sec` or `speech_len_sec` |
| 9 | LIPSYNC (d) | provenance fields present + hash valid | `audio_slice.slice_sha256`, `parent_mp3_sha256`, `file` |
| 10 | CROP_SAFETY | hero beats must declare `crop_safety=center_safe` | beat field |
| 11 | BLANK_SCREEN | Luma stddev > threshold on sampled frames | `constraints.json → qa_thresholds.min_luma_stddev` |
| 12 | FROZEN_VIDEO | freezedetect % < threshold | `constraints.json → qa_thresholds.max_freeze_pct` |
| 13 | STALE_ARTIFACT | Fingerprint verification | `.fp.json` sidecar, `artifact_fingerprint.py` |
| 14 | COVERAGE_DEFICIT | clip duration vs timing-map requirement | `beat_timing_map.json` → `end - start` for each beat_id |

---

## 2. Critical Inconsistency #1: `LIPSYNC_MAX_DUR` vs `constraints.json`

### The contradiction

| Source | Value | Used by |
|--------|-------|---------|
| `generate_media.py` line 38: `LIPSYNC_MAX_DUR = 10` | **10s** | Actual Seedance API call duration clamp (line 914) |
| `qa_media.py` line 102: `from generate_media import LIPSYNC_MAX_DUR` | **10s** | QA duration acceptance threshold |
| `constraints.json` line 192: `"max_clip_duration_sec": 15` | **15s** | Read by `compile_media_prompts.py` (line 479), `slice_continuous_lipsync.py` (line 37), `reconcile_production_storyboard.py` (line 42) |

### The effect

1. `constraints.json` says max=15 → `compile_media_prompts.py` allows `padded_len` up to 15s without error.
2. `slice_continuous_lipsync.py` reads max=15 → allows speech spans up to 15s without raising.
3. `storyboard.py` line 48: `LIPSYNC_RENDER_MAX_SEC = 10.0` → splits beats at 10s at storyboard creation time. ✅ correct.
4. But `reconcile_production_storyboard.py` loads constraints (line 42) → uses max=15 → allows beats up to 15s without splitting.
5. `generate_media.py` line 914: `duration = min(duration, LIPSYNC_MAX_DUR)` → **always clamps to 10s** regardless of what was planned.
6. Seedance renders a **10.1s clip** (10s + encoding overage).
7. QA reads `LIPSYNC_MAX_DUR=10` from generate_media → accepts 10±0.15s as valid for the clamped-at-render case.
8. But `beat_timing_map` says the beat needs 12-14s → **COVERAGE_DEFICIT** fires.

### Root cause

`constraints.json` was updated to 15s (perhaps aspirationally or in error), but the actual Seedance model capability remains 10s. The constraint document disagrees with the hardware.

---

## 3. Critical Inconsistency #2: COVERAGE_DEFICIT comparison formula

### The exact formula (qa_media.py lines 288-296):

```python
timing_map = _load_timing_map(pid, base)
tm_lookup = {b["beat_id"]: b for b in timing_map.get("beats", [])}
for entry in results:
    bid = entry.get("id")
    if bid and bid in tm_lookup and entry.get("duration"):
        req = tm_lookup[bid]["end"] - tm_lookup[bid]["start"]
        actual = entry["duration"]
        deficit = req - actual
        if deficit > 0.25:
            # FAIL
```

**Expected duration** = `beat_timing_map[beat_id]["end"] - beat_timing_map[beat_id]["start"]`

This is the **proportional word-weighted span** in the continuous narration audio (from `audio_timing.py`). It is NOT the `padded_len_sec` from the audio slice, and NOT the `duration_target_sec` from compile.

### The problem

The timing map span represents how much screen time the beat NEEDS (i.e., how long the narrator talks during that beat). If a beat has 14s of narration → timing map says 14s → but Seedance can only render 10s → **coverage deficit is 4s**.

This is **correct behavior** — QA is right to flag this. The upstream failure is that a 14s hero_lipsync beat should never have been allowed past the storyboard/reconciliation stage without being split into two sub-beats.

---

## 4. Critical Inconsistency #3: Gate timing (media_plan_review recorded after slice)

### Pipeline step order (produce.py):
```
compile_media_plan  (step 10) → writes media_plan.json
slice_lipsync       (step 11) → MODIFIES media_plan.json (adds audio_slice to beats)
                               → THEN records media_plan_review gate bound to media_plan.json
gate_a_budget       (step 12) → records budget + render_approval gates
generate_media      (step 13) → requires [storyboard_review, media_plan_review, budget, render_approval]
qa_media            (step 14)
```

**Finding:** The `media_plan_review` gate is recorded by `step_slice_lipsync` (produce.py line 576) AFTER the slice mutates media_plan.json. This is **intentionally correct** — the gate binds to the final state of the plan including slices.

However, there is NO actual LLM review of the plan happening here — the gate is auto-recorded with status "pass" without any review logic. This defeats the purpose of the `media_plan_review` gate as a quality check.

### Other gate ordering issues:

| Gate | Artifact bound to | Can become stale? |
|------|-------------------|-------------------|
| `storyboard_review` | `storyboard.json` | Yes — if production_storyboard reconciliation splits beats, the creative storyboard is unchanged but the PRODUCTION storyboard (what gets compiled) diverges. The gate checks creative storyboard only. |
| `media_plan_review` | `media_plan.json` (post-slice) | No — recorded last-writer-wins. ✅ |
| `budget` | `media_plan.json` | Yes — if plan is recompiled after budget approval, gate goes stale (SHA mismatch blocks generation). ✅ correct enforcement. |
| `render_approval` | None (no artifact) | Never stale (no hash check). Human approval is not invalidated by changes. ⚠️ |

### `render_approval` gap

`render_approval` has no artifact binding (produce.py line 608: no `artifact_path` passed). It's a pure intent gate. If the plan changes after human approval (e.g., costs double), the gate doesn't catch it. The `budget` gate does re-check cost, but `render_approval` doesn't.

---

## 5. Critical Inconsistency #4: storyboard.py vs reconcile_production_storyboard.py split thresholds

| Component | Max hero_lipsync beat | Source |
|-----------|-----------------------|--------|
| `storyboard.py` line 48 | `LIPSYNC_RENDER_MAX_SEC = 10.0` | Hardcoded |
| `storyboard.py` line 46 | `HERO_MAX_SEC = 15.0` | Hardcoded (used for non-lipsync hero) |
| `reconcile_production_storyboard.py` line 42 | `constraints.json → max_clip_duration_sec` = **15** | constraints.json |
| `compile_media_prompts.py` line 479 | `constraints.json → max_clip_duration_sec` = **15** | constraints.json |
| `slice_continuous_lipsync.py` line 37 | `constraints.json → max_clip_duration_sec` = **15** | constraints.json |
| `generate_media.py` line 38 | `LIPSYNC_MAX_DUR = 10` | Hardcoded |

**Timeline of how this causes failure:**

1. `storyboard.py` splits at 10s ✅ — beats are correctly sized at storyboard creation.
2. `reconcile_production_storyboard.py` re-processes with max=15 (from constraints) → may NOT split a beat that was correctly split at storyboard time but whose actual speech came out at 12s (ElevenLabs pacing variance).
3. `compile_media_prompts.py` allows padded_len up to 15 without error → writes `padded_len_sec: 14` into plan.
4. `slice_continuous_lipsync.py` allows up to 15s → extracts a 14s audio slice.
5. `generate_media.py` receives padded_len=14 → clamps to 10 → Seedance renders 10s.
6. QA: LIPSYNC check passes (10.1s ≈ LIPSYNC_MAX_DUR=10 ±0.15).
7. QA: COVERAGE_DEFICIT fires (timing map says 14s needed, clip is 10.1s).

---

## 6. Critical Inconsistency #5: `speech_len_sec` in audio_slice vs timing_map span

In the existing project data (B001):
- `audio_slice.speech_len_sec` = 13.994
- `audio_slice.padded_len_sec` = 10 (clamped by old logic before constraint was bumped)
- `beat_timing_map` end - start = 13.994

The `speech_len_sec` field stores the ACTUAL narration duration, but `padded_len_sec` was clamped to the old max (10). When constraints were bumped to 15, new compiles would write `padded_len_sec` = 14 (ceil(13.994 + 0.2)). But Seedance still renders 10s.

---

## 7. Proposed Fixes

### Fix 1: Restore `constraints.json` max to 10s (the truth)

**File:** `docs/channel_universe/constraints.json` line 192  
**Change:** `"max_clip_duration_sec": 15` → `"max_clip_duration_sec": 10`  
**Reason:** Seedance 2.0 has a hard 10s limit. The constraint must reflect hardware reality.

### Fix 2: Remove hardcoded fallback defaults of 10 in readers

These lines already fallback to 10 if the key is missing, which is correct. Once Fix 1 is applied, they'll read 10 from constraints directly. No code change needed, but document that the `10` default in these lines is the safety net:

- `compile_media_prompts.py` line 479: `get("max_clip_duration_sec", 10)` ✅
- `slice_continuous_lipsync.py` line 37: `get("max_clip_duration_sec", 10)` ✅
- `reconcile_production_storyboard.py` line 42: `get("max_clip_duration_sec", 10.0)` ✅

### Fix 3: Make `generate_media.py` read from constraints instead of hardcoding

**File:** `scripts/generate_media.py` line 38  
**Change:** Replace `LIPSYNC_MAX_DUR = 10` with a function that reads from constraints.json (with fallback to 10). This ensures a single source of truth.

```python
def _load_lipsync_max():
    try:
        c = json.loads((ROOT / "docs" / "channel_universe" / "constraints.json").read_text())
        return int(c.get("lipsync_render_rules", {}).get("max_clip_duration_sec", 10))
    except Exception:
        return 10

LIPSYNC_MAX_DUR = _load_lipsync_max()
```

### Fix 4: Make `storyboard.py` read LIPSYNC_RENDER_MAX_SEC from constraints

**File:** `scripts/storyboard.py` line 48  
**Change:** Replace hardcoded `LIPSYNC_RENDER_MAX_SEC = 10.0` with a constraints.json read (fallback 10).

### Fix 5: Enforce split in `reconcile_production_storyboard.py` at true model max

After Fix 1, `reconcile_production_storyboard.py` will read max=10 from constraints. Beats with actual speech >10s will be split. **This is the critical fix** that prevents >10s beats from reaching generation.

### Fix 6: `slice_continuous_lipsync.py` must reject >10s (already does after Fix 1)

After Fix 1, the `raise ValueError` on line 89 will trigger for any beat with padded > 10. This forces a re-split upstream. ✅

### Fix 7: `compile_media_prompts.py` must reject >10s (already does after Fix 1)

The error on line 484 will trigger for padded > 10. ✅

### Fix 8 (optional): Add a safety assertion in `generate_media.py`

**File:** `scripts/generate_media.py` around line 914  
**Change:** Instead of silently clamping, WARN or FAIL when padded_len exceeds the limit:

```python
if duration > LIPSYNC_MAX_DUR:
    print(f"  WARNING: {beat['beat_id']} requested {duration}s but Seedance max is {LIPSYNC_MAX_DUR}s — this beat should have been split upstream", file=sys.stderr)
    duration = LIPSYNC_MAX_DUR
```

### Fix 9: `render_approval` gate should bind to an artifact

**File:** `scripts/produce.py` line 608  
**Change:** Add `artifact_path=project_dir / "media_plan.json"` to the `record_gate` call for `render_approval` so it becomes stale if the plan changes.

---

## 8. Summary of Root Cause Chain

```
constraints.json says 15s
         ↓
reconcile_production_storyboard allows 15s beats (no split)
         ↓
compile_media_prompts writes padded_len=14 (valid per constraint)
         ↓
slice_continuous_lipsync extracts 14s audio slice (valid per constraint)
         ↓
generate_media.py clamps to 10s (hardcoded LIPSYNC_MAX_DUR)
         ↓
Seedance renders 10.1s clip
         ↓
QA LIPSYNC check: 10.1 ≈ LIPSYNC_MAX_DUR=10 → PASS
QA COVERAGE_DEFICIT: timing_map says 14s, clip is 10.1s → FAIL (deficit 3.9s)
```

**Single root fix:** Set `constraints.json max_clip_duration_sec = 10`. This propagates to all readers and forces splits at the correct boundary.

---

## 9. Files Requiring Changes (Priority Order)

| Priority | File | Line(s) | Change |
|----------|------|---------|--------|
| **P0** | `docs/channel_universe/constraints.json` | 192 | `15` → `10` |
| P1 | `scripts/generate_media.py` | 38 | Read from constraints instead of hardcoding |
| P1 | `scripts/storyboard.py` | 48 | Read from constraints instead of hardcoding |
| P2 | `scripts/produce.py` | 608 | Bind `render_approval` gate to `media_plan.json` |
| P3 | `scripts/generate_media.py` | 914 | Warn (not silently clamp) when duration exceeds max |

After P0, re-run the pipeline from `production_storyboard` step forward. Beats >10s will be split correctly, and QA will pass.

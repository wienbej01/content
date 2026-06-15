# Forensic Audit: `how_to_use_ai_to_better_organize_your_de_short`

**Date:** 2026-06-15T14:34 +08:00  
**Auditor:** Independent read-only forensic pass  
**Verdict:** THE DATA MODEL IS FUNDAMENTALLY INCONSISTENT ACROSS STAGES.  
The system has **three different definitions of what a "beat" is** depending on which stage you ask, and no stage reconciles them.

---

## Executive Summary

The pipeline has a **schema identity crisis**. Three expansions happen at different stages and each produces a different cardinality:

| Stage | Beat count | ID scheme | Notes |
|-------|-----------|-----------|-------|
| Storyboard | 13 | B001–B011 | Original creative beats |
| beat_timing_map | 13 | B001–B011 | 1:1 with storyboard — the narration timeline |
| production_storyboard | 14 | B001–B010, B011a, B011b | B011 split for lipsync duration cap |
| media_plan | **16** | B001–B011b, with **B003 × 3 slots** | Coverage-slot expansion + B011 split |
| clip_db | 16 | matches media_plan | DB is a faithful mirror of plan |
| QA report | 9 | only generated_video beats | local_graphic beats invisible |
| duration_reconciliation | 13 | B001–B011 (original IDs) | Collapses B011a/b back, ignores slots |

The manifest builder (`build_manifest.py`) iterates `media_plan.json` (16 rows) and checks `beat_id` uniqueness — but **media_plan has 3 rows with `beat_id=B003`** (coverage slots). The check was written assuming beat_id is a primary key. It isn't. The slot expansion violated that assumption.

---

## P0 — BLOCKS PRODUCTION (cannot ship without fixing)

### P0-1: `build_manifest.py` duplicate beat_id check is incompatible with coverage-slot expansion

**Evidence:**
```
media_plan.json beat_id counts: {'B003': 3}
ERROR: Duplicate beat_id in media_plan: B003
ERROR: Duplicate beat_id in media_plan: B003
```

**Root cause:** `_expand_coverage_slots()` (compile_media_prompts.py:659) creates 3 rows all with `beat_id=B003` but different `coverage_slot_id` (B003-s0, B003-s1, B003-s2). Each row has a unique `clip_id` and `output_path`.

But `build_manifest.py:108-112` does:
```python
for b in plan_beats:
    bid = b["beat_id"]
    if bid in seen_ids:
        errors.append(f"Duplicate beat_id in media_plan: {bid}")
    seen_ids.add(bid)
```

This assumes `beat_id` is the primary key of the plan. It isn't — the actual key is `(beat_id, coverage_slot_id)` or equivalently `clip_id`. **The manifest builder was never updated to handle multi-slot beats.**

**Fix needed:** `build_manifest.py` must either:
- (a) Use `clip_id` or `(beat_id, coverage_slot_id)` as the de-dup key, OR
- (b) Aggregate coverage slots back into a single manifest segment with sub-clips, OR
- (c) The timing_map lookup must handle one timing entry mapping to N plan rows.

### P0-2: `beat_timing_map.json` has 13 beats; media_plan has 16. ID mismatch makes lookup fail for B011a/B011b.

**Evidence:**
```
Timing map IDs:  ['B001','B002','B003','B003b','B004','B005','B005c','B006','B007','B008','B009','B010','B011']
Media plan IDs:  ['B001','B002','B003','B003b','B004','B005','B005c','B006','B007','B008','B009','B010','B011a','B011b']

In plan but NOT timing_map: ['B011a', 'B011b']
In timing_map but NOT plan: ['B011']
```

The production storyboard split `B011 → B011a + B011b` (18.9s exceeds lipsync 10s cap). The timing map was **never regenerated** to reflect this split. `build_manifest.py:121` would fail with "Beat B011a in media_plan but missing from timing_map" — but the B003 duplicate error fires first, so this bug has never surfaced yet.

**This means even if P0-1 is fixed, P0-2 immediately blocks.**

**Fix needed:** Either:
- (a) Regenerate beat_timing_map after production_storyboard splits (add split entries), OR
- (b) build_manifest must look up parent beat_id (`source_beat_id`) in timing_map and use `audio_start_sec`/`audio_end_sec` from the plan beat itself.

### P0-3: Coverage-slot timing vs timing_map — the timing_map gives B003 one 15.9s block, but plan has 3 × ~5.3s slots. Which is authoritative?

**Evidence:**
- Timing map: `B003 start=16.943 end=32.889 dur=15.946` (one block)
- Plan slots: `B003-s0: 16.943→22.258`, `B003-s1: 22.258→27.574`, `B003-s2: 27.574→32.889`

If manifest uses timing_map, it sees one 15.9s segment. If it uses plan slots, it sees three ~5.3s segments. These are fundamentally different assembly instructions. No code reconciles this.

**Fix needed:** The manifest must understand that a single timing-map beat can map to multiple plan slots, and assemble them sequentially.

---

## P1 — WRONG OUTPUT (would produce incorrect video if assembled)

### P1-1: B003 rerouted from `broll_environment` (kling3_0 generated video) to `local_graphic` (static PNG) — **creative regression**

**Evidence:**
- Storyboard: `shot_type=broll_environment`, `model=kling3_0`, `asset_type=generated_video`
- Media plan: `model=local_graphic`, `asset_type=local_graphic`
- Trigger: visual_brief contains banned terms `"writing"` and `"document"` (text_surface_policy)
- On disk: `B003_B003-s0.png`, `B003_B003-s1.png`, `B003_B003-s2.png` — **all identical** (22,351 bytes each)

**What this means for the viewer:** Instead of a 16-second cinematic b-roll of a clinician at a desk (slow push-in, documentary register), they get THREE IDENTICAL STATIC CARDS displayed for 5.3s each. This is a **massive quality degradation** — the flagship video's key credibility-establishing shot becomes a glorified PowerPoint slide.

**Is the reroute correct behavior?** NO. The text_surface_policy (line 177-179) reroutes ANY broll_* beat if the visual_brief mentions "writing" or "document" — but the visual_brief explicitly says `"all text out of focus"` and `"text_policy": "out_of_focus"`. The policy should respect the text_policy field. The word "writing" appears as an ACTION (pen in hand, writing a note), not as a request for readable text on screen. This is a false positive.

**The correct fix:** The text_surface_policy check should be narrowed to only trigger when text is meant to be **readable/legible** — i.e., when `text_policy != "out_of_focus"` and `text_policy != "none"`. Or better: check the `text_policy` field FIRST and skip the banned-term scan if text is explicitly marked non-readable.

### P1-2: B003b and B005c have 0.01s duration — phantom beats

**Evidence:**
```
Timing map: B003b start=32.889 end=32.899 dur=0.010
Timing map: B005c start=49.833 end=49.843 dur=0.010
```

These are `graphic_progressive` and `kinetic_text` beats that have narration_word_span but no audible speech assigned (10ms = effectively nothing). They exist in the storyboard as visual punctuation intended to display over a time period, but the TTS system assigned them ~0s because they have no dedicated narration text (their text displays as on-screen graphics while narration continues over adjacent beats).

**Impact:** Assembly will try to display these as 10ms clips — literally one frame at 24fps (actually less than one frame at 41.6ms/frame). They're functionally invisible.

### P1-3: Three identical B003 slot PNGs

**Evidence:**
```
B003_B003-s0.png — 22,351 bytes
B003_B003-s1.png — 22,351 bytes  
B003_B003-s2.png — 22,351 bytes
```

All three files have the exact same byte count (and likely identical content). The coverage-slot expansion created 3 slots with **identical prompts** (same positive_prompt), so `render_graphics` rendered the same card three times. This makes no visual sense — 16 seconds of the same static image.

---

## P1-4: B011a/B011b split exists in production & plan but timing_map has only B011

The split was correctly motivated (B011 is 18.9s, exceeds lipsync 10s cap), and the generated clips exist on disk (`B011a.mp4` at 12.3s, `B011b.mp4` at 6.6s). But the timing_map still only knows about `B011`.

This means:
- `duration_reconciliation.csv` correctly reports B011=18.9s by summing generated clips
- But build_manifest will fail to find B011a/B011b in the timing_map lookup

---

## P2 — INEFFICIENCY (wasted time/money)

### P2-1: QA only validates 9/16 plan beats

**Evidence:**
```
QA total results: 9
IDs in QA: ['B001','B002','B005','B006','B007','B008','B010','B011a','B011b']
In plan but NOT in QA: ['B003','B003b','B004','B005c','B009']
```

All 7 missing beats are `local_graphic`. The QA step skips them. This means local_graphic assets are **never validated** — no dimension check, no existence check. If render_graphics fails silently, nothing catches it before assembly.

### P2-2: No narration slice for B003 (16 seconds of narration with no lipsync coverage)

**Evidence:** `narration/slices/` has no `B003.mp3`. B003 is a b-roll beat so no slice is needed (audio strips on assembly). But because it was rerouted to local_graphic PNG, the assembly will display a static card for 16s while narration plays. The viewer experience is: stare at one static image for 16 seconds straight. Regardless of technical correctness, this is a creative disaster.

### P2-3: media_generation_log has 9 entries (all succeeded) — no waste detected

The generation log shows single-attempt success for all Higgsfield beats: B001, B002, B005, B006, B007, B008, B010, B011a, B011b. Total spend: ~$9.90 (all lipsync via seedance_2_0). No regenerations or failed attempts recorded.

The waste here is **human time** — hours of debugging pipeline failures, not API dollars.

### P2-4: Clip DB marks all 16 clips as "valid" but production is actually broken

The clip_db's `assert_all_valid()` gate passes because all rows have `status=valid`. But the system is broken at the manifest stage. The DB is faithfully recording garbage state (3 identical PNGs, phantom 10ms beats) and calling it valid. The DB has no semantic validation — it just tracks existence and status.

---

## Root Cause Analysis: The Beat Identity Crisis

The pipeline has **THREE different beat-expansion events** that happen at different stages, and no contract enforces a single authoritative ID scheme:

1. **TTS/Timing map** (stage 5): Creates the narration timeline using storyboard beat_ids. **This is the only stage that defines the temporal contract.** It has 13 beats.

2. **Production storyboard** (post-TTS): Splits beats that exceed lipsync duration caps. `B011 → B011a + B011b`. Creates NEW beat_ids. **Does NOT regenerate the timing map.** Now 14 beats.

3. **Compile media plan** (stage 4): Expands coverage slots for beats whose `audio_duration_sec` exceeds `model_max_duration_sec`. `B003 → 3 rows with same beat_id but different slot_id`. Now 16 rows.

Each expansion uses a different strategy:
- Split: new IDs (B011a, B011b) — **breaks timing_map lookup**
- Slots: same ID + slot qualifier — **breaks uniqueness assumption**

**No downstream stage handles both.** `build_manifest.py` was written for the simple 1:1 case. The data model implicitly assumes beat_id is a primary key throughout, but two separate expansion mechanisms violate that assumption in two different ways.

---

## The B003 Reroute Decision: Is It A Defect?

**YES.** The text_surface_policy is a blunt instrument that doesn't understand context:

- The visual_brief says: "writing a note with a pen" (physical action)
- The text_policy field is: `"out_of_focus"` (explicitly says text won't be readable)
- The reroute trigger: checks if banned term appears ANYWHERE in visual_brief string

The policy correctly identifies that AI video models hallucinate readable text. But it incorrectly treats ALL mentions of text-adjacent words as requests for readable text. A clinician "writing" is an ACTION, not a UI element. The brief explicitly suppresses readable text via `text_policy: out_of_focus`.

The correct behavior: a `broll_environment` shot with "writing" as an action should add `"no readable text, no legible writing"` to the negative_prompt (as it already does for hero shots), NOT reroute to a static graphic. The reroute should only trigger when `text_policy` is `"readable"` or `"prominent"`.

---

## Complete Beat Traceability Table

| Storyboard | Timing Map | Production | Plan | Clip DB | Disk | Issue |
|-----------|-----------|-----------|------|---------|------|-------|
| B001 | B001 | B001 | B001 | B001 | B001.mp4 ✓ | — |
| B002 | B002 | B002 | B002 | B002 | B002.mp4 ✓ | — |
| B003 | B003 (15.9s) | B003 | B003×3 (slots) | B003×3 | 3 identical PNGs | P0-1, P1-1, P1-3 |
| B003b | B003b (0.01s) | B003b | B003b | B003b | B003b.png ✓ | P1-2 phantom beat |
| B004 | B004 | B004 | B004 | B004 | B004.png ✓ | — |
| B005 | B005 | B005 | B005 | B005 | B005.mp4 ✓ | — |
| B005c | B005c (0.01s) | B005c | B005c | B005c | B005c.png ✓ | P1-2 phantom beat |
| B006 | B006 | B006 | B006 | B006 | B006.mp4 ✓ | — |
| B007 | B007 | B007 | B007 | B007 | B007.mp4 ✓ | — |
| B008 | B008 | B008 | B008 | B008 | B008.mp4 ✓ | — |
| B009 | B009 | B009 | B009 | B009 | B009.png ✓ | — |
| B010 | B010 | B010 | B010 | B010 | B010.mp4 ✓ | — |
| B011 | B011 (18.9s) | B011a+B011b | B011a+B011b | B011a+B011b | B011a.mp4+B011b.mp4 ✓ | P0-2: timing_map mismatch |

---

## Ordered Fix Sequence (recommendations only — no implementation)

1. **Fix text_surface_policy** (P1-1): Respect `text_policy` field. If `text_policy ∈ {out_of_focus, none}`, suppress term in negative_prompt instead of rerouting. Then regenerate B003 as actual kling3_0 video.

2. **Fix build_manifest.py** (P0-1): Use `(beat_id, coverage_slot_id or "whole")` as the uniqueness key. Handle multi-slot beats by assembling them sequentially within the parent timing window.

3. **Fix timing_map contract** (P0-2): Either regenerate beat_timing_map after production_storyboard splits, or have build_manifest use `audio_start_sec`/`audio_end_sec` from the plan beat directly instead of timing_map lookup.

4. **Address phantom 10ms beats** (P1-2): Either give them a minimum display duration (e.g., 2s) or merge them into the adjacent beat's overlay.

5. **Add local_graphic to QA** (P2-1): At minimum validate existence and dimensions.

---

## Conclusion

The pipeline does not have a consistent definition of "beat" across stages. The data model assumes beat_id is a primary key but two separate expansion mechanisms (coverage slots and lipsync splits) violate that in incompatible ways. The clip_db was added to provide a single authority but it mirrors the plan's expanded state — it doesn't reconcile with the timing_map's unexpanded state.

**The fundamental architectural problem:** beat expansion happens AFTER the timing_map is frozen. The timing_map is the temporal authority but doesn't know about post-hoc splits or slot expansions. The manifest builder needs both but can't reconcile them because the contract between compile → manifest was never specified.

This is not a bug to patch — it's a schema disagreement across three files that needs a single authoritative expansion point BEFORE any downstream consumption.

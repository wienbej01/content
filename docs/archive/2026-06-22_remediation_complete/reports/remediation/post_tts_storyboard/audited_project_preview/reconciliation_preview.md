# Reconciliation Preview — Audited Project

**Project:** `using_ai_to_help_memory_retention_short`  
**Date:** 2026-06-14  
**Mode:** Dry-run (no paid API calls)

---

## Summary

| Metric | Value |
|--------|-------|
| Input beats (creative) | 10 |
| Output beats (production) | 12 |
| Master audio duration | 146.599s |
| Split beats | 4 (from 2 parents: B006, B010) |
| Needs LLM repair | 3 (B001, B008, B009) |
| Multi-slot broll | 3 (B003, B005, B007) |

---

## Over-Limit Hero Beats (Seedance max 10s)

| Beat | Duration | Sentences | Resolution |
|------|----------|-----------|------------|
| **B001** | 13.994s | 1 | ❌ NEEDS_LLM_REPAIR — single sentence, no split point |
| **B006** | 10.626s | 2 | ✅ Split → B006a (2.657s) + B006b (7.969s) |
| **B008** | 23.889s | 3 | ❌ NEEDS_LLM_REPAIR — first sentence alone exceeds 10s |
| **B009** | 23.422s | 1 | ❌ NEEDS_LLM_REPAIR — single sentence, no split point |
| **B010** | 12.661s | 2 | ✅ Split → B010a (7.996s) + B010b (4.665s) |

---

## Broll Beats Needing Multiple Visual Assignments

| Beat | Duration | Model | Coverage Slots |
|------|----------|-------|----------------|
| **B003** | 18.894s | kling3_0 | 4 × ~4.72s |
| **B005** | 21.601s | kling3_0 | 4 × ~5.40s |
| **B007** | 11.087s | kling3_0 | 2 × ~5.54s |

---

## Required Graphics Preserved

| Beat | Layout | Text | Status |
|------|--------|------|--------|
| B001 | lower_third | COGNITIVE WITHDRAWAL | ✅ Preserved (on repair beat) |
| B003 | stat_callout | RCT 2025 — Barcaui / ScienceDirect | ✅ Preserved |
| B005 | key_line | DIGITAL AMNESIA | ✅ Preserved |
| B007 | lower_third | ACTIVE RETRIEVAL | ✅ Preserved |
| B008 | key_line | The variable: is your brain working... | ✅ Preserved (on repair beat) |
| B010 | side_by_side | W — Withdrawal \| D — Deposit | ✅ Inherited by B010a + B010b |

All 6 required graphics preserved.

---

## Validation Issues

The production storyboard has 3 validation errors (expected — repair beats intentionally exceed model limits):

1. `Beat B001: audio_duration_sec 13.994 exceeds model_max_duration_sec 10`
2. `Beat B008: audio_duration_sec 23.889 exceeds model_max_duration_sec 10`
3. `Beat B009: audio_duration_sec 23.422 exceeds model_max_duration_sec 10`

These will resolve once LLM repair rewrites the narration into multi-sentence form.

---

## Next Steps

1. LLM repair pass for B001, B008, B009 (rewrite narration into ≥2 sentences each)
2. Re-run reconciliation after repair
3. Validate resulting storyboard passes PST-01 clean

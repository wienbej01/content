# PTC-03 Audit Report — Reroute Unsplittable Hero to Continuous-VO B-Roll/Cutaway

**Date:** 2026-06-14  
**Auditor:** kiro-cli subagent (read-only)  
**Project:** using_ai_to_help_memory_retention_short  
**Verdict:** PASS

---

## Scope

PTC-03 addresses hero_lipsync beats whose audio duration exceeds the Seedance 2.0 model limit (10 s) but cannot be split at sentence boundaries (single-sentence beats). The fix reroutes these beats to `hero_cutaway` treatment with continuous-voiceover b-roll coverage slots, preserving narration byte-for-byte.

---

## Affected Beats

| Beat | Audio Duration | Sentences | Resolution |
|------|---------------|-----------|------------|
| B001 | 13.994 s | 1 | Rerouted → hero_cutaway (3 slots × 4.665 s) |
| B008 | 18.429 s | 3 | Split at measured silence boundaries → 3 children (B008a/b/c) |
| B009 | 23.422 s | 1 | Rerouted → hero_cutaway (4 slots × 5.856 s) |

---

## Implementation Review

### `reroute_unsplittable_hero()` (line 136, reconcile_production_storyboard.py)

- Transforms single-sentence over-limit hero beats to `hero_cutaway`.
- Generates contiguous coverage slots each ≤ `broll_slot_max` (6.0 s).
- Sets `audio_policy=strip`, `needs_repair=False`, `model_max_duration_sec=None`.
- Preserves `narration_text` verbatim — no mutation.
- Attaches `reroute` provenance dict recording from/to/reason.

### Reconcile integration (lines 317–337, 387–407)

Two call sites:
1. **Single-sentence branch** (line 317): when `len(sentences) < 2`.
2. **No legal split points branch** (line 387): when `_select_split_points` returns None.

Both paths: construct prod_beat with `needs_repair=True`, then immediately call `reroute_unsplittable_hero()` which clears it to `False`.

### Constraints loading

`_load_constraints()` reads `reroute_policy.unsplittable_hero_target` from `constraints.json`, defaulting to `"hero_cutaway"`.

---

## Findings

1. **B001/B008/B009 all resolved** — zero `needs_repair` beats in reconciled output.
2. **Narration preserved exactly** — B001 (114 chars), B009 (183 chars) exact string match; B008 3-child concatenation matches original (199 chars).
3. **Coverage slots within limit** — B001: 3 × 4.665 s ≤ 6.0 s ✓; B009: 4 × 5.856 s ≤ 6.0 s ✓.
4. **Contiguous coverage** — slots span full beat interval with zero gap.
5. **No issues reported** — reconcile returned empty issues list.
6. **Test suite** — 7/7 reroute tests pass; 449/449 full suite pass.

---

## Risk Assessment

- **Low risk:** Rerouted beats produce VO-covered b-roll instead of lipsync — visual downgrade is acceptable per constraints (hero_cutaway still counts toward hero shot-mix band).
- **No narration mutation:** Audio pipeline unchanged; TTS output preserved verbatim.
- **Gate integrity:** Rerouted beats carry `audio_policy=strip` — assembly will not overlay narration on these clips (correct behavior for non-lipsync hero).

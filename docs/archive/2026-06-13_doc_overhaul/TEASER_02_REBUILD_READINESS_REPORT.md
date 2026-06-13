# Teaser 02 Rebuild Readiness Report

**Date:** 2026-06-09
**Project:** `james_growth_system_teaser_02`
**Verdict:** READY FOR ONE-SCENE GENERATION TEST ONLY

---

## 1. Verdict

**READY FOR ONE-SCENE GENERATION TEST ONLY**

The dry-run pipeline works end-to-end. A single controlled clip can be generated safely (as proved in M3-A). Full teaser regeneration is blocked by four issues, all fixable in 1–2 sprints before spending generation credits.

---

## 2. What the System Can Do Now

| Capability | Status | Command |
|---|---|---|
| Generate storyboard from script | ✅ | `python3 scripts/storyboard.py script.json --output storyboard.json` |
| Validate storyboard (rule-based) | ✅ | `python3 scripts/review_storyboard.py storyboard.json` |
| Compile universe-constrained prompt plan | ✅ | `python3 scripts/compile_media_prompts.py storyboard.json --output plan.json` |
| Generate one b-roll test clip (wan2_7) | ✅ | `python3 scripts/generate_media.py script.json` (M3-A proved) |
| Generate ElevenLabs narration | ✅ | `python3 scripts/tts.py script.json` |
| Assemble to 16:9 + 9:16 | ✅ | `python3 scripts/assemble.py manifest.json` |
| Use existing teaser_01 narration as-is | ✅ | Narration in `Videos/Projects/trailer_demo/narration/` |

---

## 3. What the System Cannot Do Yet

| Missing capability | Impact | Milestone |
|---|---|---|
| No approved reference images | A-roll/lipsync without reference = inconsistent James | M4.3 reference gen |
| No studio/library reference images | Each studio scene invents the room | M4.3 reference gen |
| No continuous narration assembly | Segment gaps would be audible in final | M7 |
| No audio timing map | Cannot align beats to narration precisely | M7.1 |
| No visual media QA | Cannot programmatically verify generated clips | M9.1 |
| Storyboard 50% James presence (below 60% teaser minimum) | QA warning; storyboard should be improved before full gen | Manual edit |

---

## 4. Blockers Before Full Teaser Regeneration

These must all be resolved before spending Higgsfield credits on all 8 scenes:

### BLOCKER 1 — No approved James reference images
- `assets/reference/james/` is empty
- Every Higgsfield A-roll session without a reference generates a different person
- **Fix:** Generate `JAMES_FRONT_DESK_001` + `JAMES_THREE_QUARTER_STUDY_001` first (1 credit each, static image generation). These seed all other A-roll prompts.

### BLOCKER 2 — No approved studio/library reference images
- `assets/reference/studio_library/` is empty
- Each studio-scene clip invents a different room (this was the root cause of teaser_01 visual incoherence)
- **Fix:** Generate `STUDIO_LIBRARY_WIDE_001` first (1 credit). Use it as the spatial anchor for all 6 other studio angles.

### BLOCKER 3 — Storyboard James-presence below teaser minimum (50%, needs ≥60%)
- Current storyboard has 4/8 beats with James — 50% by beat count
- Teaser minimum is 60% (4.8 → needs ≥5 James-present beats)
- **Fix:** Upgrade one B-roll beat (`beat_003_pattern` or `beat_005_give_back`) to `A_ROLL_CHARACTER_PRESENT_VOICEOVER`. Costs nothing to fix in the JSON.

### BLOCKER 4 — No continuous narration assembly support (M7)
- Full teaser with 8 segments will have 7 audible inter-segment gaps
- Teaser_01 had this problem; teaser_02 must not
- **Fix:** Either implement M7.1 continuous narration (recommended), or accept segment mode for teaser_02 with explicit approval and gap-concat tuning.
- **Interim acceptable mitigation:** reduce `gap_seconds` in the manifest and use carefully timed narration so gaps are imperceptible. Mark this as an explicit compromise if M7 isn't done.

---

## 5. Non-Blocking Gaps (Proceed Anyway for One-Scene Test)

| Gap | Why non-blocking | What to do |
|---|---|---|
| No audio timing map | One-scene test doesn't need timing across beats | Skip M7.1 for the test |
| No visual media QA script | Manual human review (Gate B via Telegram) covers this | Proceed with human QC |
| Storyboard scene-evolution warning (2 locations) | Warning, not fail; acceptable for a test | Park |
| Cat reference images missing | Cat is optional; don't include cat beats in test | Omit |
| No LLM reviewer (M6) | Rule-based review passes; Sonnet review deferred | Proceed |

---

## 6. Recommended Sprint Sequence Before Full Generation

| Sprint | Objective | Blocks full gen? | Cost |
|---|---|---|---|
| **Ref-A** | Generate `STUDIO_LIBRARY_WIDE_001` (one static image) | ✅ Yes | ~1 credit |
| **Ref-B** | Generate `JAMES_FRONT_DESK_001` + `JAMES_THREE_QUARTER_STUDY_001` | ✅ Yes | ~2 credits |
| **SB-fix** | Update storyboard to ≥60% James presence | ✅ Yes | 0 credits |
| **M7-interim** | Reduce gap_seconds + verify narration continuity OR implement M7 | ✅ Yes | 0 credits |
| **One-scene test** | Generate one B-roll clip (beat_002) into temp path | Proves b-roll works | ~8 credits |
| **One-A-roll test** | Generate one A-roll lipsync (beat_001_hook) into temp path | Proves James consistency | ~22 credits |
| **Human approval** | Review both test clips against reference | Gate before full run | 0 credits |
| **Full teaser_02** | All 8 clips → assemble → Gate B → Telegram | Only after approval | ~100 credits |

---

## 7. Dry-Run Commands Already Available (safe to run, no credits)

```bash
# Generate the teaser storyboard
python3 scripts/storyboard.py scripts/generated/james_growth_system_teaser_01.json \
  --output scripts/generated/james_growth_system_teaser_01_storyboard.json

# Review the storyboard
python3 scripts/review_storyboard.py \
  scripts/generated/james_growth_system_teaser_01_storyboard.json

# Compile constrained media prompts
python3 scripts/compile_media_prompts.py \
  scripts/generated/james_growth_system_teaser_01_storyboard.json \
  --output scripts/generated/james_growth_system_teaser_01_prompt_plan.json

# Inspect the compiled prompts
cat scripts/generated/james_growth_system_teaser_01_prompt_plan.json | python3 -m json.tool

# Validate TTS script without spending credits
python3 scripts/tts.py scripts/generated/james_growth_system_teaser_01.json --validate-only
```

---

## 8. Commands That Must NOT Be Run Until Blockers Are Resolved

```bash
# DO NOT run until BLOCKER 1+2 (reference images) are resolved:
python3 scripts/generate_media.py scripts/generated/james_growth_system_teaser_02.json

# DO NOT run --assemble until narration continuity issue (BLOCKER 4) is addressed:
python3 scripts/tts.py scripts/generated/james_growth_system_teaser_02.json --assemble
```

---

## 9. Acceptance Criteria Before Spending Higgsfield Credits (Full Gen)

| Criterion | Current state |
|---|---|
| `STUDIO_LIBRARY_WIDE_001` reference image exists and human-approved | ❌ |
| `JAMES_FRONT_DESK_001` reference image exists and human-approved | ❌ |
| Storyboard James-presence ≥60% | ❌ (50%) |
| Storyboard passes review_storyboard.py with score ≥4 | ❌ (3/5) |
| One-scene b-roll test clip approved by human | ❌ (not run yet) |
| One-scene A-roll test clip (James) approved by human | ❌ (not run yet) |
| Narration continuity plan in place (M7 or approved interim) | ❌ |
| New project_id `james_growth_system_teaser_02` confirmed | ❌ (exists as concept) |
| `scripts/generated/james_growth_system_teaser_01` outputs not overwritten | ✅ |

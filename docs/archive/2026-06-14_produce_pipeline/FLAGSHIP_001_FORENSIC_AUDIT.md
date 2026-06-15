# Forensic Audit — Flagship_001 End-to-End Pipeline

**Author:** Principal AI Video Engineer
**Date:** 2026-06-13
**Scope:** Full pipeline forensic. Confirm root cause of the "garbage script" symptom; identify every quality-killing implementation error end-to-end; analyze how the 9 remediation tickets affect the full flow.
**Method:** Direct inspection of the live flagship_001 artifacts (script, storyboard, media_plan, manifest, narration, gates). No code changed.

---

## 0. VERDICT ON THE "GARBAGE SCRIPT" (the question you asked first)

**It is NOT a scripting error, and NOT a TTS/voice error. The script and narration are clean. The audible "stutter" is an ASSEMBLY-LAYER double-audio artifact.**

Evidence chain:

1. **Source script is clean.** In `scripts/generated/flagship_001_learn_half_time.json`, the phrase *"Read it. Sketch it. Explain it aloud."* appears **exactly once** (segment `005_layered_encoding`). It is intentional, correct copy. There is no repetition loop in the script.

2. **TTS is per-segment and clean.** `tts.py` synthesizes ONE ElevenLabs file per segment from `seg["text"]` (line 484). The narration audio for segment 005 says the sentence once. No LLM loop, no doubled audio at generation.

3. **The doubling is structural, in assembly.** The storyboard maps the *same* sentence to BOTH:
   - `B025` (graphic_title_card) `narration_text` = *"The first principle is Layered Encoding…"* (the full first sentence), AND
   - `B026` (hero_lipsync) `narration_text` = *"Read it. Sketch it. Explain it aloud. …"*

   In the **mixed-shots assembly path** (`assemble.py`), the hero lipsync shot B026 plays its **baked Seedance audio** ("Read it. Sketch it…") while the **segment narration master** ALSO plays the same words across that span. The current `manifest_v2.json` has **no `narration_mode`**, so it uses the per-segment shots-bed path that overlays segment narration AND keeps lipsync baked audio → **the same words are heard twice, offset = the "stutter."**

**Conclusion:** The post-mortem mis-attributed the symptom to an LLM generation loop (§2A). The actual root cause is the audio-assembly architecture — exactly what remediation tickets **R2 (continuous master audio)** and the audio decision in §0 of the remediation plan address. Fixing the LLM (R4) is still worth doing as a guard, but **it would not have fixed this specific stutter**, because the stutter was never in the script.

> This is the single most important finding: the post-mortem's §2A diagnosis is wrong. The stutter is a double-audio bug, not a script bug. R2 fixes it; R4 does not.

---

## 1. Confirmed quality-killing defects (forensic findings)

### F1 — Double-audio stutter (CRITICAL, root-caused above)
- **Where:** `assemble.py` mixed-shots path; `manifest_v2.json` missing `narration_mode`.
- **Mechanism:** lipsync baked audio + segment narration master both play the overlapping span.
- **Fix:** R2 (continuous master only; mute all clips). Until R2, ANY segment with a lipsync beat double-plays.

### F2 — Duplicated `[beat focus]` prompt tag (HIGH — degrades every generated clip)
- **Where:** `compile_media_prompts.py` `_compose_positive()`.
- **Evidence:** **81 of 96 beats** have the beat-focus tag emitted TWICE, e.g. `[beat focus: Sketch Explain aloud modality] [beat focus: Sketch Explain aloud modality]`.
- **Impact:** doubles a noisy, keyword-salad fragment in the image/video prompt. Seedance/Kling weight repeated tokens — this amplifies a low-quality instruction and crowds out the real scene description. A likely contributor to the generic/AI-slop visuals.
- **Not in the post-mortem.** New finding. Single-line fix (dedupe foci) — but it means re-compiling and re-rendering affected beats.

### F3 — No continuous timing map produced (HIGH — blocks the correct audio fix)
- **Where:** `tts.py` continuous path; `narration/timing_map.json` is ABSENT.
- **Impact:** the continuous-master assembly (R2) needs beat→[start,end] timestamps to snap muted clips to the master. Without it, R2 cannot place clips accurately. R2 depends on R-timing-map being generated.
- **Implication for plan:** R2 has a hidden prerequisite — `tts.py` must emit a real timing map (silence-snapped) for the master file. This should be an explicit sub-ticket.

### F4 — Long-speech lipsync desync (HIGH, already known)
- **Where:** B047 (15s), B086 (13s), B090 (14s) clamped to 10s render.
- **Mechanism:** Seedance compresses the speech or truncates; mouth drifts from the 15s master span.
- **Fix:** R3 (split at compile, never clamp). Confirmed still present in the live plan (padded_len 11–16 on these beats).

### F5 — Blank screens / frozen lipsync undetected (CRITICAL safety gap)
- **Where:** `qa_media.py` has NO perceptual checks (only dimensions, audio-stream, duration, provenance, crop-safety).
- **Impact:** the 2.5 min of blank screens and frozen hosts passed Gate 8. QA verified the files *existed and had the right shape*, never that they *contained moving, non-blank video*.
- **Fix:** R1 (blank + freeze detection). This is the net that should have stopped the build.

### F6 — Title-card + hero narrate the SAME sentence (MEDIUM — pacing/redundancy)
- **Where:** storyboard beat mapping: B025 title card narration_text overlaps B026 hero.
- **Impact:** even with R2 (single master), the *visual* sequence shows a title card for a sentence, then immediately a talking head re-stating adjacent words — redundant pacing. This is a storyboard segmentation issue, not just audio.
- **Fix:** storyboard beat-boundary logic should not assign the same narration span to a title card AND the following hero. Relates to R7 (structural) but is a distinct segmentation bug worth its own check.

### F7 — Text-surface b-roll gibberish (MEDIUM, known)
- **Where:** `constraints.json` negatives don't forbid writing/reading; `generate_media.py` only *flags* text-surface risk, doesn't reject.
- **Fix:** R5.

### F8 — Wardrobe drift / host hallucination (MEDIUM, partially mitigated)
- **Where:** reference rotation now locks to `navy_sweater_library` (post the G14 fix), but b-roll beats with `james_presence` can still hallucinate a different person because b-roll isn't reference-locked the way hero beats are.
- **Fix:** R8 + a check that any james-present b-roll also cites a canonical reference.

### F9 — Manifest is hand-built and drifts from the plan (PROCESS risk)
- **Where:** `manifest_v2.json` was generated by an ad-hoc script, separate from `compile_media_prompts.py`. It lacks `narration_mode`, timing map refs, and can fall out of sync with the media plan.
- **Impact:** the assembly input is not a first-class, gated artifact. The double-audio bug (F1) is partly because the manifest wasn't built for continuous mode.
- **Fix:** the manifest should be EMITTED by the compiler (or a dedicated `build_manifest.py`) as a gated artifact derived from the media_plan, with `narration_mode: continuous_voiceover` baked in. Recommend a new ticket **R10**.

---

## 2. How the remediation tickets impact the end-to-end flow

| Ticket | Stage affected | Net effect on flow | New dependency exposed |
|--------|---------------|--------------------|------------------------|
| **R2** continuous master audio | Assembly | Eliminates F1 (stutter) + F4 audio shift. Changes assembly from "stitch per-shot audio" to "one master + muted snapped video". | Requires **timing map (F3)** + manifest with `narration_mode` (**F9/R10**). |
| **R3** split long beats | Storyboard + compile | Eliminates F4 desync. Increases beat count (more, shorter hero clips) → slightly more render jobs but each ≤10s. Interacts with reference rotation (more angles needed). | More hero beats → reference set must have enough angles (navy set has 4 ✓). |
| **R1** perceptual QA | QA (G8) | Adds the missing safety net (F5). Will RETROACTIVELY fail much of the current flagship_001 render → forces re-gen of blank/frozen clips. | Needs thresholds in constraints.json; risk of false-positives on intentionally static graphics (must scope to generated_video only). |
| **R4** stutter pre-filter | Script review (G1) | Guards against a *future* LLM loop. Does NOT fix F1 (the current stutter is not a script loop). Low cost, worth it. | None. |
| **R5** text negatives | Compile/generate | Fixes F7. Tightens b-roll prompts → fewer gibberish-text clips. | May over-constrain (e.g. a legitimate "notebook" b-roll); needs careful wording. |
| **R6** anti-loop LLM | Script gen | Reduces F-future loops. kiro-cli may not expose sampling params → leans on R4 + prompt directive. | Limited lever; R4 is the real guard. |
| **R7** shot-mix failsafe | Storyboard | Fixes "0% graphics" / monotony. Injects graphic/kinetic beats. Interacts with F6 (segmentation). | Could collide with R3 beat-count growth; bands must be recomputed after both. |
| **R8** reference lock | Compile + QA | Mitigates F8. Provenance-checks references. | Wardrobe-from-pixels still needs human canary. |
| **R9** short mode | Whole pipeline | Cheap validation vehicle. Exercises every fix at ~$3–5. | A short has few beats → may not exercise R3 (long-beat split) unless the short deliberately includes a >10s beat. **Recommend the validation short include one long-speech beat to test R3.** |

### 2.1 Critical interaction the plan under-specified
- **R2 ⇄ F3 ⇄ F9 are a single chain.** Continuous-master assembly is impossible without (a) a real timing map from `tts.py` and (b) a manifest that declares continuous mode. The remediation plan listed R2 as one ticket; the audit shows it is actually **three coupled changes**: timing-map generation (new R-timing), manifest-as-gated-artifact (R10), and the assembler rewrite (R2). Sequencing R2 before those two will fail.
- **R1 will fail the existing flagship render.** Once perceptual QA lands, the current 59-clip flagship_001 render will show its blank/frozen clips. Expect a re-generation wave. This is correct (it's the net working) but is real additional spend — another argument for proving on the **short** first.
- **R3 + R7 both change beat count.** Splitting long beats (R3) and injecting graphics (R7) both grow the beat list. The shot-mix bands (% of runtime) must be recomputed AFTER both run, or the storyboard review (G2) may report stale percentages. The order must be: route → R3 split → R7 inject → recompute mix → review.

### 2.2 What the plan got right
- Adopting §2C (continuous master) as the audio architecture is correct and is the actual fix for the headline symptom.
- Splitting long beats instead of clamping (R3) is the correct desync fix.
- Proving on a 3-min short before flagship spend is exactly right given the defect density found here.

---

## 3. Revised ticket additions (from this audit)

| New ticket | Why |
|-----------|-----|
| **R-TIMING** `tts.py` — emit silence-snapped `timing_map.json` for the continuous master (beat→[start,end]). | Hidden prerequisite for R2 (F3). |
| **R10** Manifest as a gated, compiler-emitted artifact with `narration_mode: continuous_voiceover`. | F9 — stop hand-building the assembly input. |
| **R11** `compile_media_prompts.py` — dedupe `[beat focus]` tag (F2). | 81/96 beats carry a doubled noisy prompt fragment degrading every clip. |
| **R12** Storyboard — forbid the same narration span on a title-card AND the following hero (F6). | Redundant pacing even after the audio fix. |
| **R13** `generate_media.py` — text-surface b-roll = hard reject (not flag) in source scope (F7 enforcement half). | Pairs with R5. |

---

## 4. Severity-ranked summary

| # | Defect | Severity | Fixed by | In original plan? |
|---|--------|----------|----------|-------------------|
| F1 | Double-audio stutter (the "garbage script") | CRITICAL | R2 (+R-TIMING, R10) | Partially (R2 listed, deps missing) |
| F5 | Blank/frozen clips pass QA | CRITICAL | R1 | Yes |
| F2 | Duplicated `[beat focus]` prompt on 81/96 beats | HIGH | R11 | **No (new)** |
| F3 | No timing map (blocks R2) | HIGH | R-TIMING | **No (new)** |
| F4 | Long-beat lipsync desync | HIGH | R3 | Yes |
| F9 | Manifest hand-built, not gated | HIGH (process) | R10 | **No (new)** |
| F6 | Title-card + hero same sentence | MEDIUM | R12 | **No (new)** |
| F7 | Text-surface gibberish b-roll | MEDIUM | R5 + R13 | Yes (R5) |
| F8 | Wardrobe/host drift on b-roll | MEDIUM | R8 | Yes |

**Bottom line:** The headline failure ("garbage script") is a double-audio assembly bug, not a script or voice/render bug. The remediation plan's audio direction is right but under-scoped — it needs the timing-map and gated-manifest prerequisites (R-TIMING, R10) or R2 cannot land. Two additional high-severity defects (F2 prompt duplication on 81/96 beats; F9 ungated manifest) were missed by the post-mortem entirely and materially hurt visual quality. Prove everything on the cheap 3-min short — and make that short include one >10s speech beat so R3 is actually exercised before flagship spend.

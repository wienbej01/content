# M4 Opus Review Report

**Reviewer:** Opus-class review sprint
**Date:** 2026-06-09
**Scope:** M4.1 Universe Bible + M4.2 Technical Bible + constraints.json + planning docs
**Companion:** `M4_OPUS_REVIEW_FIXLIST.md`

---

## 1. Executive Verdict

**READY AFTER MINOR FIXES**

The M4 creative-control layer is substantively strong. There are no fundamental contradictions, no missing core content, and the bad-teaser failure modes are well covered. However, **three P0 definitional gaps** would cause a cheaper implementation model to either build the wrong validation logic or stall on ambiguity when scripting M5. All three are small, surgical clarifications — not rewrites. Fix them (one Sonnet fixlist sprint), then begin M5.

The bibles successfully solve the original problem: they prevent each AI-generated scene from inventing its own world. The remaining work is tightening enforcement hooks so a coding model can mechanize the rules without interpretation.

---

## 2. Files Inspected

All present and read:
- `docs/channel_universe/`: README, UNIVERSE_BIBLE, JAMES_CHARACTER_BIBLE, JAMES_RECORDING_STUDIO_LIBRARY, BACKGROUND_CAT_BIBLE, PEOPLE_AND_EXTRAS_BIBLE, FORBIDDEN_PATTERNS, REFERENCE_ASSET_MANIFEST, TECHNICAL_BIBLE, PROMPT_RULES, QA_RUBRIC, constraints.json (12 files)
- `docs/plans/`: M4_M10_CREATIVE_CONTROL_WORKPLAN, M4_M10_SCHEMA_DESIGN, M4_M10_IMPLEMENTATION_PROMPTS, M4_M10_ACCEPTANCE_TESTS, LLM_KIRO_CLI_INVOCATION_PLAN
- `brand/BRAND_SPEC.md`

**Missing / not yet created:**
- `assets/reference/` directory does **not exist**. Sprint M4.3 (reference folders + `.gitkeep` + seed mapping) was never run. The REFERENCE_ASSET_MANIFEST documents paths and seed assets that have no physical files yet. (See §12 — P1, not P0: M5 needs asset *IDs*, which exist; it does not need the image *files*, which are needed at M8/M10 generation.)

---

## 3. Validation Command Results

| Command | Result |
|---|---|
| `find docs/channel_universe -maxdepth 1 -type f` | 12 files present |
| `python3 -m json.tool constraints.json` | **VALID** |
| `grep A_ROLL` | scene types consistent across constraints.json, schema design, workplan, prompt rules |
| `grep continuous_voiceover` | present in TECHNICAL_BIBLE, QA_RUBRIC, constraints.json — consistent |
| `grep STUDIO_LIBRARY_WIDE_001` | present in manifest, constraints, forbidden patterns, studio bible, technical bible |
| `ls assets/reference/` | **does not exist** |

---

## 4. Contradictions Found

| # | File/Section | Issue | Why it matters | Recommended fix | Blocking? |
|---|---|---|---|---|---|
| C1 | constraints.json `required_prompt_fields` vs PROMPT_RULES §3 vs b-roll reality | `camera_angle_id` is listed as required for **every** prompt, but only the 7 studio shots have angle IDs. B-roll and exterior shots have no angle ID. | A prompt-compiler validator that requires `camera_angle_id` on all entries will reject every b-roll prompt, or implementers will invent fake IDs. | Make `camera_angle_id` required only when `location_id` is the studio/library; for b-roll use the free-text `camera_movement` field and allow `camera_angle_id: null`. Update constraints.json + PROMPT_RULES. | **Yes (P0)** |
| C2 | FORBIDDEN_PATTERNS §1 ("`absent` on >60% of beats") vs TECHNICAL_BIBLE §7 ("60–75% James presence") | Two different presence thresholds and two different measurement units (beat-count vs implied duration). | The single most important fail condition (no James) depends on an inconsistent, unit-ambiguous threshold. M5.2 validator cannot be written deterministically. | Pick ONE measurement (recommend: % of beats with `james_presence != absent`) and ONE set of thresholds. Reconcile FORBIDDEN_PATTERNS, TECHNICAL_BIBLE, QA_RUBRIC, constraints. | **Yes (P0)** |
| C3 | "host-led episode" — used in 8+ places, defined nowhere | The hard-fail "no James in host-led episode" hinges on an undefined term. | A coding model cannot determine which episodes are "host-led," so it cannot apply the most important rule. | Add an explicit definition: "All episodes are host-led by default. An episode is non-host-led only if the storyboard sets `allow_all_broll: true`." Put it in UNIVERSE_BIBLE + constraints.json. | **Yes (P0)** |
| C4 | TECHNICAL_BIBLE §10 ("music ducks to -26 to -30 dB") vs constraints.json (`music_bed_db_target: -26`, `music_bed_db_max: -22`) | Prose says duck to -26/-30; JSON says target -26 / max -22. The "-30" and the "-22 max" are not aligned. | Minor, but a QA script reading constraints.json will use -22/-26 while a human reading prose expects -26/-30. | Align the numbers. Recommend: target -28, acceptable range -22 (loudest) to -32 (quietest). Update both. | No (P1) |

**No contradictions found** between: Universe Bible ↔ BRAND_SPEC (clean extension), James rules ↔ A-roll rules, studio rules ↔ camera rules, cat rules ↔ studio rules, futuristic bans (consistent everywhere), continuous_voiceover policy (consistent).

---

## 5. Vague or Unenforceable Rules

The Technical Bible already operationalizes most subjective terms. Remaining gaps are about *where* the operational definition lives (prose vs machine-readable).

| Phrase/Rule | Why vague | Enforcement hook needed | Recommended edit |
|---|---|---|---|
| "premium," "elegant," "restrained cinematic" | Subjective adjectives | Already defined operationally in TECHNICAL_BIBLE §2 (shallow DoF, consistent color temp, no clipping). But these aren't in constraints.json, so only a Sonnet reviewer (not a script) can apply them. | Acceptable for M5 (storyboard is Sonnet-reviewed). Add a `quality_markers` block to constraints.json in M4.2-fix for the future media QA script. P1. |
| "grounded" | Subjective | Defined in TECHNICAL_BIBLE §2 (light has a source; physically plausible). Good operational definition. | No change needed; it's enforceable by the creative QA reviewer. |
| "meaningful share" of James presence (TECHNICAL_BIBLE §7) | Not a number | See C2 — needs the % threshold + measurement unit. | Covered by C2 fix. P0. |
| "occasional" cat (1 in 3–4 episodes) | Cross-episode rule with no tracking mechanism | There is no per-channel state tracking episodes. | Acknowledge this is a human-judgment rule for now (no DB by design). Note in QA_RUBRIC that cat frequency is a human-review item, not an automated check. P2. |
| "scene evolution" (use 3–4 angles) | "Meaningful" progress is subjective | Partially enforceable: count distinct `camera_angle_id`/`location_id` per storyboard. | Add a measurable hook: storyboard QA warns if `distinct_locations_or_angles < 3`. P1. |

---

## 6. Missing Enforcement Hooks

| # | Rule (exists in prose) | Missing from | Recommended destination | Blocking? |
|---|---|---|---|---|
| H1 | "host-led" definition | Everywhere (undefined) | UNIVERSE_BIBLE + constraints.json (`host_led_default: true`, `non_host_led_requires: allow_all_broll`) | **Yes (P0)** — same as C3 |
| H2 | James-presence measurement method + threshold | constraints.json has thresholds but no measurement unit | constraints.json `a_roll_rules.presence_measured_by: "beat_count"` | **Yes (P0)** — same as C2 |
| H3 | camera_angle_id applies only to studio | constraints.json marks it universally required | constraints.json: split into `studio_required_fields` vs `broll_required_fields` | **Yes (P0)** — same as C1 |
| H4 | "scene evolution: 3–4 distinct angles" | No measurable threshold in constraints/QA | constraints.json `storyboard_rules.min_distinct_angles_or_locations: 3` | No (P1) |
| H5 | Reference asset required for A-roll/studio/cat | constraints.json `a_roll_required_fields: ["reference_assets"]` exists for A-roll, but no equivalent for cat shots | constraints.json: add `cat_requires_reference: true` | No (P1) |
| H6 | Quality markers (DoF, color-temp consistency, no clipping) | Only in TECHNICAL_BIBLE prose | constraints.json `quality_markers` block (for future media QA) | No (P1) |
| H7 | Episode-type → ratio band lookup | TECHNICAL_BIBLE table exists; constraints has per-type pct but no `episode_type` enum | constraints.json: add `episode_types: [teaser, explainer, trailer, short]` enum + storyboard `episode_type` field | No (P1) — needed for M5 but storyboard schema can carry it |

**Well-covered hooks (no action):** audio strip for generated_tts (code + constraints + QA), default negative block (constraints + PROMPT_RULES), automatic-fail list (constraints + QA + TECHNICAL_BIBLE all aligned), studio angle IDs (manifest + constraints + studio bible).

---

## 7. Implementer Ambiguity

| # | Ambiguity | How a cheaper model might misread it | Recommended clarification |
|---|---|---|---|
| A1 | `A_ROLL_TALKING_HEAD` vs `A_ROLL_CHARACTER_PRESENT_VOICEOVER` | Might treat both as "James talks to camera" and generate lipsync for both, wasting Seedance credits on voiceover scenes that don't need lipsync. | Add a one-line distinction to PROMPT_RULES: TALKING_HEAD = direct address + lipsync from final narration; CHARACTER_PRESENT_VOICEOVER = James in frame, NOT addressing camera, audio_policy=strip, no lipsync. |
| A2 | Storyboard beat field `camera`/`movement` vs prompt field `camera_angle_id`/`camera_movement` | Might assume they are the same field and fail to map storyboard→prompt. | Add a mapping note in PROMPT_RULES: storyboard `camera` (angle) → prompt `camera_angle_id`; storyboard `movement` → prompt `camera_movement`. |
| A3 | "media prompts must not use raw visual_brief after M5" — but generate_media.py still reads visual_brief | Might delete the visual_brief path, breaking M3 tests. | Already noted in TECHNICAL_BIBLE §13 (backward-compat preserved). Reinforce in PROMPT_RULES that the visual_brief path stays for tests; new episodes use the compiler. (Adequately covered — low risk.) |
| A4 | "continuous_voiceover required" vs assemble.py only supports per-segment audio today | Might assume assemble.py already handles continuous narration and build M5 on a false premise. | Add a note: continuous_voiceover is REQUIRED for final publish but the assembly support is an M7 task; M5 storyboards may declare narration_mode but the assembly change comes later. |
| A5 | `text_policy` enum differs: PROMPT_RULES uses `none/soft_focus_only/post_overlay`; storyboard schema uses `none/post_overlay`; constraints uses nested object | Validator might reject `soft_focus_only`. | Standardize the `text_policy` enum to one set across schema + PROMPT_RULES + constraints. Recommend: `none / soft_focus_only / post_overlay`. |

---

## 8. constraints.json Review

- **Valid:** Yes (`python3 -m json.tool` passes).
- **Stdlib-parseable:** Yes — flat-to-moderate nesting, no exotic types.
- **Maps to markdown:** Mostly. Palette, lighting, camera, scene types, forbidden patterns, negative constraints, audio policy, text policy, crop safety, a_roll/b_roll rules, model routing, QA scale, automatic fail conditions all present and aligned.
- **Missing fields (recommend adding):**
  - `host_led_default` + `non_host_led_condition` (P0, C3/H1)
  - `a_roll_rules.presence_measured_by` (P0, C2/H2)
  - split `required_prompt_fields` into universal vs studio-only vs a-roll-only (P0, C1/H3)
  - `episode_types` enum (P1, H7)
  - `storyboard_rules.min_distinct_angles_or_locations` (P1, H4)
  - `cat_requires_reference` (P1, H5)
  - `quality_markers` (P1, H6)
- **Overcomplicated fields:** none. `text_policy` is a nested object while PROMPT_RULES treats it as an enum — reconcile (A5).
- **Mismatches with docs:** music dB numbers (C4); text_policy shape (A5); camera_angle_id universality (C1).

---

## 9. M5 Readiness Checklist

| Item | Status | Note |
|---|---|---|
| Scene types | **PASS** | 9 types, consistent across constraints + schema + prompt rules |
| A-roll/B-roll rules | **PARTIAL** | Rules exist; ratio measurement unit undefined (C2/H2) |
| James presence rules | **PARTIAL** | "host-led" undefined (C3/H1); threshold inconsistent (C2) |
| Studio angle IDs | **PASS** | 7 IDs defined and cross-referenced |
| Reference asset IDs | **PASS** (IDs) / **PARTIAL** (files) | IDs defined; physical files + folders not yet created (M4.3 not run) — needed at M8, not M5 |
| Text policy | **PARTIAL** | Enum shape inconsistent across 3 files (A5) |
| Audio policy | **PASS** | strip/keep_lipsync/silent clear; WPS bands defined |
| Crop safety | **PASS** | center_safe rule + 56% horizontal defined |
| QA hooks | **PASS** | Full rubric with scoring + gates |
| Automatic fail conditions | **PASS** | 16 conditions, aligned across TECHNICAL_BIBLE + QA + constraints |

**Net:** 6 PASS, 4 PARTIAL. All 4 PARTIAL resolve with the 3 P0 fixes + the text_policy reconciliation.

---

## 10. Bad Teaser Failure Coverage

| Original failure | Covered? | Where | Remaining gap |
|---|---|---|---|
| All b-roll | **PARTIAL** | FORBIDDEN_PATTERNS #1, QA auto-fail, constraints | Trigger "host-led" undefined (C3) |
| No meaningful A-roll | **PARTIAL** | TECHNICAL_BIBLE §7 guardrails | Measurement unit undefined (C2) |
| Narrative broken | **YES** | QA_RUBRIC §3 narrative continuity dimension | — |
| Audible breaks | **YES** | TECHNICAL_BIBLE §10 continuous_voiceover, QA §7 | Assembly support is M7 (A4) |
| Futuristic b-roll | **YES** | FORBIDDEN_PATTERNS #3, constraints forbidden_visual_patterns | — |
| Meaningless generated text | **YES** | §9 text policy, constraints text_policy, fail condition | — |
| Each scene independently directed | **YES** | PROMPT_RULES §2 source hierarchy, QA scene-evolution | Scene-evolution threshold not measurable yet (H4) |
| No coherent universe | **YES** | Entire M4 layer | — |

**6 fully covered, 2 partial.** Both partials close with the C2/C3 P0 fixes.

---

## 11. Programmatic LLM Call Readiness

**READY.** Sonnet/auto routing is clearly documented in TECHNICAL_BIBLE §14, QA_RUBRIC §10, constraints.json `model_routing_policy`, and the LLM_KIRO_CLI_INVOCATION_PLAN. Key safeguards present:
- `auto_utility` explicitly forbidden as sole final creative approver (3 places).
- No direct API tokens; Kiro-CLI session auth only.
- Structured output schema defined.
- Creative-authority task gating defined.

One note: the invocation plan's Open Question #3 (multi-line JSON response extraction) must be solved when `llm_call.py` is built, but it does not block M5 doc readiness.

---

## 12. Reference Asset Readiness

**PARTIAL.**
- Asset IDs: clear and complete (James, studio angles, cat, wardrobe, props, palette). **Good.**
- Allowed/forbidden uses: defined per asset. **Good.**
- Multiple studio angles: supported (7 IDs). **Good.**
- **Gap:** `assets/reference/` folder does not exist; no `.gitkeep`; seed images from `brand/James_*.png` are documented but not copied/linked. The manifest's "status" column correctly marks most as `*Needed*` and seeds as `seed_needs_review`, so the manifest is honest — but M4.3 (folder creation + seed mapping) was skipped.
- **Impact:** Does NOT block M5 (storyboard uses asset IDs as strings). DOES block M8/M10 (generation needs the actual reference images). Classify as **P1 (before media generation)**.

---

## 13. Recommended Fix Order

### Must fix before M5 (P0)
1. **C3/H1** — Define "host-led episode" (default true; non-host-led only if `allow_all_broll: true`). Files: UNIVERSE_BIBLE, constraints.json.
2. **C2/H2** — Pick one James-presence measurement (recommend `beat_count`) and reconcile thresholds across FORBIDDEN_PATTERNS, TECHNICAL_BIBLE, QA_RUBRIC, constraints.json.
3. **C1/H3** — Make `camera_angle_id` studio-only; b-roll uses `camera_movement` + nullable angle. Files: constraints.json, PROMPT_RULES.
4. **A5** — Standardize `text_policy` enum (`none/soft_focus_only/post_overlay`) across schema-design, PROMPT_RULES, constraints.json.

### Should fix before media generation (P1)
5. **M4.3** — Create `assets/reference/` folders + `.gitkeep`; copy/map `brand/James_*.png` seeds.
6. **H7** — Add `episode_type` enum + storyboard field.
7. **H4** — Add `min_distinct_angles_or_locations` measurable hook.
8. **H5** — Add `cat_requires_reference`.
9. **H6** — Add `quality_markers` block to constraints.json.
10. **C4** — Reconcile music dB numbers.
11. **A1/A2/A4** — Add the clarification notes to PROMPT_RULES / TECHNICAL_BIBLE.

### Can defer (P2)
12. Cat-frequency cross-episode tracking (human-review note; no DB by design).
13. `b_roll_rules` category tokens → scene_type mapping table.

---

## 14. Exact Next Prompt for Cheaper Implementation Model (Fixlist Sprint, use Sonnet)

> You are applying the M4 review fixlist for the AI Educational Influencer Factory. Repo: /home/jacobw/YTchannel. Use python3. Read `docs/plans/M4_OPUS_REVIEW_FIXLIST.md` and apply ONLY the **P0** rows (and P1 rows 5–11 if time permits, clearly separating them). These are surgical edits to existing docs — do NOT rewrite whole files. Specifically: (1) Define "host-led episode" in UNIVERSE_BIBLE.md and add `host_led_default`/`non_host_led_condition` to constraints.json. (2) Reconcile the James-presence measurement to `beat_count` with one consistent threshold set across FORBIDDEN_PATTERNS.md, TECHNICAL_BIBLE.md, QA_RUBRIC.md, constraints.json; add `presence_measured_by` to constraints.json. (3) Make `camera_angle_id` studio-only by splitting `required_prompt_fields` in constraints.json into universal vs studio-only, and update PROMPT_RULES.md §3. (4) Standardize the `text_policy` enum to `none/soft_focus_only/post_overlay` across PROMPT_RULES.md, constraints.json, and the schema-design doc. After edits, run `python3 -m json.tool docs/channel_universe/constraints.json` to confirm validity, and `python3 tests/test_assemble.py`, `test_tts.py`, `test_generate_media.py`, `test_media_pack.py` to confirm no regression. Do NOT generate media, call Higgsfield/ElevenLabs, regenerate TTS, or modify scripts/assemble.py/tts.py/generate_media.py. Report each edit made.

After the fixlist sprint passes, M5 (Storyboard Generator) scripting may begin.

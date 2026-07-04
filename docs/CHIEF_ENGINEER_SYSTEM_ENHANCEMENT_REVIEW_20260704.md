# Chief Engineer System Enhancement Review

Date: 2026-07-04
Role: Chief Software Engineer, video production
Repository: `/home/jacobw/YTchannel`
Source spec analyzed: `docs/END_TO_END_PRODUCTION_SYSTEM_TECHNICAL_SPEC_20260704.md`
Evidence basis: spec document plus direct code inspection of the lipsync, b-roll, and graphics subsystems (file:line citations throughout).
Scope: architectural assessment and enhancement program to reach systemic, repeatable production of professional-level educational YouTube videos with (1) perfect lipsync, (2) highly relevant b-roll, (3) integrated, relevant graphics. No code changes were made.

---

## 1. Executive Summary

The pipeline's orchestration backbone is genuinely strong: DB-native staged execution, artifact hashing, render-unit lineage, provider-job state tracking, fail-closed human gates, and sample-exact audio provenance for hero segments. This is better plumbing than most production shops have.

However, for the three quality pillars you asked about, the system currently exhibits the same structural pattern in all three places: **the contract and gating layers are rigorous, but the measurement/execution layer behind them is a stub, a proxy, or dead code.** The gates demand evidence that production code cannot yet produce, so real productions either block or fall through to review-only human acceptance.

| Pillar | Contract/gate layer | Actual execution layer | Verdict |
| --- | --- | --- | --- |
| Lipsync | Per-segment `syncnet_offset` evidence required at assembly; sample-exact audio slicing; temporal-edit prohibition | No SyncNet exists. Only a whole-frame RMS/frame-diff proxy (`provisional: True`) plus test-mode fakes | **Gate is unsatisfiable in production** |
| B-roll relevance | 8 mandatory semantic fields per unit; `semantic_role_qa` required at assembly; concept-memory dedup schema | No vision model wired. Semantic verifier is `DeterministicTestVerifier`. Dedup functions never called; `concept_key = shot_id` makes dedup vacuous | **Relevance rests entirely on prompt authoring; zero pixel-level verification** |
| Graphics | Text-spec hashing, provider exclusion, hold-duration gates | Static 1080p PNGs frame-held via `tpad`; animation system is an uncalled brightness-fade stub; overlay-on-video system is test-only; brand fonts unused; word-level timing impossible | **Cutaway freeze-cards, not integrated motion graphics** |

The enhancement program below closes each pillar with a real measurement engine, then upgrades the creative execution layer. The single highest-leverage cross-cutting investment is **forced alignment (word-level timestamps)** — it simultaneously improves lipsync verification granularity, b-roll cut timing, and graphics synchronization.

---

## 2. Current-State Assessment: Lipsync

### 2.1 What is genuinely working

- **Generation plumbing is production-grade.** Hero units route to Seedance 2.0 via Higgsfield CLI with a reference speaking-frame image and a sample-exact 48 kHz narration slice (`scripts/paid_adapters.py:184-231`; `scripts/slice_continuous_lipsync.py:60-246`). Slices are extracted with re-encode (never `-c copy`), padded with synthesized zero-PCM, registered as artifacts with full provenance (`speech_start_sample`, `master_sha256`), and submission is blocked without `source_slice_sha256` (`scripts/media_service.py:114-125`).
- **Contract enforcement is strict.** `production_repo.validate_hero_slicing_intervals` (`scripts/production_repo.py:209-251`) enforces generation == speech ± declared silence, visible ⊆ generation, and forbids all temporal transforms (`setpts`, `atempo`, trim-through-speech) on `HERO_SYNC_LOCKED` units (`scripts/production_repo.py:190-198`).
- **Assembly gates exist.** Every publish-grade hero segment requires a passing `syncnet_offset` validation (`scripts/assemble_db.py:479-556`), tiered by framing (`close_hero`/`medium_hero`/`wide_hero`), plus a compensated-audio artifact (`scripts/assemble_db.py:564-592`). Hero clips are assembled as `hero_island` audio (provider-synced audio preserved) while everything else is muted under the master narration spine (`scripts/assemble.py:1200-1236`).

### 2.2 What is broken or missing

1. **No real sync measurement exists anywhere.** `scripts/evals/eval_lipsync.py:2-7` states it: SyncNet NOT AVAILABLE, Wav2Lip LSE NOT AVAILABLE; the fallback is cross-correlation of audio RMS envelope vs whole-frame 160×90 grayscale frame-diff (`correlate_signals`, lines 193-230), with no face detection (`face_track_found: False`) and self-labeled `provisional: True`. `scripts/lipsync_scoring.py` correctly fail-closes ("Heuristic scoring NEVER returns PASS on the release path") but its only registered adapter is `NoModelLoaded` (line 81). `scripts/evals/eval_syncnet.py` never runs SyncNet even when dependencies are present (`"status": "not_run"`, line 235).
2. **The only writer of passing `syncnet_offset` evidence is the test-mode fake** (`scripts/media_service.py:976-987`, `method: "yt_test_mode_fake_provider"`). Production runs therefore stay BLOCKED at publish-grade assembly and can only proceed via review-only human A/V acceptance, explicitly labeled `REVIEW_ONLY_HUMAN_AV_ACCEPTED_NOT_AUTOMATED_SYNCNET_PASS` (`scripts/assemble_db.py:678`). Real-production outputs under `outputs/seedance_truth_test_001/` confirm this.
3. **Offset compensation is manual.** `scripts/evals/remux_compensated_hero.py:24-79` takes `--offset-ms` as an operator argument; nothing measures and feeds a trusted offset automatically.
4. **Mechanical duration tolerance is wide** (1500 ms, `scripts/media_service.py:944-945`) to accommodate Seedance drift — acceptable only because sync is supposed to be verified separately, which it currently is not.
5. **Visible-window fields are validated but not populated by the main path** (`scripts/produce_db.py` sets speech/generation only), weakening the visible ⊆ generation contract in practice.

### 2.3 Verdict

The system is one component away from honest publish-grade lipsync: a **real, calibrated audio-visual sync scorer with face tracking**. Everything upstream (slicing, provenance, prohibition of temporal edits) and downstream (per-segment gating, tiered thresholds, compensated remux) is already built and waiting for it.

---

## 3. Current-State Assessment: B-roll Relevance

### 3.1 What is genuinely working

- **Creative authoring is well specified.** The Sonnet 5 storyboard director prompt injects structured source research (`docs/prompts/STORYBOARD_SONNET5_DIRECTOR.md:272-273`), bans generic b-roll phrases with a `BLOCKED_GENERIC_BROLL` failure mode (lines 132-148), and requires per-shot `why_this_visual`, `narrative_alignment`, `claim_refs` tied to a claim inventory with `visual_obligation: must_show|may_show|explicitly_avoid` (`schemas/storyboard_v2.schema.json:171-202, 241-263`).
- **The semantic contract is persisted end-to-end.** The R7 b-roll semantic contract (`db/migrations/005_broll_semantic.sql:12-35`) carries `narrative_claim`, `information_to_show`, `viewer_takeaway`, `semantic_acceptance_criteria`, `distinctness_requirement`, `concept_key/hash` onto every render unit, and `production_repo.plan_render_units` refuses empty fields (`scripts/broll_semantic.py:39-86`).
- **Assembly hard-blocks without semantic evidence.** `assemble_db.validate_semantic_role_qa` (`scripts/assemble_db.py:198-269`) requires a passing `semantic_role_qa` validation matching each publish-grade unit's `visual_role`.

### 3.2 What is broken or missing

1. **Semantic verification is fake.** The only verifier implementation is `DeterministicTestVerifier` ("does NOT perform real semantic understanding", `scripts/semantic_role_pipeline.py:72-127`); production evidence comes solely from `record_test_mode_semantic_role_qa` (`scripts/media_service.py:1218-1260`), which runs only under `YT_TEST_MODE=1` and auto-passes anything that passed technical QA. No code sends sampled frames to a vision-capable LLM.
2. **`broll_qa.py` is dead code.** `check_semantic_relevance` (keyword ∩ detected-object overlap), duplicate detection via embeddings, and gibberish detection exist (`scripts/broll_qa.py:129-316`) but default to `NoVisionModel` → `review_required`, and **no pipeline stage imports the module**.
3. **Concept deduplication is vacuous twice over.** `check_concept_quota` / `register_concept` / `concept_memory` / `FORBIDDEN_CHEAP_CONCEPTS` are never invoked; and canonical projection sets `concept_key = concept_hash = shot_id` (`scripts/storyboard_projection.py:177-178`), so no two shots could ever collide even if it were invoked.
4. **Prompt compilation drops the research.** Provider prompts are string concatenation of intent fields plus regex vagueness lint (`scripts/produce_db.py:877-942`; `scripts/compile_media_prompts.py:436-451`); source research informs only the storyboard stage. In deterministic/test mode `narrative_claim` degrades to the first 8 words of narration (`scripts/produce_db.py:490, 611-612`).
5. **Only OCR and ffprobe touch real pixels in production** (`scripts/media_service.py:831-892`). A clip that is on-brand-looking but semantically wrong for its claim passes every gate that actually executes.
6. **Text-to-video only for b-roll.** No stock/library integration, no image-to-video path for b-roll (image conditioning is hero-only, `scripts/paid_adapters.py:215-231`), no reference-image grounding for factual/historical subjects — the weakest possible generation mode for educational specificity.

### 3.3 Verdict

B-roll relevance is currently a **single-point-of-authoring guarantee**: if Sonnet writes a great grounded shot and the provider happens to honor the prompt, it's relevant. There is no closed loop. The fix is a real vision-verification stage (frames → vision LLM → judged against `semantic_acceptance_criteria` and `must_show`/`must_avoid`), plus grounded generation inputs (reference images / image-to-video / curated asset library) so the provider has less room to hallucinate.

---

## 4. Current-State Assessment: Graphics

### 4.1 What is genuinely working

- **Deterministic separation is correct architecture.** Text-bearing graphics are excluded from paid providers, rendered locally with PIL, and hashed (`text_spec_sha256` recomputed at QA, `scripts/media_service.py:691-699`); provider prompts are text-risk-checked before spend.
- **12 layout templates exist** (`scripts/render_graphics.py:813-827`), including 8 "professional" templates (comparison card, framework, decision tree, cost stack, before/after, timeline, annotated UI mock, quote card).
- **A schema-complete overlay system exists**: layered, positioned (16x9/9x16), time-windowed overlays with fades (`scripts/assemble.py:454-531`, `schemas/overlay_timeline.schema.json`).

### 4.2 What is broken or missing

1. **Production graphics are static freeze-cards.** The production path renders one static 1080p PNG per unit and frame-holds it via `tpad=stop_mode=clone` for the whole span (`scripts/assemble.py:1259-1266`). The animation system (`render_animated_template`, `render_fade_animation`, `scripts/render_graphics.py:632-810`) is never called by `invoke_graphics_compositing`; "progressive reveal" delegates to fade; the fade is an RGB brightness ramp, not alpha; lines 786-789 are unreachable dead code. The 4s-warn/6s-fail static-hold gates (`scripts/assemble_db.py:723-742`) exist precisely because of this.
2. **The 8 professional templates are unreachable from production.** `render_local_graphic_render_unit`'s layout map only routes to the 4 original layouts (`scripts/render_graphics.py:1044-1049`).
3. **The overlay-on-video system is dormant.** `build_assembly_manifest` never emits an `overlay_timeline`; production graphics are full-frame cutaways, so text can never annotate hero/b-roll footage in the DB-native flow. Worse, a second unstyled FFmpeg `drawtext` path (48px white, dead-center, `scripts/assemble.py:1034-1076`) can fire for the same beat as the branded PIL card.
4. **Brand fidelity gap.** Renderer hardcodes DejaVu fonts with silent fallback to PIL default (`scripts/render_graphics.py:46-55`); brand fonts (`brand/fonts/Inter.ttf`, `PlayfairDisplay.ttf`) and brand assets (`brand/assets/lower_third.png`, wordmark) are never loaded. Palette is honored; typography is not.
5. **No word-level timing exists anywhere.** Timing derives from ffmpeg `silencedetect` sentence gaps plus word-count-proportional allocation (`scripts/audio_timing.py:100-130`). The storyboard's `timing: "on_spoken_line"` intent is a string label that is never interpreted. A stat cannot pop when the number is spoken.
6. **No pixel-level text verification.** OCR is deliberately skipped for local graphics ("renders exact text by design", `scripts/media_service.py:734-738`), so hard truncation (`text[:120]`, `scripts/render_graphics.py:948/1052`) or wrap overflow ships undetected. The `graphic_text_hash` DB column is write-only.
7. **Generational quality loss.** Each overlay/drawtext pass fully re-encodes the video (libx264 CRF 18 per pass, `scripts/assemble.py:523-528`).
8. **`still_kenburns` never moves.** Units are counted in graphics_compositing but nothing renders them, and no Ken Burns motion exists anywhere.

### 4.3 Verdict

Graphics are currently review-grade slide inserts, not integrated motion graphics. The overlay_timeline subsystem plus forced alignment plus the already-written professional templates are 70% of the raw material for a proper solution — they need to be wired, animated, brand-typed, and verified.

---

## 5. Cross-Cutting Architectural Findings

1. **"Gate demands evidence nothing can produce" is a systemic anti-pattern instance count of 3.** It is correct fail-closed design, but the sprint plan must treat the three measurement engines (sync scorer, vision verifier, graphic pixel verifier) as the critical path — everything else is polish on top of unverifiable output.
2. **Test mode is the only entity that ever fully "succeeds."** Every publish-grade evidence type (syncnet_offset, semantic_role_qa) has a test-mode auto-pass writer and no production writer. This inflates confidence from the 104-passing test suite: the tests validate plumbing, not the quality pillars. Add a CI assertion that greps for production writers of each required validator, or a "production evidence producibility" self-check in `produce_db.py status`.
3. **Word-level timestamps are the single highest-leverage missing primitive.** They upgrade: lipsync verification granularity (per-word drift windows), hero slice boundary placement (cut in silence, never mid-phoneme), b-roll cut points (motivated cuts on clause boundaries), graphic reveal timing (stat pops on the spoken number), and future captions/subtitles. One forced-alignment stage after `tts` serves five consumers.
4. **Generation is prompt-only where it should be reference-grounded.** Hero already uses image conditioning; b-roll does not. Educational content lives or dies on specificity — image-to-video from curated/verified reference frames dramatically narrows provider hallucination space.
5. **Analytics loop is a stub** (production metadata snapshots only). The DB lineage (claims → shots → render units → deliverable) is already sufficient to attribute retention dips to specific visuals once real YouTube analytics are ingested — this is a data-plumbing task, not a schema redesign.
6. **Operator tooling gaps** (reused-footage linking CLI, unified `inspect-production` report) are acknowledged in the spec (§28) and remain the correct near-term ergonomics work.

---

## 6. Enhancement Program

Priorities: P0 = required for honest publish-grade output; P1 = required for "professional-level" quality; P2 = compounding advantage.

### P0-1. Real lipsync measurement engine

Goal: production-writable `syncnet_offset` evidence with calibrated thresholds; retire the test-mode fake as the only producer.

- Integrate a real AV-sync scorer behind the existing `SyncModelAdapter` interface in `scripts/lipsync_scoring.py` (which was designed for exactly this). Candidates: SyncNet (original), Wav2Lip LSE-C/LSE-D expert discriminator, or a modern latent-sync scorer. Must include face detection/tracking (e.g., RetinaFace/MediaPipe) so scoring is mouth-region, not whole-frame.
- Wire it into `_qa_hero_lipsync` (`scripts/media_service.py:895-1046`) as the production branch, replacing the envelope proxy for publish-grade decisions; keep the proxy as a cheap pre-filter.
- Automate offset compensation: measured offset feeds `remux_compensated_hero.py` directly (no manual `--offset-ms`), with re-verification after remux (measure → compensate → re-measure → gate).
- Calibrate the tiered thresholds in `lipsync_policy.py` (`close_hero`/`medium_hero`/`wide_hero`) against a labeled set of known-good and known-bad Seedance outputs before trusting them.
- Populate `visible_start/end_sample` in the main compile path so the visible ⊆ generation contract is actually exercised.
- Acceptance: a real production reaches publish-grade assembly with zero `REVIEW_ONLY_HUMAN_AV_ACCEPTED` exemptions on hero units; test-mode fake evidence is rejected outside `YT_TEST_MODE`.

### P0-2. Vision-LLM semantic QA for b-roll (close the relevance loop)

Goal: every generated clip is judged against its own `semantic_acceptance_criteria`, `must_show`, `must_avoid`, and `narrative_claim` before assembly.

- Implement a production `Verifier` for `scripts/semantic_role_pipeline.py` that samples N frames (start/middle/end + scene changes via the existing frame_sampling module) and sends them with the unit's semantic contract to a vision-capable LLM through the existing `llm_call.py` routing (add a `vision_qa` profile in `configs/llm_models.yaml`).
- Structured verdict: `{claim_supported, must_show_present[], must_avoid_violations[], described_content, confidence}` recorded as `semantic_role_qa` validation evidence — the assembly gate at `scripts/assemble_db.py:198-269` then works unchanged.
- Route failures through the existing repair lifecycle with **prompt-revision feedback**: the vision model's `described_content` is diffed against intent and appended to the regeneration prompt (this converts QA failures into better prompts instead of blind resubmits).
- Wire the model-free checks from `scripts/broll_qa.py` immediately (gibberish/frozen-frame detection is ffmpeg-only and already works): they are free signal currently discarded.
- Acceptance: a deliberately mismatched clip (wrong subject for the claim) is auto-rejected in production mode; evidence lineage shows vision verdict per unit.

### P0-3. Fix concept deduplication (small, do alongside P0-2)

- Make projection derive `concept_key` from normalized visual concept (subject + action + setting), not `shot_id` (`scripts/storyboard_projection.py:177-178`).
- Call `check_concept_quota`/`register_concept` from `compile_media`, and enforce `FORBIDDEN_CHEAP_CONCEPTS`.
- Add cross-clip near-duplicate detection at QA (perceptual hash of sampled frames is sufficient initially; embedding similarity later).

### P0-4. Forced alignment stage (word-level timestamps)

Goal: a `word_timing` document kind produced right after `tts`, consumed by timing, graphics, and assembly.

- Add an alignment step (WhisperX / Montreal Forced Aligner / aeneas — script text is known, so this is forced alignment, not ASR) producing word → [start_ms, end_ms] against the master narration.
- Replace word-count-proportional beat allocation (`scripts/audio_timing.py:100-130`) with measured word boundaries; place hero slice cuts and span boundaries in silence gaps between words.
- Interpret the currently-discarded `timing: "on_spoken_line"` graphic intent against real timestamps.
- Acceptance: timeline spans land on word boundaries; a graphic reveal can be bound to a specific spoken word.

### P1-1. Integrated motion graphics (overlays on video, animated, brand-true)

Goal: graphics annotate footage instead of replacing it, with real motion and brand typography.

- **Wire `overlay_timeline` into production**: extend storyboard overlay projection and `build_assembly_manifest` (`scripts/assemble_db.py:872-989`) to emit overlay_timeline entries for lower thirds, stat callouts, key lines, and source citations composited over hero/b-roll; reserve full-frame cards for genuinely full-frame content (frameworks, comparisons, timelines).
- **Real animation**: replace the brightness-fade stub with alpha-channel animation (per-element slide/scale/reveal). Two viable implementation strategies, in order of preference: (a) render element layers as separate PNGs and animate positions/opacity in the FFmpeg overlay graph (keeps determinism, no new deps); (b) frame-sequence rendering from the existing PIL templates. Remove dead code at `scripts/render_graphics.py:786-789`; wire `render_animated_template` (or its successor) into `invoke_graphics_compositing`; honor `validate_animation_requirement` for >2s graphics.
- **Brand typography**: load `brand/fonts/` (Inter/Playfair) in `_font()`; fail closed if brand fonts are missing rather than silently falling back to DejaVu/PIL-default; use `brand/assets/` lower-third and wordmark plates.
- **Route to the professional templates**: fix the layout map (`scripts/render_graphics.py:1044-1049`) so comparison_card/framework_3_step/decision_tree/cost_stack/before_after/timeline/quote_card are reachable from the storyboard's deterministic text specs.
- **Kill the duplicate drawtext path** (`scripts/assemble.py:1034-1076`) or gate it off for DB-native productions.
- **Single-pass compositing**: build one filter graph with all overlays instead of one re-encode per overlay (`scripts/assemble.py:523-528`) to stop generational quality loss.
- **Implement Ken Burns** for `still_kenburns` units (zoompan is a one-filter change) or remove the asset type.
- Acceptance: a production deliverable contains at least one animated overlay composited over moving footage, brand fonts verified in output frames, one re-encode total for graphics.

### P1-2. Graphic pixel verification

- OCR every rendered graphic and fuzzy-match against `graphic_text_content` (pytesseract is already integrated for provider video); fail on truncation/overflow.
- Add an auto-fit text layout pass (shrink-to-fit within min/max font sizes) to eliminate the `text[:120]` hard truncation.
- Render at 2x and downsample (supersampling) for professional text anti-aliasing; add a native 9x16 layout variant instead of repositioning 16x9 rasters.
- Make `graphic_text_hash` verified, not write-only.

### P1-3. Grounded b-roll generation (reduce hallucination at the source)

- **Reference-image conditioning for b-roll**: extend the adapter layer to support image-to-video for b-roll units where the storyboard declares a `must_show` visual anchor; source reference stills from research citations, the reused-footage library, or a curated brand asset pool. (The hero path proves the plumbing pattern at `scripts/paid_adapters.py:215-231`.)
- **Curated asset library as a first-class asset type**: build on the existing `asset_type=reused` path; add the missing operator CLI (`produce_db.py link-artifact`, spec §28.1) plus a searchable library index (tags, embeddings, license/provenance fields) so the storyboard director can *cite* library assets and projection can auto-link them.
- **Feed structured research into compile-time prompts** (spec §28.2): pass claim-linked source excerpts into `_compose_generation_prompt` so provider prompts inherit factual anchors (dates, names, places, object specifics) rather than only Sonnet's paraphrase.

### P1-4. Operator visibility and E2E validation

- `inspect-production` command emitting the full evidence bundle (shots, units, prompts, artifacts, QA verdicts, costs, blockers, approvals) — spec §29.10.
- After P0 items land: one full paid seed→publish run with all publish-grade gates satisfied by production-produced evidence (spec §28.7). This is the true acceptance test of the entire program.

### P2-1. Analytics-driven creative learning loop

- Ingest YouTube Analytics (retention curves, CTR, APV) via the API as a provider subsystem; snapshot into `metric_snapshots`.
- Join retention timestamps to timeline spans → render units → storyboard shots → claims (lineage already exists) to attribute drops/spikes to visual decisions.
- Feed aggregated findings into the storyboard director prompt as channel-performance priors (e.g., "graphics-heavy segments retain X% better in minute 2-4").

### P2-2. Publish subsystem

- Real YouTube upload as a provider boundary: resumable upload, platform ID capture, AI-disclosure flag enforcement, thumbnail/metadata artifacts, failure recovery — consistent with the existing provider-job pattern.

### P2-3. Policy engine consolidation (deferred, deliberate)

- Spec §29.7 asks whether compliance should centralize. Recommendation: **keep distributed enforcement, centralize policy *definitions*** (a single versioned policy document that stages read), so stage-local fail-closed behavior is preserved while policies stop drifting across files.

---

## 7. Recommended Sequencing

```text
Wave 1 (measurement engines — unblocks honest publish-grade):
  P0-1 lipsync scorer   P0-2 vision semantic QA   P0-3 concept dedup fix
Wave 2 (timing primitive):
  P0-4 forced alignment (word timestamps)
Wave 3 (professional execution layer):
  P1-1 integrated motion graphics   P1-2 graphic pixel verification
Wave 4 (grounding + ops):
  P1-3 grounded b-roll generation   P1-4 inspect-production + full paid E2E run
Wave 5 (compounding):
  P2-1 analytics loop   P2-2 publish subsystem   P2-3 policy consolidation
```

Waves 1 and 2 are parallelizable across three engineers/agents (lipsync, vision QA, alignment are independent subsystems). Wave 3 depends on Wave 2 (graphics timing needs word timestamps). The full paid E2E validation (P1-4) is the program's exit criterion.

---

## 8. Risks and Constraints

1. **Vision/sync model dependencies.** SyncNet-class models and vision LLM calls add runtime deps and per-unit cost. Mitigate: proxy pre-filter before expensive scoring; vision QA batched per unit (3-5 frames), cost-capped through the existing spend-gate pattern.
2. **QA-driven regeneration cost spiral.** Real semantic QA will reject clips that today would ship, increasing provider spend per finished video initially. Mitigate: prompt-revision feedback loop (P0-2) and reference-grounded generation (P1-3) both cut rejection rates at the source; track rejection-rate as a first-class metric in `cost_events`.
3. **Threshold calibration.** Both sync and semantic gates need labeled calibration sets before enforcement, or they will block everything / pass everything. Budget a calibration ticket per gate.
4. **Test-mode divergence.** As production evidence writers land, ensure test-mode fakes are clearly non-substitutable outside `YT_TEST_MODE` (assert on `method`/`simulated` fields at the gate, which `assemble_db.py` partially does today).
5. **FFmpeg filter-graph complexity** for single-pass overlay compositing is real but bounded; the existing overlay_timeline schema already models the needed inputs.

---

## 9. Bottom Line

The architecture is sound and unusually disciplined about provenance and fail-closed gating. The gap between "review-only" and "professional publish-grade" is concentrated in exactly three missing engines — a real lipsync scorer, a real vision-based semantic verifier, and a real motion-graphics/overlay execution path — plus one missing primitive, word-level forced alignment, that multiplies the value of all three. Every gate, schema column, and repair loop those engines need already exists and is waiting for them. Build the measurement layer first; the system was designed for it.

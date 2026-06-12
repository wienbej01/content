# Pipeline Gaps and Pending Steps

**Generated:** 2026-06-12
**Scope:** Gap analysis against the intended end-to-end AI content generator.

Model tier guide for later fix work:
- **Fable:** High-value reasoning, architecture, taste/quality evaluation, strategic pipeline design
- **Opus:** Substantial implementation, complex debugging, larger refactors
- **Sonnet:** Routine implementation, docs, tests, straightforward wiring

---

## Gap Matrix

| # | Intended Capability | Current Status | Gap | Impact on Quality/Efficiency | Priority | Next Action | Model Tier |
|---|---|---|---|---|---|---|---|
| G01 | Automated script generation from research brief | **Missing** — no `script_writer.py` | Script JSON must be hand-crafted. Largest manual bottleneck in the system. | **Critical** — output quality depends entirely on human script quality; no LLM assist in the loop | **P0** | Design script generation prompt + implement `scripts/generate_script.py` that takes research brief → structured script JSON | Fable (design) + Opus (implement) |
| G02 | Scripts are gated by LLM review before downstream spend | ~~**Partial** — `review_script.py` exists but is not a hard gate~~ **RESOLVED** — `tts.py --require-gates` enforces G1 (`script_review` ledger gate); `gates.py record` CLI available for manual recording | ~~Review is advisory~~ Gate ledger records the review; `tts.py` refuses ElevenLabs spend without the gate when `--require-gates` is passed | **P0** → DONE | Implemented in T3 (`scripts/gates.py`) + T3 wire into `tts.py` | Sonnet |
| G03 | Storyboard with A-roll/B-roll plan used in media generation | ~~**Partial** — `storyboard.py` exists but is NOT wired into `generate_media.py`~~ **RESOLVED** — V2 directorial layer: `storyboard.py` v2 produces beat-level plan → `review_storyboard.py` (G2 hard gate) → `compile_media_prompts.py` produces `media_plan.json` → `generate_media.py` reads `media_plan.json` as the SOLE prompt source. Raw `visual_brief` path is deprecated/blocked. | ~~No A-roll/B-roll rhythm enforcement~~ Shot-mix bands, hero cap, archival/graphic/kinetic trigger rules are all enforced in the gate chain. | **P1** → DONE | Implemented in T4 (`storyboard.py` v2 router), T5 (`review_storyboard.py` G2), T6 (`compile_media_prompts.py`), T8 (`generate_media.py` refactor). Commits cc05b71–47a3e0b. | Fable + Opus |
| G04 | Constrained media prompts compiled from bibles | ~~**Partial** — `compile_media_prompts.py` exists but uses banned model (wan2_7)~~ **RESOLVED** — `constraints.json:model_routing_policy.grounded_broll` and `.abstract_broll` are now `kling3_0`. `compile_media_prompts.py` reads costs from `model_routing.yaml` and routes per blueprint §5. | ~~Blocked if anyone tries to use the prompt plan~~ Working. | **P0** → DONE | Fixed in T1 config update (commit 738736b). | Sonnet |
| G05 | Lipsync (talking-head) quality matching script intent | **Partial** — Seedance 2.0 works for lipsync when using `--image + --audio`; hook clip has wrong voice | Segment 001 was generated with native Kling voice, not ElevenLabs. Assembled 001 overrides it via `audio` field — but source clip is corrupted. Future lipsync workflows need rigorous audio provenance. | **High** — published video may have wrong voice on hook if audio field is ever removed | **P0** | Re-render 001_hook.mp4 with ElevenLabs audio via seedance --image --audio; enforce audio provenance check at assembly gate | Sonnet |
| G06 | Test suite is valid and green | ~~**Broken** — 13 fail, 7 error~~ **RESOLVED** — `pytest` fully green: 222 passed, 0 failed. `test_shot_router.py` updated to current routing; `test_assemble.py` pytest `log` fixture added; `shot_type` UnboundLocalError fixed in `generate_media.py`. | ~~False CI signal~~ CI signal is now trustworthy. | **P0** → DONE | Fixed in T2 (commit 738736b). | Sonnet |
| G07 | Continuous voiceover narration mode in production | **Implemented but unused** — `tts.py` and `assemble.py` both support `continuous_voiceover`; `constraints.json` says it's the production target; flagship 001 used `segment_tts` | Audible gap between segments is possible with segment_tts; continuous voiceover is the quality target | **Medium** — quality difference; natural narration flow vs. per-segment cuts | **P1** | Test continuous_voiceover end-to-end on a real project; validate `audio_timing.py` produces usable timing maps | Opus |
| G08 | Hooks and brief properly integrated into script pipeline | **Partial** — tools exist (`generate_content_brief.py`, `generate_hooks.py`) but are run ad-hoc | Hooks are not stored in a structured format that gets consumed by `script_writer` | **Medium** — content quality; hooks tend to be an afterthought | **P1** | After script_writer is built, add hook generation as step 1 → feed into script prompt | Sonnet |
| G09 | James A-roll (lipsync) quality at scale | **Partial** — seedance_2_0 works with `--image + --audio`; identity consistency not validated across clips | No automated identity check across clips; human review of review_frames is required | **High** — James looking different in each clip is a quality fail | **P1** | Build automated identity consistency check (compare face embedding across review_frames); or add structured human review gate | Fable (design) + Opus (implement) |
| G10 | Automated publishing workflow | **Missing** — no upload, metadata, or scheduling tools | Everything after assembly is manual: YouTube upload, description, tags, thumbnail | **High** — bottleneck to consistent publishing cadence | **P2** | Build `scripts/publish.py` using YouTube Data API; or document manual SOP for now | Opus |
| G11 | Shorts / atomization workflow | **Missing** | No clip extraction or reformat tools for TikTok/Reels/Shorts | **Medium** — secondary distribution channel; mentioned in business plan | **P2** | Add `scripts/atomize.py` that cuts short segments + reformats for 9:16 Shorts | Opus |
| G12 | Newsletter integration | **Missing** | No Beehiiv integration; must write separately | **Low** — separate workflow; no direct pipeline dependency | **P3** | Document manual process; eventually build `scripts/newsletter.py` | Sonnet |
| G13 | End-to-end pipeline orchestration | **Missing** — all steps are separate CLI commands | No single command runs the whole pipeline. Human must sequence steps manually, checking outputs between each. | **Medium** — operational overhead; error-prone manual sequencing | **P2** | Add `scripts/pipeline.py` that chains steps with gate checks; or document a production runbook | Opus |
| G14 | Reference asset generation (James + studio) | **Partial** — `generate_reference_assets.py` exists; `assets/reference/` has some canonical frames | Not all reference assets enumerated in `REFERENCE_ASSET_MANIFEST.md` have physical files | **Medium** — visual quality of James clips depends on reference image quality | **P1** | Complete reference asset generation per `REFERENCE_ASSET_MANIFEST.md`; validate against character bible | Opus |
| G15 | Media QA dimension check is wrong | ~~**Bug** — `qa_media.py` checks for 1280×720 but production output is 1920×1080~~ **RESOLVED** — `qa_media.py` now accepts a `--scope` flag: `source` (1280×720, Higgsfield output), `assembled_16x9` (1920×1080), `assembled_9x16` (1080×1920). | ~~QA is not trusted~~ QA is now trusted and wired as G8 gate via `--record-gate`. | **P0** → DONE | Fixed in T9 (commit 738736b). | Sonnet |
| G16 | Music generation (AI-based) | **Implemented** (`tools/generate_music.py`) but not tested/validated | Music gen tool exists; `assemble.py` calls it if `music.mood` is set; unclear if it works | **Low** — current production uses an existing music file | UNCERTAIN | Test generate_music.py with a real generation run | Sonnet |
| G17 | Voice consistency across all James clips | **Partial** — ElevenLabs eleven_v3 is the canonical voice; but `configs/james/voice_spec.yaml` documents a Kling-native TTS fallback that was tested but NOT adopted | Voice spec doc is misleading — it documents the CLI-only Kling fallback as if it's the production approach | **Low** — production uses ElevenLabs correctly; doc is confusing | **P1** | Update `voice_spec.yaml` header to clearly label it as a deprecated experiment; production path is ElevenLabs only | Sonnet |

---

## Immediate P0 Fixes (before next production run)

~~These must be fixed before attempting another end-to-end production run:~~

**All P0 items are resolved as of 2026-06-12.** The V2 gated pipeline (commits 4832ba0–738736b) addressed G02, G03, G04, G06, G15, and added G4 (budget gate, `budget.py`) and G8 (media QA gate, `qa_media.py --record-gate`). `pytest` is fully green (222 passed).

Remaining P0 item not yet resolved: **G05** (re-render `001_hook.mp4` with ElevenLabs audio). That is a production asset fix, not a code fix.

---

## Architectural Debt (Fable-level assessment needed)

The following are design questions that require judgment, not just implementation:

- **Should storyboard → prompt compiler → generate_media be a hard sequential gate, or remain advisory?** Making it mandatory is correct for quality but adds latency.
- **Should the pipeline have a state machine or remain file-presence-based?** Current approach (if file exists, skip) is fragile for partial reruns.
- **Should script writing be a pure LLM task or human-in-the-loop?** The brand voice requirement means a pure LLM output needs review; but human-in-the-loop defeats automation goals.
- **What is the right lipsync strategy?** Seedance 2.0 has face-rejection issues; cinematic_studio_3_0 is expensive; current flagship uses voiceover+shots (no lipsync). Is this intentional? It produces b-roll-only output, not a talking-head video.

Evidence: `docs/plans/M4_M10_CREATIVE_CONTROL_WORKPLAN.md`, `docs/channel_universe/constraints.json`, `configs/james/model_routing.yaml`

# Sprint Plan: World-Class Educational Video Remediation (WCR)

**Sprint ID:** `WCR-2026-07`
**Date:** 2026-07-07
**Author role:** Senior Software Engineer / sprint-plan compiler
**Repository:** `/home/jacobw/YTchannel`
**Branch at planning time:** *(current working tree)*
**Source analysis:** `IMPROVEMENT_REMEDIATION.md` (audit findings) + `END_TO_END_PRODUCTION_SYSTEM_TECHNICAL_SPEC_20260704.md` + `PRODUCTION_V2_BLUEPRINT.md`

This sprint remediates the ten systemic issues identified in the end-to-end audit that prevent world-class educational YouTube output, while preserving the programmatic E2E philosophy (every improvement is rule-driven, config-driven, or interface-driven — no manual creative steps introduced).

---

## Agent roles

This sprint uses **six agent roles** executing the Karpathy loop (`BUILD → RUN → MEASURE → ANALYZE → FIX → REPEAT`) per ticket via `ENGINEER → AUDITOR → VALIDATOR` sessions, plus three specialist roles. See `agents/AGENTS.md` for full session protocols.

| Agent | Codename | Role |
|-------|----------|------|
| Engineer | ENG | Deliver smallest coherent fix |
| Auditor | AUD | Independent diff audit |
| Validator | VAL | Independent gate verification |
| Fixture Builder | FXB | Wave 0 deterministic fixtures |
| Integration Tester | INT | Wave 9 E2E run |
| Karpathy-Loop Operator | KLO | State transitions + dispatch |

Each ticket follows three **independent** session phases:

1. **ENG session:** LOAD ticket + baseline files → RUN baseline → REPRODUCE → IMPLEMENT → FOCUSED TEST → APPEND exec log → UPDATE state to `ready_for_audit`
2. **AUD session:** LOAD ticket + diff → INDEPENDENT TEST → AUDIT QUESTIONS → STRUCTURED REPORT (`evidence/<TKT>-audit.md`) → UPDATE state to `ready_for_validation` / `audit_failed` / `blocked`
3. **VAL session:** LOAD ticket + audit report → VERIFY → INVARIANT CHECK → ACCEPT/REJECT → APPEND exec log → UPDATE state to `accepted`

Max three ENG→AUD cycles per ticket. AUD severity ≥ MEDIUM reverts to ENG for repair. Two repairs without material improvement → report `BLOCKED`.

---

## Artifact map

```text
docs/plans/WORLD_CLASS_REMEDIATION_20260707/
    PLAN.md                      <- this file: contract, evidence, waves, gates, traceability
    REQUIREMENTS.json            <- stable requirement IDs, invariants, defects, risks
    STATE.json                   <- single authoritative sprint checkpoint
    EXECUTION_LOG.jsonl          <- append-only execution events
    HANDOFF.md                   <- wave/sprint completion handoff notes
    tickets/
        TKT-001.md .. TKT-006.md  Wave 0  Foundation: inspection, fixtures, baselines
        TKT-101.md .. TKT-105.md  Wave 1  Lipsync provider resilience
        TKT-201.md .. TKT-204.md  Wave 2  Reference-frame visual variation
        TKT-301.md .. TKT-304.md  Wave 3  Hybrid b-roll pipeline
        TKT-401.md .. TKT-404.md  Wave 4  Research citation verification
        TKT-501.md .. TKT-505.md  Wave 5  Audio design & music scoring
        TKT-601.md .. TKT-604.md  Wave 6  Assembly variation & review diversity
        TKT-701.md .. TKT-705.md  Wave 7  Pre-publish optimization
        TKT-801.md .. TKT-803.md  Wave 8  Budget optimizer
        TKT-901.md                 Wave 9  Sprint exit: validated production run
    evidence/
```

---

## 1. Objective and outcome contract

### Objective

Transform the pipeline from "technically functional AI-generated video" to "systemically capable of world-class educational output" by addressing all ten audit findings through programmatic, config-driven, and interface-driven improvements — without introducing manual creative steps.

### Required new behavior

- The storyboard validator enforces reference-frame variation across acts so James is not locked to one angle/wardrobe/setting for an entire episode.
- The b-roll generation path queries stock-footage APIs before falling back to generative models; generative output is verified for text/human-face contamination at the pixel level.
- Research briefs have programmatically verifiable citation URLs that resolve to source material containing the claimed content.
- Audio design is rule-scored to narrative acts with dynamic ducking and chapter marker cues, not a flat music bed.
- The reviewer panel uses explicitly weighted multi-model verdicts (defaulting to the existing DeepSeek profile, with extension points for additional models via config) and hard gate surfaces make AI-flagged issues visible to human operators.
- The manifest supports edit-decision-list overrides so editorial craft (trimming, reordering within constraints) is possible without regenerating content.
- Music drops to silence at paradigm-shift beats as a programmatic rule.
- The lipsync path supports multiple providers via a common interface with health monitoring and failover.
- The budget optimizer allocates spend by beat-attention-weight rather than a uniform flat cap.
- A pre-publish sticker/title variant generator produces A/B candidates before final publishing.

### Behavior that must remain unchanged

- Fail-closed gate semantics (Gate A content, storyboard, spend, Gate B).
- Sample-exact hero audio slicing and the temporal-edit prohibition on `HERO_SYNC_LOCKED` units.
- Local graphics never reach paid providers; `still_kenburns` uses zero-cost local rendering.
- Test mode (`YT_TEST_MODE=1`) never makes paid calls.
- Artifact registration/hashing and DB-native orchestration contracts.
- Deterministic assembly as the default (EDL overrides are opt-in per-variant).

### Failures that must become impossible

- **F1:** James appearing from the same reference frame in 10+ consecutive hero passes without an intervening visual transition (monotony).
- **F2:** A b-roll clip containing readable text or an AI-generated human face passing all production gates unaided by human review.
- **F3:** A key factual claim in a published video citing a URL whose fetched content does not contain the claimed statistic or attribution.
- **F4:** Music playing at full volume during a paradigm-shift or philosophical-close beat (no dynamic ducking).
- **F5:** A lipsync provider outage leaving the entire pipeline blocking (no health monitoring + failover).
- **F6:** A resource-identical b-roll generative clip failing pixel-level QC (gibberish/frozen-frame/text in focus).

### Architectural invariants (must hold at end of every Wave)

- **INV-1:** `YT_TEST_MODE=1 python3 -m pytest -q` passes; the current 2,825-test baseline is the floor.
- **INV-2:** No paid provider/LLM/TTS call occurs under `YT_TEST_MODE=1` or in pytest.
- **INV-3:** New validators fail loudly (non-zero / stage blocked) when their backend is unavailable; they never fabricate a pass.
- **INV-4:** All new evidence is recorded in the `validations` table with validator name, method, and input SHA provenance.
- **INV-5:** Repository stays runnable after every ticket (no partial feature activation; new stages/paths behind explicit config until their Wave gate).
- **INV-6:** Budget caps remain enforced; no generation path can spend above its configured cap without explicit human authorization.
- **INV-7:** The 6-Act MITmonk master structure remains the content formula; shots still obey the shot-mix bands.
- **INV-8:** All improvements are programmatic (rule-driven, config-driven, or interface-driven) — no manual creative steps introduced.

### Safety and cost restrictions

- Paid calls (ElevenLabs, Higgsfield, paid LLM vision calls at volume, paid stock- API queries beyond free-tier) require explicit human authorization; tickets that need them are marked `BLOCKED: <specific need — human must authorize paid call>` for that step but proceed with all zero-cost scaffolding.
- No destructive DB migrations; all migrations additive with pre-migration backup (existing mechanism in `production_db.py`).
- Experiments that alter threshold values (budget caps, scoring thresholds) must be justified with calibration evidence and leave the prior values in git history.

---

## 2. Evidence-based current state (baseline)

Baseline commands executed 2026-07-07:

| Command | CWD | Exit | Result |
| --- | --- | --- | --- |
| `YT_TEST_MODE=1 python3 -m pytest -q` (collection dry-run) | repo root | 0 | `2825 tests collected` |

Confirmed findings (`CONFIRMED` by direct code inspection unless marked):

| ID | Finding | Evidence |
| --- | --- | --- |
| CS-1 | Only one reference set (`navy_sweater_library`, 4 angles) is `active_set`; storyboard validator has no angle/wardrobe diversity constraint | `configs/james/model_routing.yaml:35-42`, `review_storyboard.py:88-145` (bands check only validates mix percentages, not frame variety) |
| CS-2 | No pixel-level text/face detection in `broll_technical_qa.py` is wired into `media_service.py` production QA | `scripts/broll_qa.py:259-316` (working logic), `scripts/media_service.py` (no importer of broll_qa.check_broll_technical) |
| CS-3 | Research output is prompt-instructed to cite URLs verbatim; `detect_unsourced_named_claims` and `detect_overclaim_language` are WARNING-level only | `write_script.py:127`, `write_script.py:168` |
| CS-4 | Music is a flat bed via `generate_music` with only loudnorm + silent ducking; no act-specific scoring, no chapter marker cues | `assemble.py:59`, `configs/james/model_routing.yaml` (no audio scoring config) |
| CS-5 | Reviewer panel uses only DeepSeek flash via `llm_call.py`; no multi-model or diverse-model cast | `review.py:14-40`, `configs/llm_models.yaml:1-7` |
| CS-6 | Lipsync path uses only Seedance 2.0 (`seedance_2_0`); `paid_adapters.py` sends `--generate_audio true` unconditionally | `generate_media.py:33`, `paid_adapters.py:211-213` |
| CS-7 | `generate_media.py` b-roll categories are all `kling3_0`; no stock-footage fallback, no depth-warped Ken Burns, no curated library | `generate_media.py:35`, `storyboard.py:95-106` |
| CS-8 | Budget cap is flat `$60` for explainer; no beat-attention-weighted allocation | `configs/james/model_routing.yaml:48` |
| CS-9 | Thumbnail generation is absent; publish stage has no title/thumbnail A/B testing | `scripts/publish_service.py` (URL-only publish), no thumbnail generator |
| CS-10 | Manifest is strictly deterministic; no EDL override support; no multi-variant assembly path | `assemble.py:26`, `assemble_db.py` (no variant support) |
| CS-11 | `diag_legacy` policy is marked `non_publish_only` but has `fail_ms: 9999` — effectively no failure gate for that tier | `configs/lipsync_thresholds.yaml:64-83` |
| CS-12 | `graph_db_has_clip_db_rows` uses `count_by_production` but `count_by_status` (per-status) is unused | `scripts/clip_db.py` |

UNVERIFIED items to resolve inside tickets (never assume):

- UV-1: Usable number of real hero clips locally for lipsync calibration (TKT-104 precondition).
- UV-2: Which stock-footage APIs have free tiers usable in test mode (TKT-301 discovery).
- UV-3: Budget level acceptable for flagship episodes before human authorization gates (TKT-901).
- UV-4: Whether the existing SyncNet/Wav2Lip backend used in TKT-101/TKT-104 of the PPQ sprint is stable under the current environment (TKT-101 precondition).
- UV-5: Provider CLI support for HeyGen/D-ID/Hydra lipsync APIs (TKT-102 discovery).

---

## 3. Architectural decisions

- **AD-1:** Build the interface/config skeleton first (provider interface, b-roll router, stock-footage query, variation constraint), then the rule engine, then validation, then paid-call requiring execution. Gates already exist; never weaken a gate to "unblock" output.
- **AD-2:** Every paid-call-requiring path has a deterministic fixture/mock backend selected explicitly via env/config. Tests never make paid calls; production mode with no backend = loud failure.
- **AD-3:** Reference-frame variation is enforced as a storyboard validator constraint (within the existing `review_storyboard.py` bands-check framework), not as a runtime generation change.
- **AD-4:** B-roll generation priority order: (1) Stock footage matching semantic tags, (2) Depth-warped still (Ken Burns 2.0), (3) Full generative video. The router is config-driven.
- **AD-5:** EDL overrides are additive to the manifest (never destructive to the source manifest) and are validated by the same constraint engine before assembly re-runs.
- **AD-6:** Reviewer diversity is a config-level capability: `configs/llm_models.yaml` gains a `reviewer_cast` section (models per persona). The default config retains DeepSeek (zero-cost from a routing standpoint); model additions require human authorization for spending.
- **AD-7:** Budget optimizer is a pre-generation allocation step; it never increases the total cap, only redistributes spend across beats.
- **AD-8:** Citation verification is a post-research, pre-script gate: each key_claim's URL is fetched, NER-extracted, and cross-checked. Unverifiable claims are downgraded to general observations before the script stage.

---

## 4. Requirement register

### Reference frame & visual variation

- **R-VIS-1:** Storyboard validator enforces a minimum gap between consecutive hero beats using the same reference frame (configurable `min_frame_gap`, default 3).
- **R-VIS-2:** Validator computes a `visual_fatigue_score` from beat angle/wardrobe distribution and blocks when the score exceeds a configured threshold.
- **R-VIS-3:** Compiler maps `visual_chapter` beats to approved reference-frame sets per episode (config in `configs/james/model_routing.yaml`).

### B-roll generation quality

- **R-BR-1:** B-roll generation queries a stock-footage adapter (Pexels/Pixabay via their free APIs) before generative fallback; deterministic fixture in test mode.
- **R-BR-2:** Generated b-roll is checked at the pixel level for readable text and human-face `in focus`; failures route to repair.
- **R-BR-3:** `still_kenburns` units render depth-warped motion via MiDaS (deterministic test fixture without GPU dependency) or fall back to 2D pan/zoom.

### Research credibility

- **R-RES-1:** Each key_claim in the research brief has a URL that, when fetched, resolves to source material containing the claimed content (fuzzy NER match).
- **R-RES-2:** Named entities in the final script that do not appear in the fetched source corpus are flagged as `unsourced_named_claim` and block script acceptance.
- **R-RES-3:** Source diversity gate: no single source contributes >40% of key claims.

### Music and audio design

- **R-AUD-1:** Music scoring rules are act-specific (tempo/instrumentation per MITmonk act) and config-driven.
- **R-AUD-2:** Music drops to silence for beats whose `narrative_function` is in a configurable set (`myth_bust_reveal`, `paradigm_shift`, `philosophical_close`).
- **R-AUD-3:** Chapter marker audio cues (soft UI tink / low swoosh) are inserted at act boundaries in the assembly manifest.
- **R-AUD-4:** Dynamic ducking is frequency-selective (not flat based on narration spectral profile), encoded as a constant config in `configs/`.

### Assembly variation & editorial craft

- **R-EDT-1:** Manifest supports an opt-in `edl_overrides` file (trim points ±0.5s, adjacent beat reorder, per-beat music ducking) validated by the constraint engine.
- **R-EDT-2:** Emotional beats (thesis close, philosophical statement) receive a 0-1.5s programmatic hold extension in the assembler.

### Lipsync provider resilience

- **R-LS-1:** Lipsync generation goes through a `LipsyncProvider` interface; multiple providers implement the common API (`submit(reference_image, audio_slice) → job_id`, `poll(job_id) → clip_path`, `cost_estimate() → USD`).
- **R-LS-2:** Provider health monitoring submits periodic liveness checks; a provider failing its check is removed from rotation until healed.
- **R-LS-3:** The default production provider remains Seedance 2.0; additional providers require human authorization for spending.

### Multi-model review diversity

- **R-REV-1:** Reviewer cast is config-driven (`configs/llm_models.yaml → reviewer_cast`); default retains DeepSent v4 flash.
- **R-REV-2:** Each human gate report surfaces AI-flagged issues explicitly: the `gate_a_content` and `gate_b_review` reports include a section `ai_reviewer_flags` listing each persona's blocking issues and predicted metrics.

### Pre-publish optimization

- **R-PRE-1:** A `thumbnail_generator.py` module produces 3 thumbnail variants from hero frames + title text, validated for mobile readability.
- **R-PRE-2:** Title A/B candidates are produced via the existing LLM call path and stored in the production DB as a list of equally-valid options for human selection (no automated publishing of A/B test until explicitly authorized).

### Budget optimization

- **R-BUD-1:** Pre-generation optimizer classifies beats by viewer-attention weight and allocates generation budget to maximize weighted quality within the configured cap.
- **R-BUD-2:** The tiered quality levels (`teaser`/`short`/`explainer`/`flagship`) have distinct configurable caps.

### Operations & E2E

- **R-OPS-1:** `produce_db.py` exposes the new variation and selection flags as CLI args (with test-mode defaults).
- **R-E2E-1:** One full production run (seed → publish) completes with all new variation, quality, and scoring rules operational; any paid-call ticket is explicitly marked `BLOCKED: requires human authorization for paid calls`.

### Major risks

- **RISK-1:** SyncNet scorer dependencies/weights may have drifted from the PPQ sprint (UV-4).
- **RISK-2:** Stock-footage API free-tier may have rate limits that throttle production discovery (UV-2).
- **RISK-3:** Reference-frame rotation may produce visual discontinuities if frames are not brand-consistent.
- **RISK-4:** Adding multi-model reviewers increases LLM spend; must be authorizable only.
- **RISK-5:** Manifest EDL overrides, if unconstrained, could violate the shot-mix bands; validation is mandatory.

---

## 5. Wave structure and dependency graph

```text
Wave 0  Foundation: inspection, fixtures, baselines          TKT-001..006   deps: none
Wave 1  Lipsync provider resilience + health monitoring     TKT-101..105   deps: W0
Wave 2  Reference-frame visual variation engine             TKT-201..204   deps: W0
Wave 3  Hybrid b-roll pipeline + pixel-level QC             TKT-301..304   deps: W0, W1
Wave 4  Research citation verification                      TKT-401..404   deps: W0
Wave 5  Audio design & music scoring rules                  TKT-501..505   deps: W0
Wave 6  Assembly variation (EDL, emotional holds)           TKT-601..604   deps: W0, W2
Wave 7  Multi-model reviewers + pre-publish optimization    TKT-701..705   deps: W0, W5
Wave 8  Budget optimizer                                    TKT-801..803   deps: W0, W3
Wave 9  Sprint exit: validated E2E run (human-authorized)   TKT-901         deps: W1..W8
```

**Parallelization:** Waves 1, 2, 4, 5, 7, 8 are mutually independent after Wave 0 and may run in parallel by separate engineers/agents. Wave 3 depends on W1 (provider stability) and W0. Wave 6 depends on W2 (reference-frame sets). Wave 9 is the sprint exit.

---

## 6. Ticket index

| Ticket | Title | Wave | Class |
| --- | --- | --- | --- |
| TKT-001 | Inspect & baseline reference-frame config + storyboard validator gaps | 0 | ROUTINE |
| TKT-002 | Build deterministic b-roll QC fixtures (frozen-frame, text-in-face) | 0 | ROUTINE |
| TKT-003 | Build research citation fixture (correctly sourced + fabricated) | 0 | ROUTINE |
| TKT-004 | Build audio design fixture (flat vs act-scored stem comparison) | 0 | ROUTINE |
| TKT-005 | Build EDL override fixture + constraint validation tests | 0 | ROUTINE |
| TKT-006 | Build budget allocation fixture (flat vs beat-weighted) | 0 | ROUTINE |
| TKT-101 | Discovery: prove secondary lipsync provider interface (HeyGen/D-ID/Hydra) | 1 | REASONING_CRITICAL |
| TKT-102 | Implement `LipsyncProvider` interface + Seedance wrapper + health monitor | 1 | COMPLEX |
| TKT-103 | Provider failover in `generate_media` submit path | 1 | COMPLEX |
| TKT-104 | SyncNet scorer drift check + calibration pin | 1 | COMPLEX |
| TKT-105 | Lipsync `generate_audio` conditional fix (matching W2 from PPQ 601B) | 1 | COMPLEX |
| TKT-201 | Multi-reference-set config + compiler `visual_chapter` mapping | 2 | COMPLEX |
| TKT-202 | Storyboard validator frame-gap + visual-fatigue constraint | 2 | COMPLEX |
| TKT-203 | `location_transition` beat type + minimum-gap rule | 2 | ROUTINE |
| TKT-204 | Reference-frame rotation enforcement test (negative + regression) | 2 | ROUTINE |
| TKT-301 | Discovery: stock-footage API integration (Pexels/Pixabay) | 3 | REASONING_CRITICAL |
| TKT-302 | B-roll hybrid router (stock → depth-warped still → generative) | 3 | COMPLEX |
| TKT-303 | Pixel-level text + human-face detection wired into `media_service` QA | 3 | COMPLEX |
| TKT-304 | Curated asset library index + semantic tagging | 3 | COMPLEX |
| TKT-401 | Citation URL download + NER cross-reference pipeline | 4 | COMPLEX |
| TKT-402 | Script-stage `unsourced_named_claim` hard gate | 4 | COMPLEX |
| TKT-403 | Claim-strength mapper (derives source's hedging language) | 4 | ROUTINE |
| TKT-404 | Source diversity gate (>40% per-source cap) | 4 | ROUTINE |
| TKT-501 | Act-specific music scoring rules in `configs/audio_scoring.yaml` | 5 | ROUTINE |
| TKT-502 | Paradigm-shift music silence rule in assembler | 5 | COMPLEX |
| TKT-503 | Chapter marker audio cue library + manifest schema | 5 | COMPLEX |
| TKT-504 | Frequency-selective dynamic ducking (config + constant) | 5 | COMPLEX |
| TKT-505 | Animated element integration for emotional beats | 5 | ROUTINE |
| TKT-601 | Manifest EDL override schema + constraint validation | 6 | COMPLEX |
| TKT-602 | Emotional-beat hold extension in assembler (thesis/close) | 6 | ROUTINE |
| TKT-603 | `visual_chapter` beats in canonical storyboard schema | 6 | ROUTINE |
| TKT-604 | Multi-variant assembly scoring (deterministic selection) | 6 | COMPLEX |
| TKT-701 | `reviewer_cast` config section (multi-model weights) | 7 | COMPLEX |
| TKT-702 | Human gate report surfaces AI-flagged issues + predicted metrics | 7 | COMPLEX |
| TKT-703 | Thumbnail generator: 3 variants + mobile-readability validation | 7 | COMPLEX |
| TKT-704 | Title A/B candidate generator + persistence | 7 | ROUTINE |
| TKT-705 | Pre-publish checklist CLI (human-selects-from-candidates) | 7 | ROUTINE |
| TKT-801 | Beat attention-weight classifier | 8 | COMPLEX |
| TKT-802 | Pre-generation budget allocator (within current cap) | 8 | COMPLEX |
| TKT-803 | Tiered quality-level config (`teaser`/`short`/`explainer`/`flagship`) | 8 | ROUTINE |
| TKT-901 | Sprint exit: full validated production run (human-authorized) | 9 | REASONING_CRITICAL |

---

## 7. Traceability matrix

| Requirement | Ticket | Proof |
| --- | --- | --- |
| R-VIS-1 | TKT-202 | storyboard validator rejects consecutive same-frame beats |
| R-VIS-2 | TKT-202 | visual_fatigue_score assertion in validator |
| R-VIS-3 | TKT-201 | compiler maps visual_chapter → reference-frame set |
| R-BR-1 | TKT-302 | hybrid router query order verified via fixtures |
| R-BR-2 | TKT-303 | pixel-level text/face detection test with synthetic fixtures |
| R-BR-3 | TKT-302 | depth-warped fixture test (CPU fallback) |
| R-RES-1 | TKT-401 | fixture: cited URL NER matches claimed content |
| R-RES-2 | TKT-402 | negative test: unsourced named claim blocks script |
| R-RES-3 | TKT-404 | diversity gate rejects >40% single-source brief |
| R-AUD-1 | TKT-501 | audio scoring config loads per-act rules |
| R-AUD-2 | TKT-502 | paradigm-shift silence beat produces zero-level music |
| R-AUD-3 | TKT-503 | chapter marker cue appears in assembly manifest |
| R-AUD-4 | TKT-504 | ducking config selects frequency-selective constant |
| R-EDT-1 | TKT-601 | EDL override test: valid override accepted, invalid rejected |
| R-EDT-2 | TKT-602 | emotional-beat hold extension produces +0-1.5s duration |
| R-LS-1 | TKT-102 | LipsyncProvider interface with Seedance wrapper test |
| R-LS-2 | TKT-102 | health monitor test: failing provider removed from rotation |
| R-LS-3 | TKT-103 | failover test: secondary provider selected when primary unhealthy |
| R-REV-1 | TKT-701 | reviewer_cast config loads multi-model weights |
| R-REV-2 | TKT-702 | gate report includes ai_reviewer_flags section |
| R-PRE-1 | TKT-703 | thumbnail generator produces 3 validated variants |
| R-PRE-2 | TKT-704 | title A/B candidates persisted in DB |
| R-BUD-1 | TKT-801 | beat attention-weight classifier fixture test |
| R-BUD-2 | TKT-802 | allocator test: flat cap unchanged, distribution varied |
| F1 (variation) | TKT-202 | storyboard validator frame-gap test |
| F2 (b-roll QC) | TKT-303 | pixel-level text/face detection fixture |
| F3 (citation) | TKT-402 | unsourced claim blocks script |
| F4 (ducking) | TKT-502 | paradigm-shift silence test |
| F5 (provider) | TKT-103 | provider failover test |
| F6 (b-roll QC) | TKT-303 | frozen-frame fixture fails QA |

---

## 8. Wave gates

Each Wave gate must pass before the next Wave begins:

- **W0-G1:** TKT-001..006 accepted by independent validator.
- **W0-G2:** All new fixtures are deterministic and hermetic (no paid calls).
- **W0-G3:** Full 2,825-test suite passes.

- **W1-G1:** TKT-101..105 accepted; LipsyncProvider interface implemented; health monitor wired.
- **W1-G2:** Failover demonstrated with fixtures (no paid calls).
- **W1-G3:** Full suite passes.

- **W2-G1:** TKT-201..204 accepted; validator enforces frame-gap and fatigue constraints.
- **W2-G2:** Rotation demonstrated with fixtures.
- **W2-G3:** Full suite passes.

- **W3-G1:** TKT-301..304 accepted; hybrid router wired; pixel-level QC integrated.
- **W3-G2:** Fixtures demonstrate stock → still → generative fallback.
- **W3-G3:** Full suite passes.

- **W4-G1:** TKT-401..404 accepted; citation verification pipeline gates script acceptance.
- **W4-G2:** Fabricated-claim fixture rejected; sourcing diversity test passes.
- **W4-G3:** Full suite passes.

- **W5-G1:** TKT-501..505 accepted; audio scoring rules loaded; ducking config wired.
- **W5-G2:** Paradigm-shift silence and chapter marker fixture tests pass.
- **W5-G3:** Full suite passes.

- **W6-G1:** TKT-601..604 accepted; EDL override validated; emotional-hold wired.
- **W6-G2:** Manifest EDL override test: valid accepted, invalid rejected.
- **W6-G3:** Full suite passes.

- **W7-G1:** TKT-701..705 accepted; reviewer_cast config loaded; thumbnail generator operational.
- **W7-G2:** Multi-model reviewer call + A/B title generation fixture tests pass.
- **W7-G3:** Full suite passes.

- **W8-G1:** TKT-801..803 accepted; budget allocator produces valid distribution.
- **W8-G2:** Allocator fixture demonstrates beat-weighted distribution within cap.
- **W8-G3:** Full suite passes.

- **W9-G1:** TKT-901 accepted: one full production run completes with all new rules operational.
- **W9-G2:** All Wave gates W1..W8 re-verified on the post-W8 codebase.
- **W9-G3:** Full 2,825-test suite passes; evidence archive complete.

---

## 9. Final sprint gates

The final plan must prove:

1. Requested behavior works through a real observable path (fixtures + interface tests).
2. Confirmed defects have regression tests (each negative finding has a test ticket).
3. Invalid states fail loudly and consistently (valdiators fail closed).
4. No dummy output or silent fallback was introduced.
5. Source-of-truth and architecture rules remain consistent (INV-1..INV-8 hold).
6. Existing unrelated behavior did not regress (2825-test floor holds after every Wave).
7. Performance and resource use did not materially regress without acceptance.
8. Independent audit and validator evidence exist for every ticket.
9. The final repository is buildable, testable, and reviewable.
10. Budget caps remain enforced; no generation path spends above its configured cap without human authorization.

---

## 10. Execution protocol

Every ticket passes through three independent agent sessions: `ENGINEER → AUDITOR → VALIDATOR`, following the Karpathy loop defined in `agents/AGENTS.md`.

- **Engineer** (ENG): LOAD ticket + baseline files → RUN baseline → REPRODUCE → IMPLEMENT → FOCUSED TEST → RECORD
- **Auditor** (AUD): LOAD ticket + diff → INDEPENDENT TEST → AUDIT QUESTIONS → REPORT → UPDATE STATE
- **Validator** (VAL): LOAD ticket + audit report → VERIFY → ACCEPT/REJECT → UPDATE STATE
- **Fixture Builder** (FXB): Wave 0 only — build deterministic hermetic fixtures
- **Integration Tester** (INT): Wave 9 only — full production-mode run
- **Karpathy Loop Operator** (KLO): state transitions, dispatch, cycle limits

Max three engineer→audit→repair cycles per ticket. Stop earlier on genuine blocker or two repairs with no material improvement; report `BLOCKED`.

Detailed session protocols: `agents/AGENTS.md`.

---

## 11. Major risks and blockers

| Risk | Mitigation |
| --- | --- |
| RISK-1 SyncNet scorer drift | TKT-104 pins calibration; UV-4 discoverable inside ticket |
| RISK-2 Stock API rate limits | TKT-301 is discovery-only (no paid calls); fallback path preserves existing behavior |
| RISK-3 Reference-frame discontinuities | TKT-202 enforces rotation within validated sets (same brand DNA) |
| RISK-4 Multi-model reviewer spend | TKT-701 defaults to existing DeepSeek config; additional models require human auth |
| RISK-5 EDL override violates constraints | TKT-601 validates every override against the constraint engine before apply |

---

## 12. Recommended first ticket

**TKT-001** — Inspect & baseline reference-frame config + storyboard validator gaps. It is Wave 0, no dependencies, read-and-doc only (no production code changes). It establishes the evidence baseline for all subsequent variation work.

---

*Sprint plan produced 2026-07-07 — 9 Waves, 41 tickets, ~32 requirements traced.*

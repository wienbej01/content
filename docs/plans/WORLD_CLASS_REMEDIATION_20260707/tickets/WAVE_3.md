## Wave 3 — Hybrid B-Roll Pipeline + Pixel-Level QC

These tickets diversify b-roll generation beyond pure generative video, routing through stock-footage and still-image pipelines first, and wire pixel-level text/face detection into production QA.

---

### TKT-301 — Discovery: stock-footage API integration

| Field | Value |
|-------|-------|
| Ticket | TKT-301 |
| Title | Discovery: stock-footage API integration |
| Requirement / risk IDs | R-BR-1, RISK-2, UV-2 |
| Priority | high |
| Severity | medium |
| Risk level | low |
| Execution class | REASONING_CRITICAL (discovery) |
| Wave | 3 |
| Status | planned |

#### Observable outcome

Decision record `evidence/TKT-301-stock-footage-api-decision.md` documenting Pexels/Pixabay video APIs, free tiers, and a test-mode stubbing strategy. Names one recommended provider. `BLOCKED` with evidence if no viable free tier exists.

No production code changes.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| evidence | decision record exists | `evidence/TKT-301-stock-footage-api-decision.md` | `ls evidence/TKT-301-stock-footage-api-decision.md` |
| evidence | record documents ≥2 providers | file has ≥2 provider sections | `grep -c "^## " evidence/TKT-301-stock-footage-api-decision.md` |

#### Acceptance gates

- G1: Decision record exists.
- G2: At least two providers documented.
- G3: Test-mode determinism strategy documented.
- G4: No production files modified.

---

### TKT-302 — B-roll hybrid router

| Field | Value |
|-------|-------|
| Ticket | TKT-302 |
| Title | B-roll hybrid router (stock → depth-warped still → generative) |
| Requirement / risk IDs | R-BR-1, R-BR-2, R-BR-3, CS-7, CS-11, CS-12 |
| Priority | high |
| Severity | high |
| Risk level | high |
| Execution class | COMPLEX |
| Wave | 3 |
| Status | planned |

#### Observable outcome

A `scripts/broll_router.py` module with a priority-ordered router:
1. **Stock adapter:** queries stock provider; deterministic fixture in test mode.
2. **Still + depth-warped adapter:** high-res still → MiDaS warp → CPU fallback in test mode.
3. **Generative adapter:** existing Kling/Seedance path.

Common interface: `can_handle(beat) -> bool`, `generate(beat) -> clip_path`, `cost_estimate_usd(beat) -> float`.

Behind config flag `BROLL_ROUTER_MODE = generative|hybrid`. Default `generative`. `hybrid` enables new path.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | stock adapter fixture in test mode | deterministic clip path | `python3 -m pytest tests/test_broll_router.py::test_stock_adapter_fixture -q` |
| unit | still adapter CPU fallback | deterministic clip path | `python3 -m pytest tests/test_broll_router.py::test_still_adapter_cpu -q` |
| unit | generative fallback | returns generative path | `python3 -m pytest tests/test_broll_router.py::test_generative_fallback -q` |
| unit | router priority | stock → still → generative | `python3 -m pytest tests/test_broll_router.py::test_router_priority -q` |
| contract | generative mode | no change to existing path | `python3 -m pytest tests/test_generate_media.py -q` |

#### Acceptance gates

- G1: All three adapters implement common interface.
- G2: Router selects highest-priority adapter that `can_handle`.
- G3: Test mode produces deterministic clips, zero network/cost.
- G4: `generative` mode leaves existing behavior unchanged.
- G5: Full suite passes.

---

### TKT-303 — Pixel-level text + human-face detection wired into QA

| Field | Value |
|-------|-------|
| Ticket | TKT-303 |
| Title | Pixel-level text + human-face detection wired into QA |
| Requirement / risk IDs | R-BR-2, F2, F6, CS-2 |
| Priority | high |
| Severity | high |
| Risk level | high |
| Execution class | COMPLEX |
| Wave | 3 |
| Status | planned |

#### Observable outcome

Extend `scripts/broll_qa.py` with two production QA checks:
- **Text detection:** OCR sampled frame; if >N readable ASCII tokens, fail.
- **Face detection:** lightweight face detector; if human face detected in non-hero clip, fail.

Wired into `media_service.py:_qa_provider_video()`. Failures route to repair lifecycle with `broll_text_contamination` / `broll_face_contamination`.

Behind config flag `PIXEL_QA_MODE = off|on`. Default `off`. `on` enables.

Uses fixtures from TKT-002.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | text-in-focus fixture | QA fails with `broll_text_contamination` | `python3 -m pytest tests/test_pixel_qa.py::test_text_fail -q` |
| unit | face-in-focus fixture | QA fails with `broll_face_contamination` | `python3 -m pytest tests/test_pixel_qa.py::test_face_fail -q` |
| unit | clean moving fixture | QA passes | `python3 -m pytest tests/test_pixel_qa.py::test_clean_pass -q` |
| unit | frozen fixture | QA fails with `broll_frozen` | `python3 -m pytest tests/test_pixel_qa.py::test_frozen_fail -q` |
| contract | PIXEL_QA_MODE=off | checks do not run | `python3 -m pytest tests/test_pixel_qa.py::test_off_mode -q` |

#### Acceptance gates

- G1: Text-in-focus fixture triggers `broll_text_contamination`.
- G2: Face-in-focus fixture triggers `broll_face_contamination`.
- G3: Clean moving clip passes.
- G4: Frozen clip still fails (regression).
- G5: `PIXEL_QA_MODE=off` does not run new checks.
- G6: Full suite passes.

---

### TKT-304 — Curated asset library index + semantic tagging

| Field | Value |
|-------|-------|
| Ticket | TKT-304 |
| Title | Curated asset library index + semantic tagging |
| Requirement / risk IDs | R-BR-1, CS-11, CS-12 |
| Priority | medium |
| Severity | low |
| Risk level | low |
| Execution class | COMPLEX |
| Wave | 3 |
| Status | planned |

#### Observable outcome

`scripts/asset_library/` module with SQLite table `asset_library` (path, tags, license, sha256) and `query_semantic(tags, limit)`. Seeded from `configs/asset_library.yaml` (initially empty). `produce_db.py asset-library add <path> --tags ...` for operator population.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | add fixture asset | row created, sha256 recorded | `python3 -m pytest tests/test_asset_library.py::test_add -q` |
| unit | query by subject | matching rows returned | `python3 -m pytest tests/test_asset_library.py::test_query -q` |

#### Acceptance gates

- G1: Asset row created with sha256.
- G2: Semantic query returns deterministic results.
- G3: Full suite passes.

---

## Wave 3 gate

- W3-G1: TKT-301..TKT-304 accepted by independent validator.
- W3-G2: Hybrid router wired; pixel-level QC integrated.
- W3-G3: Full pytest suite passes.

### Wave 3 handoff notes

Stock-footage discovery documented. B-roll router is behind `BROLL_ROUTER_MODE=hybrid` flag (default `generative`). Pixel-level QC is behind `PIXEL_QA_MODE=on` flag (default `off`). All existing behavior preserved.

---

## Wave 4 — Research Citation Verification

---

### TKT-401 — Citation URL download + NER cross-reference pipeline

| Field | Value |
|-------|-------|
| Ticket | TKT-401 |
| Title | Citation URL download + NER cross-reference pipeline |
| Requirement / risk IDs | F3, R-RES-1, R-RES-2, CS-3 |
| Priority | high |
| Severity | high |
| Risk level | medium |
| Execution class | COMPLEX |
| Wave | 4 |
| Status | planned |

#### Observable outcome

`scripts/citation_verify.py` with:
- `fetch_and_extract(url) -> str` (HTML → text, cached).
- `extract_entities(text) -> dict` (deterministic NER: capitalized names + years + percentages).
- `verify_claim(claim_text, source_text) -> float` (overlap score).
- `CITATION_CONFIDENCE_THRESHOLD` (default 0.6).

Research stage runs verification on every `key_claim`. Results recorded in brief as `citation_verification`.

Behind config flag `CITATION_VERIFY_MODE = off|on`. Default `off`.

Test mode uses fixtures from TKT-003.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | correctly-sourced fixture | confidence >= threshold | `python3 -m pytest tests/test_citation_verify.py::test_correct_sourced -q` |
| unit | fabricated fixture | confidence < threshold | `python3 -m pytest tests/test_citation_verify.py::test_fabricated -q` |
| unit | unreachable URL | graceful failure | `python3 -m pytest tests/test_citation_verify.py::test_unreachable_url -q` |
| contract | CITATION_VERIFY_MODE=off | no regression | `python3 -m pytest tests/test_research.py -q` |

#### Acceptance gates

- G1: Correctly-sourced fixture passes.
- G2: Fabricated fixture fails.
- G3: Unreachable URL does not crash.
- G4: `off` mode leaves research unchanged.
- G5: Full suite passes.

---

### TKT-402 — Script-stage unsourced_named_claim hard gate

| Field | Value |
|-------|-------|
| Ticket | TKT-402 |
| Title | Script-stage unsourced_named_claim hard gate |
| Requirement / risk IDs | R-RES-2, F3 |
| Priority | high |
| Severity | high |
| Risk level | high |
| Execution class | COMPLEX |
| Wave | 4 |
| Status | planned |

#### Observable outcome

`detect_unsourced_named_claims()` upgraded from WARNING to hard gate:
- During `invoke_review_script`, any named entity in final script not in fetched source corpus BLOCKS with `BLOCKED_UNSOURCED_NAMED_CLAIM`.
- Error lists entity, segment id, citation URL.
- Repair path: writer revises citation or removes claim.

Behind config flag `UNSOURCED_CLAIM_MODE = warn|block`. Default `warn`.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | fabricated claim injected | review blocked | `python3 -m pytest tests/test_unsourced_claim_gate.py::test_blocked -q` |
| unit | correctly-sourced script | review passes | `python3 -m pytest tests/test_unsourced_claim_gate.py::test_pass -q` |
| contract | warn mode | current behavior preserved | `python3 -m pytest tests/test_review_script.py -q` |

#### Acceptance gates

- G1: Fabricated claim blocks review.
- G2: Correctly-sourced script passes.
- G3: `warn` mode preserves current behavior.
- G4: Full suite passes.

---

### TKT-403 — Claim-strength mapper

| Field | Value |
|-------|-------|
| Ticket | TKT-403 |
| Title | Claim-strength mapper |
| Requirement / risk IDs | R-RES-2 |
| Priority | medium |
| Severity | low |
| Risk level | low |
| Execution class | ROUTINE |
| Wave | 4 |
| Status | planned |

#### Observable outcome

`scripts/claim_strength.py` extracts framing language from source ("an observation", "one study suggests", "we prove") → maps to `claim_strength` enum: `observation | quote | single_study | settled_science`. Attached to each `key_claim`. Pure heuristic, no paid calls.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | "one study suggests X" | strength=single_study | `python3 -m pytest tests/test_claim_strength.py::test_single_study -q` |
| unit | "we prove X" | strength=settled_science | same |

#### Acceptance gates

- G1: Mapper produces expected strengths.
- G2: Full suite passes.

---

### TKT-404 — Source diversity gate

| Field | Value |
|-------|-------|
| Ticket | TKT-404 |
| Title | Source diversity gate |
| Requirement / risk IDs | R-RES-3 |
| Priority | medium |
| Severity | low |
| Risk level | low |
| Execution class | ROUTINE |
| Wave | 4 |
| Status | planned |

#### Observable outcome

Gate rejects briefs where any single source >40% of `key_claims`. Researcher re-run with diversification instructions.

Behind config flag `SOURCE_DIVERSITY_MODE = off|on`. Default `off`.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | single source 80% of claims | brief rejected | `python3 -m pytest tests/test_source_diversity.py::test_reject -q` |
| unit | diverse sources | brief passes | `python3 -m pytest tests/test_source_diversity.py::test_pass -q` |

#### Acceptance gates

- G1: Skewed sources rejected.
- G2: Diverse sources pass.

---

## Wave 4 gate

- W4-G1: TKT-401..TKT-404 accepted.
- W4-G2: Citation verification and unsourced-claim gate operational.
- W4-G3: Full pytest suite passes.

### Wave 4 handoff notes

All citation checks behind config flags (`CITATION_VERIFY_MODE`, `UNSOURCED_CLAIM_MODE`, `SOURCE_DIVERSITY_MODE`). Default = no behavior change. No paid calls.

---

## Wave 5 — Audio Design & Music Scoring Rules

---

### TKT-501 — Act-specific music scoring rules

| Field | Value |
|-------|-------|
| Ticket | TKT-501 |
| Title | Act-specific music scoring rules in configs/audio_scoring.yaml |
| Requirement / risk IDs | R-AUD-1, MITmonk §5 |
| Priority | high |
| Severity | low |
| Risk level | low |
| Execution class | ROUTINE |
| Wave | 5 |
| Status | planned |

#### Observable outcome

New `configs/audio_scoring.yaml` defining per-act: tempo_bpm, instrumentation, energy_level, reference_style. Assembler reads act of each beat and selects matching stem. Test mode uses fixtures from TKT-004.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | load audio_scoring.yaml | valid, all acts 1-6 | `python3 -m pytest tests/test_audio_scoring.py::test_load -q` |
| unit | query act 3 | correct energy/tempo | same |

#### Acceptance gates

- G1: File loads and validates.
- G2: Each act has distinct settings.
- G3: Full suite passes.

---

### TKT-502 — Paradigm-shift music silence rule

| Field | Value |
|-------|-------|
| Ticket | TKT-502 |
| Title | Paradigm-shift music silence rule in assembler |
| Requirement / risk IDs | R-AUD-2, F4 |
| Priority | high |
| Severity | medium |
| Risk level | medium |
| Execution class | COMPLEX |
| Wave | 5 |
| Status | planned |

####Observable outcome

Beats whose `narrative_function` in `SILENCE_FUNCTIONS` (default: `myth_bust_reveal`, `paradigm_shift`, `philosophical_close`) have music volume `-∞` for beat duration + 1s ramp-in after.

Configurable in `configs/audio_scoring.yaml → silence_functions`.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | paradigm_shift beat | music volume -∞ | `python3 -m pytest tests/test_silence_rule.py::test_silence -q` |
| unit | factual_data beat | music unchanged | `python3 -m pytest tests/test_silence_rule.py::test_nosilence -q` |

#### Acceptance gates

- G1: Paradigm-shift beat produces silence.
- G2: Non-silence functions unchanged.
- G3: Full suite passes.

---

### TKT-503 — Chapter marker audio cue library + manifest schema

| Field | Value |
|-------|-------|
| Ticket | TKT-503 |
| Title | Chapter marker audio cue library + manifest schema |
| Requirement / risk IDs | R-AUD-3 |
| Priority | medium |
| Severity | low |
| Risk level | low |
| Execution class | COMPLEX |
| Wave | 5 |
| Status | planned |

#### Observable outcome

`assets/audio/cues/` with 3-5 CC0 audio cue WAVs. `configs/audio_cues.yaml` maps names to files. Assembler inserts a cue at each act boundary. Behind `CHAPTER_MARKERS_MODE = off|on`.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | act boundary present | cue inserted at boundary | `python3 -m pytest tests/test_chapter_markers.py::test_insert -q` |

#### Acceptance gates

- G1: Cue at each act boundary.
- G2: Full suite passes.

---

### TKT-504 — Frequency-selective dynamic ducking

| Field | Value |
|-------|-------|
| Ticket | TKT-504 |
| Title | Frequency-selective dynamic ducking |
| Requirement / risk IDs | R-AUD-4 |
| Priority | medium |
| Severity | low |
| Risk level | low |
| Execution class | COMPLEX |
| Wave | 5 |
| Status | planned |

#### Observable outcome

Replace current loudnorm ducking with frequency-selective ducking (using `ffmpeg` sidechain compress keyed on narration audio). Default ducking level `MUSIC_DUCK_DB` configurable. Behind `DUCKING_MODE = simple|selective`. Default `simple`.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | narration energy high in 1-4kHz | music in 1-4kHz reduced | `python3 -m pytest tests/test_ducking.py::test_selective -q` |

#### Acceptance gates

- G1: Selective ducking reduces music under narration band.
- G2: `simple` mode unchanged.

---

### TKT-505 — Animated element integration for emotional beats

| Field | Value |
|-------|-------|
| Ticket | TKT-505 |
| Title | Animated element integration for emotional beats |
| Requirement / risk IDs | MITmonk §5 |
| Priority | low |
| Severity | low |
| Risk level | low |
| Execution class | ROUTINE |
| Wave | 5 |
| Status | planned |

#### Observable outcome

In `scripts/render_graphics.py`: graphics >2s whose `narrative_function` is in config set get alpha-based animation (fade in, slow scale, element reveal).

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | emotional beat graphic >2s | animation metadata attached | `python3 -m pytest tests/test_graphics.py -k animation -q` |

#### Acceptance gates

- G1: Animation applied to qualifying beats.
- G2: Full suite passes.

---

## Wave 5 gate

- W5-G1: TKT-501..TKT-505 accepted.
- W5-G2: Music act-scoped, paradigm-shift silence operational, chapter markers optional, ducking selective.
- W5-G3: Full pytest suite passes.

### Wave 5 handoff notes

All audio design features behind config flags. Default config = no behavior change. Music is generated locally; no paid calls.

---

## Wave 6 — Assembly Variation (EDL, Emotional Holds)

---

### TKT-601 — Manifest EDL override schema + constraint validation

| Field | Value |
|-------|-------|
| Ticket | TKT-601 |
| Title | Manifest EDL override schema + constraint validation |
| Requirement / risk IDs | R-EDT-1, RISK-5 |
| Priority | high |
| Severity | high |
| Risk level | high |
| Execution class | COMPLEX |
| Wave | 6 |
| Status | planned |

#### Observable outcome

`scripts/edl.py` parses YAML/JSON EDL override file with `overrides: [{beat_id, trim_start_sec, trim_end_sec, reorder_after, music_duck_db}]`. Each override validated against the constraint engine (shot-mix bands, hero-block ≤15s). Invalid overrides rejected with named error.

`scripts/assemble.py` applies valid overrides. Behind `EDL_MODE = off|on`. Default `off`.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | valid EDL override | accepted, assembly applied | `python3 -m pytest tests/test_edl.py::test_valid -q` |
| unit | invalid EDL override (violates bands) | rejected with named error | `python3 -m pytest tests/test_edl.py::test_invalid -q` |
| contract | EDL_MODE=off | no override applied | `python3 -m pytest tests/test_assemble.py -q` |

#### Acceptance gates

- G1: Valid override produces re-lengths/reorders.
- G2: Invalid override rejected.
- G3: `off` mode leaves existing flow unchanged.
- G4: Full suite passes.

---

### TKT-602 — Emotional-beat hold extension

| Field | Value |
|-------|-------|
| Ticket | TKT-602 |
| Title | Emotional-beat hold extension in assembler |
| Requirement / risk IDs | R-EDT-2 |
| Priority | medium |
| Severity | low |
| Risk level | low |
| Execution class | ROUTINE |
| Wave | 6 |
| Status | planned |

#### Observable outcome

Beats whose `narrative_function` in `EMOTIONAL_HOLD_FUNCTIONS` (default: `thesis_close`, `philosophical_statement`, `identity_shift`, `final_motivation`) extended by `EMOTIONAL_HOLD_SEC` (default 0.0-1.5s, deterministic from beat duration).

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | thesis_close beat | extended by EMOTIONAL_HOLD_SEC | `python3 -m pytest tests/test_emotional_hold.py::test_hold -q` |

#### Acceptance gates

- G1: Emotional beat receives hold.
- G2: Non-emotional beats unchanged.

---

### TKT-603 — visual_chapter beats in canonical storyboard schema

| Field | Value |
|-------|-------|
| Ticket | TKT-603 |
| Title | visual_chapter beats in canonical storyboard schema |
| Requirement / risk IDs | R-VIS-3 |
| Priority | low |
| Severity | low |
| Risk level | low |
| Execution class | ROUTINE |
| Wave | 6 |
| Status | planned |

#### Observable outcome

`schemas/storyboard_v2.schema.json` gains `visual_chapter` field. `direct_storyboard.py` and `storyboard.py` emit from act.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | valid storyboard | field populated | `python3 -m pytest tests/test_storyboard_v2_schema.py -q` |

#### Acceptance gates

- G1: Field populated.

---

### TKT-604 — Multi-variant assembly scoring

| Field | Value |
|-------|-------|
| Ticket | TKT-604 |
| Title | Multi-variant assembly scoring |
| Requirement / risk IDs | R-EDT-1 |
| Priority | high |
| Severity | medium |
| Risk level | high |
| Execution class | COMPLEX |
| Wave | 6 |
| Status | planned |

#### Observable outcome

`scripts/assembly_scoring.py` scores EDL variations using deterministic function: `score = w1*pacing_match + w2*variety_match + w3*constraint_margin`. Weights documented in config. Returns highest-scoring variation. No paid calls.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | three variations | highest score selected deterministically | `python3 -m pytest tests/test_assembly_scoring.py -q` |

#### Acceptance gates

- G1: Deterministic selection of highest-scoring variant.
- G2: Full suite passes.

---

## Wave 6 gate

- W6-G1: TKT-601..TKT-604 accepted.
- W6-G2: EDL overrides validated/applied; emotional-hold operational.
- W6-G3: Full pytest suite passes.

### Wave 6 handoff notes

EDL overrides behind `EDL_MODE=on`. All existing assemblies produce identical output in `off` mode. Multi-variant scoring deterministic; weights in config.

---

## Wave 7 — Reviewer Diversity + Pre-Publish Optimization

---

### TKT-701 — reviewer_cast config section

| Field | Value |
|-------|-------|
| Ticket | TKT-701 |
| Title | reviewer_cast config section (multi-model weights) |
| Requirement / risk IDs | R-REV-1, RISK-4 |
| Priority | high |
| Severity | medium |
| Risk level | high |
| Execution class | COMPLEX |
| Wave | 7 |
| Status | planned |

#### Observable outcome

`configs/llm_models.yaml` gains `reviewer_cast` mapping persona → model_profile + weight. `review.py` routes each persona through its profile. Default retains existing behavior. Additional models require human authorization for spending.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | load reviewer_cast | personas → profiles | `python3 -m pytest tests/test_reviewer_cast.py::test_load -q` |
| unit | review route | correct model used | `python3 -m pytest tests/test_reviewer_cast.py::test_route -q` |

#### Acceptance gates

- G1: Cast config loads.
- G2: Each persona routes through its profile.
- G3: Default preserves current behavior.

---

### TKT-702 — Human gate report surfaces AI-flagged issues

| Field | Value |
|-------|-------|
| Ticket | TKT-702 |
| Title | Human gate report surfaces AI-flagged issues |
| Requirement / risk IDs | R-REV-2 |
| Priority | high |
| Severity | medium |
| Risk level | medium |
| Execution class | COMPLEX |
| Wave | 7 |
| Status | planned |

#### Observable outcome

Gate report JSON includes `ai_reviewer_flags` section with each persona's blocking_issues + predicts. Human approval gate surfaces these prominently.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | gate report JSON | ai_reviewer_flags present | `python3 -m pytest tests/test_gate_report.py::test_flags_present -q` |

#### Acceptance gates

- G1: Gate report includes ai_reviewer_flags.
- G2: Full suite passes.

---

### TKT-703 — Thumbnail generator: 3 variants + readability validation

| Field | Value |
|-------|-------|
| Ticket | TKT-703 |
| Title | Thumbnail generator: 3 variants + readability validation |
| Requirement / risk IDs | R-PRE-1 |
| Priority | high |
| Severity | medium |
| Risk level | medium |
| Execution class | COMPLEX |
| Wave | 7 |
| Status | planned |

#### Observable outcome

`scripts/thumbnail_generator.py` takes hero frame + title + brand → produces 3 layout variants (wide text, face+text, colored band). Validates mobile readability (text ≥5% height, contrast ≥4.5:1). Outputs to `assets/thumbnails/<id>/v{1,2,3}.png`. Test mode uses deterministic fixtures.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | generate 3 variants | 3 PNGs created | `python3 -m pytest tests/test_thumbnail_generator.py::test_generate -q` |
| unit | readability validation | pass/fail on fixtures | same |

#### Acceptance gates

- G1: 3 variants generated.
- G2: Readability validation matches ground truth.
- G3: Full suite passes.

---

### TKT-704 — Title A/B candidate generator + persistence

| Field | Value |
|-------|-------|
| Ticket | TKT-704 |
| Title | Title A/B candidate generator + persistence |
| Requirement / risk IDs | R-PRE-2 |
| Priority | medium |
| Severity | low |
| Risk level | low |
| Execution class | ROUTINE |
| Wave | 7 |
| Status | planned |

#### Observable outcome

`scripts/title_ab.py` calls LLM (DeepSeek flash) to produce 5 candidate titles. Persisted in DB table `title_candidates`. Uniqueness check against existing titles. Test mode uses deterministic stub.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | generate titles (stubbed) | 5 unique, persisted | `python3 -m pytest tests/test_title_ab.py -q` |

#### Acceptance gates

- G1: 5 unique candidates.
- G2: Persisted in DB.

---

### TKT-705 — Pre-publish checklist CLI

| Field | Value |
|-------|-------|
| Ticket | TKT-705 |
| Title | Pre-publish checklist CLI |
| Requirement / risk IDs | R-PRE-1, R-PRE-2 |
| Priority | medium |
| Severity | low |
| Risk level | low |
| Execution class | ROUTINE |
| Wave | 7 |
| Status | planned |

#### Observable outcome

`produce_db.py pre-publish-checklist <production_id>` prints all gate statuses, AI flags, thumbnail variants, title candidates, and `READY` or `BLOCKED: <reason>`. Does NOT publish — information surface only.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| integration | run checklist | prints all sections | `python3 -m pytest tests/test_pre_publish_checklist.py -q` |

#### Acceptance gates

- G1: CLI prints all sections.
- G2: Full suite passes.

---

## Wave 7 gate

- W7-G1: TKT-701..TKT-705 accepted.
- W7-G2: Reviewer cast config-driven; gate reports surface flags; thumbnails + titles generated.
- W7-G3: Full pytest suite passes.

### Wave 7 handoff notes

Reviewer cast defaults to existing DeepSeek profile. Multi-model additions require human authorization for spending. Thumbnails generated locally. Title candidates require one LLM call per production (cached).

---

## Wave 8 — Budget Optimizer

---

### TKT-801 — Beat attention-weight classifier

| Field | Value |
|-------|-------|
| Ticket | TKT-801 |
| Title | Beat attention-weight classifier |
| Requirement / risk IDs | R-BUD-1 |
| Priority | high |
| Severity | medium |
| Risk level | medium |
| Execution class | COMPLEX |
| Wave | 8 |
| Status | planned |

#### Observable outcome

`scripts/beat_weight.py` maps each beat to `viewer_attention_weight` ∈ [0.5, 3.0] from narrative_function lookup, shot_type modifier, act modifier. Configurable via `configs/beat_weights.yaml`. Deterministic.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | thesis_close hero in Act 1 | weight ≥ 5.85 | `python3 -m pytest tests/test_beat_weight.py -q` |
| unit | transition beat | weight ≤ 0.5 | same |

#### Acceptance gates

- G1: Weight matches documented function.
- G2: Deterministic.

---

### TKT-802 — Pre-generation budget allocator

| Field | Value |
|-------|-------|
| Ticket | TKT-802 |
| Title | Pre-generation budget allocator |
| Requirement / risk IDs | R-BUD-2, INV-6 |
| Priority | high |
| Severity | medium |
| Risk level | high |
| Execution class | COMPLEX |
| Wave | 8 |
| Status | planned |

#### Observable outcome

`scripts/budget_allocator.py` allocates `cap × (beat_weight / W)` per beat, clamped to floor ($0.25) and ceiling ($8.00). Total must equal cap (within FP tolerance). Recorded in media plan. Uses TKT-006 fixture.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| allocator | 10-beat fixture, cap $60 | sum = 60 | `python3 -m pytest tests/test_budget_allocator.py::test_sum -q` |
| clamp | very high weight | clamped to ceiling | same |
| clamp | very low weight | clamped to floor | same |

#### Acceptance gates

- G1: Total equals cap.
- G2: Per-beat respects floor/ceiling.
- G3: Full suite passes.

#### Audit focus

- Budget invariant: auditor writes independent test asserting total ≤ cap over 1000 random storyboards.

---

### TKT-803 — Tiered quality-level config

| Field | Value |
|-------|-------|
| Ticket | TKT-803 |
| Title | Tiered quality-level config |
| Requirement / risk IDs | R-BUD-2 |
| Priority | low |
| Severity | low |
| Risk level | low |
| Execution class | ROUTINE |
| Wave | 8 |
| Status | planned |

#### Observable outcome

`configs/james/model_routing.yaml → budget_caps`: teaser=15, short=30, explainer=60, flagship=120. Flagship requires explicit human authorization.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | load budget_caps | map of 4 entries | `python3 -m pytest tests/test_budget_tiers.py -q` |

#### Acceptance gates

- G1: Four tiers load.
- G2: Full suite passes.

---

## Wave 8 gate

- W8-G1: TKT-801..TKT-803 accepted.
- W8-G2: Budget allocator produces beat-weighted distribution within cap.
- W8-G3: Full pytest suite passes.

### Wave 8 handoff notes

Budget allocator uses existing cap (default explainer=60). Flagship tier requires human authorization. All allocations within cap (INV-6).

---

## Wave 9 — Sprint Exit: Validated Production Run

---

### TKT-901 — Sprint exit: full validated production run (human-authorized)

| Field | Value |
|-------|-------|
| Ticket | TKT-901 |
| Title | Sprint exit: full validated production run (human-authorized) |
| Requirement / risk IDs | R-E2E-1, F1..F6 |
| Priority | critical |
| Severity | high |
| Risk level | high |
| Execution class | REASONING_CRITICAL |
| Wave | 9 |
| Status | planned |

#### Observable outcome

A single production run (seed → publish) exercising all WCR changes. Evidence bundle in `evidence/TKT-901/`. Every gate satisfied by production-produced evidence.

Any step requiring paid calls (Higgsfield, ElevenLabs, vision LLM, stock API paid tier) is BLOCKED until user explicitly authorizes.

#### Preconditions and baseline

- Waves 0-8 fully accepted.
- `YT_TEST_MODE=1 python3 -m pytest -q` passes on WCR changeset.

#### Implementation steps

1. Human authorizes seed + video type.
2. Run `produce_db.py run <id>` with WCR flags.
3. Each gate: capture evidence, verify passes.
4. Apply one EDL override.
5. Verify act-scored stems and silence.
6. Present thumbnail + title candidates; select one; publish (if authorized).
7. Archive evidence bundle.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| production | full run, WCR flags | all gates satisfied | manual + evidence |
| invariant | inspect report | new flags present | `produce_db.py inspect <id>` |

#### Acceptance gates

- G1: All WCR rules operational on one production.
- G2: All W1..W8 gates re-verified on post-W8 codebase.
- G3: Full 2,825-test suite passes.
- G4: Evidence archive complete.

#### Audit focus

- Gate-by-gate: verify each gate satisfied by production-produced evidence.
- Budget: verify total cost within cap.
- Any paid authorization explicitly human-approved.

---

## Wave 9 gate

- W9-G1: TKT-901 accepted.
- W9-G2: All W1..W8 gates re-verified.
- W9-G3: Full pytest suite passes.
- W9-G4: Evidence archive complete.

---

## Sprint handoff

On completion:
- Visual variation, b-roll diversification, citation verification, audio craft, EDL, reviewer diversity, pre-publish, budget optimization, lipsync resilience — all operational.
- Programmatic E2E philosophy preserved.
- Paid-call paths behind explicit human authorization.

Residual risks: paid stock API, secondary lipsync provider, multi-model reviewers, flagship budget tier require explicit authorization.

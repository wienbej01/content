# Sprint Plan: Professional Production Quality (PPQ)

Sprint ID: `PPQ-2026-07`
Date: 2026-07-04
Author role: Chief Software Engineer / sprint-plan compiler
Repository: `/home/jacobw/YTchannel`
Branch at planning time: `forensic/use_ai_to_manage_your_time_efficiently-20260620T151859Z`
Source analysis: `docs/CHIEF_ENGINEER_SYSTEM_ENHANCEMENT_REVIEW_20260704.md` and `docs/END_TO_END_PRODUCTION_SYSTEM_TECHNICAL_SPEC_20260704.md`

This is the authoritative sprint plan. Ticket details live in `tickets/WAVE_*.md` in this directory. It is written so a lower-capability model can expand each ticket into a full Karpathy-loop ticket file and a junior coding model can implement one ticket per session. No production code was changed while producing this plan.

Artifact map:

```text
docs/plans/PPQ_SPRINT_20260704/
    PLAN.md                 <- this file: contract, evidence, waves, gates, traceability
    STATE.json              <- single authoritative sprint checkpoint
    EXECUTION_LOG.jsonl     <- append-only execution events
    tickets/WAVE_0.md       <- TKT-001..006  Integrity & operator foundations
    tickets/WAVE_1.md       <- TKT-101..104  Lipsync measurement engine
    tickets/WAVE_2.md       <- TKT-201..204  Vision semantic QA engine
    tickets/WAVE_3.md       <- TKT-301..303  Word-level timing primitive
    tickets/WAVE_4.md       <- TKT-401..407  Graphics professionalization
    tickets/WAVE_5.md       <- TKT-501..503  Grounded b-roll generation
    tickets/WAVE_6.md       <- TKT-601..603  E2E validation & platform loop
    evidence/               <- calibration reports, decision records, run evidence
```

---

## 1. Objective and Outcome Contract

### Objective

Bring the pipeline from "review-only output with unverifiable quality gates" to systemic, repeatable production of professional-level educational YouTube videos with:

1. Publish-grade, machine-verified lipsync on all hero segments.
2. B-roll whose semantic relevance to the script's claims is verified against rendered pixels, not just prompts.
3. Brand-true, animated, overlay-integrated graphics timed to spoken words.

### Required new behavior

- Production code can produce passing `syncnet_offset` evidence from a real face-tracked AV-sync measurement.
- Production code can produce passing `semantic_role_qa` evidence from a real vision-model judgment of sampled frames against the unit's semantic contract.
- Graphics are verified at pixel level (OCR), rendered with brand fonts, animated, and composable as overlays over footage.
- A `word_timing` document (forced alignment) exists per production and drives span boundaries and graphic reveal timing.
- Operators can link reused footage and inspect a full evidence bundle from the CLI.

### Behavior that must remain unchanged

- Fail-closed gate semantics (Gate A content, storyboard, spend, Gate B).
- Sample-exact hero audio slicing and the temporal-edit prohibition on `HERO_SYNC_LOCKED` units (`scripts/production_repo.py:190-251`).
- Local graphics never reach paid providers.
- Test mode (`YT_TEST_MODE=1`) never makes paid calls.
- Artifact registration/hashing and DB-native orchestration contracts.

### Failures that must become impossible

- F1: Test-mode fake evidence (`method: yt_test_mode_fake_provider`, `simulated: true`) satisfying any publish-grade gate in production mode.
- F2: A b-roll clip semantically unrelated to its `narrative_claim` passing all executed production gates.
- F3: A graphic shipping with truncated/overflowed text.
- F4: Two near-identical b-roll concepts passing dedup because `concept_key == shot_id`.

### Architectural invariants (must hold at end of every Wave)

- INV-1: `YT_TEST_MODE=1 python3 -m pytest -q` passes; at minimum the focused suite (`tests/test_storyboard_projection.py tests/test_compile_media_from_canonical_shots.py tests/test_produce_db_orchestrator.py tests/test_llm_call.py tests/test_sonnet_storyboard_wrapper.py`) passes.
- INV-2: No paid provider/LLM/TTS call occurs under `YT_TEST_MODE=1` or in pytest.
- INV-3: Publish-grade evidence writers fail loudly (non-zero / stage blocked) when their measurement backend is unavailable; they never fabricate a pass.
- INV-4: All new evidence is recorded in the `validations` table with validator name, method, and input SHA provenance.
- INV-5: Repository stays runnable after every ticket (no partial feature activation; new stages/paths behind explicit config until their Wave gate).

### Safety and cost restrictions

- Paid calls (ElevenLabs, Higgsfield, paid LLM vision calls at volume) require explicit human authorization; tickets that need them are marked and otherwise report `BLOCKED`.
- No destructive DB migrations; all migrations additive with pre-migration backup (existing mechanism in `scripts/production_db.py`).

---

## 2. Evidence-Based Current State (baseline)

Baseline commands executed 2026-07-04:

| Command | CWD | Exit | Result |
| --- | --- | --- | --- |
| `YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py tests/test_compile_media_from_canonical_shots.py tests/test_produce_db_orchestrator.py tests/test_llm_call.py tests/test_sonnet_storyboard_wrapper.py -q` | repo root | 0 | `104 passed in 12.81s` |
| `git status --porcelain` | repo root | 0 | clean except untracked review doc |

Confirmed findings (`CONFIRMED` by direct code inspection unless marked):

| ID | Finding | Evidence |
| --- | --- | --- |
| CS-1 | No real AV-sync scorer; only RMS-envelope vs whole-frame-diff proxy, `provisional: True`, no face tracking | `scripts/evals/eval_lipsync.py:2-7,193-230,310,319` |
| CS-2 | Only writer of passing `syncnet_offset` evidence is the YT_TEST_MODE fake branch | `scripts/media_service.py:958-988` |
| CS-3 | `lipsync_scoring.py` fail-closed scorer has only `NoModelLoaded`; `eval_syncnet.py` returns `not_run` even with deps | `scripts/lipsync_scoring.py:81`, `scripts/evals/eval_syncnet.py:235-238` |
| CS-4 | Assembly requires per-segment `syncnet_offset` + compensated audio artifact; review-only human acceptance is the only production escape | `scripts/assemble_db.py:479-592,678` |
| CS-5 | Offset compensation is manual (`--offset-ms` operator arg) | `scripts/evals/remux_compensated_hero.py:24-79` |
| CS-6 | Semantic verifier is `DeterministicTestVerifier`; production evidence only via test-mode auto-pass | `scripts/semantic_role_pipeline.py:72-127`, `scripts/media_service.py:1218-1260` |
| CS-7 | `scripts/broll_qa.py` (relevance, duplicates, gibberish) is unwired dead code with `NoVisionModel` default | `scripts/broll_qa.py:49-61,129-316`; no importers |
| CS-8 | Concept dedup vacuous: `concept_key = concept_hash = shot_id`; quota/registration never called | `scripts/storyboard_projection.py:177-178`, `scripts/broll_semantic.py:117-154` |
| CS-9 | Provider prompts are intent-field concatenation; source research unused at compile time | `scripts/produce_db.py:877-942`, `scripts/compile_media_prompts.py:436-451` |
| CS-10 | Only OCR (NO_VISIBLE_TEXT) + ffprobe touch real pixels in production QA | `scripts/media_service.py:831-892` |
| CS-11 | Graphics ship as static 1080p PNGs frame-held via `tpad`; animation system is uncalled brightness-fade stub with dead code | `scripts/assemble.py:1259-1266`, `scripts/render_graphics.py:632-810,786-789` |
| CS-12 | 8 professional templates unreachable from production layout map | `scripts/render_graphics.py:1044-1049,813-827` |
| CS-13 | `overlay_timeline` compositing is schema-complete but never emitted by production manifest | `scripts/assemble.py:454-531`, `scripts/assemble_db.py:872-989` |
| CS-14 | Duplicate unstyled FFmpeg drawtext path can double-render graphic text | `scripts/assemble.py:1034-1076` |
| CS-15 | Brand fonts (`brand/fonts/Inter.ttf`, `PlayfairDisplay.ttf`) never loaded; DejaVu hardcoded with silent PIL-default fallback | `scripts/render_graphics.py:46-55` |
| CS-16 | No word-level timestamps; timing = silencedetect + word-count-proportional allocation; `timing:"on_spoken_line"` never interpreted | `scripts/audio_timing.py:100-130` |
| CS-17 | Local graphic OCR deliberately skipped; `graphic_text_hash` write-only; `text[:120]` hard truncation | `scripts/media_service.py:734-738`, `scripts/render_graphics.py:948,1052` |
| CS-18 | Reused footage lacks operator linking CLI; `generate_media` blocks `reused_asset_unlinked` | spec §15.3, §28.1 |
| CS-19 | Each overlay/drawtext pass is a full re-encode (generational loss) | `scripts/assemble.py:523-528` |
| CS-20 | `still_kenburns` units counted but never rendered; no Ken Burns motion exists (SUPPORTED_INFERENCE: loop handles only `local_graphic`) | `scripts/produce_db.py:1944-1971` |
| CS-21 | `visible_start/end_sample` validated only if set; main compile path never sets them | `scripts/produce_db.py:1157-1185`, `scripts/production_repo.py:241-245` |
| CS-22 | Hero generation plumbing (Seedance 2.0 image+audio conditioning, slice provenance, submission gate) works | `scripts/paid_adapters.py:184-231`, `scripts/slice_continuous_lipsync.py:60-246`, `scripts/media_service.py:114-125` |

UNVERIFIED items to resolve inside tickets (never assume):

- UV-1: Availability of a runnable SyncNet/Wav2Lip-LSE implementation and weights in this environment (TKT-101 discovery).
- UV-2: Whether the Kilo routing layer exposes a vision-capable model profile (TKT-201 discovery step).
- UV-3: Provider CLI support for image conditioning on the b-roll (kling) route (TKT-502 discovery step).
- UV-4: Presence/usability of real hero clips under `outputs/seedance_truth_test_001/` for calibration (TKT-104 precondition).

---

## 3. Architectural Decisions

- AD-1: Build the measurement layer first (sync scorer, vision QA), then the timing primitive, then the creative execution layer. Gates already exist; never weaken a gate to "unblock" output.
- AD-2: New measurement backends plug into existing seams: `SyncModelAdapter` (`scripts/lipsync_scoring.py`), `Verifier` (`scripts/semantic_role_pipeline.py`), `VisionModel` (`scripts/broll_qa.py`). Do not invent parallel frameworks.
- AD-3: Every ML/LLM-backed verifier has a deterministic fixture backend for tests, selected explicitly (env/config), never silently. Production mode with no backend = loud failure (INV-3).
- AD-4: Forced alignment is a new document kind `word_timing` produced by a new stage after `tts`, consumed by `audio_timing`; the legacy proportional allocation remains only as an explicit, logged fallback marked `timing_precision: sentence` vs `word`.
- AD-5: Graphics move to a two-class model: full-frame cards (frameworks, comparisons) and `overlay_timeline` overlays (lower thirds, stats, citations) composited over footage in a single filter-graph pass.
- AD-6: Vision LLM calls route through `scripts/llm_call.py` with a new `vision_qa` profile in `configs/llm_models.yaml`; per-production call/cost caps enforced like provider spend.
- AD-7: No time-based estimates anywhere; tickets bounded by one behavior + one subsystem + focused proof.

---

## 4. Requirement Register

Lipsync:

- R-LS-1: A face-tracked AV-sync scorer runs locally on a video+audio pair and emits `offset_ms`, `confidence`, `face_track_found`.
- R-LS-2: `_qa_hero_lipsync` writes production `syncnet_offset` validations from R-LS-1 output; test-mode fake evidence is rejected by gates outside `YT_TEST_MODE` (F1).
- R-LS-3: Measured offset automatically drives compensation remux and re-verification (no manual `--offset-ms` on the production path).
- R-LS-4: Tiered thresholds (`close_hero`/`medium_hero`/`wide_hero`) calibrated against labeled clips; calibration data and method recorded.
- R-LS-5: `visible_start/end_sample` populated on the main compile path; visible ⊆ generation enforced in practice (CS-21).

B-roll:

- R-BR-1: Sampled frames of every generated b-roll unit are judged by a vision model against `semantic_acceptance_criteria`, `must_show`, `must_avoid`, `narrative_claim`; verdict recorded as `semantic_role_qa` evidence.
- R-BR-2: Vision QA failures route to repair with prompt-revision feedback derived from the model's described content.
- R-BR-3: `concept_key` derives from normalized visual concept; quota/forbidden-concept enforcement runs in `compile_media` (F4).
- R-BR-4: Model-free checks (gibberish/frozen-frame) run in production `qa_media`.
- R-BR-5: Cross-clip near-duplicate detection (perceptual hash) runs at QA.
- R-BR-6: Compile-time prompts include claim-linked source-research anchors.
- R-BR-7: B-roll units with a declared visual anchor can be generated image-to-video from a reference still.
- R-BR-8: A curated asset library (indexed, tagged, licensed) supports reuse; operator CLI links artifacts to reused units.

Graphics:

- R-GFX-1: Renderer uses brand fonts from `brand/fonts/`, fails closed if missing; renders supersampled; native 9x16 layouts exist.
- R-GFX-2: All 12 templates reachable from production specs; duplicate drawtext path removed/gated.
- R-GFX-3: Every rendered graphic OCR-verified against `graphic_text_content`; truncation/overflow fails QA (F3); `graphic_text_hash` verified.
- R-GFX-4: Text auto-fits (shrink-to-fit within bounds); no silent hard truncation.
- R-GFX-5: Graphics >2s are animated (alpha-based element animation); validated by `validate_animation_requirement`.
- R-GFX-6: `overlay_timeline` produced by the production manifest and composited over footage in one encode pass.
- R-GFX-7: `still_kenburns` renders actual motion or the asset type is removed.

Timing:

- R-TIME-1: A forced-alignment stage produces word-level timestamps (`word_timing` document) for the master narration.
- R-TIME-2: Span/beat boundaries derive from measured word boundaries (silence gaps), replacing proportional allocation.
- R-TIME-3: Graphic reveal timing can bind to a specific spoken word (`on_spoken_line` honored).

Operations / E2E:

- R-OPS-1: `produce_db.py link-artifact` safely links reused footage to render units.
- R-OPS-2: `produce_db.py inspect <production_id>` emits a complete evidence bundle.
- R-E2E-1: One full paid seed→publish production completes with all publish-grade gates satisfied by production-produced evidence (zero review-only exemptions on hero units).
- R-E2E-2: Publish uploads to YouTube as a resumable provider subsystem with platform ID capture and AI disclosure.
- R-E2E-3: YouTube analytics ingested and joined to spans/units/shots/claims.

Major risks:

- RISK-1: Sync scorer deps/weights unavailable in environment (UV-1).
- RISK-2: Vision QA cost/latency spiral; rejection-rate spiral raising provider spend.
- RISK-3: Threshold miscalibration blocking everything or passing everything.
- RISK-4: FFmpeg filter-graph complexity for single-pass overlay compositing.
- RISK-5: Forced-alignment tool dependency footprint (torch/whisperX) conflicts.

---

## 5. Wave Structure and Dependency Graph

```text
Wave 0  Integrity & operator foundations        TKT-001..006   deps: none
Wave 1  Lipsync measurement engine              TKT-101..104   deps: W0 (TKT-001)
Wave 2  Vision semantic QA engine               TKT-201..204   deps: W0 (TKT-001,002,004)
Wave 3  Word-level timing primitive             TKT-301..303   deps: W0
Wave 4  Graphics professionalization            TKT-401..407   deps: W0; TKT-406/407 also need W3
Wave 5  Grounded b-roll generation              TKT-501..503   deps: W2, W0 (TKT-005)
Wave 6  E2E validation & platform loop          TKT-601..603   deps: all prior
```

Waves 1, 2, 3 are mutually independent and may run in parallel by separate engineers/agents after Wave 0. Wave 4 tickets 401–405 depend only on Wave 0; 406–407 also need Wave 3. Wave 6 is the sprint exit.

Ticket index (titles):

| Ticket | Title | Class |
| --- | --- | --- |
| TKT-001 | Reject simulated QA evidence outside test mode | ROUTINE |
| TKT-002 | Real concept keys and enforced dedup quota | ROUTINE |
| TKT-003 | Populate visible windows on main compile path | ROUTINE |
| TKT-004 | Wire model-free b-roll technical checks into qa_media | ROUTINE |
| TKT-005 | Operator CLI: link reused footage artifacts | ROUTINE |
| TKT-006 | `inspect` command: unified evidence bundle | ROUTINE |
| TKT-101 | Discovery: select and prove face-tracked AV-sync scorer | REASONING_CRITICAL |
| TKT-102 | Production sync adapter and `syncnet_offset` evidence writer | COMPLEX |
| TKT-103 | Automated measure → compensate → re-measure loop | COMPLEX |
| TKT-104 | Threshold calibration and tier policy | REASONING_CRITICAL |
| TKT-201 | Vision QA profile, frame bundle builder, caps | COMPLEX |
| TKT-202 | Production semantic verifier writing `semantic_role_qa` | COMPLEX |
| TKT-203 | Repair loop prompt-revision feedback | COMPLEX |
| TKT-204 | Cross-clip near-duplicate detection | ROUTINE |
| TKT-301 | Forced-alignment stage producing `word_timing` | COMPLEX |
| TKT-302 | Measured word boundaries drive spans | COMPLEX |
| TKT-303 | Word-anchored graphic timing | ROUTINE |
| TKT-401 | Brand typography, fail-closed fonts, supersampling, 9x16 | ROUTINE |
| TKT-402 | Professional templates reachable; duplicate drawtext removed | ROUTINE |
| TKT-403 | Graphic OCR verification and verified text hash | ROUTINE |
| TKT-404 | Auto-fit text layout (no hard truncation) | ROUTINE |
| TKT-405 | Real animation wired into graphics_compositing | COMPLEX |
| TKT-406 | Production overlay_timeline: graphics over footage, single-pass | COMPLEX |
| TKT-407 | Ken Burns for still units | ROUTINE |
| TKT-501 | Claim-linked research anchors in compile-time prompts | COMPLEX |
| TKT-502 | Reference-image conditioning for anchored b-roll | COMPLEX |
| TKT-503 | Curated asset library index and storyboard citation | COMPLEX |
| TKT-601 | Full paid E2E production run (human authorized) | REASONING_CRITICAL |
| TKT-602 | YouTube publish provider subsystem | COMPLEX |
| TKT-603 | Analytics ingestion and creative attribution join | COMPLEX |

---

## 6. Execution Protocol (applies to every ticket)

Every ticket must pass through three independent agent sessions:

`ENGINEER → AUDITOR → VALIDATOR`

### Engineer session

`LOAD → BASELINE → REPRODUCE → IMPLEMENT → FOCUSED TEST → RECORD`

Rules:

1. One ticket per coding session. Load only: the ticket's section from `tickets/WAVE_*.md`, `STATE.json`, the ticket's listed files, and `AGENTS.md`.
2. BASELINE: run the ticket's baseline commands; record command, cwd, exit code. If baseline does not match "expected current result", stop and report `BLOCKED: <reason>`.
3. REPRODUCE: for defect tickets, write the failing test first; for capability tickets, write the behavior-contract test first (it must fail before implementation).
4. IMPLEMENT the smallest coherent change. No dummy outputs, no permissive fallbacks, no test-only production branches, no weakened assertions.
5. FOCUSED TEST: run the ticket's test matrix, then the sprint invariant suite: `YT_TEST_MODE=1 python3 -m pytest -q` (full), or at minimum the focused 104-test suite plus the ticket's tests.
6. RECORD: append an engineer event to `EXECUTION_LOG.jsonl`. Update `STATE.json` to `ready_for_audit`. Stop — do not begin the next ticket.

### Auditor agent session

`LOAD → AUDIT → REPORT → UPDATE STATE`

The auditor is an independent agent session. It does not modify production code or tests. It may only modify: evidence audit report, `EXECUTION_LOG.jsonl`, `STATE.json`.

Rules:

7. Load: the ticket, `STATE.json`, actual git diff, changed production files, changed tests, and the ticket's audit focus.
8. Run the ticket's focused test matrix independently. Run the sprint invariant suite.
9. Answer the audit questions listed in each ticket's `- Audit steps:` section.
10. Return exactly one verdict: `PASS`, `PASS_WITH_FINDINGS`, `FAIL`, or `BLOCKED`.
11. Write findings to `evidence/<TICKET-ID>-audit.md` with structured fields: finding ID, severity (`CRITICAL|HIGH|MEDIUM|LOW`), file/symbol, violated requirement, concrete evidence, required correction, required regression test.
12. Update `STATE.json`:

    | Verdict | STATE.json status |
    |---------|-------------------|
    | `PASS` | `ready_for_validation` |
    | `PASS_WITH_FINDINGS` (severity ≤ LOW only) | `ready_for_validation_with_findings` |
    | `PASS_WITH_FINDINGS` (severity ≥ MEDIUM) | `audit_failed` — reverts to engineer for repair |
    | `FAIL` | `audit_failed` — reverts to engineer |
    | `BLOCKED` | `blocked` |

13. Append structured auditor event to `EXECUTION_LOG.jsonl`. Stop — do not begin validation.

### Finding reversion rules

14. When audit returns `PASS_WITH_FINDINGS` with ≥ MEDIUM findings, or `FAIL`:
    - The ticket reverts to the engineer with structured outstanding findings from the audit report.
    - Engineer corrects only the remaining delta; adds required regression tests.
    - After repair, re-submit to auditor for re-audit.
    - Maximum three total engineer→audit cycles per ticket (one initial + up to two repair rounds).
    - Stop earlier on genuine blocker or two repairs with no material improvement; then report `BLOCKED`.
15. When `ready_for_validation_with_findings` (LOW-severity only): the validator reviews these findings and may accept with residual risks recorded.

### Validator agent session

`LOAD → VALIDATE → ACCEPT/REJECT → COMMIT`

The validator is an independent agent session. It does not modify production code or tests. It may only modify: validation reports, `EXECUTION_LOG.jsonl`, `STATE.json`, `HANDOFF.md` (Wave/sprint completion only).

Rules:

16. Load: the ticket, `STATE.json`, `evidence/<TICKET-ID>-audit.md`, repository diff, and the ticket's `- Validation steps:`.
17. Independently run all commands in the ticket's test matrix plus the sprint invariant suite.
18. Verify: focused tests pass, broader tests pass, original defect irrereproducible, no silent fallbacks, no unintended file changes, audit findings resolved or properly non-blocking.
19. Write structured validation report to `evidence/<TICKET-ID>-validation.md`.
20. Return exactly one verdict: `PASS`, `FAIL`, or `BLOCKED`.

    | Verdict | STATE.json status | Action |
    |---------|-------------------|--------|
    | `PASS` | `accepted`; add to `accepted_tickets` | Git commit working tree with message `feat(<TICKET-ID>): <title>` |
    | `FAIL` | `validation_failed`; revert to engineer | Structured findings in validation report; must re-audit after repair |
    | `BLOCKED` | `blocked` | Record exact missing dependency, permission, or evidence |

21. ONLY the validator may mark a ticket, Wave, or sprint accepted.
22. After validation PASS: `git add` changed files + evidence reports + STATE.json + EXECUTION_LOG.jsonl; `git commit` with conventional commit message referencing the ticket ID. Stop — the ticket is complete. Update `active_ticket` and `next_ticket` in `STATE.json`.

### Paid calls and safety

23. Paid calls, destructive ops, and production deploys require explicit human authorization; otherwise report `BLOCKED`.

Ticket status vocabulary: `planned | in_progress | ready_for_audit | ready_for_validation | ready_for_validation_with_findings | audit_failed | validation_failed | accepted | blocked`.

`EXECUTION_LOG.jsonl` event shape:

```json
{"ts": "", "ticket": "", "phase": "baseline|implement|audit|repair|validate", "role": "engineer|auditor|validator", "verdict": "", "gates_verified": {}, "commands": [], "exit_codes": [], "files_changed": [], "result": "", "residual_risks": [], "commit": ""}
```

---

## 7. Wave Gates

All gates are binary and observable.

- W0-G1: TKT-001..006 accepted by independent validator.
- W0-G2: `YT_TEST_MODE=1 python3 -m pytest -q` full suite passes.
- W0-G3: A test-mode production run end-to-end (`produce_db.py` in test harness) still completes as before.

- W1-G1: In a production-mode integration harness with the fixture sync backend, a hero unit travels QA → (compensation if needed) → assembly `syncnet_offset` gates with zero simulated evidence and zero review-only exemptions.
- W1-G2: With `SYNC_SCORER_BACKEND=none`, the same harness blocks (fail-closed proof).
- W1-G3: Full pytest suite passes.

- W2-G1: Prod-mode harness: a semantically mismatched fixture clip is auto-rejected, prompt-revised, regenerated (fake provider), re-verified, and assembly's semantic gate is satisfied by production-written evidence only.
- W2-G2: `SEMANTIC_QA_BACKEND=none` blocks publish-grade b-roll (fail-closed proof).
- W2-G3: Full suite passes; vision budget caps demonstrably enforced.

- W3-G1: Test-mode production run produces `word_timing`, word-precision spans, and one resolved graphic anchor, all visible via `inspect`.
- W3-G2: Alignment-absent production path is loud and precision-marked, never silently proportional.
- W3-G3: Full suite passes.

- W4-G1: A test-mode production assembles a deliverable containing: one animated full-frame graphic, one word-anchored overlay over footage, brand fonts (verified by TKT-401 metrics test on an extracted frame), single-pass overlay compositing.
- W4-G2: OCR verification passes on every graphic in that deliverable; a planted truncation fixture fails.
- W4-G3: Full suite passes.

- W5-G1: Test-mode compile shows factual anchors with citation lineage on anchored units; anchored b-roll submits image-conditioned jobs to the fake provider; library-cited assets auto-link.
- W5-G2: Text-risk and spend gates still enforce on anchored prompts and image-conditioned jobs.
- W5-G3: Full suite passes.

- W6-G1 (final): One real paid production completes seed→publish with all publish-grade gates satisfied by production-produced evidence; `inspect` bundle archived under `evidence/`.
- W6-G2: Published video has platform ID recorded and AI disclosure set; analytics snapshot joined to at least span-level attribution.
- W6-G3: Full suite passes; docs updated to match actual behavior.

---

## 8. Final Sprint Acceptance Gates

1. Requested behavior works through a real observable path (W6-G1 run evidence).
2. Confirmed defects (F1–F4) have regression tests that fail on the old behavior.
3. Invalid states fail loudly: backend-absent sync QA, backend-absent semantic QA, missing brand fonts, unresolved graphic anchors, truncated graphics — each has a loud-failure test.
4. No dummy output or silent fallback introduced (audit evidence per ticket; grep gates in TKT-404, TKT-001).
5. Source-of-truth and architecture rules consistent (DB-native authority, adapter seams per AD-2).
6. Existing unrelated behavior did not regress (`YT_TEST_MODE=1 python3 -m pytest -q` green at every Wave gate).
7. Unit, contract, integration, and (Wave 6) end-to-end checks pass.
8. Performance/resource use did not materially regress without acceptance (single-pass compositing measured in TKT-406; QA runtime bounds in TKT-004/204).
9. Documentation and operating commands match actual behavior (spec doc updated in TKT-601 scope).
10. Restart/recovery works: resume mid-wave verified in TKT-103 (idempotency) and TKT-602 (resumable upload).
11. Independent audit and validator evidence exist per ticket in `EXECUTION_LOG.jsonl`.
12. Final repository is buildable, testable, reviewable.

---

## 9. Traceability Matrix

| Requirement / risk | Ticket(s) | Executable proof | Gate |
| --- | --- | --- | --- |
| F1 simulated evidence | TKT-001 | `tests/test_simulated_evidence_rejection.py` | W0-G1 |
| R-BR-3 / F4 dedup | TKT-002 | `tests/test_concept_dedup.py` | W0-G1 |
| R-LS-5 visible windows | TKT-003 | `tests/test_hero_visible_window.py` | W0-G1 |
| R-BR-4 model-free checks | TKT-004 | `tests/test_broll_technical_qa.py` | W0-G1 |
| R-OPS-1 link CLI | TKT-005 | `tests/test_link_artifact_cli.py` | W0-G1 |
| R-OPS-2 inspect | TKT-006 | `tests/test_inspect_production.py` | W0-G1 |
| R-LS-1 / RISK-1 scorer | TKT-101, TKT-102 | spike harness + `tests/test_sync_scorer_adapter.py` | W1-G1/G2 |
| R-LS-2 evidence writer | TKT-102 | prod-mode integration test | W1-G1 |
| R-LS-3 compensation | TKT-103 | `tests/test_offset_compensation_loop.py` | W1-G1 |
| R-LS-4 / RISK-3 calibration | TKT-104 | calibration report + `tests/test_lipsync_policy_calibrated.py` | W1-G1 |
| R-BR-1 / F2 vision QA | TKT-201, TKT-202 | `tests/test_semantic_verifier.py`, `tests/test_semantic_qa_integration.py` | W2-G1/G2 |
| R-BR-2 repair feedback | TKT-203 | `tests/test_semantic_repair.py` | W2-G1 |
| R-BR-5 duplicates | TKT-204 | `tests/test_broll_duplicate.py` | W2-G1 |
| R-TIME-1 / RISK-5 alignment | TKT-301 | `tests/test_word_alignment.py` | W3-G1/G2 |
| R-TIME-2 word spans | TKT-302 | `tests/test_word_boundary_spans.py` | W3-G1 |
| R-TIME-3 anchors | TKT-303 | `tests/test_graphic_anchor.py` | W3-G1 |
| R-GFX-1 brand render | TKT-401 | `tests/test_brand_render.py` | W4-G1 |
| R-GFX-2 templates/drawtext | TKT-402 | `tests/test_template_routing.py`, `tests/test_single_graphic_representation.py` | W4-G1 |
| R-GFX-3 / F3 OCR verify | TKT-403 | `tests/test_graphic_ocr.py` | W4-G2 |
| R-GFX-4 auto-fit | TKT-404 | `tests/test_autofit.py` + grep gate | W4-G2 |
| R-GFX-5 animation | TKT-405 | `tests/test_graphic_animation.py` | W4-G1 |
| R-GFX-6 / RISK-4 overlays | TKT-406 | `tests/test_overlay_singlepass.py` | W4-G1 |
| R-GFX-7 Ken Burns | TKT-407 | `tests/test_kenburns.py` | W4-G1 |
| R-BR-6 anchors in prompts | TKT-501 | `tests/test_prompt_anchors.py` | W5-G1 |
| R-BR-7 / UV-3 image-to-video | TKT-502 | `tests/test_broll_image_conditioning.py` | W5-G1 |
| R-BR-8 asset library | TKT-503 | `tests/test_asset_library.py` | W5-G1 |
| R-E2E-1 paid run | TKT-601 | archived `inspect` bundle + gate evidence | W6-G1 |
| R-E2E-2 upload | TKT-602 | `tests/test_youtube_publish_adapter.py` + authorized runtime proof | W6-G2 |
| R-E2E-3 analytics | TKT-603 | `tests/test_analytics_attribution.py` | W6-G2 |
| RISK-2 cost spiral | TKT-201 (caps), TKT-203 (attempt cap) | budget/attempt-cap tests | W2-G3 |

Every ticket maps to at least one requirement; no orphan tickets.

---

## 10. Major Risks and Blockers

1. RISK-1 (sync scorer availability): TKT-101 is a discovery ticket; if weights/deps are unobtainable, Wave 1 blocks and the sprint continues on Waves 2–4 (independent). Report `BLOCKED: need <exact dependency>`.
2. RISK-2 (cost spiral): hard caps (TKT-201) + semantic-repair attempt cap (TKT-203) + rejection-rate recorded in `cost_events`; review at W5 gate.
3. RISK-3 (miscalibration): thresholds only from measured labeled sets (TKT-104); until calibrated, measured-but-unthresholded units route to review, never auto-pass.
4. RISK-4 (filter-graph complexity): TKT-406 requires command-log assertions and frame-sampling proof; fallback is bounded multi-pass with explicit acceptance of quality cost (documented deviation).
5. RISK-5 (alignment deps): TKT-301 isolates the dependency and keeps a loud, precision-marked fallback path.
6. Paid-run authorization (TKT-601) and YouTube API credentials (TKT-602/603) are human-provided; tickets report `BLOCKED` without them.

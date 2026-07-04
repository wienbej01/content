# Wave 2 — Vision Semantic QA Engine (TKT-201..204)

Sprint: `PPQ-2026-07`. See `../PLAN.md`. Depends on Wave 0 (TKT-001, 002, 004). Goal: rendered b-roll pixels are judged against the unit's semantic contract (CS-6, CS-7, F2); failures feed prompt-revised regeneration.

---

## TKT-201 — Vision QA profile, frame bundle builder, and caps

- Requirements: R-BR-1 (infrastructure), AD-6, UV-2, RISK-2. Class: COMPLEX. Deps: TKT-001. Blocks: TKT-202, TKT-204.
- Observable outcome: (a) `configs/llm_models.yaml` gains a `vision_qa` profile routed through `scripts/llm_call.py` — verify first that the Kilo invocation path supports image inputs; if it cannot, report `BLOCKED` with the exact interface gap; (b) a `build_frame_bundle(artifact_path, n) -> [frame_paths]` utility using the existing `frame_sampling.py` (start/middle/end + scene changes), deterministic given the same file; (c) a per-production vision-call budget with hard cap enforcement analogous to `SmokeConfig` spend caps, persisted as `cost_events` rows (`kind: vision_qa_call`).
- Evidence: routing `scripts/llm_call.py`; sampling `frame_sampling.py` (used by `scripts/semantic_role_pipeline.py:130-270`).
- Scope: config, `scripts/llm_call.py` (vision payload support), frame utility, tests (no real LLM calls — mock at the transport seam). Protected: storyboard-authority model rules in `llm_call.py`.
- Baseline: `python3 scripts/llm_call.py --check-availability` exits 0; grep confirms no `vision_qa` profile exists.
- Steps:
  1. In-ticket discovery: confirm the Kilo invocation path supports image inputs; document findings; BLOCKED if not.
  2. Add profile + payload plumbing.
  3. Frame bundle utility writing sha-named frames under the production assets dir.
  4. Budget counter persisted via cost_events; refusal is a loud error when the cap is reached.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | frame bundle on fixture mp4 (twice) | deterministic N frames, stable hashes across runs | `python3 -m pytest tests/test_frame_bundle.py -q` (new) |
| unit | budget cap reached | further vision calls refused with loud error | `python3 -m pytest tests/test_vision_budget.py -q` (new) |
| contract | vision payload construction (mocked transport) | images + contract fields serialized per documented schema | same |

- Acceptance gates: G1 frame bundle deterministic across two runs (asserted); G2 cap enforcement test passes; G3 no test performs a network/paid call (mocked transport asserted); G4 full suite passes.
- Audit focus: image payload size limits; temp-file cleanup; cap accounting is per-production and survives resume.
- Rollback: revert commit; profile addition is inert without callers.

---

## TKT-202 — Production semantic verifier writing `semantic_role_qa`

- Requirements: R-BR-1, F2. Class: COMPLEX. Deps: TKT-201. Blocks: TKT-203.
- Observable outcome: A production `Verifier` implementation for `scripts/semantic_role_pipeline.py` sends the frame bundle + the unit's `semantic_acceptance_criteria`, `must_show`, `must_avoid`, `narrative_claim`, `visual_role` to the `vision_qa` profile and parses a structured verdict `{claim_supported, must_show_present[], must_avoid_violations[], described_content, confidence}`. `qa_media` invokes it for publish-grade `generated_video` units in production mode and records pass/fail `semantic_role_qa` evidence consumed unchanged by `assemble_db.validate_semantic_role_qa` (`scripts/assemble_db.py:198-269`). Backend selection explicit (`SEMANTIC_QA_BACKEND=vision|fixture|none`); `none` → unit does not pass (INV-3). Test mode keeps existing auto-pass behavior.
- Evidence: verifier seam `scripts/semantic_role_pipeline.py:130-270`; evidence recorder `scripts/semantic_role_qa.py:36-136`; current test-only writer `scripts/media_service.py:1218-1260`.
- Scope: new verifier module, `scripts/media_service.py` QA dispatch, tests with fixture verifier + mocked vision transport. Protected: assembly gate logic; test-mode writer.
- Baseline: production-mode qa_media writes no `semantic_role_qa` evidence today (assert in harness).
- Steps:
  1. Implement the verifier with a strict JSON response schema + one repair-parse retry.
  2. Verdict→pass rule: `claim_supported` true AND no `must_avoid_violations` AND all mandatory `must_show` present AND confidence ≥ documented constant (revisit after E2E).
  3. Failure records the full verdict (needed by TKT-203).
  4. Wire into `run_contract_media_qa` after technical QA passes.
  5. Evidence includes frame hashes + model id.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | fixture verdict: supported, clean | pass evidence written; matches `visual_role` | `python3 -m pytest tests/test_semantic_verifier.py -q` (new) |
| negative | verdict with must_avoid violation | fail evidence; unit `needs_repair` | same |
| negative | backend `none`, prod mode | unit not passed; loud status | same |
| negative | malformed model JSON twice | QA fails loudly (never default-pass) | same |
| integration | prod-mode harness, fixture backend | assembly semantic gate satisfied end-to-end | `python3 -m pytest tests/test_semantic_qa_integration.py -q` (new) |

- Acceptance gates: G1 a semantically mismatched fixture clip is rejected in production mode (F2 regression test); G2 evidence rows satisfy the existing assembly gate without modifying the gate; G3 parse failures never yield pass; G4 full suite passes.
- Audit focus: prompt-injection surface (frame content cannot alter verdict schema handling); verdict schema versioned; per-unit cost bounded by TKT-201 caps.
- Rollback: revert commit; backend default `none` keeps behavior inert.

---

## TKT-203 — Repair loop prompt-revision feedback

- Requirements: R-BR-2, RISK-2. Class: COMPLEX. Deps: TKT-202.
- Observable outcome: When a unit fails semantic QA, the repair lifecycle creates a regeneration whose provider prompt is revised using the verdict — the diff of `described_content` vs intent appended as corrective directives ("previous render showed X; must instead show Y; avoid Z") — stored in the unit's `metadata_json` with revision lineage; bounded to 2 semantic-repair regenerations per unit, then `block_for_manual_review`.
- Evidence: repair lifecycle `media_service.run_repair_lifecycle()`; routing `scripts/media_service.py:1459-1480`; prompt composition `scripts/produce_db.py:877-942`.
- Scope: repair classification + prompt-revision helper + metadata lineage; tests. Protected: spend gate — regenerations still count against provider-job caps (verify, do not bypass).
- Baseline: semantic failures currently have no dedicated repair route.
- Steps:
  1. Failure class `semantic_mismatch`.
  2. `revise_prompt(original, verdict) -> str` — deterministic template, no LLM call.
  3. Attempt counter in metadata.
  4. Regeneration passes back through full QA including vision.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | verdict-driven revision | revised prompt contains must_show and avoid directives; original preserved in lineage | `python3 -m pytest tests/test_semantic_repair.py -q` (new) |
| boundary | third semantic failure | manual-review block; no further submission | same |
| contract | regenerated job counted against provider caps | spend gate math includes it | same |

- Acceptance gates: G1 revision lineage visible in `inspect` output (TKT-006); G2 attempt cap enforced; G3 full suite passes.
- Audit focus: no unbounded spend; prompt revision never strips safety/negative-prompt content.
- Rollback: revert commit.

---

## TKT-204 — Cross-clip near-duplicate detection

- Requirements: R-BR-5. Class: ROUTINE. Deps: TKT-201 (frame bundles), TKT-002.
- Observable outcome: QA computes perceptual hashes (dHash/pHash via PIL — no ML dependency) of sampled frames per generated unit; pairwise similarity above a documented threshold across different units in one production records a `broll_duplicate` validation failure on the later unit and routes to repair with a distinctness directive.
- Evidence: intended-but-dead embedding path `scripts/broll_qa.py:193-256` (this ticket implements the model-free variant instead).
- Scope: hash utility, QA wiring, tests with duplicated/distinct fixture clips. Protected: none.
- Baseline: no duplicate detection runs today (grep).
- Steps:
  1. Perceptual hash utility over the TKT-201 frame bundle.
  2. Pairwise comparison bounded per production (cap pair count; documented).
  3. Failure evidence names the earlier conflicting unit.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | same clip linked to two units | later unit fails with duplicate evidence naming the earlier unit | `python3 -m pytest tests/test_broll_duplicate.py -q` (new) |
| negative | two visually distinct clips | both pass | same |
| boundary | same scene, different crop | documented expected behavior (threshold test) | same |

- Acceptance gates: G1 duplicate fixture detected; G2 distinct fixture not flagged; G3 full suite passes.
- Audit focus: threshold documented and justified; O(n²) pair count bounded.
- Rollback: revert commit.

---

## Wave 2 gate

- W2-G1: Prod-mode harness: a semantically mismatched fixture clip is auto-rejected, prompt-revised, regenerated (fake provider), re-verified, and assembly's semantic gate is satisfied by production-written evidence only.
- W2-G2: `SEMANTIC_QA_BACKEND=none` blocks publish-grade b-roll (fail-closed proof).
- W2-G3: Full suite passes; vision budget caps demonstrably enforced.

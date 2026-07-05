# Wave 5 — Grounded B-roll Generation (TKT-501..503)

Sprint: `PPQ-2026-07`. See `../PLAN.md`. Deps: Wave 2 accepted (relevance gains measurable), Wave 0 (TKT-005). Goal: narrow provider hallucination space at the source — research anchors in prompts, reference-image conditioning, curated asset library (CS-9; spec §28.2).

---

## TKT-501 — Claim-linked research anchors in compile-time prompts

- Requirements: R-BR-6, CS-9. Class: COMPLEX. Deps: Wave 2 accepted. Blocks: TKT-502.
- Observable outcome: `compile_media` resolves each unit's `claim_refs`/`narrative_claim` to the research brief's cited facts (via `source_citations` and the research document) and appends a bounded "FACTUAL ANCHORS" block (dates, names, places, object specifics; token-bounded; sanitized through existing text-risk checks) to `_compose_generation_prompt`; anchors and their citation ids recorded in unit metadata for audit. Claims with no resolvable citation record `anchor_status: unresolved` (visible in `inspect`) — nothing is fabricated.
- Evidence: prompt composition `scripts/produce_db.py:877-942`; research lineage tables (spec §4.2, §7).
- Scope: compile path, research lookup helper; tests with fixture research docs. Protected: provider text-risk gate (anchors must pass it); prompt length limits.
- Baseline: grep proves no research lookup in the compile path; focused suite passes.
- Steps:
  1. Claim → citation resolver over `source_citations` and the active research document.
  2. Anchor block composer with token bound and sanitization.
  3. Metadata recording (`anchors`, `citation_ids`, `anchor_status`).
  4. Negative behavior: unresolved claims warn, never invent.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | unit with claim_ref matching a cited fact | prompt contains anchor block with the fact; metadata records citation id | `python3 -m pytest tests/test_prompt_anchors.py -q` (new) |
| negative | claim with no resolvable citation | `anchor_status: unresolved` recorded; prompt unchanged; no fabricated facts | same |
| negative | wrong-citation pairing (fixture mismatch) | resolver refuses; unresolved status | same |
| contract | anchor block through the text-risk check | no forbidden visible-text risk introduced | same |

- Acceptance gates: G1 anchors present and cited for resolvable claims; G2 nothing fabricated for unresolvable ones; G3 full suite passes.
- Audit focus: prompt bloat control; anchor sanitization; citation-to-claim mismatch prevention.
- Audit steps:
   1. Confirm claim → citation resolver reads `source_citations` and research document correctly.
   2. Verify anchor block is token-bounded and passes text-risk sanitization.
   3. Confirm unresolved claims record `anchor_status: unresolved` and never fabricate facts.
   4. Verify citation-to-claim mismatch is detected and refused.
   5. Run focused tests (`test_prompt_anchors.py`) independently; run invariant suite.
- Validation steps:
   1. Run `python3 -m pytest tests/test_prompt_anchors.py -q` — all passing.
   2. Run the sprint invariant 5-file suite — passing.
   3. Verify resolvable claim produces anchor block with citation id in metadata.
   4. Verify unresolvable claim records `unresolved` status, no fabricated facts.
   5. Verify wrong-citation pairing is refused.
   6. Verify anchor block passes text-risk check.
   7. Write validation report `evidence/TKT-501-validation.md`.
   8. If PASS: update `STATE.json` accepted list, `git commit`.
- Rollback: revert commit; prompts return to prior composition.

---

## TKT-502 — Reference-image conditioning for anchored b-roll

- Requirements: R-BR-7, UV-3. Class: COMPLEX (contains in-ticket discovery of provider CLI capability). Deps: TKT-501, TKT-005.
- Observable outcome: B-roll units whose storyboard shot declares a visual anchor (new optional additive field, e.g. `reference_asset`, naming a library/reused artifact or research-derived still) submit image-to-video with `--image <reference>` on the b-roll provider route, mirroring the hero pattern (`scripts/paid_adapters.py:215-231`) while preserving the I4 invariant (`--audio` remains Seedance-only). Discovery step: if the b-roll model's CLI does not support image conditioning, report `BLOCKED: <exact CLI evidence>` and change nothing.
- Evidence: hero-only conditioning `scripts/paid_adapters.py:215-231`, `scripts/produce_db.py:1108-1112`; archived prior image-to-video path `scripts/archive/kling_tts_lipsync.py.disabled`.
- Scope: adapter argument plumbing, compile-path `image_path` for anchored b-roll, additive schema field; tests with the fake provider. Protected: I4 audio invariant; spend estimation updated if the provider prices image-conditioned jobs differently.
- Baseline: fake-provider submission log for a b-roll unit contains no `--image` (write failing test first).
- Steps:
  1. Discovery: verify the b-roll provider CLI supports image conditioning; record evidence in `../evidence/TKT-502-provider-capability.md`.
  2. Additive storyboard/projection field `reference_asset`; resolution to an artifact path at compile.
  3. Adapter plumbing for `--image` on the b-roll route; assert `--audio` never present for non-hero units.
  4. Loud block when the referenced artifact is missing.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | anchored b-roll unit, fake provider | submitted command includes `--image` with resolved artifact path; no `--audio` | `python3 -m pytest tests/test_broll_image_conditioning.py -q` (new) |
| negative | anchor references a missing artifact | compile/generate blocks loudly | same |
| negative | non-anchored b-roll unit | no `--image`; behavior unchanged | same |
| contract | I4 invariant | `--audio` with a non-Seedance model raises `ProviderAdapterError` (existing behavior retained) | existing adapter tests |

- Acceptance gates: G1 image-conditioned submission proven via fake-provider command log; G2 missing-artifact case blocks; G3 I4 invariant tests still pass; G4 full suite passes.
- Audit focus: reference artifact provenance (sha recorded on the provider job); spend estimate correctness.
- Audit steps:
   1. Confirm discovery note `../evidence/TKT-502-provider-capability.md` exists if CLI capability was verified.
   2. Verify `--image` flag is present in provider submission command for anchored b-roll.
   3. Confirm `--audio` is never present for non-hero (non-Seedance) units (I4 invariant).
   4. Verify missing reference artifact blocks loudly.
   5. Confirm reference artifact sha is recorded on the provider job for provenance audit.
   6. Run focused tests (`test_broll_image_conditioning.py`) independently; run invariant suite.
- Validation steps:
   1. Run `python3 -m pytest tests/test_broll_image_conditioning.py -q` — all passing.
   2. Run the sprint invariant 5-file suite — passing.
   3. Verify anchored b-roll submits `--image` with resolved path; no `--audio`.
   4. Verify missing artifact blocks loudly.
   5. Verify non-anchored b-roll unchanged (no `--image`, behavior preserved).
   6. Verify I4 invariant tests still pass.
   7. Write validation report `evidence/TKT-502-validation.md`.
   8. If PASS: update `STATE.json` accepted list, `git commit`.
- Rollback: revert commit; additive field is inert.

---

## TKT-503 — Curated asset library index and storyboard citation

- Requirements: R-BR-8. Class: COMPLEX. Deps: TKT-005.
- Observable outcome: A library index (new table or additive migration, e.g. `asset_library`: id, uri, sha256, media kind, tags, description, license, provenance) with CLI verbs `library add|list|search`; the storyboard director prompt and schema gain an optional additive field letting shots cite a library asset id; projection resolves cited assets to `asset_type=reused` units and auto-links the artifact (via the TKT-005 mechanism) so `generate_media` does not block. Uncited/unknown library ids fail projection loudly.
- Evidence: reuse path exists (`storyboard_projection._is_reused_footage()` lines 131-142; spec §15.3); linking primitives from TKT-005.
- Scope: additive migration `db/migrations/`, library CLI (in `scripts/produce_db.py` or `scripts/asset_library.py`), storyboard schema additive field, projection resolution; tests. Protected: artifact immutability rules; no license-less asset may be added without an explicit `--license` value.
- Baseline: no library table exists (sqlite schema dump proof); focused suite passes.
- Steps:
  1. Additive migration with SHA-immutability conventions matching existing migrations.
  2. CLI verbs with validation (file exists, probeable, license required).
  3. Storyboard schema additive `library_asset_id` on shots; director prompt documentation line.
  4. Projection: cited id → reused unit + auto-link; unknown id → loud failure.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| integration (subprocess) | `library add` then `search` | asset indexed with sha + license; searchable by tag | `python3 -m pytest tests/test_asset_library.py -q` (new) |
| unit | shot citing a known library id | projected reused unit auto-linked; `generate_media` does not block | same |
| negative | unknown library id in shot | projection fails naming the id | same |
| negative | `library add` without license | exit non-zero; nothing indexed | same |
| regression | productions with no library citations | unchanged | orchestrator suite |

- Acceptance gates: G1 cited asset flows storyboard → reused unit → linked artifact in a test-mode run; G2 unknown id and missing license are loud; G3 migration applies cleanly to a copy of an existing DB (backup/restore mechanism exercised); G4 full suite passes.
- Audit focus: license/provenance enforcement; migration safety; no silent substitution when a cited asset file is missing on disk.
- Audit steps:
   1. Confirm additive migration creates `asset_library` table with SHA-immutability conventions.
   2. Verify `library add` validates file exists, is probeable, and requires `--license`.
   3. Verify `library search` returns correct results by tag.
   4. Confirm storyboard `library_asset_id` field resolves to reused unit + auto-link.
   5. Verify unknown library id fails projection loudly.
   6. Run focused tests (`test_asset_library.py`) independently; run invariant suite.
- Validation steps:
   1. Run `python3 -m pytest tests/test_asset_library.py -q` — all passing.
   2. Run the sprint invariant 5-file suite — passing.
   3. Verify `library add` + `search` workflow indexes asset with sha + license.
   4. Verify known library id → projected reused unit auto-linked.
   5. Verify unknown library id → projection fails naming the id.
   6. Verify `library add` without `--license` → non-zero exit.
   7. Verify migration applies cleanly to DB copy (backup/restore).
   8. Write validation report `evidence/TKT-503-validation.md`.
   9. If PASS: update `STATE.json` accepted list, `git commit`.
- Rollback: additive migration; revert commit leaves the table unused (documented).

---

## Wave 5 gate

- W5-G1: Test-mode compile shows factual anchors with citation lineage on anchored units; anchored b-roll submits image-conditioned jobs to the fake provider; library-cited assets auto-link.
- W5-G2: Text-risk and spend gates still enforce on anchored prompts and image-conditioned jobs.
- W5-G3: Full suite passes.

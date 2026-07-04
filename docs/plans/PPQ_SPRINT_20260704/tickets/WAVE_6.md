# Wave 6 — E2E Validation and Platform Loop (TKT-601..603)

Sprint: `PPQ-2026-07`. See `../PLAN.md`. Deps: all prior Waves accepted. Goal: prove the whole system on one real paid production, then close the platform loop (upload + analytics attribution). TKT-601 is the sprint exit criterion (R-E2E-1).

---

## TKT-601 — Full paid E2E production run (human authorized)

- Requirements: R-E2E-1; validates F1–F4 closures in reality. Class: REASONING_CRITICAL. Deps: Waves 0–5 accepted. HUMAN AUTHORIZATION REQUIRED for all paid calls (ElevenLabs, Higgsfield, vision QA volume); without it report `BLOCKED: paid run authorization required`.
- Observable outcome: One production runs seed → research → script → gates → storyboard → TTS → alignment → compile → spend gate → generation → QA (real sync scorer, real vision QA) → repair → graphics → assembly → final QA → Gate B → publish state, with:
  - zero simulated evidence anywhere (TKT-001 enforcement observed live);
  - zero review-only exemptions on hero units (real `syncnet_offset` passes);
  - every publish-grade b-roll unit carrying a production-written `semantic_role_qa` pass;
  - every graphic OCR-verified; at least one animated graphic and one word-anchored overlay in the deliverable;
  - the full `inspect --json` bundle archived to `docs/plans/PPQ_SPRINT_20260704/evidence/TKT-601-run-<production_id>.json`.
- Evidence basis: spec §28.7 (full paid E2E still needed); all prior Wave gates.
- Scope: NO production code changes expected. Permitted: configuration, operator commands, gate approvals by the human, and defect filing. Any defect found → file a repair ticket (do not hot-fix inside this ticket); the run restarts from the affected stage after the repair ticket lands (restartability is the point).
- Preconditions: `ELEVENLABS_API_KEY` set; Higgsfield authenticated with capacity; Sonnet 5 and vision profile available via Kilo; `SYNC_SCORER_BACKEND=real`; `SEMANTIC_QA_BACKEND=vision`; `PRODUCTION_DB_PATH` set to the intended DB; spend caps configured and human-approved.
- Baseline (readiness checklist, all must exit 0):

```bash
python3 scripts/production_db.py check
python3 scripts/llm_call.py --check-availability
YT_TEST_MODE=1 python3 -m pytest -q
ffmpeg -version && ffprobe -version
npm ls @higgsfield/cli
```

- Steps:
  1. Human selects seed and format; create production.
  2. Run stages with human gate approvals at gate_a_content, gate_storyboard, gate_a_spend, gate_b_review.
  3. At each gate, archive `inspect` output to evidence/.
  4. Record every blocker, repair cycle, and cost event.
  5. On completion, archive the final bundle + deliverable QA report.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| e2e runtime | full run | Gate B pass; deliverable `published` state; evidence bundle archived | `python3 scripts/produce_db.py run <id>` (+ approvals) |
| contract | evidence audit over the bundle | zero rows with `simulated: true` or `yt_test_mode` method; hero units all have real `syncnet_offset` passes; b-roll all have `semantic_role_qa` passes | audit script or manual query, recorded in evidence/ |
| negative (spot) | one deliberately mis-prompted b-roll unit (human-chosen) | rejected by vision QA and repaired via prompt revision within the attempt cap | observed in run evidence |

- Acceptance gates: G1 run completes with all publish-grade gates satisfied by production-produced evidence; G2 evidence audit query returns zero simulated/review-only satisfactions; G3 total cost within the approved cap (cost_events sum); G4 archived bundle exists and is complete.
- Audit focus: honesty of the evidence audit; any manual intervention documented; restart behavior after any mid-run repair.
- Rollback: none needed (run produces artifacts and records only); a failed run leaves the ledger consistent by design.

---

## TKT-602 — YouTube publish provider subsystem

- Requirements: R-E2E-2. Class: COMPLEX. Deps: TKT-601 (a publishable deliverable exists); human-provided YouTube API credentials (else `BLOCKED: YouTube OAuth credentials required`).
- Observable outcome: `publish` uploads the deliverable to YouTube as a provider boundary consistent with the existing adapter pattern (`scripts/paid_adapters.py`): resumable upload with persisted upload state (survives interruption and resumes), platform video ID recorded in `publications`, AI-disclosure flag set on the upload, title/description/tags/thumbnail taken from deliverable metadata, and failure recovery via the provider-job state machine. Current DB-only publish behavior remains as the explicit `--record-only` mode.
- Evidence: current publish records state only (spec §22); provider-job pattern (spec §4.2, §15.1-15.2).
- Scope: new adapter (e.g. `YouTubeUploadAdapter` in `scripts/paid_adapters.py` or `scripts/youtube_adapter.py`), publish invoker changes, `publications` row population, credential handling via env (never committed); tests mock the API transport entirely. Protected: Gate B requirements (upload only after pass); secrets hygiene (no tokens in DB payloads or logs).
- Baseline: publish stage sets DB state only (code observation); no YouTube client dependency present.
- Steps:
  1. Adapter with resumable-upload session persistence in `provider_jobs` (request/response payloads sanitized of tokens).
  2. AI-disclosure and metadata mapping documented in the module docstring.
  3. Interruption recovery: resuming a production re-attaches to the stored upload session or verifies completion server-side before creating a new one (idempotency key = deliverable sha).
  4. `--record-only` preserves current behavior for non-upload workflows.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit (mocked API) | successful upload | platform ID stored in `publications`; deliverable `published`; AI disclosure flag in the request | `python3 -m pytest tests/test_youtube_publish_adapter.py -q` (new) |
| negative (mocked) | interrupted mid-upload then resume | same upload session resumed; no duplicate video created | same |
| negative (mocked) | Gate B not passed | publish refuses; exit non-zero | same |
| contract | secrets hygiene | no token material in DB rows or logs (asserted) | same |
| runtime (authorized) | real upload of the TKT-601 deliverable | video visible on the channel; platform ID recorded | human-authorized execution, evidence archived |

- Acceptance gates: G1 mocked matrix passes; G2 idempotency proven (double-run creates one video in mocked tests); G3 secrets-hygiene assertion passes; G4 authorized real upload evidence archived (or ticket ends `BLOCKED` at this gate with mocked gates green).
- Audit focus: OAuth token storage; retry/backoff behavior; partial-upload cleanup; disclosure compliance.
- Rollback: `--record-only` mode preserves prior behavior; revert commit restores it as default.

---

## TKT-603 — Analytics ingestion and creative attribution join

- Requirements: R-E2E-3. Class: COMPLEX. Deps: TKT-602 (platform ID exists); human-provided YouTube Analytics API access (else `BLOCKED`).
- Observable outcome: The `analytics` stage ingests real YouTube metrics (retention curve, CTR, watch time, APV) for published videos into `metric_snapshots`, and a join module attributes retention timestamps to `timeline_spans` → `render_units` → `creative_beats`/shots → claims using existing lineage (no new identifiers needed — verify; if a lineage gap is found, file it as a follow-up migration ticket rather than widening this one). Output: a per-production attribution report (`analytics attribution <production_id>`) listing retention deltas per span with its visual role, asset type, and claim.
- Evidence: analytics currently records production metadata only (spec §23); lineage tables (spec §4.2-4.3); spec §29.9 poses exactly this join question.
- Scope: analytics invoker, ingestion adapter (mocked in tests), join/report module; tests with fixture analytics payloads. Protected: append-only `metric_snapshots` semantics.
- Baseline: analytics snapshot contains only internal counts (code observation).
- Steps:
  1. Ingestion adapter (API transport mocked in tests; real calls only when authorized).
  2. Retention-curve → span mapping using span start/end ms against video duration.
  3. Attribution report with deterministic ordering; `--json` output.
  4. Snapshot provenance: platform ID, fetch time, API version.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | fixture retention curve over known spans | correct per-span deltas; joined to unit/shot/claim | `python3 -m pytest tests/test_analytics_attribution.py -q` (new) |
| negative | production with no publication | attribution refuses with clear error | same |
| contract | snapshot rows | append-only; provenance fields present | same |
| runtime (authorized) | real ingestion for the TKT-602 video | snapshot + attribution report archived to evidence/ | human-authorized execution |

- Acceptance gates: G1 fixture attribution exact (asserted values); G2 no-publication case is loud; G3 authorized real ingestion evidence archived (or `BLOCKED` at this gate with mocked gates green); G4 full suite passes.
- Audit focus: timestamp alignment correctness (retention bins vs span ms); API quota handling; no PII beyond platform-provided aggregates.
- Rollback: revert commit; snapshots already written remain valid append-only history.

---

## Wave 6 / Final sprint gate

- W6-G1 (final): One real paid production completes seed→publish with all publish-grade gates satisfied by production-produced evidence; `inspect` bundle archived under `evidence/`.
- W6-G2: Published video has a platform ID recorded and AI disclosure set; analytics snapshot joined to at least span-level attribution.
- W6-G3: Full suite passes; `docs/END_TO_END_PRODUCTION_SYSTEM_TECHNICAL_SPEC_*.md` updated to match actual behavior (doc update executed within TKT-601/602/603 completion evidence).

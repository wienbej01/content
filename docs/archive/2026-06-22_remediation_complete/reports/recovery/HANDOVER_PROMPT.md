# Handover Prompt — AI Influencer YouTube Production System Recovery

## Continue Recovery Sprints S8–S9 in Claude CLI (GLM 5.2)

You are continuing a multi-sprint recovery program for an automated AI-influencer YouTube production pipeline. Sprints 0–7 are **COMPLETE and committed**. Sprints 8–9 remain. This prompt gives you everything needed to continue.

---

## 1. Repository State

```
Repository:  wienbej01/content (local path: /home/jacobw/YTchannel)
Branch:      fix/flagship-001-end-to-end-recovery
Base SHA:    68f3ee5498611d2a18c1a58a6f05a8f94eee4b0f  (original program base; do not modify prior migrations)
Committed:   6792b70 (Sprints S4-S7) on top of 3ec64bd (S0-S3). Working tree CLEAN.
Uncommitted: (none — S4-S7 committed 2026-06-18)
```

**S4–S7 is already committed (commit `6792b70`, 2026-06-18).** Do NOT re-commit. Contract tests were verified green (104 passed) before that commit. Working tree is clean.

**Session checkpoint (2026-06-18) — where we are now:**
- Sprints S0–S7: COMPLETE and committed (`3ec64bd` = S0-S3, `6792b70` = S4-S7).
- Baseline verification (full `pytest -q` + the 6 CI gate scripts in §3) was STARTED but NOT completed before a restart — **re-run it first** to re-confirm green before any S8 work.
- Next work item: **Sprint 8 (§4). S8-T01** = define/extend the 45-second deterministic fixture.
- Sprints 8–9 remain. Sprint 9 is PAID and is blocked until Sprint 8's exit gate passes AND the user explicitly approves the S9 plan + hard cap (§6, §11). No paid calls have ever been made.

**First action on resume:** verify the baseline (§3 commands), then begin S8-T01. No commit is pending.

---

## 2. Completed Sprints Summary

### Sprint 0 (COMPLETE — committed in 3ec64bd)
- Fixed 20 failing tests → 0 (D-002 through D-012)
- Release interlock hardened (`release_guard.py`): env-injectable paths, LEGACY_FILE_AUTHORITY blocker, wired into `produce_db.run_production`
- Test taxonomy dirs created (`media_integration/`, `crash_recovery/`, `real_provider/`)
- `pytest-timeout` added (timeout=300s); `pytest.ini` created
- `check_test_quality.py` meta-gate for placeholder PASS pattern

### Sprint 1 (COMPLETE — committed in 3ec64bd)
- Removed legacy JSON fallback reads from `invoke_write_script` / `invoke_review_script` (fail-closed)
- Enhanced `check_forbidden_file_reads.py` with AST dynamic-path detection
- Pre-migration backup + failed-migration rollback + restore in `production_db.migrate()`
- Migration 006: partial unique index `one_active_revision_per_kind`
- Replaced JSON-content LIKE join in `tts_service` with direct `metadata_json` query

### Sprint 2 (COMPLETE — committed in 3ec64bd)
- Fixed stage graph dependency inversion: storyboard no longer depends on audio_timing
- Canonical order: research → write_script → review_script → gate_a_content → storyboard → review_storyboard → tts → audio_timing → reconcile_timing → compile_media → gate_a_spend → generate_media → qa_media → repair → graphics_compositing → assemble → qa_final → gate_b_review → publish → analytics
- Added `requires_committed_output` flag to `StageDefinition`; LegacyAdapter verifies committed output
- 5 invalidation tests + 2 approval gate tests

### Sprint 3 (COMPLETE — committed in 3ec64bd)
- Expanded `ProviderAdapter` ABC: `prepare_request`, `estimate_cost`, `submit`, `get_external_id`, `poll`, `download`, `validate_response`, `record_actual_cost`, `cancel_if_supported`
- `FakeProviderAdapter` generates REAL valid FFmpeg MP4/WAV media (not arbitrary bytes) with controllable failure/offset/corruption/timeout
- 3 crash-injection tests (no duplicate submission after acceptance)
- Spend enforcement: `submit_provider_job` rejects without `gate_a_spend` pass

### Sprint 4 (COMPLETE — uncommitted)
- Verified TTS master provenance: script_revision, voice, model, settings, fingerprint, provider_request_id, sample_rate, channels, sample_count, duration, cost
- Checksum mismatch rejection (corrupt master → RuntimeError, not reuse)
- `timeline_utils.py` integer-sample timebase (MASTER_SAMPLE_RATE=48000); TimeInterval immutable, rejects negative/inverse
- `slice_hero_units` extracts exact speech, generates true silence via `anullsrc`, concatenates — RMS < -60dB in padding
- Hero render groups: deterministic ID from SHA-256(members + slice_sha + prompt_rev)

### Sprint 5 (COMPLETE — uncommitted)
- `validate_broll_semantics` enforces 8 required fields (visual_function, narrative_claim, information_to_show, viewer_takeaway, required_action, distinctness_requirement, semantic_acceptance_criteria, concept_key)
- `concept_memory` table UNIQUE(production_id, concept_hash) prevents duplicate visuals
- `FORBIDDEN_CHEAP_CONCEPTS`: laptop, notebook, coffee_shop, office_worker_typing, city_skyline_generic
- `route_render_mode`: text-bearing → deterministic_graphic/post_composite, never generated_video
- `vagueness_lint` rejects vague prompts

### Sprint 6 (COMPLETE — uncommitted)
- `register_artifact` rejects corrupt media for media kinds via ffprobe
- Lipsync fail-closed (R6-001): `NoModelLoaded` → REVIEW_REQUIRED, score=0.0, NEVER PASS
- Real models registerable via `register_sync_model`; evidence stores video/audio SHA + model info
- `validate_safe_boundaries` uses face detector; without detector → review_required (never pass)
- Selective repair: `route_change_request` creates structured CR; `invoke_repair` blocks assembly on open CRs; unaffected units preserved

### Sprint 7 (COMPLETE — uncommitted)
- Fixed duplicate `_check_filter_names` in `ffmpeg_validator.py`
- Added minterpolate, freeze, settb to FORBIDDEN_FILTERS; -stream_loop to FORBIDDEN_FLAGS
- Assembly DTO built exclusively from DB (no JSON fallback)
- Master narration referenced exactly once; provider diagnostic audio tagged ineligible
- Final QA evidence bound to deliverable SHA

---

## 3. Current Test State

```
Total tests collected: 1040
Contract tests (tests/contracts/): 104 passed, 0 failed
Full suite: ~930+ passed, 0 failed (last full run was 926 passed after S3)
```

**Key test files and what they cover:**
- `tests/contracts/` — 11 files covering S1–S7 named tests (104 tests)
- `tests/test_assemble.py` — 17 real FFmpeg assembly tests
- `tests/test_assemble_lb202.py` — 8 master-narration-once tests
- `tests/test_sprint3_stage_runner.py` — 23 stage graph/invalidation tests
- `tests/test_produce_db_orchestrator.py` — 9 orchestrator tests
- `tests/test_sprint6_media_service.py` — 16 provider/QA/repair tests
- `tests/test_tts_lb200.py` — 6 TTS master reuse tests
- `tests/test_provider_fingerprint_lb400.py` — 10 fingerprint tests
- `tests/test_release_guard.py` — 10 release interlock tests
- `tests/e2e/test_full_fixture.py` — 5 E2E fixture tests
- `tests/e2e/test_crash_matrix.py` — 6 crash matrix tests

**CI gates (all pass):**
```bash
python3 tools/check_forbidden_file_reads.py      # detects dynamic JSON reads
python3 tools/check_forbidden_beat_id_lookups.py
python3 tools/check_release_placeholders.py
python3 tools/check_direct_db_writes.py
python3 tools/check_test_quality.py              # placeholder PASS detection
python3 scripts/release_guard.py status          # ready:true, blockers:[]
```

**Run tests:**
```bash
python3 -m pytest -q                              # full suite (~6 min)
python3 -m pytest tests/contracts/ -q             # contract tests only (~12s)
YT_TEST_MODE=1 python3 -m pytest tests/e2e/ -q   # E2E tests (need YT_TEST_MODE)
```

---

## 4. Remaining Work: Sprint 8 — Full Local 45-Second E2E

### S8-T01 — Define the deterministic 45-second fixture
The fixture must include:
- ~45 seconds total
- One approved topic seed
- One hook
- One complete short script
- One immutable master narration
- At least 2 hero lipsync units
- At least 2 B-roll units with different semantic functions
- One hero → B-roll → hero continuity case
- One deterministic graphic with exact readable text
- One post-composited screen or document
- Captions
- Music bed
- Final 16:9 output

**Existing E2E tests to build on:** `tests/e2e/test_full_fixture.py` already has 5 tests (test_full_fixture_slices, test_broll_semantic_rejection, test_semantic_broll_accepted, test_duplicate_concept_rejected, test_final_deliverable_assembly). These may need extension to cover the full 45-second scenario.

### S8-T02 — Execute local E2E with test providers
Run from: clean checkout, clean database, empty project directory, no legacy JSON, test-provider mode. Execute every stage through final approval. No manual file editing.

**Key entry point:** `scripts/produce_db.py` has `run_production(production_id)` which walks the stage graph. Use `YT_TEST_MODE=1` for test providers.

### S8-T03 — Delete projections and resume
After a completed run: delete all exported JSON and temporary projections, resume/status the production, prove no authoritative input is missing, rerun a downstream invalidation scenario.

### S8-T04 — Complete crash matrix
Inject crashes at every boundary:
```
after script commit
after TTS provider acceptance
after master write
after slice write
after provider submission
after external ID
after download
after artifact registration
after QA failure
during repair resolution
during assembly
after final file write
before deliverable registration
after final QA
before approval
```
Prove: no duplicate paid-equivalent work, no stale artifact reuse, no orphan active state, correct resume point.

**Existing crash tests:** `tests/e2e/test_crash_matrix.py` has 6 tests. May need extension to cover all 15 boundaries.

### S8-T05 — Local release candidate validation
Independent validation: check out exact SHA, create clean DB, run migrations, run all suites, run full 45-second local production, inspect DB, inspect artifact SHAs, inspect FFmpeg commands, inspect final audio provenance, view the final video, issue PASS or BLOCKED.

### Sprint 8 Exit Gate
```
all automated suites PASS
full local 45-second production PASS
crash matrix PASS
zero legacy authority
zero production stubs
zero fake-media artifacts
zero unresolved repairs
final output approved locally
```
**Only after this gate may Sprint 9 (paid test) begin.**

---

## 5. Remaining Work: Sprint 9 — Controlled Paid 45-Second Provider Test

### S9-T01 — Produce paid-test plan
Before ANY paid request, present: exact 45-second script, storyboard, render plan, provider models, number of TTS/hero/B-roll requests, duration per request, estimated cost per request, estimated total, proposed hard cap, retry policy, stop conditions, artifact destinations, required human approvals.

**No paid call until the user explicitly approves the plan and hard cap.**

### S9-T02 — Lock paid-test inputs
Freeze and hash: script revision, storyboard revision, render plan, master request, hero slices, prompts, references, provider parameters, cost estimate. Create spend approval bound to the exact render-plan SHA.

### S9-T03 — Execute one paid production
Rules: One 45-second production only. No automatic unapproved regeneration. Stop on first failed paid request. Record every external job ID. Record actual cost. Preserve raw provider responses. Validate every downloaded artifact. Run same QA and repair logic. If repair requires another paid request, stop and request explicit approval.

### S9-T04 — Independent paid-run audit
Audit: approval binding, fingerprinting, request payload, external IDs, retries, downloaded bytes, costs, QA evidence, final narration, FFmpeg operations, final deliverable.

### S9-T05 — Final validation and release decision
Validate: actual 45-second output, correct James presentation, acceptable lipsync, no neighbouring speech, no provider narration in final mix, relevant B-roll, no repetitive laptop/notebook filler, exact deterministic text, no frozen or blank media, music and graphics present, captions aligned, final technical QA passes, actual spend within cap, all evidence current.

Final decision: GO / CONDITIONAL GO / NO-GO / BLOCKED.

---

## 6. Non-Negotiable Financial Rule

```
No paid testing until Sprint 8 exit gate passes.
No ElevenLabs / Higgsfield / Seedance / Kling / Wan paid requests.
No paid LLM requests initiated by the pipeline.
No automatic paid retry.
```

All development and validation before S9 must use:
- deterministic local authoring fixtures
- valid deterministic audio fixtures (real WAV via FFmpeg)
- valid deterministic video fixtures (real MP4 via FFmpeg)
- test-only provider adapters (`FakeProviderAdapter` in YT_TEST_MODE=1)
- real SQLite, real FFmpeg/FFprobe, real filesystem artifacts, real checksums

---

## 7. Critical Architecture Context

### Stage Graph (corrected in S2)
```
research → write_script → review_script → gate_a_content → storyboard →
review_storyboard → tts → audio_timing → reconcile_timing → compile_media →
gate_a_spend → generate_media → qa_media → repair → graphics_compositing →
assemble → qa_final → gate_b_review → publish → analytics
```

### Key Files
- `scripts/produce_db.py` — orchestrator; `STAGE_INVOKERS` dict maps stage names to invoker functions; `run_production()` walks the graph
- `scripts/stage_runner.py` — `STAGE_REGISTRY` (StageDefinition dataclass), `run_stage()`, `LegacyAdapter`, `invalidate_document_descendants()`
- `scripts/production_db.py` — `migrate()` (with backup/rollback), `connect()` (FK=ON), `transaction()`
- `scripts/authoring_service.py` — `save_script()`, `save_storyboard()`, `request_approval()`, `record_approval_decision()`
- `scripts/tts_service.py` — `record_tts_artifact()` (checksum mismatch rejection), `compile_render_plan()`
- `scripts/media_service.py` — `submit_provider_job()` (requires spend approval), `complete_provider_job()`, `route_change_request()`
- `scripts/provider_adapter.py` — `ProviderAdapter` ABC, `FakeProviderAdapter` (real FFmpeg media), `validate_downloaded_artifact()`
- `scripts/paid_adapters.py` — `HiggsfieldSeedanceAdapter`, `ElevenLabsAdapter` (real adapters with estimate_cost)
- `scripts/lipsync_scoring.py` — fail-closed: `NoModelLoaded` → REVIEW_REQUIRED, never PASS; `register_sync_model()` for real models
- `scripts/safe_boundary_qa.py` — `validate_safe_boundaries()` (face detector; without → review_required)
- `scripts/slice_continuous_lipsync.py` — `slice_hero_units()` (exact speech + anullsrc silence)
- `scripts/assemble.py` — `_is_hero_lipsync()` helper, `process_segment()`, per-shot B-roll path
- `scripts/ffmpeg_validator.py` — `validate_ffmpeg_command()` (rejects atempo/loop/reverse/minterpolate/trim; fail-closed for hero)
- `scripts/assembly_dto.py` — `build_hero_assembly_dto()` (DB-only, no JSON fallback)
- `scripts/release_guard.py` — `require_production_ready()`, `assess_release_readiness()` (env-injectable for testing)
- `scripts/broll_semantic.py` — `validate_broll_semantics()`, `route_render_mode()`, `check_concept_quota()`
- `scripts/timeline_utils.py` — `MASTER_SAMPLE_RATE=48000`, `TimeInterval`, `ms_to_samples()`, `samples_to_ms()`

### Database
- Production DB: `db/production.db` (gitignored)
- Migrations: `db/migrations/001-006_*.sql` (tracked)
- `PRAGMA foreign_keys=ON` on all connections (production_db, clip_db, content_db)
- 30+ tables: productions, document_revisions, render_units, artifacts, provider_jobs, validations, change_requests, approvals, cost_events, etc.

### Test Mode
- `YT_TEST_MODE=1` enables `FakeProviderAdapter` and auto-approves gates
- `PYTEST_CURRENT_TEST` set during pytest also bypasses release guard
- `PRODUCTION_DB_PATH` env var overrides DB path for test isolation
- `_db._db_path_override` module variable for programmatic override

---

## 8. Defects Status

All 12 defects (D-001 through D-012) identified in Sprint 0 are FIXED:
- D-001: legacy JSON fallback removed (S1-T02); dynamic-read CI gate strengthened
- D-002: release_guard tests injectable (S0-T02)
- D-003: hero temporal guard via `_is_hero_lipsync` helper (S0 + S7-T02)
- D-004: timing drift cross-correlation fixed (S0)
- D-005: assembly manifest validation fixed (S0)
- D-006: TTS master checksum mismatch rejection (S0)
- D-007: migration backup/rollback/restore (S1-T03)
- D-008: FK on all connections (S0)
- D-009: fingerprint includes negative_prompt + model_version (S0)
- D-010: lipsync fail-closed, no PASS without real model (S6-T03)
- D-011: pytest-timeout added (S0-T03)
- D-012: local E2E fixed via hero-policy fix (S0)

---

## 9. Known Limitations / Deferred Items

1. **Legacy CLI entry points** (`run_episode.py`, `slice_continuous_lipsync.slice_hero_from_master`, `reconcile_duration.py`) still read JSON files. These are NOT on the DB-native stage graph and are allowlisted. Migration/deprecation is future work.
2. **Cross-correlation in `timing_drift.py`** is O(N·max_lag) pure-Python (~150s for the drift suite). Correctness is fixed; FFT optimization is future work.
3. **Most legacy tests** still live at `tests/` root unclassified into taxonomy dirs. Physical reclassification is cosmetic and deferred.
4. **No real AV-sync lipsync model** is integrated — `NoModelLoaded` returns REVIEW_REQUIRED. A real SyncNet-class model can be registered via `register_sync_model()` when available. The fail-closed design ensures no false PASS.
5. **No real face detector** is integrated — `NoDetectorLoaded` returns review_required. Same fail-closed pattern.

---

## 10. Exact Commands to Continue

```bash
# 1. Commit S4-S7 work first
cd /home/jacobw/YTchannel
git add scripts/ffmpeg_validator.py tests/contracts/ reports/recovery/S4/ reports/recovery/S5/ reports/recovery/S6/ reports/recovery/S7/ reports/recovery/PROGRAM_STATUS.md
git commit -m "feat: recovery sprints S4-S7 — master narration, B-roll text policy, media/lipsync QA, assembly"

# 2. Verify current state
python3 -m pytest tests/contracts/ -q                    # should be 104 passed
python3 tools/check_forbidden_file_reads.py              # should PASS
python3 scripts/release_guard.py status                  # should be ready:true

# 3. Start Sprint 8
# Read the existing E2E tests to understand the fixture pattern:
cat tests/e2e/test_full_fixture.py
cat tests/e2e/test_crash_matrix.py

# 4. For S8-T01/T02: extend test_full_fixture.py or create a new test that:
#    - Sets up a 45-second production with 2+ hero units, 2+ B-roll units, graphics, music
#    - Runs the full pipeline via produce_db.run_production() in YT_TEST_MODE
#    - Asserts the final deliverable is a valid 45-second 16:9 video

# 5. For S8-T04: extend test_crash_matrix.py to cover all 15 crash boundaries

# 6. Run full suite to verify
python3 -m pytest -q
```

---

## 11. Program Rules (Non-Negotiable)

1. No silent fallback
2. No production dummy or fabricated media
3. No display label as relational identity
4. No stage success without committed output evidence
5. No artifact validity without file existence, FFprobe success, and live SHA match
6. No validation accepted for a different artifact SHA
7. No approval accepted for a stale subject SHA
8. No provider submission without current spend approval
9. No automatic paid retry
10. No provider audio as final narration
11. No hero speed change, loop, freeze, reverse, interpolation, or trim through active speech
12. No adjacent speech in hero padding
13. No meaningful readable text delegated to a generative video model
14. No B-roll without an informational function
15. No production fake-provider selection
16. No `assert True` placeholder tests
17. No broad `except Exception: pass` in critical paths
18. No test claiming DB integration while mocking the database connection
19. No test claiming FFmpeg integration while mocking FFmpeg
20. No modification of previously applied migrations (additive only)
21. Every external effect must be idempotent and crash recoverable
22. Report uncertainty as `BLOCKED: <reason>`

---

## 12. Reports to Maintain

Continue updating these files as you complete S8 and S9:
- `reports/recovery/PROGRAM_STATUS.md` — sprint progress table
- `reports/recovery/DEFECT_LEDGER.md` — defect status
- `reports/recovery/TEST_MATRIX.md` — test inventory
- `reports/recovery/PAID_TEST_READINESS.md` — create before S9
- `reports/recovery/S8/` — engineer/auditor/validator reports
- `reports/recovery/S9/` — engineer/auditor/validator reports

Every ticket report must contain: ticket ID, agent, objective, base SHA, result SHA, files inspected, files changed, implementation summary, tests added, exact commands, test results, database effects, artifact effects, known limitations, rollback, BLOCKED conditions.

---

## 13. Immediate Next Steps

1. **Verify green baseline** — re-run `python3 -m pytest -q` + the 6 CI gate scripts (§3). S4–S7 is already committed (`6792b70`); the prior session's baseline run was interrupted before restart, so re-confirm green first.
2. _(S4–S7 commit: DONE at `6792b70`. Sprint 8 work starts at item 3.)_
3. **Sprint 8-T01**: Define/extend the 45-second deterministic fixture
4. **Sprint 8-T02**: Execute local E2E with test providers
5. **Sprint 8-T03**: Delete projections and resume
6. **Sprint 8-T04**: Complete crash matrix (15 boundaries)
7. **Sprint 8-T05**: Independent validation
8. **Sprint 8 exit gate** → only then begin Sprint 9
9. **Sprint 9**: Paid test (requires explicit human approval of plan + hard cap)

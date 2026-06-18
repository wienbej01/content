# Sprint 0 — Baseline Report (Ticket S0-T01)

**Owner:** Agent 0 — Chief Software Architect / Program Director
**Type:** Read-only verification. No code changed.
**Generated:** 2026-06-17

---

## 1. Repository and Branch

| Field | Value |
|---|---|
| Repository | `wienbej01/content` (origin → https://github.com/wienbej01/content.git) |
| Target branch (program spec) | `fix/flagship-001-remediation` |
| Recovery branch (program spec) | `fix/flagship-001-end-to-end-recovery` |
| Local branch (checked out) | `fix/flagship-001-end-to-end-recovery` |
| Local HEAD (recovery) | `68f3ee5498611d2a18c1a58a6f05a8f94eee4b0f` |
| Remote HEAD `origin/fix/flagship-001-remediation` | `68f3ee5498611d2a18c1a58a6f05a8f94eee4b0f` |
| Heads match (recovery base == remote remediation) | **YES** |
| Merge-base (recovery ↔ remediation) | `68f3ee5` (no commits beyond base) |
| Local `fix/flagship-001-remediation` | `6b3bfe8` — **STALE** (1 commit behind remote `68f3ee5`) |
| `origin/fix/flagship-001-end-to-end-recovery` | does not exist on remote (local-only recovery branch) |

**Base SHA for all Sprint 0 work:** `68f3ee5498611d2a18c1a58a6f05a8f94eee4b0f`

## 2. Worktree Status

- `git status --short`: only untracked report files under `reports/recovery/` (prior interrupted session).
  - `reports/recovery/00_BASELINE.md` (pre-existing, reviewed and updated in place per human decision)
  - `reports/recovery/PROGRAM_STATUS.md` (pre-existing, reviewed and updated in place)
- No staged/modified tracked files. No stashes.
- **Human decision recorded:** keep/update prior report files in place; do not discard.

## 3. Environment

| Component | Version |
|---|---|
| Python | 3.13.7 |
| FFmpeg | 7.1.1-1ubuntu4.2 |
| FFprobe | 7.1.1-1ubuntu4.2 |
| pytest | 9.0.3 |
| pytest-timeout | **NOT installed** (no per-test timeout enforcement) |
| `package-lock.json` (npm/Higgsfield) | present |
| `requirements.lock` | present |

## 4. Database Files (filesystem)

- `db/production.db` (production ledger)
- `db/clips.db` (clip store)
- `db/test_migrate.db`, `db/test_produce_db.db` (test artifacts)
- **Tracked DB files:** none. `db/*.db` are gitignored; only `db/migrations/*.sql` are tracked. ✅ S0-T03 "remove tracked runtime DB" already satisfied at git level.

## 5. Migrations

Tracked migrations (forward-only, applied via `production_db.migrate()`):
- `001_production_ledger.sql`
- `002_lipsync_policies.sql`
- `003_hero_slicing.sql`
- `004_schema_enforcement.sql`
- `005_broll_semantic.sql`

Migration policy in code: `schema_migrations` table records `sha256`; `migrate()` raises `RuntimeError` if an already-applied migration's content changed (checksum immutability). No executable `down`/rollback path — rollback exists only as commented reference text in 004/005. See DEFECT_LEDGER D-007.

## 6. Fresh-DB Migration Proof

Executed against a clean empty DB (`/tmp/kilo/baseline.db`):

```
python3 scripts/production_db.py migrate   → ok (db path returned)
PRAGMA foreign_keys (via production_db.connect)  → 1   (ON)
PRAGMA integrity_check                           → ok
PRAGMA foreign_key_check                         → []  (no violations)
PRAGMA journal_mode                              → wal
```

Tables created (30): productions, content_items, document_revisions, document_dependencies, creative_beats, script_segments, render_units, hero_render_groups, hero_group_members, hero_covered_intervals, timeline_spans, artifacts, artifact_dependencies, provider_jobs, jobs, outbox_messages, cost_events, validations, change_requests, approvals/approval_requests, deliverables, publications, experiments, metric_snapshots, stage_runs, production_events, config_snapshots, source_citations, concept_memory, schema_migrations.

## 7. Module Import Proof

All 44 live production modules import cleanly under Python 3.13.7 (0 failures):
`production_db, produce_db, release_guard, stage_runner, canonical_master, lipsync_scoring, provider_adapter, paid_adapters, provider_fingerprint, artifact_fingerprint, assemble, assemble_db, assembly_dto, ffmpeg_validator, broll_semantic, broll_cutaway, broll_qa, shot_router, authoring_service, production_storyboard, direct_storyboard, tts, tts_service, media_service, generate_media, compile_media_prompts, render_graphics, audio_timing, audio_alignment, audio_qa, slice_continuous_lipsync, hero_grouping, speech_boundary_qa, safe_boundary_qa, qa_media, qa_lipsync, qa_final, repair_routing, gates, review, publish_service, clip_db, content_db, production_repo`.

## 8. Test Suite Result (current branch, base SHA)

Command: `python3 -m pytest -q --tb=no -p no:cacheprovider`

| Metric | Count |
|---|---|
| collected | 925 |
| passed | 901 |
| **failed** | **20** |
| skipped | 1 |
| xfailed | 1 |
| xpassed | 2 |
| warnings | 11 |
| duration | 332–335 s (~5.5 min) |

**Note:** full run exceeds 5 minutes and one test spawned a long-running child subprocess (`repair_storyboard_beats.py`) observed mid-run. No `pytest-timeout` is installed, so a hung test could stall the suite indefinitely. See DEFECT_LEDGER.

### Failure clusters (20)

| Cluster | Count | Tests | Characterization |
|---|---|---|---|
| release_guard credibility | 4 | `test_release_guard.py::test_blocked_with_placeholder_scorer`, `test_blocked_with_fake_provider`, `test_fake_rejected_outside_test_mode`, `test_status_lists_all_blockers` | Tests expect blockers but `release_guard` scans hardcoded production paths; test fixtures cannot trigger blockers. Guard reports `ready:true` (production is clean) but tests cannot prove the guard works. **Test-design defect.** |
| timing drift | 5 | `test_timing_drift_lb402.py` (5 of class) | `perfect_alignment_passes` returns `'fail'` — real logic defect in `timing_drift.py` analysis/correlation. |
| assembly | 6 | `test_assemble.py` (master narration, trim, provenance, segment timing) + `test_assemble_lb202` | Manifest validation failures (`missing 'words'`), master-narration-once rules, FFmpeg filter errors (`No such filter: ''`). Mix of fixture staleness and real defects. |
| hero temporal guard | 2 | `test_hero_temporal_edit_guard.py` | `process_segment` raises `ValueError: could not convert string to float: ''` and FFmpeg `Filter not found` instead of emitting `BLOCKED: HERO_TEMPORAL_EDIT_FORBIDDEN`. **Guard not firing.** |
| TTS master reuse | 1 | `test_tts_lb200::test_checksum_mismatch_invalidates_master` | Master reuse/invalidation defect. |
| local E2E | 1 | `test_pipeline_local_e2e::test_valid_pipeline_passes` | Broad E2E assertion failure. |

Full per-test list in `DEFECT_LEDGER.md`.

## 9. CI Guard Tools (all PASS at base SHA)

```
tools/check_forbidden_file_reads.py        → PASS  (but only catches literal-string reads; bypassable — see D-001)
tools/check_forbidden_beat_id_lookups.py   → PASS
tools/check_release_placeholders.py        → PASS
tools/check_direct_db_writes.py            → PASS
tools/check_test_quality.py                → PASS
scripts/release_guard.py status            → {"ready": true, "blockers": []}
```

## 10. Corrected Classification of Provisional Forensic Findings

Each prior-audit hypothesis is classified by **proven evidence on this branch**, not by default assumptions. See `DEFECT_LEDGER.md` for detail.

| # | Hypothesis | Classification | Basis |
|---|---|---|---|
| 1 | legacy JSON may remain authoritative | **PARTIALLY_PROVEN** | Production DB is core authority; but legacy JSON wrappers remain (`slice_hero_from_master` reads `media_plan.json`/`beat_timing_map.json`; `run_episode.py`/`produce_db.py` read/write `script.json`; `compile_media_prompts` emits `media_plan.json`). File-read CI gate only catches literal-string `open`/`Path().read_text()` and has an allowlist; dynamic path construction bypasses it. |
| 2 | provider execution may be simulated/incompletely verified | **PARTIALLY_PROVEN** | `release_guard` clean; `paid_adapters.py` + `provider_adapter.py` exist; test/real separation present. Runtime proof that the REAL adapter is selected in production (vs test) and that a real HTTP request is issued is **not yet proven** — deferred to Sprint 3. |
| 3 | lipsync scoring may be placeholder/fallback | **CONTRADICTED** (placeholder) / **MISSING** (real model) | No 0.85/0.90 placeholder. Code is fail-closed: `NoModelLoaded` returns `REVIEW_REQUIRED`, never `PASS`. BUT no real AV-sync model is registered, so lipsync can never PASS. Placeholder claim contradicted; real-model integration missing (S6-T03). |
| 4 | tests rely too heavily on mocking | **PARTIALLY_PROVEN** | `check_test_quality` passes, but `release_guard` tests cannot trigger blockers (hardcoded paths) and 20 tests fail on real FFmpeg/fixture issues. Credibility gap. |
| 5 | foreign-key enforcement inconsistent | **PARTIALLY_PROVEN** | `production_db.connect()` sets `PRAGMA foreign_keys=ON` (proven at runtime, fk=1, no violations). BUT `clip_db.py` and `content_db.py` use raw `sqlite3.connect()` **without** enabling foreign_keys — separate stores with inconsistent enforcement. |
| 6 | provider idempotency keys omit meaningful inputs | **PROVEN_CODE (partial gap)** | `provider_fingerprint.generate_hero_request_fingerprint` includes most inputs but OMITS `negative_prompt` and `model_version` (only `model`); uses `prompt_hash` not `prompt_revision_sha`. Real gap → S3-T03. |
| 7 | migration rollback incomplete | **PARTIALLY_PROVEN** | Forward-only; checksum immutability enforced. No executable `down` path; rollback only as commented reference. Pre-migration backup / failed-migration rollback / restore not implemented. |
| 8 | hero temporal locking incomplete | **PROVEN_DEFECT** | `test_hero_temporal_edit_guard` (2) fails: guard does not reject hero temporal edits; it errors on empty-string parsing / FFmpeg filter issues instead of emitting the BLOCKED sentinel. `ffmpeg_validator.py` exists but runtime enforcement in `assemble.process_segment` is non-functional. |
| 9 | text-policy enforcement stops at prompt generation | **PARTIALLY_PROVEN** | `shot_router`/`render_graphics` infra exists; runtime enforcement at render/assembly unverified. Deferred to Sprint 5. |
| 10 | silence padding needs runtime verification | **PROVEN_CODE + PROVEN_TEST (byte-level pending)** | `slice_continuous_lipsync` generates true digital silence via `anullsrc` (re-encode, never `-c copy`); speech extracted sample-exact. `test_speech_boundary_qa_lb600` passes. Byte-level silence proof across full fixture matrix pending S4-T03. |

## 11. Provisional Finding Status Legend

```
PROVEN_CODE / PROVEN_TEST / PROVEN_RUNTIME / PROVEN_REAL_PROVIDER
PARTIALLY_PROVEN
CONTRADICTED
MISSING
BLOCKED: <reason>
```

## 12. Baseline Reproducibility

- Branch/SHA verified and reproducible: **YES**
- Fresh-DB migration reproducible: **YES**
- Test suite reproducible: **YES** (20 failed / 901 passed stable across 2 runs, 332–335 s)
- Every provisional finding classified: **YES**
- Code changed: **NO** (read-only ticket)

## 13. Sprint 0 Validator Gate (target)

```
clean DB migration succeeds              → MET (S0-T01 proof)
release interlock blocks production      → NOT YET MET (S0-T02 pending; tests broken)
test taxonomy exists                     → PARTIAL (dirs: unit/contracts/e2e/integration; no media_integration/crash_recovery dirs)
test-quality gates pass                  → PARTIAL (check_test_quality passes; 20 real failures)
all current defects explicitly recorded  → MET (this sprint, DEFECT_LEDGER.md)
```

# Rectification Implementation Plan — Sprints R0 + R1

**Source audit:** `~/ai_influencer_codebase_rectification_sprint_plan.md`
**Branch:** `fix/flagship-001-remediation`
**Scope this cycle:** Sprint R0 (Safety Freeze & Test Credibility) + Sprint R1 (Restore DB-Native Orchestrator)
**Governance artifacts:** Coder reports only — `reports/remediation/rectification/<TICKET-ID>/coder_report.md`
**Placeholder policy:** fail-closed (placeholders never return PASS; real ML models deferred to R6)

---

## 1. Context

An external audit found the branch **not production-ready**. The dominant pattern is *new helper modules + migrations + mocked tests ≠ live orchestrator integration*. The session wrap-up claimed Sprints 4–6 complete and the repo production-ready; the code contradicts that.

The critical claims were **independently re-verified against the current code** before planning. Summary of verification:

| # | Audit claim | Verdict | Evidence |
|---|---|---|---|
| 1 | `produce_db.py` imports deleted `produce.py` functions | **TRUE** | `produce_db.py:260,268` (`step_storyboard_create`, `step_storyboard_review_loop`); `produce.py` deleted in `c784867` |
| 2 | TTS service called with obsolete signature | **TRUE** | `produce_db.py:191-198` passes `voice_config=`; real sig needs `voice_id, model, voice_settings, request_fingerprint` (`tts_service.py:28-39`) |
| 3 | Reads legacy JSON fallbacks | **TRUE** | `produce_db.py:84,120,127,172,183,217,264,272` |
| 4 | Invalid stage order | **FALSE** | `STAGE_INVOKERS` matches `STAGE_REGISTRY` (`stage_runner.py:39-57`); execution gated on `depends_on` |
| 5 | Selects nonexistent `timeline_spans.narration_text` | **TRUE** | `produce_db.py:282`; schema has only `narration_text_sha256` (`001_production_ledger.sql:198`) |
| 6 | Human gates auto-approved | **TRUE** | `produce_db.py:157-159, 346-348, 695-707` |
| 7 | Simulated provider execution | **TRUE** | `produce_db.py:373-397` writes `b"stubbed video content"` |
| A | "Silence padding" copies adjacent master speech | **TRUE** | `slice_continuous_lipsync.py:100-101,107-108` widens `-ss/-t` into master |
| B | Lipsync scorer is a fixed-PASS placeholder | **TRUE** | `lipsync_scoring.py:120-127` → 0.85/0.90/offset 0 on any audio energy |
| C | Hero slicing uses MP3 stream-copy (not sample-accurate) | **TRUE** | `slice_continuous_lipsync.py:108` `-c copy` |
| D | Safe-boundary QA substitutes audio energy for vision | **TRUE** | `safe_boundary_qa.py:106-107,122-124` |
| E | Repair routing SQL incompatible with schema | **TRUE** | `repair_routing.py:33-46` omits NOT NULL `change_type`/`requested_by_stage`; `:113-118` writes nonexistent `resolution` (schema: `resolution_json`) |
| F | Assembly mixes `keep_lipsync` + `HERO_SYNC_LOCKED` | **PARTIAL** | `assemble.py:73,422,491,580-603` mix both + per-shot narration slices; `assemble_db.py` mixes nothing |

**Infrastructure gaps verified:** root `test.db` is git-tracked; `.gitignore` has no `*.db` rule; 3 of 5 validator tools missing (`check_release_placeholders.py`, `check_direct_db_writes.py`, `check_test_quality.py`); no `tests/{contracts,integration,e2e}` dirs; no `requirements.lock`; no `.github/workflows`; `production_db.py` migrate subcommand is named `init` not `migrate`; two `assert True` no-ops at `tests/test_repair_routing_lb603.py:135,145`.

**Governing rule (`.kiro/rules/no-hacks.md`):** fix the system; never hand-edit intermediate JSON/DB rows to mask a bug.

---

## 2. Existing primitives to reuse (do not rewrite)

| Need | Reuse | Location |
|---|---|---|
| DB-native storyboard save/read | `save_storyboard()`, `get_storyboard()`, `get_creative_beats()` | `authoring_service.py:168,227,231` |
| Real approvals (writes `approval_requests` + outbox) | `request_approval()`, `record_approval_decision()`, `get_approval()`, `is_approved()` | `authoring_service.py:248-382` |
| TTS provenance + idempotent reuse | `record_tts_artifact()` | `tts_service.py:28` |
| Provider fingerprint | `provider_fingerprint` helper | `scripts/provider_fingerprint.py` |
| Render-plan compile + reconcile | `compile_render_plan()`, `reconcile_storyboard_with_timing()` | `tts_service.py:281,224` |
| Active script revision id | `get_active_script_revision_id()`, `get_script_segments()` | `authoring_service.py:135,151` |
| CI-gate AST pattern to copy | `check_forbidden_file_reads.py` (AST walk + ALLOWLIST + `sys.exit(1)`) | `tools/check_forbidden_file_reads.py` |
| Blockers surfacing pattern | `blockers()` | `production_db.py:714` |

---

## 3. Sprint R0 — Safety Freeze & Test Credibility

### R0-001 — Production safety interlock — **BLOCKER**
New `scripts/release_guard.py`:
- `assess_release_readiness() -> {ready: bool, blockers: [{code, detail, location}]}`. Detects, on the live path: placeholder lipsync scorer, simulated/stubbed provider, auto-approved gates, deleted-`produce.py` import, master-range padding slicer, publish/analytics stubs.
- `require_production_ready()` → raises `RuntimeError("BLOCKED: PRODUCTION_RELEASE_INVARIANTS_UNMET")` unless ready.
- Fake/simulated providers allowed **only** when `YT_TEST_MODE=1` (or pytest marker); never in production.
- CLI `python3 scripts/release_guard.py status` → machine-readable blocker JSON, non-zero exit when blocked.
- Wire `require_production_ready()` into `produce_db.run_production` before any billable stage (`tts`, `generate_media`) unless test mode.

**Tests** (`tests/test_release_guard.py`): blocked w/ placeholder scorer; blocked w/ fake provider; fake accepted in test mode only; auto-approval blocks production; `status` lists every blocker.

### R0-002 — Reproduce B001/B008 contamination defects
New `tests/integration/test_defect_reproduction.py` + a deterministic fixture builder (ffmpeg `sine`+`anullsrc` tone-marked master: speech regions separated by true-silence gaps):
- adjacent-speech beat slice from `slice_continuous_lipsync` contains out-of-interval tone → contamination present (**`xfail` until R3**).
- placeholder `lipsync_scoring` returns PASS on a deliberately offset fixture (documents R6 bug).
- assembly does not lay one global master (documents R5 bug).
Red-now / green-after regression anchors, explicitly marked.

### R0-003 — Test-suite credibility
- `git rm --cached test.db`; add `*.db` + `*.sqlite*` to `.gitignore` (preserve `!db/migrations/*.sql`).
- Replace the two `assert True` no-ops (`tests/test_repair_routing_lb603.py:135,145`) with real schema-conformance assertions, or `xfail` tied to R6-004 while `repair_routing.py` stays broken.
- Create `tests/{unit,contracts,integration,e2e}/` with package init + conftest; document the suite-split convention (no forced moves of existing files).
- New CI-gate tools (mirror `check_forbidden_file_reads.py`):
  - `tools/check_release_placeholders.py` — fail on `assert True`, fixed-score PASS scorers, `simulated`/`stubbed` provider markers on release path.
  - `tools/check_direct_db_writes.py` — fail on direct `INSERT/UPDATE` into constrained tables (`render_units`, `change_requests`, `approval_requests`) outside repository services.
  - `tools/check_test_quality.py` — fail on empty tests, unconditional asserts, all-SQL-mocked DB-compat tests.
- `.github/workflows/ci.yml` — migrate-from-zero + gate tools + `pytest` on push/PR.
- `requirements.lock` — pin actually-imported deps (pyyaml + test deps).

**Sprint R0 exit:** interlock active; current defects reproducible; test-quality gates active; no runtime DB tracked.

---

## 4. Sprint R1 — Restore the DB-Native Orchestrator

### R1-001 — Stage graph + storyboard lifecycle
- Rewrite `invoke_storyboard`/`invoke_review_storyboard` (`produce_db.py:259-272`) to use a DB-native storyboard step + `authoring_service.save_storyboard()`; delete both `from produce import …` lines. Headless fallback: deterministically derive beats from `get_script_segments()` and persist via `save_storyboard` (no JSON authority).
- Remove storyboard JSON fallback in `invoke_audio_timing` (`:216-218`); hard-fail if no DB storyboard.
- Require an approved storyboard revision before `audio_timing`/`tts`.
- Add a registry test asserting semantic prerequisites (storyboard before timing; approval before downstream).

**Tests:** clean production reaches storyboard; approved storyboard exists before timing; deleted legacy import absent; missing approval blocks downstream; changed storyboard invalidates timing/render plan.

### R1-002 — TTS invoker contract
Rewrite `invoke_tts` (`produce_db.py:162-200`):
- Load voice/model/settings from `configs/james/model_routing.yaml` (versioned), not hardcoded `voice_config`.
- Compute `request_fingerprint` (via `provider_fingerprint`) **before** the call; pass real signature `record_tts_artifact(voice_id=, model=, voice_settings=, request_fingerprint=)`.
- Consume active script revision from DB (`get_active_script_revision_id`); remove `script.json` fallback (`:172-177,183`) and the `"legacy_fallback"` revision id.
- Crash-safe idempotency via existing reuse path in `record_tts_artifact`.

**Tests** (`tests/contracts/test_tts_invoker.py`): no `script.json` needed; exact retry no dup spend; script/voice change invalidates reuse; damaged master not reused.

### R1-003 — Compile-media query + policy output
In `invoke_compile_media` (`produce_db.py:275-…`):
- Remove `ts.narration_text` from SELECT (`:282`); read `narration_text_sha256` only; join narration text from script segments if required.
- Require reconciled creative beats (`reconcile_storyboard_with_timing` first; block on unmatched spans).
- Emit **new** audio/text policy vocabulary (not legacy `baked_in`/`strip` at `:304-309`) — e.g. `HERO_SYNC_LOCKED` / `narration_overlay` / `silent`.
- Compute nonzero estimated cost; supersede old render units; bind plan to input revision hashes.

**Tests** (`tests/contracts/test_compile_media.py`): clean-migration compile succeeds; legacy policy rejected; unmatched spans block; paid plan has nonzero estimate; replan invalidates old units.

### R1-004 — Real approval gates
- `invoke_gate_a_content` (`:157-159`): `request_approval(gate="gate_a_content", subject=script+storyboard SHA)`; pause (non-advancing pending) unless `is_approved`; never auto-pass in production.
- `invoke_gate_a_spend` (`:346-348`): bind to render-plan SHA + amount.
- `invoke_gate_b_review` (`:695-707`): bind to deliverable SHA + final QA; remove `actor="stubbed_orchestrator"` auto-pass.
- Decision injection: `produce_db.py approve <production> <gate> --pass/--fail`; `YT_TEST_MODE` auto-decision only in test mode.

### Supporting: migrate CLI alias
Add `migrate` subcommand alias to `production_db.py` (`:775`) so the validator baseline (`production_db.py migrate`) works; keep `init` as alias.

**Sprint R1 exit:** a clean no-provider run (`YT_TEST_MODE=1`) advances research → … → `gate_a_spend` and pauses pending, with zero legacy-JSON authority reads (verified by `check_forbidden_file_reads.py`).

---

## 5. Coder report format (per ticket)

```
Ticket / Coder status / Files changed / Tests added /
Exact commands / Results / Remaining risks / Rollback /
BLOCKED conditions / Commit SHA
```
Screenshots and narrative summaries are not sufficient evidence.

---

## 6. Verification

```bash
# clean DB, migrate from zero
rm -f db/validation.db && export PRODUCTION_DB_PATH="$PWD/db/validation.db"
python3 scripts/production_db.py migrate            # new alias

# R0 interlock
python3 scripts/release_guard.py status             # lists blockers, exit != 0
python3 -m pytest tests/test_release_guard.py -q

# R0 credibility gates
python3 tools/check_forbidden_file_reads.py
python3 tools/check_release_placeholders.py
python3 tools/check_direct_db_writes.py
python3 tools/check_test_quality.py
git ls-files | grep -c '\.db$'                      # -> 0

# R1 orchestrator reaches spend approval, no provider call, no JSON authority
YT_TEST_MODE=1 python3 scripts/produce_db.py run "test seed" --format short --project r1_smoke
#   expect: pauses at gate_a_spend pending

python3 -m pytest -q
python3 -m pytest tests/contracts -q
```

---

## 7. Out of scope (later sprints)

R2 (constrained migrations, repository-only writes, media probe), R3 (canonical master audio + **true-silence slicer** — the real contamination fix), R4 (provider adapter + real timing drift), R5 (single master-audio spine assembly), R6 (real audiovisual QA + repair-routing rebuild), R7–R9 (semantic B-roll), R10 (E2E/crash matrix + forbidden-behavior CI), R11 (paid-provider smoke + legacy retirement). The R0 interlock keeps production **blocked** until these land.

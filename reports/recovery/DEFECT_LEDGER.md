# Defect Ledger — Recovery Program

Living ledger of proven defects and open questions. Each defect is traceable to a Sprint/ticket.
Statuses: `OPEN`, `IN_TRIAGE`, `FIXED`, `VERIFIED`, `WONTFIX`.
Severity: `BLOCKER`, `HIGH`, `MEDIUM`, `LOW`.

---

## Proven Defects (from Sprint 0 baseline)

### D-001 — Legacy JSON authority partially remains + CI gate bypassable
- **Severity:** HIGH
- **Hypothesis ref:** #1
- **Status:** OPEN (Sprint 1 — S1-T01/S1-T02)
- **Evidence:** `scripts/slice_continuous_lipsync.py:330` `slice_hero_from_master` reads `media_plan.json` + `beat_timing_map.json` as authoritative and writes `media_plan.json` back. `scripts/run_episode.py:123,128,157` and `scripts/produce_db.py:105,122,155,213` read/write `script.json`. `scripts/compile_media_prompts.py:928` emits `media_plan.json`.
- **Gate weakness:** `tools/check_forbidden_file_reads.py` only inspects AST `open("literal")` / `Path("literal").read_text()` calls and maintains an allowlist. Dynamic path construction (`project_dir / "media_plan.json"`) bypasses detection.
- **Fix direction:** enforce single DB authority; add CI gate that detects dynamic JSON reads (not merely literal filenames).

### D-002 — release_guard tests cannot trigger blockers (test credibility)
- **Severity:** HIGH
- **Hypothesis ref:** #4
- **Status:** FIXED (S0-T02; verified)
- **Evidence:** `scripts/release_guard.py` scans hardcoded module paths (`LIPSYNC_SCORING`, `PRODUCE_DB`). Tests in `tests/test_release_guard.py` construct fixture files expecting blockers, but the guard ignores fixtures and scans the real (clean) production files → `assessment["ready"]==True`, tests assert-fail (4 failures).
- **Fix direction:** make guard injectable/parameterizable over target paths so tests can prove each blocker code; or have tests monkeypatch the module path constants.

### D-003 — Hero temporal guard not firing (PROVEN_DEFECT)
- **Severity:** BLOCKER
- **Hypothesis ref:** #8
- **Status:** FIXED (S0; _is_hero_lipsync helper; verified)
- **Evidence:** `tests/unit/test_hero_temporal_edit_guard.py` (2 failures). `process_segment` in `scripts/assemble.py` raises `ValueError: could not convert string to float: ''` and FFmpeg `No such filter: ''` instead of emitting `BLOCKED: HERO_TEMPORAL_EDIT_FORBIDDEN`. The structured FFmpeg-operation validator (`ffmpeg_validator.py`) is not enforced on the runtime hero path.
- **Fix direction:** wire `ffmpeg_validator` into `process_segment`; reject speed/atempo/setpts/loop/reverse/freeze/interp/trim-through-speech; fail closed on unknown temporal ops.

### D-004 — Timing drift analysis returns fail for perfect alignment
- **Severity:** HIGH
- **Hypothesis ref:** (audio/timing integrity)
- **Status:** FIXED (S0; cross-correlation/boundary/padding; verified)
- **Evidence:** `tests/test_timing_drift_lb402.py` (5 failures). `test_perfect_alignment_passes` gets `evidence["pass_fail_result"]=="fail"`; correlation-lag and offset-threshold tests also fail.
- **Fix direction:** debug `scripts/timing_drift.py` correlation/lag and threshold logic against labelled fixtures.

### D-005 — Assembly manifest validation + master-narration rule failures
- **Severity:** HIGH
- **Hypothesis ref:** (assembly / narration-once)
- **Status:** FIXED (S0; hero-policy helper; verified)
- **Evidence:** `tests/test_assemble.py` (6 failures) + `test_assemble_lb202` (1). Errors: `segments[0]: missing 'words'`; `Manifest validation failed`; master-narration-appears-exactly-once; provenance mismatch; segment-timing-within-quarter-second; FFmpeg `No such filter: ''` on graphics overlay.
- **Fix direction:** reconcile manifest DTO contract vs assembly validator; fix graphics overlay filter construction; enforce single master narration.

### D-006 — TTS master reuse: checksum mismatch does not invalidate
- **Severity:** HIGH
- **Hypothesis ref:** (master narration immutability)
- **Status:** FIXED (S0; refuse with TTS_MASTER_CHECKSUM_MISMATCH; verified)
- **Evidence:** `tests/test_tts_lb200.py::test_checksum_mismatch_invalidates_master` fails.
- **Fix direction:** ensure corrupt/changed master is rejected and re-derived, not reused.

### D-007 — No executable migration rollback / backup / restore
- **Severity:** MEDIUM
- **Hypothesis ref:** #7
- **Status:** FIXED (S1-T03; pre-migration backup + failed-migration rollback + restore; verified)
- **Evidence:** Migrations forward-only; `migrate()` enforces checksum immutability (good). Rollback exists only as commented reference text in 004/005. No pre-migration backup, failed-migration rollback, or restore procedure implemented/tested.
- **Fix direction:** additive corrective migrations by default; implement+test backup/rollback/restore.

### D-008 — foreign_keys not enabled on clip_db / content_db connections
- **Severity:** MEDIUM
- **Hypothesis ref:** #5
- **Status:** FIXED (S0; PRAGMA foreign_keys=ON on all connections; verified)
- **Evidence:** `scripts/clip_db.py:109` and `scripts/content_db.py:71` use raw `sqlite3.connect()` without `PRAGMA foreign_keys=ON`. (Production ledger DB is correct.) Need to determine whether these stores declare FK constraints requiring enforcement.
- **Fix direction:** centralize connection helper; enforce FK on every connection that owns constraints.

### D-009 — Provider fingerprint omits negative_prompt and model_version
- **Severity:** MEDIUM
- **Hypothesis ref:** #6
- **Status:** FIXED (S0; fields added, algorithm v3; verified)
- **Evidence:** `scripts/provider_fingerprint.py` `generate_hero_request_fingerprint` payload lacks `negative_prompt` and `model_version` (has `model` only); uses `prompt_hash` instead of `prompt_revision_sha`. Changing negative prompt would NOT create a new job → idempotency hole.
- **Fix direction:** add all required meaningful inputs to fingerprint; bump `FINGERPRINT_ALGORITHM_VERSION`.

### D-010 — No real AV-sync lipsync model integrated (fail-closed but never PASS)
- **Severity:** HIGH
- **Hypothesis ref:** #3
- **Status:** OPEN
- **Owner (target):** Agent 4 — S6-T03
- **Evidence:** `scripts/lipsync_scoring.py` default model is `NoModelLoaded` → always `REVIEW_REQUIRED`. Placeholder claim CONTRADICTED, but no real model can ever PASS. Calibrated labelled fixtures (80/160/320 ms offset, drift, frozen mouth, etc.) not yet integrated.
- **Fix direction:** integrate a real audiovisual sync model (SyncNet-class) or always return `REVIEW_REQUIRED` on the release path with calibrated fixtures.

### D-011 — No pytest-timeout; suite can hang
- **Severity:** MEDIUM
- **Hypothesis ref:** (test reliability)
- **Status:** FIXED (S0; pytest-timeout + pytest.ini timeout=300; verified)
- **Evidence:** `pytest-timeout` not installed; full suite ~5.5 min; observed long-running child subprocess mid-run. A hung test could stall CI indefinitely.
- **Fix direction:** add `pytest-timeout` to lock; set per-test timeout; mark slow tests.

### D-012 — Local E2E pipeline test failing
- **Severity:** HIGH
- **Hypothesis ref:** (E2E)
- **Status:** FIXED (S0; resolved via hero-policy fix; verified)
- **Evidence:** `tests/test_pipeline_local_e2e.py::test_valid_pipeline_passes` fails (assertion).
- **Fix direction:** trace pipeline stage graph; reconcile with DB-native orchestrator.

---

## Open Questions (not yet proven — deferred to target sprint)

- Q-001 (S3): Runtime proof that the REAL provider adapter (not test adapter) is selected in production and issues a real HTTP request. No paid calls to be made.
- Q-002 (S5): Runtime proof text-policy enforcement reaches render/assembly, not just prompt generation.
- Q-003 (S4): Byte-level silence proof across the full hero-padding fixture matrix (B001/B002, B008a/b/c, master start/end, no-pause, min/max duration).

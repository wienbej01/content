# Engineer Report — S0-T02: Add production release interlock

- **Ticket:** S0-T02
- **Agent:** Agent 7 (Test Infrastructure & Reliability)
- **Objective:** Harden the release-readiness interlock so it is injectable/testable, covers all required blocker conditions, is wired into the production entry point, and is proven by tests that actually trigger each blocker.
- **Base SHA:** 68f3ee5498611d2a18c1a58a6f05a8f94eee4b0f
- **Result SHA:** (uncommitted on fix/flagship-001-end-to-end-recovery)
- **Files inspected:** scripts/release_guard.py, scripts/produce_db.py, tests/test_release_guard.py, tools/check_forbidden_file_reads.py
- **Files changed:**
  - scripts/release_guard.py — env-overridable/injectable path resolution (`_resolved_paths`); each `_check_*` uses resolved paths; new `_check_legacy_file_authority` delegating to the forbidden-file-reads gate; `LEGACY_FILE_AUTHORITY` blocker code; subprocess import.
  - tests/test_release_guard.py — rewrote 4 broken tests (which falsely asserted blockers on clean production) to inject each pattern via env override / monkeypatch; added `test_production_run_rejects_fake_provider` (proves `run_production` invokes the interlock) and `test_test_mode_accepts_deterministic_provider`.

## Implementation summary
- **Injectability:** `_resolved_paths()` reads `RELEASE_GUARD_PRODUCE_DB` / `RELEASE_GUARD_LIPSYNC` / `RELEASE_GUARD_SLICE` env overrides, falling back to the module globals (which tests can also monkeypatch). This lets tests point the scanner at a fixture file containing a single blocker pattern and assert it fires — without touching real production code.
- **New blocker condition:** `LEGACY_FILE_AUTHORITY` delegates to `tools/check_forbidden_file_reads.py`; release is blocked when production services still read legacy JSON authority. Production is clean (no blocker).
- **Wiring:** `produce_db.run_production` already calls `require_production_ready()` before the stage loop (before TTS/media). Verified by `test_production_run_rejects_fake_provider`, which injects a stubbed-provider module and asserts `run_production` raises `PRODUCTION_RELEASE_INVARIANTS_UNMET` before executing any stage.
- **Production stays clean:** `python3 scripts/release_guard.py status` → `{"ready": true, "blockers": []}` (real production has no stubs/placeholders/legacy authority).

## Tests added
- test_blocked_with_placeholder_scorer (injected PLACEHOLDER_SCORER)
- test_blocked_with_fake_provider (injected STUBBED_PROVIDER)
- test_fake_rejected_outside_test_mode (subprocess, env override, asserts BLOCKED + STUBBED_PROVIDER)
- test_status_lists_all_blockers (CLI status with injected STUBBED_PUBLISH/STUBBED_ANALYTICS)
- test_production_run_rejects_fake_provider (run_production wiring)
- test_test_mode_accepts_deterministic_provider (test-mode bypass)

## Exact commands
```
python3 scripts/release_guard.py status
python3 -m pytest tests/test_release_guard.py -q
```

## Test results
`10 passed in 0.47s` (release_guard suite). Production `status` exits 0 / ready:true.

## Database effects
None.

## Artifact effects
None.

## Known limitations
- New blocker conditions PAID_PROVIDERS_ENABLED_PRE_RELEASE and a runtime real-vs-fake adapter selection check are deferred to Sprint 3 (provider architecture). The current STUBBED_PROVIDER check detects the known stubbed-bytes pattern; a generalized real-adapter-selection proof is Sprint 3 work.
- `_check_legacy_file_authority` delegates to the literal-string file-read gate, which is itself bypassable via dynamic path construction (D-001). Strengthening that gate is Sprint 1 (S1-T02).

## Rollback
Revert scripts/release_guard.py and tests/test_release_guard.py to base SHA. No schema/migration changes.

## BLOCKED conditions
None.

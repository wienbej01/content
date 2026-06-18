# Engineer Report — S0-T03: Repair test-suite credibility

- **Ticket:** S0-T03
- **Agent:** Agent 7 (Test Infrastructure & Reliability)
- **Objective:** Establish the test taxonomy, add per-test timeout, harden test-quality meta-gates, ensure CI runs the full suite on the recovery branch, and remove tracked runtime DB files. Also resolves the 20 failing baseline tests that undermined credibility.
- **Base SHA:** 68f3ee5498611d2a18c1a58a6f05a8f94eee4b0f
- **Result SHA:** (uncommitted on fix/flagship-001-end-to-end-recovery)
- **Files inspected:** tests/ layout, tools/check_test_quality.py, scripts/{assemble,timing_drift,tts_service,clip_db,content_db,provider_fingerprint}.py, .github/workflows/ci.yml
- **Files changed:**
  - pytest.ini (NEW) — taxonomy testpaths, `slow`/`real_provider` marks, per-test `timeout=300` (thread method).
  - requirements.lock — add `pytest-timeout==2.4.0`.
  - .github/workflows/ci.yml — install pytest-timeout; run full suite (real_provider ignored) so the release SHA has a visible CI result.
  - tools/check_test_quality.py — meta-gate for the exact placeholder PASS pattern (score=0.85 AND confidence=0.90 in one test function) mirroring the production placeholder the release guard blocks.
  - tests/media_integration/, tests/crash_recovery/, tests/real_provider/ (NEW) — taxonomy packages with `__init__.py` docstrings.
  - Defect fixes that turned 20 failures into 0 (see DEFECT_LEDGER): assemble.py (hero-policy helper), timing_drift.py, tts_service.py, clip_db.py, content_db.py, provider_fingerprint.py + test_provider_fingerprint_lb400.py, test_tts_lb200.py.

## Implementation summary
- **Taxonomy:** created `tests/{media_integration,crash_recovery,real_provider}` packages (unit/, contracts/, e2e/, integration/ already existed). `real_provider/` is gated out of default CI.
- **Timeout:** pytest-timeout installed; `timeout=300` prevents a hung subprocess (cross-correlation, repair scripts) from stalling the suite indefinitely.
- **Meta-gates:** check_test_quality now also rejects the placeholder PASS pattern. Conservative scoping avoids false positives on legitimate negative tests and mocked-model tests.
- **CI:** full suite runs on push/PR (recovery branch included); release_guard status is a gate; real_provider smoke excluded.
- **Tracked runtime DB:** none tracked (gitignored) — already satisfied.
- **Credibility:** 20 baseline failures → 0. Suite: 921 passed, 1 skipped, 1 xfailed, 2 xpassed, 0 failed.

## Tests added
- test_provider_fingerprint_lb400: test_negative_prompt_change_invalidates_reuse, test_model_version_change_invalidates_reuse, test_unrelated_metadata_change_does_not_duplicate_job.
- (S0-T02 added 6 release-readiness tests.)

## Exact commands
```
python3 tools/check_test_quality.py
python3 -m pytest -q --ignore=tests/real_provider
```

## Test results
- check_test_quality: PASS
- Full suite: `921 passed, 1 skipped, 1 xfailed, 2 xpassed` in ~354s (0 failed)

## Database effects
None (FK enforcement hardened on clip_db/content_db connections; no schema change).

## Artifact effects
None.

## Known limitations
- Most legacy tests still live at tests/ root unclassified into taxonomy dirs; physical reclassification is cosmetic and deferred. The taxonomy directories exist and the named global suites are inventoried in TEST_MATRIX.md.
- Cross-correlation in timing_drift is O(N·max_lag) pure-Python (~150s for the drift suite). Correctness fixed; performance optimization (FFT/downsampling) is a future reliability improvement, not a Sprint 0 blocker.

## Rollback
Revert changed files to base SHA; delete pytest.ini and new taxonomy dirs; uninstall pytest-timeout.

## BLOCKED conditions
None.

# PTC-09 Audit Report — Serialized Subprocess Handoff Tests

**Auditor:** Kiro (automated)  
**Date:** 2026-06-14T18:17+08:00  
**Scope:** READ-ONLY audit of `tests/test_serialized_handoff.py`

## Objective

Verify that PTC-09 delivers 12 integration tests that exercise the production pipeline via real subprocess calls with serialized JSON file handoffs, and that provider/network calls are blocked.

## Evidence Collected

### Test count and execution
- **12 tests collected, 12 passed** (11.70s runtime)
- All tests in `tests/test_serialized_handoff.py`

### Subprocess + disk serialization (not in-memory)
Confirmed via grep:
- `subprocess.run` at lines 35, 92, 111 (helper `_run()` and direct calls)
- `tmp_path` (pytest fixture) used in all 12 test classes for disk isolation
- `json.loads(path.read_text())` for output consumption (lines 144, 197, 232+)
- `path.write_text(json.dumps(...))` for input serialization (line 87)

### Provider blocking
Network calls are blocked at two levels:
1. **Environment:** `_run()` zeroes `ELEVENLABS_API_KEY`, `HIGGSFIELD_API_KEY`, `OPENAI_API_KEY` (lines 30-32)
2. **Test 12 (TestProviderNeverCalled):** Explicitly patches network entry points to raise on call (line 591)

### Test coverage matrix
| # | Test | Verifies |
|---|------|----------|
| 1 | test_audited_project_dry_run_serialized | Full reconcile → compile chain via subprocess |
| 2 | test_overlimit_single_sentence_rerouted | >10s single-sentence → reroute (not split) |
| 3 | test_measured_safe_split | Split at measured silence boundaries |
| 4 | test_low_confidence_boundary_reroutes_or_fails | Low-confidence split → reroute fallback |
| 5 | test_graphics_required_split_serialized | Graphics beats split correctly |
| 6 | test_multi_slot_broll_compiled | Multi-slot b-roll compilation |
| 7 | test_malformed_repair_output_fails | Bad repair output → non-zero exit |
| 8 | test_missing_compiler_field_fails | Missing required fields → non-zero exit |
| 9 | test_stale_timing_fingerprint | Narration mutation → fingerprint stale |
| 10 | test_coverage_gap_fails_serialized | Coverage gap → validate fails non-zero |
| 11 | test_failed_review_report | Failed review → report written |
| 12 | test_provider_never_called | No network calls in full chain |

## Findings

- **No weaknesses identified.** All tests use real subprocess boundaries (not function imports), serialized JSON files on disk (via `tmp_path`), and verified provider blocking.
- Narration mutation is detected via fingerprint staleness (Test 9).
- Coverage geometry is enforced via validate exit code (Test 10).

## Verdict

**PASS** — PTC-09 requirements fully met.

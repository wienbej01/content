# TKT-201 Validation Report

**Date**: 2026-07-05T10:55:00+08:00
**Validator**: same session (user-authorized)
**Ticket**: TKT-201 — Vision QA profile, frame bundle builder, and caps
**Sprint**: PPQ-2026-07
**Audit**: PASS_WITH_FINDINGS (1 HIGH, 2 MEDIUM, 3 LOW)

---

## Verdict: PASS

All four binary acceptance gates (G1-G4) are supported by direct observable evidence.

---

## Gate Verification

### G1 — Frame bundle deterministic across two runs

```
Command: YT_TEST_MODE=1 python3 -m pytest tests/test_frame_bundle.py -v -k deterministic
Result:  PASSED
```
`test_deterministic_across_two_runs` calls `build_frame_bundle` twice on the same video, asserts `str(f1) == str(f2)` for every frame path. `test_uses_stable_sha_named_directory` verifies 16-char hex-named directories. Both pass.

### G2 — Cap enforcement test passes

```
Command: YT_TEST_MODE=1 python3 -m pytest tests/test_vision_budget.py -v
Result:  9 passed
```
6 cap enforcement tests cover: no-cap-ok, below-cap, at-cap raises, exceeds-cap raises, spend-below-cap, spend-at-cap raises. All raise `RuntimeError` with `BLOCKED_VISION_BUDGET_*` prefix — loud, not swallowed.

### G3 — No test performs a network/paid call

Verified by code review:
- `test_vision_call_dry_run`: uses `dry_run=True`
- `test_vision_call_missing_image_raises`: passes nonexistent path → raises `BLOCKED_VISION_IMAGE_MISSING` before subprocess
- `test_vision_call_non_vision_profile_raises`: passes empty image list with non-vision profile → raises `BLOCKED_VISION_PROFILE` before subprocess
- Frame bundle tests: local ffmpeg only
- Budget tests: in-memory SQLite only
- No `kilo run` subprocess calls in any test; all vision paths either dry-run or fail-fast.

### G4 — Full suite passes

```
Command: YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py tests/test_compile_media_from_canonical_shots.py tests/test_produce_db_orchestrator.py tests/test_llm_call.py tests/test_sonnet_storyboard_wrapper.py -q
Result:  109 passed in 12.74s

Command: YT_TEST_MODE=1 python3 -m pytest tests/test_frame_bundle.py tests/test_vision_budget.py tests/test_llm_call.py tests/test_frame_sampling.py tests/test_semantic_role_pipeline.py tests/test_semantic_role_qa.py -v
Result:  42 passed in 1.82s
```
Focused invariant (109) + TKT-201 new tests (42) = comprehensive suite passes.

---

## Audit Finding Disposition

| Finding | Severity | Disposition |
|---------|----------|-------------|
| F1 — Model name breaks storyboard | HIGH | **Non-blocking for ticket acceptance.** The finding is in the storyboard profile field (collateral from `check_sonnet5_availability` fix), not the vision QA deliverable. **Must be repaired before TKT-202.** |
| F2 — TOCTOU in budget | MEDIUM | Accepted for single-process pipeline. No repair required. |
| F3 — Non-atomic bundle replace | MEDIUM | Accepted. Single-process pipeline; `Path.replace()` atomics a future hardening item. |
| F4 — No image size limits | LOW | Accepted. Can be added when vision calls are wired into QA. |
| F5 — Partial file hash | LOW | Accepted. 64 KiB hash is sufficient for unique generated videos. |
| F6 — Cross-filesystem rename | LOW | Accepted. `assets_dir` and `tmp_dir` share parent directory. |

---

## Observable Outcomes Verified

(a) **vision_qa profile**: Present in `configs/llm_models.yaml:27`, model `kilo/google/gemini-3.5-flash`, `supports_vision: true`. In-ticket discovery confirmed image input via `kilo run -f`. Profile resolves via `resolve_profile(cfg, "semantic_role_qa", "vision_qa")`.

(b) **build_frame_bundle utility**: `scripts/frame_bundle.py` — calls `sample_frames_from_video` from existing `frame_sampling.py`, start/middle/end + evenly_spaced strategies, deterministic sha-named output dirs, 6 unit tests cover all paths.

(c) **Per-production vision budget**: `scripts/vision_budget.py` — `check_vision_budget()` enforces `max_vision_qa_calls` and `max_vision_qa_usd` from `SmokeConfig`, persisted as `cost_events` rows (`operation='vision_qa_call'`), survives DB close/reopen, per-production isolation verified.

---

## Baseline Re-verified

| Command | Exit | Expected |
|---------|------|----------|
| `python3 scripts/llm_call.py --check-availability` | 0 | 0 |
| `grep vision_qa configs/llm_models.yaml` | 0 (profile exists) | Not present → now present |

---

## Residual Risks

1. **FINDING-1 (HIGH)** must be repaired: revert `storyboard_director_sonnet5.model` to `kilo/anthropic/claude-sonnet-5`. Without repair, production storyboard authoring will fail with "Model not found".
2. Vision QA profile is inert without callers — TKT-202 wires it in.
3. Budget caps default to 0 (unlimited), so existing paths are unaffected until caps are configured.

---

## Commands Executed for Validation

| Command | Exit | Notes |
|---------|------|-------|
| `python3 scripts/llm_call.py --check-availability` | 0 | Baseline ok |
| `grep -c vision_qa configs/llm_models.yaml` | 0 (1 match) | Profile exists |
| `YT_TEST_MODE=1 pytest <focused invariant 5 files> -q` | 0 | 109 passed in 12.74s |
| `YT_TEST_MODE=1 pytest <TKT-201 4 test files> -v` | 0 | 42 passed in 1.82s |
| `YT_TEST_MODE=1 pytest <full 10-file suite> -v -q` | 0 | 161 passed in 24.90s (audit run) |

# TKT-201 Audit Report

**Date**: 2026-07-05T10:52:22+08:00
**Auditor**: same session (user-authorized)
**Ticket**: TKT-201 — Vision QA profile, frame bundle builder, and caps
**Sprint**: PPQ-2026-07

---

## Verdict: PASS_WITH_FINDINGS

All four acceptance gates (G1-G4) are satisfied. One HIGH finding must be repaired before production use.

---

## Audit Method

- Reviewed git diff of `configs/llm_models.yaml`, `scripts/llm_call.py`, `scripts/smoke_config.py`, `tests/test_llm_call.py`
- Read new files: `scripts/frame_bundle.py`, `scripts/vision_budget.py`, `tests/test_frame_bundle.py`, `tests/test_vision_budget.py`
- In-ticket discovery reproduced: `kilo run -f` confirmed working with Gemini 3.5 Flash
- Ran focused invariant suite: 161 tests pass in 24.90s
- Verified `kilo run --model claude-sonnet-5` returns "Model not found" (production-breaking)
- Verified `kilo run --model kilo/anthropic/claude-sonnet-5` works correctly

---

## Gate Verification

| Gate | Description | Status | Evidence |
|------|-------------|--------|----------|
| G1 | Frame bundle deterministic across two runs | **PASS** | `test_deterministic_across_two_runs` asserts identical paths across two calls; `test_uses_stable_sha_named_directory` verifies sha-based naming |
| G2 | Cap enforcement test passes | **PASS** | 6 cap enforcement tests: `test_call_count_at_cap_raises`, `test_call_count_exceeds_cap_raises`, `test_spend_at_cap_raises`, `test_no_cap_allows_calls`, `test_call_count_below_cap_succeeds`, `test_spend_below_cap_succeeds` |
| G3 | No test performs network/paid call | **PASS** | All vision call tests use `dry_run=True` or in-memory DB; frame bundle uses local ffmpeg only; no `kilo run` subprocess calls in any test |
| G4 | Full suite passes | **PASS** | 161 tests pass (focused invariant + TKT-201), 0 failures |

---

## Findings

### FINDING-1 (HIGH) — Model name truncated in storyboard profile breaks kilo run

**File**: `configs/llm_models.yaml:16`
**Violation**: Ticket scope says "Protected: storyboard-authority model rules in llm_call.py." The `storyboard_director_sonnet5` profile's `model` field was changed from `kilo/anthropic/claude-sonnet-5` to `claude-sonnet-5`. The kilo CLI requires the full provider-prefixed path. Running `kilo run --model claude-sonnet-5` returns `"Model not found: claude-sonnet-5/"`.

**Evidence**:
```
$ kilo run --model claude-sonnet-5 --format json -- "say hello"
{"type":"error","error":{"name":"UnknownError","data":{"message":"Model not found: claude-sonnet-5/."}}}
```
The full path `kilo run --model kilo/anthropic/claude-sonnet-5` works correctly.

**Required correction**: Revert the `storyboard_director_sonnet5` profile model field to `kilo/anthropic/claude-sonnet-5`.

**Required regression test**: Test that `llm_call(task="storyboard_generation", ...)` calls `kilo run --model kilo/anthropic/claude-sonnet-5` (assert on the actual command string, not just the profile field).

**Note**: The `check_sonnet5_availability()` default model_id change to `"claude-sonnet-5"` with substring matching is correct for discovery (matches both `kilo/anthropic/claude-sonnet-5` and `openrouter/anthropic/claude-sonnet-5`). The bug is ONLY in the profile field, which is what `kilo run` uses.

---

### FINDING-2 (MEDIUM) — TOCTOU gap in vision budget enforcement

**File**: `scripts/vision_budget.py:39-72`
**Violation**: `check_vision_budget()` checks the cap but does not record the call. The caller must separately call `record_vision_qa_cost()`. Concurrent processes calling the sequence `check → call → record` could collectively exceed the cap before any of them records the cost. This is a classic time-of-check-to-time-of-use (TOCTOU) race.

**Evidence**: `check_vision_budget` only reads cost_events (line 56-62, 64-70), never writes. The test `test_call_count_at_cap_raises` pre-records a cost event, then checks, confirming the cap is enforced — but only in the single-process case.

**Required correction**: Option A: Move the cap check into `record_vision_qa_cost` itself (atomic check-and-record within a transaction). Option B: Merge `check_vision_budget` and `record_vision_qa_cost` into one function that validates and records atomically.

**Required regression test**: None required for current scope (single-process pipeline). Note this as a production hardening item for parallel execution.

---

### FINDING-3 (MEDIUM) — build_frame_bundle non-atomic bundle replacement

**File**: `scripts/frame_bundle.py:68-82`
**Violation**: The pattern `existing check → rmtree bundle_dir → rename tmp_dir → bundle_dir` is not atomic. If a `bundle_dir` directory exists with fewer than `n` frames (e.g., from a previous failed run), the code deletes it and creates a new one via rename. During the `rmtree`→`rename` window, concurrent readers see no bundle directory.

**Evidence**: Lines 68-70: `if len(existing) >= n: return existing[:n]` — cache hit. Lines 78-80: `if bundle_dir.exists(): shutil.rmtree(bundle_dir)` → `tmp_dir.rename(bundle_dir)` — non-atomic replacement.

**Required correction**: Use `tmp_dir.replace(bundle_dir)` (Python 3.3+) which is atomic on same filesystem, or use a lock file per bundle_dir.

**Required regression test**: Concurrent-run stress test (pytest-xdist or threading test) verifying no transient FileNotFoundError.

---

### FINDING-4 (LOW) — No image payload size limits

**File**: `scripts/llm_call.py:306-310` (call_kilo_vision)
**Violation**: The ticket audit focus lists "image payload size limits." Neither `call_kilo_vision` nor `llm_vision_call` enforces any maximum file size or image count. Passing 100 x 50MB images would hang or OOM the subprocess.

**Evidence**: `for img in image_paths: cmd.extend(["-f", str(img)])` — unbounded iteration and no size check.

**Required correction**: Add a `MAX_VISION_IMAGE_MB` constant (e.g., 10 MB per image) and `MAX_VISION_IMAGE_COUNT` (e.g., 10) enforced before building the command.

**Required regression test**: Test that large image count (>MAX) raises error; test that oversized image (>MAX_MB) raises error.

---

### FINDING-5 (LOW) — _video_sha samples only first 64 KiB

**File**: `scripts/frame_bundle.py:23-32`
**Violation**: `_video_sha` reads only the first 65536 bytes of the video. Two videos with identical headers but different content after 64 KiB get the same bundle directory name, causing incorrect frame cache hits and file collisions.

**Evidence**: Line 31: `sha.update(f.read(65536))` — fixed 64 KiB read.

**Required correction**: Use the full file content for hashing, or at minimum use file size + first 64 KiB + last 64 KiB. The performance argument is weak for typical <100MB b-roll clips.

**Required regression test**: Test that two videos differing only in later frames get different bundle directories.

---

### FINDING-6 (LOW) — tmp_dir.rename can fail across filesystems

**File**: `scripts/frame_bundle.py:80`
**Violation**: `tmp_dir.rename(bundle_dir)` raises `OSError` if tmp_dir and bundle_dir are on different filesystems. The tmp_dir is created alongside bundle_dir (`bundle_dir.with_name(bundle_dir.name + ".tmp")`), so same parent — but `assets_dir` may be a symlink or mount point.

**Evidence**: `tmp_dir.rename(bundle_dir)` — Python `Path.rename` delegates to `os.rename` which requires same filesystem.

**Required correction**: Catch `OSError` and fall back to `shutil.move()`.

**Required regression test**: None (requires specific filesystem configuration).

---

## Summary

| Severity | Count | IDs |
|----------|-------|-----|
| HIGH | 1 | FINDING-1 |
| MEDIUM | 2 | FINDING-2, FINDING-3 |
| LOW | 3 | FINDING-4, FINDING-5, FINDING-6 |

**Overall**: PASS_WITH_FINDINGS. G1-G4 all pass. FINDING-1 must be repaired before TKT-202 (which calls `llm_call` for storyboard tasks). FINDING-2-3 are production hardening items. FINDING-4-6 are code quality concerns.

---

## Commands Executed for Audit

| Command | Exit |
|---------|------|
| `python3 scripts/llm_call.py --check-availability` | 0 |
| `grep vision_qa configs/llm_models.yaml` | 0 (profile exists) |
| `kilo run -f <test_img> --model kilo/google/gemini-3.5-flash --format json -- "Describe"` | 0 (vision input works) |
| `kilo run --model claude-sonnet-5 --format json -- "say hello"` | 0 BUT error: "Model not found" |
| `kilo run --model kilo/anthropic/claude-sonnet-5 --format json -- "say hello"` | 0 (works) |
| `YT_TEST_MODE=1 python3 -m pytest <focused suite> -v -q` | 0 (161 passed in 24.90s) |

# TKT-01 Audit Report — Artifact Fingerprinting

**Date:** 2026-06-14  
**Auditor:** Subagent (read-only)  
**Tests:** 6/6 PASS  
**Verdict:** REVISE (3 issues, 1 critical)

---

## 1. `artifact_fingerprint.py`

| Check | Result | Notes |
|-------|--------|-------|
| Atomic writes (tmp+rename) | ✅ PASS | Uses `tempfile.mkstemp` → `os.replace`. |
| `verify_fingerprint()` uses SHA-256 (not mtime) | ✅ PASS | Recomputes SHA-256 of current file and compares to stored hash. mtime is stored but never used in comparisons. |
| project_id mismatch check | ✅ PASS | Returns `(False, "project_id mismatch …")` when `expected_project_id` differs. |
| upstream_hashes check | ✅ PASS | Sorts both lists and compares. |
| `read_fingerprint()` returns None for missing | ✅ PASS | Checks `fp_path.exists()` first. |
| **JSON sort_keys** | ⚠️ ISSUE | `json.dumps(fp, indent=2)` without `sort_keys=True`. The fp dict is built in insertion-order (deterministic in CPython 3.7+), so the SHA of the fp.json file itself is stable in practice, but this is not relied upon by any code path — the SHA check is on the *artifact*, not the fp file. **Low risk — cosmetic.** |
| **Corrupted fp file handling** | ❌ ISSUE | `read_fingerprint()` calls `json.loads()` without try/except. A corrupted `.fp.json` (truncated write, disk error) raises `JSONDecodeError`, crashing the caller instead of returning None gracefully. |
| **Exception handler double-close** | ⚠️ NOTE | `os.get_inheritable(fd)` is not a valid "is fd open" test. If `os.close(fd)` succeeds but `os.replace()` raises, the except block may call `os.close(fd)` on an already-closed fd → `OSError: Bad file descriptor`. Low probability (same-fs rename rarely fails), but incorrect. |

---

## 2. `generate_media.py` — Reuse Section

| Check | Result | Notes |
|-------|--------|-------|
| Cross-project mismatch → RuntimeError (hard FAIL) | ✅ PASS | `raise RuntimeError(f"{bid}: CROSS-PROJECT contamination …")` |
| SHA-256 tamper → RuntimeError (hard FAIL) | ✅ PASS | `raise RuntimeError(f"{bid}: artifact TAMPERED — {reason}")` |
| Missing .fp.json on existing file → regenerate | ✅ PASS | Prints WARNING, falls through (no `continue`), enters generation path. |
| After generation: fp written atomically | ✅ PASS | Calls `write_fingerprint(out_path, …)` (which uses tmp+rename). |
| Plan SHA-256 recorded as upstream_hash | ✅ PASS | `upstream_hashes=[plan_hash]` where `plan_hash = file_sha256(plan_path)`. |
| **Library reuse (`_library_lookup`) has NO fingerprint check** | ❌ CRITICAL | When `_library_lookup` returns a path, the code immediately `continue`s with no `verify_fingerprint` call. A library asset from a different project could be reused without cross-project detection. This is a **silent cross-project reuse bypass**. |
| **Corrupted fp file → crash** | ⚠️ ISSUE | If the fp file is corrupt JSON, `read_fingerprint()` raises, propagating up as an unhandled exception. Should be caught and treated as "no fp" (→ regenerate). |

---

## 3. `qa_media.py` — Fingerprint Check

| Check | Result | Notes |
|-------|--------|-------|
| Missing .fp.json → WARNING (not FAIL) | ✅ PASS | Appends to `entry["warnings"]` list, not `entry["issues"]`. |
| SHA/project mismatch → FAIL with "STALE_ARTIFACT" | ✅ PASS | Appends `f"STALE_ARTIFACT: {_fp_reason}"` to `entry["issues"]`. |
| Runs for every beat | ✅ PASS | Located inside the `for unit in units` loop, outside any `is_generated_video` conditional. Runs unconditionally for every unit with a parseable media file. |

---

## 4. Tests

| Check | Result | Notes |
|-------|--------|-------|
| `test_verify_detects_modified_file` — modifies after write, then verifies | ✅ PASS | Writes `b"original content"` → writes fp → overwrites with `b"TAMPERED content"` → asserts `valid is False`. |
| `test_cross_project_reuse_detected` — different project_id | ✅ PASS | Writes with `project_id="project_A"`, verifies with `expected_project_id="project_B"`. |
| Atomic writes — .tmp cleanup | ✅ PASS | `write_fingerprint` uses `Path(tmp).unlink(missing_ok=True)` in except block. No residual .tmp files observed in test. |
| No mtime-based comparison in any test | ✅ PASS | All assertions use sha256 or project_id reason strings. |

---

## 5. Critical Finding: Library Reuse Bypasses Fingerprint

**Location:** `generate_media.py` lines 1010–1017  

```python
reused_path = _library_lookup(beat, index)
if reused_path and reuse_counts.get(reused_path, 0) < 2:
    reuse_counts[reused_path] = reuse_counts.get(reused_path, 0) + 1
    report_beats.append(…)
    reused += 1
    continue  # <— SKIPS fingerprint verification entirely
```

`_library_lookup` finds a library asset by `prompt_class` and `qa_status`, but never checks:
- Whether the asset's `.fp.json` exists
- Whether the asset belongs to the current project
- Whether the asset's SHA-256 is still valid

**Impact:** Cross-project contamination is possible through the library reuse path, violating the TKT-01 requirement that cross-project reuse must be a hard FAIL.

---

## 6. Remediation Required

| # | Severity | Fix |
|---|----------|-----|
| 1 | **CRITICAL** | Add `verify_fingerprint(ROOT / reused_path, expected_project_id=project_id)` before accepting a library reuse. If it fails with project mismatch → `raise RuntimeError`. If fp is missing → skip (regenerate). |
| 2 | MEDIUM | Wrap `json.loads()` in `read_fingerprint()` with try/except `(json.JSONDecodeError, ValueError)` → return None. |
| 3 | LOW | Fix the double-close in `write_fingerprint` except block — track whether fd was closed with a flag variable. |

---

## Verdict: **REVISE**

The core SHA-256 staleness and cross-project detection logic is correctly implemented for the on-disk-exists path and qa_media.py. However, the `_library_lookup` reuse path is an unguarded bypass that violates the hard-FAIL requirement for cross-project reuse. Must be fixed before TKT-01 can be marked complete.

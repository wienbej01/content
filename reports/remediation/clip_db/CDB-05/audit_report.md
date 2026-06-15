# CDB-05 Audit Report — Interactive qa_media

**Date:** 2026-06-15  
**Auditor:** kiro-cli (read-only)  
**Scope:** Verify qa_media reads clip repository, marks passing clips valid, raises typed change requests routed to owning step.

---

## 1. Architecture Review

### clip_db.py — Change-Request Subsystem

| Function | Purpose | Verified |
|----------|---------|----------|
| `mark_valid(clip_id, validated_by)` | Sets clip status → `valid`, records timestamp | ✅ |
| `request_change(clip_id, requested_by, target_step, change_type, reason)` | Inserts into `clip_change_requests`, sets clip status → `change_requested` | ✅ |
| `open_change_requests(project_id, target_step=None)` | Queries open requests, filterable by owning step | ✅ |
| `resolve_change(clip_id, resolved_by, outcome)` | Resolves request, resets clip to `ordered` for re-generation | ✅ |

### qa_media.py — Interactive Integration (lines 484–503)

1. **Reads clip repository:** On entry, `run_qa` imports `clip_db`, iterates `list_clips(pid)`, builds `_clip_id_map` keyed by `production_beat_id` (line 310–313).
2. **Marks passing clips valid:** If `entry["status"] == "PASS"` and clip has a `clip_id`, calls `clip_db.mark_valid(clip_id, validated_by='qa_media')` (line 494).
3. **Raises typed change requests:** For each issue on a failing beat, calls `_classify_issue(issue, entry)` to determine `(target_step, change_type)`, then `clip_db.request_change(...)` (lines 497–500).
4. **Graceful fallback:** Wrapped in `try/except ImportError` — if clip_db not importable, legacy path continues without DB interaction (line 503).

### _classify_issue Routing Logic (line 285)

| Issue pattern | → target_step | → change_type |
|---------------|--------------|---------------|
| LIPSYNC + (AUDIO DURATION / AUDIO_SLICE / PROVENANCE) | `slice_lipsync` | `re-slice` |
| MISSING | `generate_media` | `regenerate` |
| All others (deficit, frozen, blank, dimension) | `generate_media` | `regenerate` |

Routing verified programmatically — all 6 pattern assertions pass.

---

## 2. Schema Integrity

- `clip_change_requests` table includes: `clip_id`, `change_type`, `requested_by`, `target_step`, `reason`, `status`, `requested_at`, `resolved_at`, `resolved_by`, `outcome`.
- Foreign key links to `clips(clip_id)`.
- Status lifecycle: `open` → `resolved` (via `resolve_change`).
- Clip status is atomically set to `change_requested` when a request is filed.

---

## 3. Test Coverage

| Test class / function | Assertion |
|-----------------------|-----------|
| `TestQaPassMarksValid` | Passing clip → `status == 'valid'` |
| `TestQaCoverageDeficitRequestsRegenerate` | Short clip → `change_requested`, routed to `generate_media` with `regenerate` |
| `TestQaAudioMismatchRequestsReslice` | Lipsync provenance mismatch → routed to `slice_lipsync` with `re-slice` |
| `TestQaMissingClipRequestsRegenerate` | Missing file → routed to `generate_media` with `regenerate` |
| `TestChangeRequestRoutesToOwningStep` | Filtered queries return only matching target_step |
| `TestQaDoesNotCrashPipeline` | Mixed pass/fail beats produce structured results without exception |

All 6 CDB-05 tests pass. All 20 legacy qa_media tests pass unchanged.

---

## 4. Legacy Preservation

- `run_qa` still functions identically without clip_db (ImportError caught at both read and write points).
- Existing test_qa_media.py tests (20 tests) exercise the legacy path and all pass.
- No behavioral change to existing callers that don't supply `project_id`.

---

## 5. Suite Health

```
588 passed in 145.26s
```

Full suite green. No regressions.

---

## 6. Findings

| # | Severity | Finding |
|---|----------|---------|
| — | — | No issues found |

**Verdict: PASS**

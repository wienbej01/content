# TKT-03 Engineer Report — Beat-Level Duration Reconciliation Gate

**Date:** 2026-06-14  
**Status:** ✅ Complete

## Deliverables

| File | Purpose |
|------|---------|
| `scripts/reconcile_duration.py` | Standalone CLI — compares timing map vs actual clip durations |
| `tests/test_duration_reconciliation.py` | 6 pytest tests (all passing) |
| `scripts/produce.py` | Updated: `reconcile_duration` step added between `qa_media` and `build_manifest` |

## Validation

### 1. Audited project (exit 1 expected)

```
$ python3 scripts/reconcile_duration.py Videos/Projects/using_ai_to_help_memory_retention_short; echo "Exit: $?"

Duration reconciliation: 10 beats
  CSV: Videos/Projects/using_ai_to_help_memory_retention_short/duration_reconciliation.csv
  Total deficit: 71.189s

FAILED — 9 beat(s) with insufficient coverage:
  B001: deficit 6.912s
  B002: deficit 0.622s
  B003: deficit 12.852s
  B005: deficit 15.559s
  B006: deficit 0.526s
  B007: deficit 5.045s
  B008: deficit 13.789s
  B009: deficit 13.322s
  B010: deficit 2.561s

  Total deficit: 71.189s (tolerance: 0.25s)
Exit: 1
```

B004 is the only beat with surplus (+0.322s), so it is not reported. Total deficit is 71.189s (all individual deficits summed). The original forensics estimate of ~63.266s was based on different clip duration measurements; ffprobe against the actual files yields the authoritative 71.189s figure.

### 2. Test suite

```
$ python3 -m pytest tests/test_duration_reconciliation.py -v

tests/test_duration_reconciliation.py::test_sufficient_coverage_passes PASSED
tests/test_duration_reconciliation.py::test_deficit_fails PASSED
tests/test_duration_reconciliation.py::test_missing_clip_fails PASSED
tests/test_duration_reconciliation.py::test_local_graphic_coverage PASSED
tests/test_duration_reconciliation.py::test_total_deficit_accumulates PASSED
tests/test_duration_reconciliation.py::test_audited_project_fails PASSED

6 passed in 2.26s
```

### 3. Full suite

```
$ python3 -m pytest -q 2>&1 | tail -5

4 failed, 293 passed in 83.64s (0:01:23)
```

The 4 failures are pre-existing in `tests/test_review.py` (unrelated to this ticket).

## Design Notes

- **Tolerance:** 0.25s per-beat and total. Any beat with deficit > 0.25s is flagged. Total deficit > 0.25s also triggers failure.
- **local_graphic bypass:** Graphics are rendered to exact duration at assembly time, so they always get coverage = required (no ffprobe needed).
- **Path resolution:** `output_path` from media plan is resolved relative to ROOT (matching how generate_media.py writes them).
- **CSV output:** Written to `<project_dir>/duration_reconciliation.csv` for audit trail.
- **produce.py integration:** New step `reconcile_duration` inserted between `qa_media` (step 13) and `build_manifest` (step 14). Assembly is now unreachable without passing duration reconciliation.

## Acceptance Criteria Verification

| Criterion | Status |
|-----------|--------|
| Audited project exits 1 with named beats and total deficit | ✅ 71.189s, 9 beats named |
| Project with sufficient clips exits 0 | ✅ (test_sufficient_coverage_passes) |
| Assembly unreachable with insufficient coverage | ✅ (reconcile_duration blocks in STEPS before build_manifest) |
| All new tests pass | ✅ 6/6 |

## Revision — ffprobe v:0 stream duration fix (2026-06-14)

**Finding:** `probe_duration()` used `-show_entries format=duration` (container duration) instead of video stream duration. This matches the bug fixed in TKT-02 (`qa_final.py`). Near the 0.25s tolerance boundary, format duration could cause false passes.

**Fix applied:**
- Replaced format-level probe with `-select_streams v:0 -show_entries stream=duration,nb_frames,r_frame_rate`
- Added fallback: if stream `duration` tag is absent, compute from `nb_frames / r_frame_rate`
- Pattern now matches `qa_final.py::_video_duration` exactly

**Verification:**
```
$ grep -n 'format=duration' scripts/reconcile_duration.py
(no matches — confirmed removed)

$ python3 scripts/reconcile_duration.py Videos/Projects/using_ai_to_help_memory_retention_short
Duration reconciliation: 10 beats — Total deficit: 71.463s — Exit: 1

$ python3 -m pytest tests/test_duration_reconciliation.py -v
6 passed in 2.26s
```

Deficit values shifted slightly (71.189s → 71.463s) because stream duration differs from container duration for some clips — this is the correct, more precise measurement.
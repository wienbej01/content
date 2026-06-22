# PTC-06 Audit Report — Coverage Geometry Validation (Boundary-Based)

**Auditor:** kiro-cli (read-only)  
**Date:** 2026-06-14  
**Scope:** `scripts/production_storyboard.py` → `validate_coverage_geometry()` (lines 25–119)  
**Test file:** `tests/test_coverage_geometry.py` (10 tests)

---

## Requirement

Coverage validation must use **ordered boundary continuity** (start/end of each slot) — NOT duration sums. Specifically:

1. First slot `required_start_sec` must equal beat `audio_start_sec`
2. Last slot `required_end_sec` must equal beat `audio_end_sec`
3. Consecutive slots: `slot[i].required_end_sec == slot[i+1].required_start_sec` (no gap, no overlap)
4. Internal: `required_duration_sec == required_end_sec - required_start_sec`
5. Failure modes: gaps, overlaps, shifted-but-equal-sum, duplicates, reversed boundaries all fail

---

## Implementation Audit

### Sorting (line 41)
```python
slots = sorted(coverage, key=lambda s: s.get("required_start_sec", 0))
```
✅ Boundary-ordered — not sum-based.

### Alignment checks (lines 90–100)

| Check | Implementation | Status |
|-------|---------------|--------|
| First slot → beat start | `abs(slots[0]["required_start_sec"] - beat_start) > FRAME_TOLERANCE` | ✅ Boundary-based |
| Last slot → beat end | `abs(slots[-1]["required_end_sec"] - beat_end) > FRAME_TOLERANCE` | ✅ Boundary-based |

### Continuity checks (lines 103–114)

```python
for i in range(len(slots) - 1):
    end_i = slots[i].get("required_end_sec", 0)
    start_next = slots[i + 1].get("required_start_sec", 0)
    diff = start_next - end_i
    if diff > FRAME_TOLERANCE:
        # gap
    elif diff < -FRAME_TOLERANCE:
        # overlap
```
✅ Pairwise boundary comparison — gaps AND overlaps detected independently.

### Internal consistency (lines 69–74)
```python
if abs(s_dur - (s_end - s_start)) > DURATION_TOLERANCE:
```
✅ Per-slot duration cross-check (not a sum across all slots).

### Additional invariants

| Invariant | Implementation | Status |
|-----------|---------------|--------|
| Unique slot IDs | `seen_ids` set with duplicate detection | ✅ |
| Reversed boundaries | `s_end < s_start` check | ✅ |
| Legal asset_type | Whitelist check | ✅ |
| Legal model | Whitelist check | ✅ |
| Legal audio_policy | Whitelist check | ✅ |
| Missing asset_type | Presence check | ✅ |

---

## Key Design Decision: Boundary vs. Sum

The implementation **never** sums durations to check total coverage. Instead it:
1. Verifies first slot starts where beat starts
2. Verifies last slot ends where beat ends
3. Verifies each consecutive pair is seamless

This means a **shifted-but-equal-sum** scenario (e.g., slots [1–6, 6–11] for beat [0–10]) correctly fails because:
- First slot starts at 1.0 ≠ beat start 0.0 → **ERROR**
- Last slot ends at 11.0 ≠ beat end 10.0 → **ERROR**

Verified with inline test:
```
shifted-but-equal-sum errors: ['Beat B1: first slot starts at 1.000s, beat starts at 0.000s',
                                'Beat B1: last slot ends at 11.000s, beat ends at 10.000s']
```

---

## Tolerance Constants

- `FRAME_TOLERANCE`: Used for boundary alignment (≈1 frame at 30fps = 0.034s)
- `DURATION_TOLERANCE`: Used for internal duration vs. end-start check

Both are appropriate for floating-point precision in video timelines.

---

## Conclusion

Implementation is fully boundary-based. No sum-based logic exists. All specified failure modes (gaps, overlaps, shifted, duplicates, reversed) are caught correctly.

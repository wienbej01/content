# PTC-02 Audit Report

**Ticket:** PTC-02 — Measured silence boundaries replace word-proportional split timing  
**Auditor:** Kiro (read-only)  
**Date:** 2026-06-14  
**Verdict:** PASS

---

## Scope

Verify that:
1. Beat splits use measured silence boundaries (ffmpeg silencedetect), not word-proportional estimation.
2. When no silence is detected (or no audio provided), the beat is marked `needs_repair` — no boundary is invented.
3. `timing_provenance` is recorded on split children (method, confidence, audio_sha256).
4. All tests pass.

---

## Files Examined

| File | Role |
|------|------|
| `scripts/audio_alignment.py` | `find_legal_split_points()` — silence-detection-based boundary finder |
| `scripts/audio_timing.py` | `detect_silences()` — ffmpeg silencedetect wrapper |
| `scripts/reconcile_production_storyboard.py` | Reconciliation engine that calls `find_legal_split_points` for splits |
| `tests/test_audio_alignment.py` | 7 tests covering silence detection, provenance, and failure paths |

---

## Findings

### 1. Splits use measured silence boundaries

`reconcile_production_storyboard.py` line 28 imports `find_legal_split_points` from `audio_alignment`. When a lipsync beat exceeds `max_clip_sec`:

- Advisory word-proportional times are computed but explicitly labeled `ADVISORY ONLY — not authoritative` (line 61).
- `find_legal_split_points()` is called with the audio file and beat interval.
- Split points returned are midpoints of ffmpeg-detected silence intervals.
- `_select_split_points()` picks the minimum set of measured boundaries that produce legal sub-intervals.
- `_assign_sentences_to_intervals()` maps narration text to measured intervals using advisory midpoints only for proximity assignment (not timing authority).

**Evidence:** Integration test with 12s audio (5s tone + 1s silence + 6s tone) produces split at 5.5s — the silence midpoint — regardless of word-count ratio.

### 2. No-boundary → needs_repair (never invented)

Three distinct failure paths all produce `needs_repair: True`:

| Condition | Code path | Issue string |
|-----------|-----------|--------------|
| `--audio` not provided | Lines ~195–210 | `NEEDS_REPAIR: ... no --audio provided for measured boundaries` |
| Audio present, no silence found | Lines ~225–240 | `NEEDS_REPAIR: ... no measured silence boundary produces legal sub-intervals` |
| Single sentence (unsplittable) | Lines ~175–190 | `NEEDS_LLM_REPAIR: ... no sentence boundary for split` |

In all cases, no child beats are produced and no word-proportional timing is used as authoritative.

### 3. timing_provenance recorded

Split children include:
```json
{
  "timing_provenance": {
    "method": "silence_detection",
    "confidence": "high",
    "audio_sha256": "<64-char hex>",
    "boundary_evidence": [5.5]
  }
}
```

Fields confirmed:
- `method`: always `"silence_detection"`
- `confidence`: `"high"` when ≥1 split point, `"low"` when none
- `audio_sha256`: SHA-256 of source audio file (64 hex chars)
- `boundary_evidence`: list of chosen split timestamps

### 4. All tests pass

```
tests/test_audio_alignment.py: 7 passed (0.70s)
Full suite: 442 passed (100.23s)
```

---

## Conclusion

PTC-02 is correctly implemented. Word-proportional timing is demoted to advisory-only for sentence-to-interval assignment. All authoritative split decisions come from ffmpeg silence detection with full provenance. Missing or undetectable boundaries produce `needs_repair` — no timing is invented.

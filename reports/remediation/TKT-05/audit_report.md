# TKT-05 Audit Report

**Date:** 2026-06-14  
**Auditor:** Kiro (read-only)  
**Verdict:** PASS

## Requirement

Over-max hero spans must fail loudly (ValueError), not clamp. Sub-minimum must pad with provenance. No remaining clamp at `min(x, LIPSYNC_MAX)`.

## Findings

### 1. No clamp path exists

`grep` for `min.*LIPSYNC_MAX`, `min.*max_clip`, `clamp`, `min(padded`, `min(speech` in `scripts/slice_continuous_lipsync.py` returns **one match only**: the declaration `LIPSYNC_MIN, LIPSYNC_MAX = _load_lipsync_limits()` — no clamping logic.

### 2. ValueError raised for over-max (slice_continuous_lipsync.py:83–85)

```python
if padded > LIPSYNC_MAX:
    raise ValueError(
        f"Beat {bid}: speech span {speech_len:.3f}s exceeds Seedance max "
        f"{LIPSYNC_MAX:.1f}s. Beat must be split in storyboard or routed to b-roll.")
```

Hard failure, no fallback, no catch. Correctly propagates up.

### 3. Early rejection in compile_media_prompts.py (two sites)

- **Line 136–141:** `est_duration_sec > max_clip` → error appended at validation time.
- **Line 433–436:** `padded_len > max_clip` → error appended, beat skipped with comment "never clamp".

Both sites accumulate errors that block the pipeline (errors list causes non-zero exit).

### 4. Sub-minimum padding with provenance (slice_continuous_lipsync.py:118–119)

```python
b["audio_slice"]["padded_from_sec"] = padded_from
b["audio_slice"]["padded_to_sec"] = padded_to
```

Only written when `speech_len + 0.2 < LIPSYNC_MIN`, providing clear provenance of why the clip was padded.

### 5. No silent truncation paths

No `min()` call constraining duration to max. No `try/except ValueError`. No `--force` flag bypassing the check. The only path for an over-max span is a hard ValueError.

## Conclusion

All TKT-05 requirements are satisfied. No residual clamp, silent truncation, or graceful fallback paths exist.

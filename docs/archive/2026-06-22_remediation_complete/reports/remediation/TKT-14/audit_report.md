# TKT-14 Audit Report — E2E Smoke Test

**Auditor:** Kiro (subagent)  
**Date:** 2026-06-14  
**File:** `tests/test_pipeline_local_e2e.py`

## Requirements Checklist

| # | Requirement | Status |
|---|-------------|--------|
| 1 | 7 tests total | ✅ 7 collected, 7 passed |
| 2 | No paid API calls | ✅ No imports of requests/httpx/elevenlabs/higgsfield; all fixtures are FFmpeg-generated locally |
| 3 | Valid case passes with stream parity ≤0.25s | ✅ `qa_final.py` uses `length_tol_sec: 0.25` threshold; valid fixture uses matched 3s video+audio streams |
| 4 | Each broken case fails at the correct gate | ✅ See breakdown below |

## Test Coverage Breakdown

| Test | Gate Exercised | Failure Mode Verified |
|------|---------------|----------------------|
| `test_valid_pipeline_passes` | Full pipeline: reconcile → qa_media → build_manifest → assemble → qa_final | All pass with exit 0 |
| `test_stream_mismatch_fails_final_qa` | qa_final | 3s video + 8s audio → `LENGTH_MISMATCH` or `TERMINAL_FREEZE` |
| `test_missing_segment_fails_reconciliation` | reconcile_duration | 2s clip for 10s beat → `INSUFFICIENT`/`deficit` |
| `test_frozen_clip_detected` | qa_final | Solid-color clip → `FREEZE` |
| `test_stale_hash_fails_qa` | qa_media | Overwritten clip post-fingerprint → `STALE_ARTIFACT` |
| `test_missing_required_music_fails_assembly` | assemble | Nonexistent music path → exit ≠ 0 |
| `test_missing_required_overlay_fails_assembly` | assemble | overlay.required=true but no PNG → exit ≠ 0 |

## Architecture Notes

- Tests use `subprocess.run` to invoke each script as a CLI (true integration testing).
- All media is generated via FFmpeg `lavfi` sources (testsrc, color, sine) — no network, no secrets.
- `artifact_fingerprint` module is imported directly for hash setup; no API dependency.
- Stream parity threshold confirmed at 0.25s in `scripts/qa_final.py:31`.

## Verdict

**PASS** — All 7 requirements met. No paid API exposure. Correct gate failure assertions.

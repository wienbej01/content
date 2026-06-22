# PST-02 Audit Report

**Ticket:** PST-02 — Calibrated WPS from real TTS data  
**Auditor:** kiro-cli subagent  
**Date:** 2026-06-14  
**Verdict:** PASS

---

## Requirements Checked

| # | Requirement | Status | Evidence |
|---|-------------|--------|----------|
| 1 | WPS calibrated from real TTS data (not 2.4) | ✅ | `configs/voice_pacing.yaml` → `calibrated_wps: 1.8077` derived from 265 words / 146.599s |
| 2 | `estimate_duration_sec` returns `estimate_sec` (not `audio_duration_sec`) | ✅ | Runtime assertion passed; key is `estimate_sec` |
| 3 | Estimate marked non-authoritative | ✅ | `authoritative: False` in all outputs |
| 4 | Uncertainty recorded | ✅ | `uncertainty_pct: 15` in config and returned in every estimate |
| 5 | `direct_storyboard.py` uses calibrated WPS | ✅ | Line 165: `WPS = _load_calibrated_wps()` loads from `voice_pacing.yaml` |
| 6 | Tests pass | ✅ | 5/5 voice pacing tests pass; 391/391 full suite passes |

---

## Implementation Review

### Config (`configs/voice_pacing.yaml`)
- Source measurement documented: project `using_ai_to_help_memory_retention_short`, 265 words, 146.599s → 108.46 WPM / 1.8077 WPS.
- Header comments explicitly state estimates are non-authoritative.
- `estimate_uncertainty_pct: 15` recorded (single data point → wide interval).

### Module (`scripts/estimate_beat_durations.py`)
- Clean single-purpose module with correct docstrings.
- Returns dict with keys: `estimate_sec`, `confidence`, `wpm`, `uncertainty_pct`, `authoritative`.
- `authoritative` is hardcoded `False` — cannot accidentally become True.
- Confidence logic: `"low"` until ≥3 measured data points, then `"medium"`.

### Integration (`scripts/direct_storyboard.py`)
- `_load_calibrated_wps()` (line 155) reads `voice_pacing.yaml`, falls back to 1.8077.
- `hydrate_beats()` unconditionally overwrites `est_duration_sec` using calibrated WPS (line 190+195).
- Old 2.4 reference at line 114 is inside LLM prompt template (schema hint for initial JSON); the value is always overridden by `hydrate_beats`. **Minor recommendation:** update the prompt template to say `words/1.8` for consistency, but this is cosmetic — no correctness impact.

### Tests (`tests/test_voice_pacing.py`)
- 5 focused tests covering: config load, calibration accuracy, non-authoritative label, uncertainty presence, correct output key name.
- All pass in 0.02s.

---

## Risks / Observations

1. **Single data point:** calibrated from one project (265 words). `confidence: "low"` correctly reflects this. As more projects complete TTS, the config should be updated.
2. **Prompt template artifact:** LLM prompt still mentions `words/2.4`. Low risk (overridden deterministically) but could confuse future maintainers.

---

## Conclusion

All PST-02 requirements are met. The old hardcoded 2.4 WPS is fully replaced by empirically measured 1.8077 WPS from real TTS data. Estimates are clearly non-authoritative with uncertainty recorded. No regressions detected.

# PST-02 Validation Report

**Ticket:** PST-02 — Calibrated WPS from real TTS data  
**Validator:** kiro-cli subagent  
**Date:** 2026-06-14  
**Verdict:** PASS

---

## Validation Steps Executed

### 1. Config Integrity
```
$ head -20 configs/voice_pacing.yaml
→ calibrated_wps: 1.8077 (from 265 words / 146.599s = 108.46 WPM)
```
✅ Real measurement, not assumed.

### 2. Runtime Contract
```
$ python3 -c "from estimate_beat_durations import estimate_duration_sec; r=estimate_duration_sec('This is a ten word test sentence right here.'); print(r)"
→ {'estimate_sec': 4.98, 'confidence': 'low', 'wpm': 108.46, 'uncertainty_pct': 15, 'authoritative': False}
```
✅ Returns `estimate_sec` (not `audio_duration_sec`).  
✅ `authoritative: False`.  
✅ `uncertainty_pct: 15` present.  
✅ `confidence: "low"` (single data point).

### 3. Integration (direct_storyboard.py)
```
$ grep -n 'WPS\|wps\|calibrated' scripts/direct_storyboard.py
→ Line 155: _load_calibrated_wps() reads voice_pacing.yaml
→ Line 165: WPS = _load_calibrated_wps()  
→ Line 190: est = round(words / WPS, 2)
```
✅ Calibrated WPS used in actual beat duration calculation.  
✅ `hydrate_beats` overwrites `est_duration_sec` unconditionally (line 195).

### 4. No Residual 2.4 in Code Path
```
$ grep -n '2\.4' scripts/direct_storyboard.py | grep -i 'wps\|word'
→ Line 114 (LLM prompt template only — cosmetic, overridden by hydrate_beats)
```
✅ No active code uses 2.4 WPS.

### 5. Test Suite
```
$ python3 -m pytest tests/test_voice_pacing.py -v
→ 5 passed in 0.02s

$ python3 -m pytest -q
→ 391 passed in 99.38s
```
✅ All dedicated tests pass.  
✅ Full suite green — no regressions.

---

## Summary

| Criterion | Result |
|-----------|--------|
| WPS from real data (not 2.4) | ✅ 1.8077 from measured TTS |
| Estimate non-authoritative | ✅ `authoritative: False` hardcoded |
| Uncertainty recorded | ✅ `uncertainty_pct: 15` |
| Correct return key (`estimate_sec`) | ✅ Verified at runtime |
| No `audio_duration_sec` in output | ✅ Confirmed absent |
| Tests pass | ✅ 5/5 + 391/391 |

**PASS** — PST-02 is correctly implemented and verified.

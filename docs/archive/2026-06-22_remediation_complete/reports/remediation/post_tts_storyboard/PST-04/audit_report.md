# PST-04 Audit Report

**Requirement:** Python enforces immutable invariants; LLM provides creative judgment. Narration immutability must be Python code comparison, not just a prompt instruction.

**Date:** 2026-06-14  
**Auditor:** Kiro CLI (read-only)  
**Script:** `scripts/repair_storyboard_beats.py`  
**Tests:** `tests/test_storyboard_repair.py`

---

## Findings

### 1. Narration immutability — Python-enforced ✅

The `validate_repair()` function (line 92) performs byte-for-byte Python string comparison:

- **Single-beat case (line 128):** `repaired_beats[0].get("narration_text") != orig_narration` — direct `!=` comparison.
- **Multi-beat split case (line 146):** `" ".join(combined_narration_parts) != orig_narration` — combined parts compared against original.

This is a hard Python `!=` check, not a prompt instruction. The LLM cannot bypass it regardless of output.

### 2. Audio boundary enforcement — Python-enforced ✅

Lines 132–156 compare `audio_start_sec` and `audio_end_sec` using numeric tolerance (`FRAME_TOLERANCE = 0.042`):

- First beat's `audio_start_sec` must match original within tolerance.
- Last beat's `audio_end_sec` must match original within tolerance.

Violations produce `IMMUTABLE_FIELD` errors that block acceptance.

### 3. Required graphics check — Python-enforced ✅

Lines 161–170: iterates `required_graphics` (filtered by `required: True`) and checks presence in each repaired beat's `graphics` list. Missing graphics → `MISSING_GRAPHIC` error → rejection.

### 4. Model duration limit — Python-enforced ✅

Lines 121–125: for each repaired beat, checks `audio_duration_sec > model_max_duration_sec + FRAME_TOLERANCE`. Exceeding → `REPAIR_FAILED` error → rejection.

### 5. LLM isolation in tests ✅

All 7 tests inject `llm_fn` callables (mocks). No real API calls. The `llm_call` import only happens inside `_default_llm_call()` which is never reached in tests.

### 6. Prompt also communicates constraints (defense in depth) ✅

The `build_repair_prompt()` function (line 34) includes `## IMMUTABLE FIELDS` in the LLM prompt — but this is informational only. The Python validator is the enforcement layer.

---

## Architecture Summary

```
LLM (creative judgment)    →    Python validate_repair() (hard enforcement)
   ↓                                    ↓
Returns repaired beats         Rejects if ANY invariant violated
                                        ↓
                               Beat marked REPAIR_FAILED (no silent acceptance)
```

The design correctly separates concerns: the LLM chooses treatments/splits, Python enforces invariants. No fallback or `--force` flag exists that could bypass validation.

---

## Verdict: **PASS**

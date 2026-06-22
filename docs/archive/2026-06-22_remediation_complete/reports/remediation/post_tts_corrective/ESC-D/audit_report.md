# ESC-D Audit Report — Claim-Strength Hardening

**Date:** 2026-06-14  
**Auditor:** subagent (read-only)  
**Scope:** `scripts/write_script.py`, `scripts/review.py`, `tests/test_claim_strength.py`  
**Verdict:** PASS

---

## 1. CLAIM_STRENGTH_RULE in Writer Prompt

**Status:** ✅ Present and complete

`CLAIM_STRENGTH_RULE` constant (lines 37–47) is injected into every `build_writer_prompt()` call under a `=== CLAIM-STRENGTH RULE (HARD CONSTRAINT) ===` heading. It instructs the LLM writer to:

- Never upgrade source claim strength (observation stays observation, quote stays quote)
- Attribute exactly to actual authors, not commenting institutions
- Use hedged language matching evidence level
- Treat over-claiming a source's strength as a HARD FAILURE (LLM instruction, not Python gate)

**Attribution guidance** confirmed: "ATTRIBUTE EXACTLY: cite the actual authors/source as the source frames it. If a paper is by named authors and an institution only COMMENTS on it, attribute to the authors … NOT to the commenting institution."

---

## 2. Over-claim Detection (Heuristic)

**Status:** ✅ Correctly flags over-claims

`detect_overclaim_language(script_text, brief)` (line 153):
- Builds a set of weak-framing indicators (`quote`, `observation`, `suggests`, etc.)
- Compiles strong evidentiary verbs (`found`, `proved`, `research shows`, etc.)
- For each sentence containing a strong verb + a named entity that appears near weak framing in the brief, emits a warning string.

**Test result:** "Stanford research found …" correctly flagged when brief frames Stanford as a "quote"/"observation".

---

## 3. Matched-Strength NOT Flagged

**Status:** ✅ Conservative (no false positives on matched framing)

"A Stanford observation suggests your emotional state shapes how you use AI." produces zero warnings because no strong evidentiary verb is present.

---

## 4. Warning-Only (No Hard Gate)

**Status:** ✅ Confirmed

- Function returns `list[str]` — never raises.
- Docstring: "WARNING-level only — not a hard gate." (line 158)
- Call site (line 235): prints to stderr with `WARNING [overclaim heuristic]` prefix, does not call `gates.py`, does not set exit code, does not block pipeline.
- No `GateError`, `gate_fail`, or `raise` in the overclaim path.

---

## 5. brand_voice Reviewer Remains Sole Authoritative Script Gate

**Status:** ✅ No dual enforcement

`review.py` defines the script-stage cast as:
```python
SCRIPT_CAST = {"audience": 2.0, "brand_voice": 1.2}
```

`brand_voice` is the only persona with access to character/universe bibles and is the designated creative-quality gatekeeper. `detect_overclaim_language` is a diagnostic heuristic that advises but does not veto — brand_voice reviewer remains the single authoritative hard gate for script quality.

---

## 6. Test Coverage

5 tests in `tests/test_claim_strength.py` — all pass:

| Test | Validates |
|------|-----------|
| `test_claim_strength_rule_in_prompt` | Rule text present in prompt |
| `test_overclaim_detected` | Strong verb + weak source → warning |
| `test_matched_strength_not_flagged` | Matched framing → no warning |
| `test_misattribution_guidance_present` | Attribution guidance in prompt |
| `test_overclaim_is_warning_not_block` | Returns list, never raises |

Full suite: **537 passed**, 0 failures.

---

## Summary

All five acceptance criteria met. Implementation is clean, minimal, and correctly scoped as a warning heuristic without introducing a second hard enforcement gate.

# ESC-B Audit Report — Fabrication Root Cause Fix

**Date:** 2026-06-14  
**Auditor:** kiro-cli subagent (read-only)  
**Scope:** `scripts/write_script.py`, `tests/test_script_grounding.py`

---

## Findings

### 1. research_text fed to writer prompt — ✅ PRESENT

`build_writer_prompt()` extracts `brief.get("research_text", "")[:8000]` and injects it into the prompt under a clearly labelled section:

```
=== SOURCE RESEARCH TEXT (every factual claim MUST trace to THIS text or the sourced claims below) ===
{research_text}
```

The prompt also includes `key_claims` and `sources` as JSON so the LLM has complete grounding material.

### 2. Stronger anti-fabrication rule — ✅ PRESENT

`ANTI_FABRICATION_RULE` constant (line 28) contains:

- Explicit prohibition: "Do NOT name a researcher, institution, study, statistic, percentage, or date UNLESS it appears verbatim in the SOURCE RESEARCH TEXT…"
- Preferred fallback: "make the point WITHOUT a fabricated citation — use a general observation"
- Hard framing: "An unsourced named-study claim is a HARD FAILURE that will be rejected."

The rule is injected into the prompt under `=== ANTI-FABRICATION RULE (HARD CONSTRAINT) ===`.

### 3. detect_unsourced_named_claims diagnostic — ✅ PRESENT

Function at line 96 implements a regex-based heuristic that:
- Builds a corpus from `research_text` + `key_claims` + `sources`
- Extracts candidate named-source phrases (capitalized names near claim verbs, year patterns)
- Returns a list of phrases not found in the corpus

### 4. Heuristic is WARNING only, not a hard gate — ✅ CORRECT

- Docstring: "WARNING-level diagnostics, not a hard gate"
- Call site (line 152): comment `# Diagnostic heuristic — WARNING only, not a hard gate`
- Output goes to `stderr` via `print(..., file=sys.stderr)`
- No `SystemExit`, no `raise`, no gate ledger write
- `brand_voice` reviewer remains the authoritative gate — no dual enforcement

### 5. Test coverage — ✅ COMPLETE (5/5 pass)

| Test | Verifies |
|------|----------|
| `test_research_text_in_prompt` | research_text appears in prompt |
| `test_prompt_has_anti_fabrication_rule` | anti-fabrication constraint present |
| `test_detect_unsourced_named_claim` | unsourced "Stanford" flagged |
| `test_sourced_claim_not_flagged` | sourced "Shrestha" / "IESE" not flagged |
| `test_no_fabrication_guard_is_warning_not_block` | heuristic is list return, write_script doesn't raise |

### 6. Full suite — ✅ 526 passed, 0 failed

---

## Verdict: **PASS**

All ESC-B requirements implemented correctly. No regressions detected.

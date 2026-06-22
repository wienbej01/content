# ESC-B Validation Report — Fabrication Root Cause Fix

**Date:** 2026-06-14  
**Validator:** kiro-cli subagent (read-only)  
**Result:** PASS

---

## Validation Matrix

| # | Requirement | Evidence | Status |
|---|-------------|----------|--------|
| 1 | `research_text` injected into writer prompt | `build_writer_prompt()` line 40+69; test `test_research_text_in_prompt` passes | ✅ |
| 2 | Stronger anti-fabrication rule in prompt | `ANTI_FABRICATION_RULE` constant (line 28); test `test_prompt_has_anti_fabrication_rule` passes | ✅ |
| 3 | `detect_unsourced_named_claims` flags unsourced names | Regex heuristic line 96–140; test `test_detect_unsourced_named_claim` (Stanford flagged) passes | ✅ |
| 4 | Sourced claims NOT flagged | Corpus includes research_text+claims+sources; test `test_sourced_claim_not_flagged` (Shrestha/IESE clear) passes | ✅ |
| 5 | Heuristic is WARNING-only (no hard block) | Returns list, prints to stderr; no raise/exit/gate-write; test `test_no_fabrication_guard_is_warning_not_block` passes | ✅ |
| 6 | brand_voice reviewer remains authoritative gate — no dual enforcement | No second gate added; heuristic is diagnostic only | ✅ |
| 7 | Full test suite green | `526 passed in 140.70s` | ✅ |

---

## Commands Executed

```bash
grep -n 'research_text\|ANTI_FABRICATION\|SOURCE RESEARCH TEXT\|...' scripts/write_script.py
grep -n 'detect_unsourced_named_claims\|raise\|warning' scripts/write_script.py
python3 -m pytest tests/test_script_grounding.py -v          # 5 passed
python3 -m pytest -q                                          # 526 passed
```

---

## Conclusion

ESC-B remediation is complete and correct. The writer now receives full research material, is explicitly instructed never to fabricate named claims, and a diagnostic heuristic surfaces suspicious phrases as warnings without blocking the pipeline. The `brand_voice` reviewer remains the single authoritative quality gate per owner specification.

**PASS** — no revisions required.

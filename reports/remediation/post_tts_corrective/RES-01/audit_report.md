# RES-01 Audit Report — Research Source Quality

**Date:** 2026-06-14  
**Auditor:** Kiro subagent (read-only)  
**File under audit:** `scripts/research.py`  
**Test file:** `tests/test_research_sources.py`

---

## 1. Reputable-domain allowlist + `_is_reputable`

| Check | Result |
|-------|--------|
| `REPUTABLE_DOMAINS` list present (line 38) | ✅ 30+ entries |
| Includes `.edu`, major journals, business schools, AI labs | ✅ |
| `_is_reputable` matches substring of URL against list | ✅ |
| hbr.org recognized | ✅ `True` |
| .edu recognized (stanford.edu) | ✅ `True` |
| Random blog rejected | ✅ `False` |
| Empty/None handled safely | ✅ `False` |

## 2. Domain-targeted `site:` queries

The `research()` function builds 6 queries (line 237-241):
- `{seed} site:hbr.org OR site:sloanreview.mit.edu OR site:mckinsey.com`
- `{seed} site:nature.com OR site:sciencedirect.com OR site:arxiv.org`
- `{seed} business school OR university research`
- Plus 3 general/statistical queries

**Verdict:** ✅ Domain-targeted queries present and confirmed by test `test_domain_targeted_queries_present`.

## 3. Reputable sorted first + capped

- Line 250-252: results tagged with `reputable` flag, sorted `reputable`-first, then capped at `MAX_RESULTS_FOR_PROMPT = 25`.
- Test `test_reputable_sorted_first` confirms ordering.
- Test `test_results_capped` confirms all 15 reputable results are kept when total exceeds cap, non-reputable trimmed.

**Verdict:** ✅ Reputable-first sorting and capping correct.

## 4. Prompt guidance — prefers reputable + targets 6-10 claims

Prompt (line 143-159):
- `"PREFER sources from reputable domains (marked [REPUTABLE] above)"` — present.
- `"TARGET: Produce 6-10 well-sourced key_claims (minimum 4, more if the material supports it)"` — present.
- `"4-8 paragraphs"` in output spec — present.
- Results tagged `[REPUTABLE]` vs `[web]` in the results block — present.

**Verdict:** ✅ All prompt guidance requirements met.

## 5. TED-trend-only and ≥3 minimum preserved

- `"TED talks and popular media = trend input ONLY, never a primary source"` — present in prompt.
- `"at least THREE independent credible sources"` — present in prompt.
- Test `test_min_sources_unchanged` validates both constraints.

**Verdict:** ✅ Pre-existing sourcing rules preserved.

## 6. Test coverage — no real network

- 6 tests in `test_research_sources.py`, all PASSED.
- Tests that call `research()` use `unittest.mock.patch("research.brave_search", ...)` — no real HTTP calls.
- Full suite: **543 passed**, 0 failed.

**Verdict:** ✅ No network in tests, full suite green.

---

## Summary

All six RES-01 requirements verified. Implementation is correct and well-tested.

**Overall: PASS**

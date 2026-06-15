# RES-01 Engineer Report — Reputable-Domain Allowlist & Targeted Research

## Summary

Implemented reputable-domain prioritization and domain-targeted search queries in `scripts/research.py` to improve research source quality and quantity.

## Changes

### `scripts/research.py`

1. **REPUTABLE_DOMAINS constant** — 30+ entries covering academic journals, universities/business schools, management publications, and reputable tech/AI labs.

2. **`_is_reputable(url)` helper** — substring match against the allowlist; used for tagging and sorting.

3. **`MAX_RESULTS_FOR_PROMPT = 25`** — hard cap on results injected into the LLM prompt.

4. **Domain-targeted queries** — expanded from 3 generic queries to 6 (3 generic + 3 site:-targeted for HBR/McKinsey/MIT Sloan, Nature/ScienceDirect/arXiv, and university research). Search count raised from 5→8 per query.

5. **Sort + cap** — after deduplication, results are tagged `reputable: bool`, sorted reputable-first, and capped at 25. Reputable results are preserved preferentially.

6. **Prompt updates (`build_research_prompt`)**:
   - Each result tagged `[REPUTABLE]` or `[web]` in the prompt text.
   - Added "SOURCE QUALITY GUIDANCE" block instructing LLM to prefer reputable, treat blogs as weak, TED as trend-only.
   - Claim target: "Produce 6-10 well-sourced key_claims (minimum 4)".
   - research_text target: "4-8 paragraphs" (was 2-4).
   - ≥3 independent sources minimum preserved.

### `tests/test_research_sources.py` (6 tests)

| Test | Validates |
|------|-----------|
| `test_is_reputable` | Allowlist matching (positive + negative cases) |
| `test_reputable_sorted_first` | Reputable results ordered before non-reputable in prompt |
| `test_prompt_has_reputable_guidance` | Prompt contains preference instructions + tags + targets |
| `test_domain_targeted_queries_present` | 6 queries including site: variants |
| `test_results_capped` | ≤25 results in prompt; reputable kept preferentially |
| `test_min_sources_unchanged` | ≥3 sources minimum + TED-as-trend-only preserved |

## Validation

```
tests/test_research_sources.py — 6 passed
Full suite — 543 passed in 129s
```

No real network or paid API calls in tests (all use `unittest.mock.patch`).

## Acceptance Criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | REPUTABLE_DOMAINS allowlist + _is_reputable | ✅ |
| 2 | Domain-targeted queries + reputable prioritized + capped | ✅ |
| 3 | Prompt prefers reputable + targets 6-10 claims + 4-8 para | ✅ |
| 4 | TED-trend-only and ≥3 minimum preserved | ✅ |
| 5 | All 6 tests pass; full suite green | ✅ |
| 6 | No real network / paid calls in tests | ✅ |

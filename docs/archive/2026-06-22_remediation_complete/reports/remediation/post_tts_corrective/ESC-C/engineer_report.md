# ESC-C Engineer Report: Anachronism Guard False-Positive Fix

**Date:** 2026-06-14
**File:** `scripts/direct_storyboard.py`
**Test:** `tests/test_anachronism_guard.py`

## Root Cause

`validate_director_output()` used `brief.find(term)` — a naive substring search. This caused:
- `'scroll'` matching `'scrolls'`, `'scrolling'`, `'scrollbar'` (modern UI verbs)
- `'candle'` matching `'candlestick'` (modern finance term)
- Any term matching as a substring inside longer words

The guard's intent (block ancient/period imagery in modern videos) was correct, but the matching was too broad.

## Changes Applied

### 1. Removed 'scroll' from ANACHRONISM_TERMS (line 49)

`'scroll'` has a dominant modern meaning (scroll a feed). The ancient-scroll case is adequately covered by `'parchment'`/`'manuscript'` which remain in the list.

### 2. Word-boundary regex matching (lines 269–279)

Replaced:
```python
idx = brief.find(term)
if idx >= 0 and term not in src_lower:
```

With:
```python
if term in src_lower:
    continue
match = re.search(r'\b' + re.escape(term) + r'\b', brief)
if match:
```

This ensures:
- `'candle'` does NOT match `'candlestick'` (no word boundary between candle/stick)
- Multi-word terms like `'19th century'` still match correctly
- Negation-aware logic preserved using `match.start()` instead of `idx`

## Acceptance Criteria Verification

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Modern 'scroll'/'scrolling' not flagged | ✅ (term removed) |
| 2 | 'candlestick' not flagged | ✅ (word boundary) |
| 3 | Genuine anachronisms still caught | ✅ (victorian/quill/parchment flagged) |
| 4 | Source-justified terms allowed | ✅ (existing behavior preserved) |
| 5 | Negation-aware logic preserved | ✅ ("no typewriter" not flagged) |
| 6 | All 6 new tests pass; full suite green | ✅ 532 passed |

## Test Results

```
tests/test_anachronism_guard.py — 6 passed
tests/test_direct_storyboard.py — 6 passed (existing, no regression)
Full suite: 532 passed in 114.47s
```

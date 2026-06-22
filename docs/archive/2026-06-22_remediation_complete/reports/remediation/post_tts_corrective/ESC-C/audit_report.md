# ESC-C Audit Report — Anachronism Guard Fix

**Date:** 2026-06-14  
**Auditor:** Kiro subagent (read-only)  
**Scope:** `scripts/direct_storyboard.py` anachronism guard logic  
**Verdict:** PASS

---

## Changes Verified

### 1. `scroll` removed from ANACHRONISM_TERMS (line 46–50)

The term list is now:

```python
ANACHRONISM_TERMS = [
    "19th century", "1800s", "1900s", "mid-century", "victorian", "vintage",
    "period piece", "antique", "manuscript", "parchment", "quill", "candle",
    "old film", "sepia", "black and white", "typewriter",
]
```

`scroll` is absent — no substring match can fire on "scrolls", "scrolling", or "candlestick".

### 2. Word-boundary regex (line 271)

```python
match = re.search(r'\b' + re.escape(term) + r'\b', brief)
```

Uses `\b` anchors so partial-word hits (e.g. "candlestick" matching "candle") are impossible. `re.escape` prevents regex injection from terms with special characters.

### 3. Negation logic preserved (lines 273–276)

Pre-match window scanned for `"no "`, `"not "`, `"without "`, `"never "` — unchanged from prior implementation.

### 4. Source-justification bypass preserved (lines 269–270)

If the term appears in `src_lower` (the source research text), the check is skipped entirely — correct behaviour for historically-justified content.

---

## Risk Assessment

- **False-positive risk:** Eliminated for `scroll*` and `candlestick`. Word-boundary regex prevents substring collisions for all remaining terms.
- **False-negative risk:** Negligible. All genuine period-aesthetic terms (`victorian`, `quill`, `parchment`, `sepia`, `typewriter`, etc.) remain in the list and are caught by the word-boundary match.
- **Regression risk:** None. Full suite (532 tests) passes; dedicated 6-test anachronism file covers the exact scenarios.

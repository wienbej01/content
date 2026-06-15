# UCI-05 Audit Report — Text-Policy False-Positive Fix

**Date:** 2026-06-15  
**Auditor:** kiro-cli (read-only)  
**Verdict:** PASS

## Findings

### 1. `_NO_READABLE_TEXT_POLICIES` guard implemented ✅

Lines 173-175 of `scripts/compile_media_prompts.py`:
```python
_NO_READABLE_TEXT_POLICIES = frozenset((
    "none", "soft_focus_only", "out_of_focus", "no_readable_text", "background",
))
```

### 2. Non-readable broll NOT rerouted ✅

Lines 183-189: when a broll beat's `text_policy` is in `_NO_READABLE_TEXT_POLICIES`:
- Does NOT set `asset_type = "local_graphic"`.
- Instead neutralizes by adding the matched banned term + `"no readable text"` to `negative_prompt`.
- Emits a "neutralized" warning (not a "rerouted" warning).
- Beat stays as `generated_video` with its original model.

### 3. Genuinely-readable-text beats still rerouted ✅

Lines 191-196: the `else` branch (text_policy is empty, absent, or not in the no-readable set):
- Sets `asset_type = "local_graphic"` and `model = "local_graphic"`.
- Emits "rerouted to local_graphic" warning.
- Covers: no text_policy, `text_policy=""`, `text_policy="post_overlay"`, or any value not in the frozen set.

### 4. Hero beats unaffected ✅

Lines 198-204 (hero_cutaway) and 205-210 (hero_lipsync/hero): these branches neutralize banned terms in `negative_prompt` without touching `asset_type`. The `_NO_READABLE_TEXT_POLICIES` branch is broll-only (gate: `shot_type in LOCAL_SHOT_TYPES or shot_type.startswith("broll")`).

### 5. Logic is case-insensitive and strip-safe ✅

Line 183: `(beat.get("text_policy") or "").strip().lower()` — handles missing, whitespace-padded, or mixed-case values safely.

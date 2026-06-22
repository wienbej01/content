# UCI-05 Engineer Report — text-surface policy false-positive fix

**Date:** 2026-06-15
**Status:** ✅ Complete — all acceptance criteria met

## Bug

B003 (`broll_environment`, visual_brief mentions "writing"/"document" as physical actions, all text explicitly out-of-focus) was rerouted to `local_graphic` by the text-surface policy. The policy matched banned terms without checking whether the beat's `text_policy` field indicated no readable text was requested.

Result: 16s of static text cards instead of cinematic b-roll.

## Root cause

`scripts/compile_media_prompts.py` line ~178: the broll reroute branch fired unconditionally on banned-term match for any broll/LOCAL_SHOT_TYPE beat, with no exemption for beats that explicitly declare non-readable text intent via `text_policy`.

## Fix (scripts/compile_media_prompts.py)

Added a `text_policy` check before the reroute in the broll branch:

```python
_NO_READABLE_TEXT_POLICIES = frozenset((
    "none", "soft_focus_only", "out_of_focus", "no_readable_text", "background",
))
```

If `beat.get("text_policy")` is in this set, the beat is **neutralized** (banned term added to negative_prompt with "no readable text") instead of rerouted. If `text_policy` is absent, empty, or `post_overlay`, the existing reroute fires as before.

This preserves the policy's intent (don't ask video models to render readable text) while correctly handling beats that explicitly declare text is out-of-focus/non-readable.

## Tests added (tests/test_uci05_text_policy.py)

| Test | Verifies |
|------|----------|
| `test_out_of_focus_broll_not_rerouted` (×5 policies) | Broll with text_policy=soft_focus_only/out_of_focus/none/no_readable_text/background + banned terms → stays generated_video |
| `test_readable_text_still_rerouted` | Broll without text_policy + banned terms → rerouted to local_graphic |
| `test_empty_text_policy_still_rerouted` | text_policy="" → still rerouted |
| `test_post_overlay_text_policy_still_rerouted` | text_policy=post_overlay → still rerouted |
| `test_hero_with_out_of_focus_unaffected` | Hero neutralization path unchanged |
| `test_negative_prompt_gets_banned_terms` | Neutralized broll has banned term + "no readable text" in negative_prompt |

## Validation

```
tests/test_uci05_text_policy.py     — 10 passed
tests/test_prompt_policy.py         —  6 passed (no regression)
Full suite                          — 603 passed in 148s
```

## Acceptance criteria checklist

- [x] out_of_focus / non-readable-text broll beats are NOT rerouted to local_graphic
- [x] Genuinely-readable-text beats still rerouted/blocked (policy intent preserved)
- [x] Banned terms negated in negative_prompt for the kept generated_video beat
- [x] All tests pass; full suite green

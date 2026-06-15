# UCI-05 Validation Report — Text-Policy False-Positive Fix

**Date:** 2026-06-15  
**Validator:** kiro-cli (read-only)  
**Verdict:** PASS

## Test Results

### Targeted suite: `tests/test_uci05_text_policy.py` + `tests/test_prompt_policy.py`

```
16 passed in 0.13s
```

| Test | Validates |
|------|-----------|
| `TestOutOfFocusBrollNotRerouted` (×5 policies) | soft_focus_only, out_of_focus, none, no_readable_text, background — all stay generated_video |
| `TestReadableTextStillRerouted::test_readable_text_still_rerouted` | No text_policy + banned term → rerouted |
| `TestReadableTextStillRerouted::test_empty_text_policy_still_rerouted` | Empty string text_policy → rerouted |
| `TestReadableTextStillRerouted::test_post_overlay_text_policy_still_rerouted` | post_overlay → rerouted |
| `TestHeroUnaffected::test_hero_with_out_of_focus_unaffected` | Hero lipsync neutralizes, no reroute |
| `TestNegativePromptGetsBannedTerms::test_negative_prompt_gets_banned_terms` | Banned term + "no readable text" appear in negative_prompt |
| `test_prompt_policy.py` (6 tests) | Pre-existing text-surface policy tests still pass |

### Full suite

```
609 passed in 132.86s
```

No regressions.

## Acceptance Criteria Verified

1. ✅ `out_of_focus` / non-readable broll NOT rerouted — stays `generated_video`, terms negated.
2. ✅ Genuinely-readable-text beats STILL rerouted to `local_graphic` (intent preserved).
3. ✅ Hero beats unaffected by the new logic path.
4. ✅ Negative prompt enrichment verified (banned term + "no readable text" injected).
5. ✅ 609/609 tests green — zero regression.

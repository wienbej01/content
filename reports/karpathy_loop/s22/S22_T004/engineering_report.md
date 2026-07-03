# Engineering Report — S22_T004

## Ticket

Define Sonnet storyboard prompt packet and guardrails. Create three prompt files (Director, Repair, Creative Review) plus focused text-presence tests.

## Primary agent

Prompt Guardrail Engineer (`deepseek-v4-pro`)

## Files changed

| File | Action | Purpose |
|------|--------|---------|
| `docs/prompts/STORYBOARD_SONNET5_DIRECTOR.md` | Created | Sonnet 5 storyboard generation prompt with full canonical SSOT output spec, immutable narration rule, strict JSON rule, generic B-roll ban, duration drift policy, segment work orders, channel universe compliance, and conclusion-alignment instruction. |
| `docs/prompts/STORYBOARD_SONNET5_REPAIR.md` | Created | Targeted repair prompt with constraints: fix-only affected entities, no narration changes, keep same IDs, no unrelated rewrites, repair summary with changed fields. |
| `docs/prompts/STORYBOARD_SONNET5_CREATIVE_REVIEW.md` | Created | Creative review prompt with four-perspective review (Visual Director, Filmmaker, Audience, Technical Producer), Sonnet-5 authorship pre-condition check, and Python-authored storyboard rejection (BLOCKED_NON_SONNET_AUTHOR). |
| `tests/test_storyboard_prompt_packet.py` | Created | 13 tests (10 required + 3 additional) verifying guardrail text presence in all three prompt files. |

## Implementation approach

1. **Director prompt**: Comprehensive prompt with system/task fragments, templated input slots (`{approved_script_json}`, `{source_research_text}`, `{bible_texts}`, `{canonical_schema_json}`), and output structure conforming to `schemas/storyboard_v2.schema.json`. Covers all S22_PROMPT_GUARDRAILS requirements: immutable narration, strict JSON, Sonnet 5 authority, segment_work_orders, why_this_visual/narrative_alignment/semantic_purpose, anti-generic B-roll terms, conclusion-alignment, duration drift policy, channel universe compliance, and feedback policy.

2. **Repair prompt**: Minimal scope prompt that explicitly prohibits narration changes and unrelated rewrites. Includes repair_summary requirement with changed_fields tracking. Input slots for validation errors, affected entities, and adjacent context.

3. **Creative review prompt**: Four-perspective review (Visual Director/Filmmaker/Audience/Technical) matching the existing reviewer prompt patterns from `docs/reviewer_prompts/`. Pre-condition Sonnet-5 authorship check with BLOCKED_NON_SONNET_AUTHOR rejection for Python-authored storyboards.

4. **Tests**: 13 pytest tests that load each prompt file and verify required guardrail substrings exist. No LLM calls, no paid APIs. Tests are hermetic.

## Non-goals respected

- No Sonnet live call made
- No wrapper code implemented
- No storyboard schema changes
- No repair loop implemented
- No Python creative fallback introduced

## Commands run

```bash
python3 -m pytest tests/test_storyboard_prompt_packet.py -q -v
# Result: 13 passed in 0.05s

rg -n "approved script is immutable|segment_work_orders|duration_drift_policy|generic" docs/prompts/STORYBOARD_SONNET5_*.md
# Result: 11 matches across all three files, all required terms present
```

## Test coverage summary

| Ticket test # | Description | Status |
|---|---|---|
| 1 | Immutable narration rule | PASS |
| 2 | Strict JSON rule | PASS |
| 3 | Sonnet 5 authority language | PASS |
| 4 | `segment_work_orders` requirement | PASS |
| 5 | `why_this_visual`, `narrative_alignment`, `semantic_purpose` | PASS |
| 6 | Generic B-roll ban | PASS |
| 7 | Conclusion-alignment instruction | PASS |
| 8 | Duration drift policy | PASS |
| 9 | Repair prompt forbids unrelated rewrites | PASS |
| 10 | Creative review bans Python author approval | PASS |

Additional tests: all prompt files exist, repair_summary required, four review perspectives present.

## Pass gates

- Prompts are explicit enough for a lesser model to implement wrapper/validators later: prompts include full schema references, all required fields with descriptions, and explicit error codes.
- Prompt tests prove required guardrail text exists: all 13 tests pass.
- No prompt asks Sonnet to rewrite narration: both Director and Repair explicitly forbid narration mutation.
- No prompt delegates readable text to generated video: text_policy is `post_overlay`, in-scene text is forbidden.

## Limitations

- Prompts reference `{approved_script_json}`, `{source_research_text}`, etc. as template slots; the Python wrapper (S22_T006) will fill these from DB/artifact records.
- The `authoring_model` value `kilo/anthropic/claude-sonnet-5-20250908` is a placeholder; the actual Kilo model ID must be verified by S22_T002 at runtime.
- No prompt compiles or validates at this ticket; those are later ticket behaviors (T005-T012).

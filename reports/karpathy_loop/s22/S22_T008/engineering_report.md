# Engineering Report — S22_T008

## Summary

Created `scripts/validate_storyboard_v2.py` — a semantic alignment validator for the canonical SSOT storyboard contract. The validator enforces business rules beyond JSON Schema validation for B-roll specificity, graphic purpose, overlay grounding, conclusion alignment, readable text in generated video, and emotional reset justification.

## Files created

- `scripts/validate_storyboard_v2.py` — Semantic alignment validator module (317 lines)
- `tests/test_storyboard_semantic_alignment.py` — Test suite (166 lines, 14 test cases)
- `tests/fixtures/storyboard_v2/semantic_generic_broll.json` — Generic B-roll failure fixture
- `tests/fixtures/storyboard_v2/semantic_vague_broll_alignment.json` — Vague B-roll alignment failure fixture
- `tests/fixtures/storyboard_v2/semantic_overlay_source_label_no_ref.json` — Source label overlay without ref
- `tests/fixtures/storyboard_v2/semantic_stat_overlay_no_claim.json` — Stat display overlay without claim ref
- `tests/fixtures/storyboard_v2/semantic_decorative_graphic.json` — Decorative graphic failure fixture
- `tests/fixtures/storyboard_v2/semantic_conclusion_unrelated_visual.json` — Conclusion unrelated visual failure
- `tests/fixtures/storyboard_v2/semantic_emotional_reset_justified.json` — Valid emotional reset (passes)
- `tests/fixtures/storyboard_v2/semantic_emotional_reset_unjustified.json` — Invalid emotional reset (fails)
- `tests/fixtures/storyboard_v2/semantic_readable_text_in_generated.json` — Readable text in generated video failure
- `tests/fixtures/storyboard_v2/semantic_source_grounded_broll.json` — Valid source-grounded B-roll (passes)

## Files modified

- None (all new files)

## Implementation details

### validate_storyboard_v2.py

- **Generic B-roll detection**: Checks `visual_concept` and `narrative_alignment` against a list of 18 common generic phrases ("business people", "professional environment", "generic office", "city skyline", etc.)
- **Vague B-roll alignment**: Requires at least 2 shared tokens between `narrative_alignment` and the segment argument or claim texts. Also checks minimum length of 20 chars.
- **Emotional reset**: Shots with `visual_role=emotional_reset` are handled as a separate code path. They skip the generic B-roll and vague alignment checks, but require a `why_this_visual` justification >= 20 chars.
- **Decorative graphics**: Detects purely decorative graphic shots by checking for decorative keywords ("decorative", "visual interest", "pretty", "aesthetic", "background", "filler") in `visual_concept`, `narrative_alignment`, or `why_this_visual`.
- **Conclusion visual alignment**: For shots in segments with act >= 5, validates that `narrative_alignment` references conclusion keywords ("conclusion", "closing", "takeaway", "reinforce", etc.) or specific claim text.
- **Readable text in generated video**: Detects patterns like "readable text", "on-screen text", "caption", "subtitle" in `visual_concept`, `narrative_alignment`, `must_show`, and `prompt_intent` — with negation-awareness ("no readable text" passes).
- **Overlay grounding**: `source_label` overlays require `source_ref` or `claim_refs`. `stat_display` overlays with text require `claim_refs` or `source_ref`.
- **Non-canonical skip**: Legacy storyboards without `storyboard_contract_version` are allowed through without validation.
- **All errors** follow the `BLOCKED_` naming convention and include `entity_id` and `path` fields.

### Design decisions

- Follows the same pattern as `validate_segment_work_orders.py` — pure validation, no LLM calls, no DB writes, no creative generation.
- Returns structured error dicts rather than raising exceptions, for integration with batch validators.
- The `emotional_reset` visual_role is treated as its own category (not a broll subtype), consistent with the PRD requirement that it's a distinct visual_role with explicit justification.

## Commands run

```bash
python3 -m pytest tests/test_storyboard_semantic_alignment.py -q        # 14 passed
python3 -m pytest tests/test_semantic_role_pipeline.py tests/test_semantic_role_qa.py -q  # 24 passed
python3 -m pytest tests/test_storyboard_v2_schema.py tests/test_segment_work_orders.py tests/test_storyboard_semantic_alignment.py -q  # 46 passed
python3 scripts/validate_storyboard_v2.py tests/fixtures/storyboard_v2/valid_semantic_storyboard.json  # PASS
python3 scripts/validate_storyboard_v2.py tests/fixtures/storyboard_v2/semantic_generic_broll.json     # FAIL with BLOCKED_GENERIC_BROLL
```

## Blockers

None.

## Limitations and residual risks

- The vague alignment check uses simple token overlap (>= 2 shared tokens). This catches obviously vague alignments but could be evaded with superficially relevant text. A future Sonnet-based semantic similarity check could be more robust — but this is explicitly out of scope per the "no LLM creative review" non-goal.
- The generic phrase list is a fixed set of 18 patterns. Additional generic phrases may need to be added over time as the pipeline encounters new patterns.
- No integration with DB staging or gate recording. This is a pure validation module that can be called by downstream stages (S22_T010 repair loop, etc.).

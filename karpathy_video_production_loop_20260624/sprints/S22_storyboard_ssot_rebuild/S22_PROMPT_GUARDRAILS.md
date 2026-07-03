# S22 Prompt Guardrails

## Storyboard authoring prompt

The Sonnet 5 storyboard prompt must include:

- Approved script JSON.
- Exact script revision/hash.
- Source log and citations.
- Claim inventory or claim extraction instructions.
- Channel universe bibles.
- Forbidden patterns.
- Technical constraints.
- Reference asset manifest.
- Output JSON schema.
- Repair and feedback policy requirements.

## Immutable narration rule

The prompt must say:

The approved script is immutable. Do not rewrite, shorten, extend, paraphrase, combine, omit, or reorder narration. Every storyboard beat must reference exact approved script text by segment id and text span.

Any narration mutation is `BLOCKED_SCRIPT_NARRATION_MUTATION`.

## Required output quality

For every segment, Sonnet 5 must provide a segment work order:

- `segment_id`
- `narration_text_exact`
- `argument_summary`
- `viewer_question`
- `retention_role`
- `source_claim_refs`
- `shot_ids`
- `overlay_ids`
- `broll_alignment_instruction`
- `graphic_alignment_instruction`
- `conclusion_alignment_instruction`
- `qa_acceptance_criteria`
- `must_avoid`

For every shot:

- `shot_id`
- `segment_id`
- `visual_role`
- `visual_concept`
- `why_this_visual`
- `narrative_alignment`
- `claim_refs`
- `literal_vs_metaphorical`
- `prompt_intent`
- `must_show`
- `must_avoid`
- `planned_duration_sec`
- `min_usable_duration_sec`
- `max_usable_duration_sec`
- `duration_drift_policy`
- `assembly_fit_policy`
- `generation_risk`
- `fallback_strategy`
- `qa_requirements`

For every overlay:

- `overlay_id`
- `segment_id`
- `shot_id`
- `overlay_type`
- `text`
- `semantic_purpose`
- `source_ref`
- `trigger_phrase`
- `start_time_offset_sec`
- `end_time_offset_sec`
- `position`
- `style_token`
- `animation`
- `safe_for_9x16`
- `qa_rules`

## Anti-generic B-roll rules

The prompt must forbid:

- "business people"
- "professional environment"
- "generic office"
- "people working"
- "stock footage"
- "abstract data"
- "city skyline"
- "person typing"
- any other visual that could fit any corporate video.

Exception: a shot may be generic only if `visual_role` is `emotional_reset`, and the work order explains why the reset is needed.

## Repair prompt rules

Repair prompts must be minimal:

- Include only the affected storyboard entities.
- Include validator errors and adjacent context.
- Require the same IDs unless a split/merge is explicitly requested.
- Forbid narration changes.
- Forbid unrelated rewrites.
- Require a repair summary with changed fields.

## JSON rules

All runtime LLM outputs must be raw JSON only:

- No markdown fences.
- No prose.
- No comments.
- No trailing explanation.
- Parse failure retries once with a JSON-repair prompt, then blocks.


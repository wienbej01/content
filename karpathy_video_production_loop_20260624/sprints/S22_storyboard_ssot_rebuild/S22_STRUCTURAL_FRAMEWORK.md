# S22 Structural Framework

## Layer 1 - LLM-authored semantic storyboard

Sonnet 5 writes the canonical storyboard from the approved script and context packet.

Canonical objects:

- `claim_inventory[]`
- `narrative_beats[]`
- `shots[]`
- `overlays[]`
- `segment_work_orders[]`
- `feedback_policy`
- `timing_policy`
- `approval`

Python must not create these creative decisions. Python may only validate, normalize IDs, compute hashes, and add mechanical metadata.

## Layer 2 - Python validation and guardrails

Python validates:

- JSON schema.
- Stable IDs and refs.
- Segment coverage.
- Approved narration immutability.
- Claim/source refs.
- Shot and overlay semantic fields.
- B-roll specificity.
- Text-surface policy.
- Duration drift policy completeness.
- Model/spend readiness preconditions.
- Repair-loop boundaries.

Validation errors must be machine-readable and start with `BLOCKED_` for blocking conditions.

## Layer 3 - Compatibility projection

Downstream code still expects beat-level fields. S22 keeps compatibility by projecting canonical objects into legacy fields:

- `shot_type`
- `asset_type`
- `model`
- `prompt_class`
- `visual_brief`
- `graphic`
- `graphics`
- `visual_intent`

These are projection outputs, not creative source of truth.

The projection must be deterministic and traceable back to canonical `shot_id` and `overlay_id`.

## Layer 4 - DB and artifact truth

The approved storyboard is intent. Rendered media and QA are observed truth.

Planned values:

- `shots[].planned_duration_sec`
- `render_units.required_duration_ms`
- `shots[].min_usable_duration_sec`
- `shots[].max_usable_duration_sec`

Observed values:

- `artifacts.duration_ms`
- `render_units.actual_render_duration_ms`
- QA validations
- compliance findings
- frame samples
- provider job status

When observed truth differs from planned intent, the system must:

1. Record the discrepancy.
2. Decide if assembly can trim/pad/extend.
3. Decide if regeneration is required.
4. Decide if Sonnet repair is required.
5. Stale only affected downstream stages.
6. Block stale artifact reuse unless lineage proves compatibility.

## Stage relationship

Canonical order:

1. research
2. write_script
3. review_script
4. gate_a_content
5. storyboard_generation
6. storyboard_validation
7. storyboard_creative_review
8. gate_storyboard
9. tts
10. audio_timing
11. reconcile_timing
12. compile_media
13. compile_overlays
14. gate_a_spend
15. generate_media
16. record_observed_media
17. qa_media
18. feedback_route
19. repair/regenerate as needed
20. render_overlays
21. assemble
22. qa_final
23. gate_b_review
24. publish

S22 tickets may introduce stages incrementally, but the final design must preserve this dependency logic.


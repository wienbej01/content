# S22 Feedback Loop Rules

## Principle

Storyboard timing is planned intent. Rendered artifact duration and QA results are observed truth. Observed truth must be recorded and may cause trim, pad, regenerate, Sonnet repair, human review, or downstream invalidation.

## Duration drift inputs

Planned:

- `shots[].planned_duration_sec`
- `shots[].min_usable_duration_sec`
- `shots[].max_usable_duration_sec`
- `render_units.required_duration_ms`

Observed:

- `artifacts.duration_ms`
- `render_units.actual_render_duration_ms`
- ffprobe evidence
- QA reports

## Drift policies

Allowed `duration_drift_policy` values:

- `trim_ok`
- `pad_ok`
- `extend_still_ok`
- `regenerate_required`
- `sonnet_repair_required`
- `human_review_required`

Examples:

- Planned 4.2s, actual 5.1s B-roll, policy `trim_ok`: accept if QA passes; assembly trims to required window and records trim metadata.
- Planned 4.2s, actual 3.9s local graphic, policy `extend_still_ok`: accept if extension is visually clean.
- Planned 4.2s, actual 3.2s hero lipsync: block unless sync and audio policy still pass.
- Actual duration exceeds max usable duration: create blocking change request.

## Compliance feedback inputs

Compliance gates may report:

- generic B-roll
- wrong James identity
- unsupported claim
- irrelevant graphic
- missing source label
- text-surface violation
- bad safe zone
- sync failure
- freeze/loop artifact
- duration drift
- stale artifact reuse

## Feedback routing

Every finding must map to:

- entity type: `claim`, `narrative_beat`, `shot`, `overlay`, `render_unit`, `artifact`
- entity id
- severity: `BLOCKER`, `MAJOR`, `MINOR`, `NOTE`
- repair action
- repair owner
- downstream stages to stale

Allowed repair actions:

- `trim_in_assembly`
- `pad_or_extend`
- `regenerate_same_prompt`
- `sonnet_repair_storyboard`
- `rerender_overlay`
- `human_review_required`
- `reject_unfixable`

## Invalidation

Changed storyboard entities stale:

- storyboard review
- gate_storyboard
- tts if approved narration mapping changed
- audio_timing if timing spans changed
- reconcile_timing
- compile_media
- compile_overlays
- gate_a_spend
- generate_media for affected render units
- qa_media for affected artifacts
- render_overlays for affected overlays
- assemble
- qa_final
- gate_b_review

Changed media artifact stales:

- qa_media
- repair
- graphics_compositing if applicable
- assemble
- qa_final
- gate_b_review

No downstream stage may reuse stale artifacts without proof that the new requirement hash matches the old artifact lineage.


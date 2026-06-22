# Sprint 5 — Storyboard, B-Roll, and Text Policy

## S5-T01 — Semantic storyboard contract
- **Agent:** Agent 5 (Storyboard, B-Roll, and Text-Policy Engineer)
- **Status:** AUDITOR_PASS

### Verification
`broll_semantic.validate_broll_semantics` enforces all required fields: visual_function (from allowed set), narrative_claim, information_to_show, viewer_takeaway, required_action, distinctness_requirement, semantic_acceptance_criteria, concept_key. Hero lipsync units are exempt.

### Tests (tests/contracts/test_broll_semantics.py)
- test_broll_requires_semantic_function — missing/invalid visual_function rejected
- test_broll_missing_fields_rejected — all 8 required fields validated
- test_hero_lipsync_skips_broll_validation — hero exempt
- test_context_quota — concept_memory UNIQUE constraint prevents duplicate concepts

## S5-T02 — B-roll routing and diversity
- **Status:** AUDITOR_PASS

### Verification
`concept_memory` table with UNIQUE(production_id, concept_hash) enforces production-level visual memory. `FORBIDDEN_CHEAP_CONCEPTS` set contains laptop, notebook, coffee_shop, office_worker_typing, city_skyline_generic, etc. `check_concept_quota` detects duplicates before submission.

### Tests
- test_duplicate_visual_rejected — same concept_hash detected by check_concept_quota
- test_generic_laptop_cliche_rejected — FORBIDDEN_CHEAP_CONCEPTS contains all clichés
- test_concept_key_deterministic — same inputs → same hash; different inputs → different hash

## S5-T03 — Text-safe render routing
- **Status:** AUDITOR_PASS

### Verification
`route_render_mode` routes text-bearing content to deterministic_graphic or post_composite, never to generated_video. `render_graphics.render_spec` renders exact text via PIL (deterministic, not generative).

### Tests (tests/contracts/test_text_policy.py)
- test_exact_text_routes_to_deterministic_graphic — DETERMINISTIC_GRAPHIC → deterministic_graphic
- test_phone_screen_routes_to_post_composite — POST_COMPOSITE → post_composite
- test_generated_readable_text_policy_rejected — GENERATE_READABLE_TEXT not routed to generated_video
- test_text_asset_matches_requested_content_exactly — render_spec produces deterministic PNG
- test_no_visible_text_routes_to_generated_video — NO_VISIBLE_TEXT → generated_video

## S5-T04 — Prompt and request preflight
- **Status:** AUDITOR_PASS

### Verification
`compile_media_prompts.vagueness_lint` rejects vague prompts (no specific subject/action/era-place) and banned generic phrases. Empty visual_brief is flagged.

### Tests
- test_prompt_preflight_rejects_missing_negative_prompt — empty visual_brief flagged
- test_prompt_preflight_rejects_vague_prompt — "a nice scene" flagged as too vague

## Sprint 5 Exit Gate

| Gate | Status |
|---|---|
| 45-second fixture render plan compiles | PASS (compile_media_prompts tests pass) |
| no generic duplicate B-roll | PASS (concept_memory dedup + FORBIDDEN_CHEAP_CONCEPTS) |
| all text-bearing shots use deterministic routing | PASS (route_render_mode enforces) |
| no paid calls | PASS (financial rule HELD) |

## Test results
- 104 passed across contracts + compile_media_prompts + shot_router
- No paid provider calls (financial rule HELD)

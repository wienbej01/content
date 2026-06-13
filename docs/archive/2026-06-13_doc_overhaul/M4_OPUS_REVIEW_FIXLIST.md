# M4 Opus Review Fixlist

**Companion to** `M4_OPUS_REVIEW_REPORT.md`. Apply P0 rows before M5. P1 before media generation. P2 later.

**Priorities:** P0 = blocking before M5 · P1 = important before media generation · P2 = useful later

| Priority | File | Issue | Exact Fix | Blocking Before M5? |
|---|---|---|---|---|
| **P0** | UNIVERSE_BIBLE.md + constraints.json | "host-led episode" used as the trigger for the most important hard-fail but never defined | Add to UNIVERSE_BIBLE a definition section: "Every episode is host-led by default. An episode is non-host-led only if its storyboard explicitly sets `allow_all_broll: true`." Add to constraints.json: `"host_led_default": true, "non_host_led_condition": "storyboard.allow_all_broll == true"`. | **Yes** |
| **P0** | FORBIDDEN_PATTERNS.md, TECHNICAL_BIBLE.md, QA_RUBRIC.md, constraints.json | James-presence threshold inconsistent (">60% beats absent" vs "60–75% presence") and measurement unit undefined | Standardize on **beat-count**: presence % = (beats where `james_presence != absent`) / (total non-transition/title beats). Reconcile all four files to: teaser ≥60%, explainer ≥45%, trailer ≥40%, short ≥70%; 0% = hard fail. Add `"presence_measured_by": "beat_count"` to constraints.json `a_roll_rules`. | **Yes** |
| **P0** | constraints.json + PROMPT_RULES.md | `camera_angle_id` listed as required for every prompt, but only the 7 studio shots have angle IDs — would break b-roll validation | In constraints.json split `required_prompt_fields` into `universal_required_fields` (all prompts) and `studio_required_fields` (adds `camera_angle_id`). Mark `camera_angle_id` nullable for b-roll. Update PROMPT_RULES §3 to state `camera_angle_id` is required only when `location_id` is the studio/library. | **Yes** |
| **P0** | PROMPT_RULES.md, constraints.json, M4_M10_SCHEMA_DESIGN.md | `text_policy` enum differs across files (`none/post_overlay` vs `none/soft_focus_only/post_overlay` vs nested object) | Standardize to enum `none / soft_focus_only / post_overlay` everywhere. In constraints.json keep the descriptive object but add `"text_policy_enum": ["none","soft_focus_only","post_overlay"]`. | **Yes** |
| P1 | assets/reference/ (filesystem) + REFERENCE_ASSET_MANIFEST.md | `assets/reference/` folders don't exist; M4.3 skipped; seed images not mapped | Create `assets/reference/{james,studio_library,cat,wardrobe,color_palette,props}/` each with `.gitkeep`. Copy or symlink `brand/James_harrington_{front,3_4,side,vertical}.png` into `assets/reference/james/` under the seed asset IDs, OR update manifest paths to point at the existing `brand/` files. Mark statuses accurately. | No (needed before M8/M10) |
| P1 | constraints.json + storyboard schema (M4_M10_SCHEMA_DESIGN.md) | No `episode_type` enum; ratio bands can't be looked up | Add `"episode_types": ["teaser","explainer","trailer","short"]` to constraints.json. Add `episode_type` field to the storyboard top-level schema. | No |
| P1 | constraints.json | No measurable "scene evolution" hook | Add `"storyboard_rules": {"min_distinct_angles_or_locations": 3}`. | No |
| P1 | constraints.json | Cat reference requirement not machine-readable | Add `"cat_requires_reference": true` (parallel to a_roll reference requirement). | No |
| P1 | constraints.json | Quality markers ("premium/grounded") only in prose | Add `"quality_markers": {"shallow_dof_aroll": true, "consistent_color_temp": true, "no_clipped_highlights": true, "no_crushed_blacks": true, "light_has_visible_source": true}` for future media QA. | No |
| P1 | TECHNICAL_BIBLE.md §10 + constraints.json | Music dB numbers misaligned (-26/-30 prose vs -22 max / -26 target JSON) | Align to: target -28 dB, range -22 (loudest) to -32 (quietest) under narration. Update both. | No |
| P1 | PROMPT_RULES.md | A_ROLL_TALKING_HEAD vs A_ROLL_CHARACTER_PRESENT_VOICEOVER distinction (lipsync vs not) could waste Seedance credits | Add one-line clarification: TALKING_HEAD = direct address + lipsync from final narration; CHARACTER_PRESENT_VOICEOVER = James in frame not addressing camera, audio stripped, no lipsync. | No |
| P1 | PROMPT_RULES.md | storyboard `camera`/`movement` → prompt `camera_angle_id`/`camera_movement` mapping unstated | Add a mapping note so the M8 compiler maps fields correctly. | No |
| P1 | TECHNICAL_BIBLE.md §10 | continuous_voiceover "required" but assemble.py doesn't support it yet (M7) | Add note: continuous_voiceover is the final-publish target; assembly support is an M7 task; M5 storyboards may declare `narration_mode` ahead of that capability. | No |
| P2 | QA_RUBRIC.md / BACKGROUND_CAT_BIBLE.md | Cat-frequency (1 in 3–4 episodes) has no tracking mechanism (no DB by design) | Add a note that cat frequency is a human-review item, not an automated check. | No |
| P2 | constraints.json | `b_roll_rules` category tokens don't map to scene_type enum | Optional: add a mapping table from b-roll category → scene_type. | No |

---

## Quick reference: the 4 P0 fixes

1. **Define "host-led"** → UNIVERSE_BIBLE + constraints.json
2. **One presence measurement (beat_count) + reconciled thresholds** → 4 files
3. **camera_angle_id studio-only** → constraints.json + PROMPT_RULES
4. **Standardize text_policy enum** → PROMPT_RULES + constraints.json + schema-design

All four are definitional clarifications. None require rewriting a document. Estimated effort: one short Sonnet sprint.

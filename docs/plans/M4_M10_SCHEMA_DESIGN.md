# M4–M10 Schema Design & Bible Content Checklists

**Companion to** `M4_M10_CREATIVE_CONTROL_WORKPLAN.md`. Defines every JSON schema and the exact content each M4 bible must contain. A cheaper model uses this so it does not invent structure.

**Validation policy:** JSON Schema files (draft-07) are documentation. Runtime validation is **stdlib Python** hand-rolled checks (follow the `validate_script`/`validate_manifest` pattern in existing scripts). No `jsonschema` dependency unless a sprint proves it necessary.

---

## Storyboard schema (`schemas/storyboard.schema.json`)

Top-level object:
| Field | Type | Required | Notes |
|---|---|---|---|
| project_id | string | yes | matches script |
| episode_title | string | yes | |
| target_audience | string | yes | |
| narrative_promise | string | yes | the "why keep watching" |
| total_target_duration | number | yes | seconds |
| narration_mode | enum | yes | `continuous_voiceover` \| `segment_tts` |
| allow_all_broll | bool | no | default false |
| beats | array<Beat> | yes | non-empty |

Beat object:
| Field | Type | Required | Notes |
|---|---|---|---|
| beat_id | string | yes | unique |
| source_script_segment_id | string | yes | links to script segment |
| narration_text | string | yes (unless TRANSITION/TITLE_CARD) | |
| narrative_function | string | yes | hook/context/argument/example/cta/etc |
| scene_type | enum | yes | (see workplan §5) |
| a_roll_or_b_roll | enum | yes | `a_roll`\|`b_roll`\|`insert`\|`transition`\|`title` |
| james_presence | enum | yes | `present_speaking`\|`present_silent`\|`absent` |
| location_id | string | yes | e.g. STUDIO_LIBRARY or b-roll location tag |
| reference_assets | array<string> | no | asset_ids |
| audio_source | enum | yes | `continuous_narration`\|`segment_tts`\|`none` |
| audio_continuity_group | string | no | beats sharing one narration span |
| duration_target_sec | number | yes | |
| start_time_target_sec | number | no | if known from timing map |
| end_time_target_sec | number | no | |
| camera | string | yes | from Technical Bible vocabulary |
| lighting | string | yes | |
| palette | string | yes | |
| movement | string | yes | |
| props | array<string> | no | |
| text_policy | enum | yes | `none`\|`post_overlay` |
| crop_safety | enum | yes | `center_safe`\|`full_frame_16x9` |
| forbidden_elements | array<string> | no | extra negatives beyond defaults |
| transition_in | string | yes | cut/fade/etc |
| transition_out | string | yes | |
| qa_notes | string | no | |

---

## Audio timing schema (`schemas/audio_timing.schema.json`)

| Field | Type | Notes |
|---|---|---|
| project_id | string | |
| narration_mode | enum | `continuous_voiceover`\|`segment_tts` |
| narration_file | string | path to master mp3/wav |
| total_duration_sec | number | |
| wps | number | words per second over whole narration |
| sentences | array | each: `{index, text, start_sec, end_sec, duration_sec}` |
| pauses | array | each: `{start_sec, duration_sec, is_long_pause}` |
| beat_time_map | array | each: `{beat_id, start_sec, end_sec}` |
| flags | array<string> | e.g. `wps_below_2.0`, `long_pause_gt_2s` |

---

## Media prompt plan schema (`schemas/media_prompt_plan.schema.json`)

| Field | Type | Notes |
|---|---|---|
| project_id | string | |
| source_storyboard | string | path |
| prompts | array<PromptEntry> | |

PromptEntry:
| Field | Type | Notes |
|---|---|---|
| beat_id | string | |
| prompt | string | compiled, includes universe+technical constraints |
| negative_prompt | string | default negatives + beat forbidden_elements |
| model | string | `seedance_2_0` (A-roll/James) \| `wan2_7` (b-roll) |
| reference_assets | array<string> | approved asset_ids |
| expected_duration_sec | number | |
| output_path | string | **Canonical clip location (single source of truth).** Generation writes here; QA, reuse-detection, and assembly all read here. Convention `assets/media/{segment_id}/{beat_id}.mp4`. Never moved without updating this field. |
| audio_policy | enum | `strip` \| `keep_lipsync` |
| crop_safety | enum | `center_safe`\|`full_frame_16x9` |
| text_policy | enum | `none`\|`post_overlay` |
| audio_slice | object | hero_lipsync only: `{file, start_sec, end_sec, speech_len_sec, padded_len_sec, slice_sha256, parent_mp3_sha256}`. `padded_len_sec = max(ceil(speech_len_sec+0.2), 4)` — the **4s Seedance minimum** (`constraints.json → lipsync_render_rules`); sub-4s beats are padded up or merged, never rendered shorter. |
| qa_checklist | array<string> | per-clip checks from QA_RUBRIC |

---

## Media QA schema (`schemas/media_qa.schema.json`)

| Field | Type | Notes |
|---|---|---|
| project_id | string | |
| clips | array<ClipQA> | |
| approved_for_assembly | array<string> | beat_ids passing |
| requires_regeneration | array<string> | beat_ids failing |

ClipQA:
| Field | Type | Notes |
|---|---|---|
| beat_id | string | |
| path | string | |
| technical | object | `{readable, has_video, has_audio, width, height, duration, codec, crop_safe}` |
| creative | object | optional/stubbed `{james_consistent, studio_consistent, cat_consistent, palette_ok, lighting_ok, camera_ok, realism_ok, text_clean, no_random_chars, no_logos}` |
| pass | bool | |
| blocking_issues | array<string> | |

---

## Reviewer output schema (shared, M6)

| Field | Type | Notes |
|---|---|---|
| persona | string | which reviewer |
| pass | bool | |
| score | number | 0–10 |
| issues | array<string> | |
| blocking_issues | array<string> | |
| recommended_fixes | array<string> | |
| may_proceed | bool | |

Aggregate: `may_proceed = all(personas.pass) and not any(persona.blocking_issues)`.

---

## M4 bible content checklists

Each bullet is a required section/answer. The writer fills prose; structure is fixed here.

### README.md
- One-paragraph purpose; how Universe vs Technical bible differ; index/links to all 11 docs + `brand/BRAND_SPEC.md`; "constraints.json is the machine-readable source for the compiler" note.

### UNIVERSE_BIBLE.md
- channel purpose; target audience; emotional promise; worldview; tone
- recurring locations (study/library primary; any others)
- recurring visual motifs; recurring objects
- "what belongs" list; "what does not belong" list
- the feels-like / must-not-feel lists (verbatim from workplan §4A)

### JAMES_CHARACTER_BIBLE.md (extends BRAND_SPEC §2/§9)
- role in channel; personality; visual identity; age impression (~60); posture
- facial expression range; eye-contact rules; movement rules; behavior rules
- signature gestures (list, marked OPTIONAL/occasional)
- quirks; speaking presence; thinking presence; what James does when not speaking
- appearance in A-roll / during voiceover / in b-roll; how James must NEVER appear
- wardrobe palette; acceptable outfits; forbidden outfits; accessories; grooming; hair consistency; glasses rule (default: none — OPEN QUESTION); watch/pen/notebook/laptop use; hand behavior
- the feels-like / must-not-feel lists (verbatim from workplan §4)

### JAMES_RECORDING_STUDIO_LIBRARY.md
- room identity; layout; background; bookshelves; desk; chair; lamp; books; wall color; window/light source; plants/artwork; laptop/papers/notebook/pen
- the seven approved camera-angle IDs, each with: framing description, where James sits/stands, what's in frame, 9:16 center-safe note:
  `STUDIO_LIBRARY_WIDE_001`, `_MEDIUM_DESK_001`, `_CLOSEUP_001`, `_OVER_SHOULDER_001`, `_SIDE_PROFILE_001`, `_STANDING_BOOKSHELF_001`, `_CAT_BACKGROUND_001`
- where the cat may appear; allowed time-of-day looks; forbidden changes (verbatim rules from workplan §4)
- "all angles belong to the same spatial layout" statement

### BACKGROUND_CAT_BIBLE.md
- appearance; breed/impression (default: British Shorthair, blue-grey); fur color/pattern; size; temperament
- typical locations; typical behaviors; frequency (occasional); when NOT to use
- subtlety level; forbidden cat behaviors (verbatim from workplan §4)
- "identical every time" statement + reference asset_id

### PEOPLE_AND_EXTRAS_BIBLE.md
- when others may appear; visual style for colleagues/founders/execs/professionals
- wardrobe rules; diversity handled tastefully/realistically; behavior; background-only default
- no influencer characters; no fake/real recognizable people; no distracting b-roll faces unless planned; never replace James as anchor

### TECHNICAL_BIBLE.md
- all sub-sections from workplan §4B: Color, Lighting, Camera, Framing, A-roll, B-roll, Audio, Editing — each as an explicit do/don't list

### PROMPT_RULES.md
- the per-prompt required-fields list + default negatives + text rule (verbatim from workplan §4)

### FORBIDDEN_PATTERNS.md
- the explicit anti-pattern list, each with "instead, do X" (workplan §4)

### QA_RUBRIC.md
- Storyboard QA checklist; Media QA checklist; the canonical automatic-fail conditions (workplan §9)

### REFERENCE_ASSET_MANIFEST.md
- folder layout under `assets/reference/{james,studio_library,cat,wardrobe,color_palette,props}/`
- naming conventions (the ID lists from the workplan)
- per-asset record fields: `asset_id`, `file_path`, `purpose`, `allowed_use`, `forbidden_use`, `prompt_anchor`, `required_for` (a_roll/b_roll), `center_safe_9x16` (bool)
- map existing seeds: `brand/James_harrington_front.png` → `JAMES_FRONT_DESK_001` (etc.) as starting entries, status `seed_needs_review`

### constraints.json (machine-readable, created in M4.2)
```
{
  "palette_hex": ["#1B2A4A","#C8973E","#F5F0E8","#2D2D2D","#6B1D2A"],
  "default_negative_prompt": "no futuristic holograms, no cyberpunk, no neon, no floating UI, no robots, no garbled text, no readable generated text, no fake logos, no distorted hands, no uncanny faces, no random smiling stock people, no sci-fi setting, no overdesigned startup office, no AI dashboard",
  "approved_studio_angles": ["STUDIO_LIBRARY_WIDE_001","STUDIO_LIBRARY_MEDIUM_DESK_001","STUDIO_LIBRARY_CLOSEUP_001","STUDIO_LIBRARY_OVER_SHOULDER_001","STUDIO_LIBRARY_SIDE_PROFILE_001","STUDIO_LIBRARY_STANDING_BOOKSHELF_001","STUDIO_LIBRARY_CAT_BACKGROUND_001"],
  "forbidden_patterns": ["all_broll_host_led","no_james","futuristic_ai_city","hologram_dashboard","unreadable_text","random_people_replacing_james","motivational_stock","sci_fi_environment","visible_logos"],
  "text_policy_default": "post_overlay",
  "wps_bands": {"calm": [2.2, 2.6], "teaser": [2.6, 3.0], "flag_below": 2.0, "flag_above": 3.2}
}
```

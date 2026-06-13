# Documentation Audit

**Generated:** 2026-06-12
**Scope:** Full inventory of all documentation files in the repo.

---

## Classification Key

- **Current** — Accurate as of this audit; trusted for production use
- **Mostly current** — Accurate in substance; minor updates needed
- **Historical** — Useful for context; not production guidance
- **Stale** — Contains outdated information that could mislead
- **Superseded** — Replaced by a newer document
- **Planned-only** — Documents intentions not yet implemented
- **Placeholder** — Empty directory or file with no content

---

## All Documents Inspected

### `docs/channel_universe/` — Channel Universe Bibles

| Path | Purpose | Status | Notes |
|---|---|---|---|
| `constraints.json` | Machine-readable production constraints | **Mostly current** | Bug: `model_routing_policy.grounded_broll = wan2_7` (banned). Must be updated. |
| `UNIVERSE_BIBLE.md` | What exists in James's world | **Current** | Comprehensive; actively used |
| `TECHNICAL_BIBLE.md` | How the world is filmed/edited | **Current** | Comprehensive; actively used |
| `JAMES_CHARACTER_BIBLE.md` | James appearance + character | **Current** | Actively used |
| `JAMES_RECORDING_STUDIO_LIBRARY.md` | Studio environment | **Current** | Actively used |
| `BACKGROUND_CAT_BIBLE.md` | Cat appearance rules | **Current** | Actively used |
| `PEOPLE_AND_EXTRAS_BIBLE.md` | Background character rules | **Current** | Actively used |
| `FORBIDDEN_PATTERNS.md` | Banned visual patterns | **Current** | Actively used |
| `PROMPT_RULES.md` | Prompt construction rules | **Current** | Used in compile_media_prompts.py |
| `QA_RUBRIC.md` | QA scoring rubric | **Current** | Used in human review |
| `REFERENCE_ASSET_MANIFEST.md` | Reference asset inventory | **Mostly current** | Physical files not all generated yet (see docs/reference_assets/) |
| `VOICE_LOCKING.md` | Voice consistency strategy | **Current** (untracked new file) | Newly created; documents Kling CLI limitations re voice cloning |
| `README.md` | Index of the channel_universe dir | **Current** | — |

### `docs/plans/` — Operational Plans

| Path | Purpose | Status | Notes |
|---|---|---|---|
| `FLAGSHIP_001_PRODUCTION_STATUS.md` | Flagship 001 production status | **Stale** | Says seedance blocked and media not generated; reality: 151 clips exist, video assembled. Must be updated. |
| `FLAGSHIP_001_HANDOVER.md` | Handover prompt for 001 production | **Historical** | Was for GCE VM session; VM is now idle. Still useful as context. |
| `FLAGSHIP_001_AUDIT_2026-06-12.md` | VM vs home server audit | **Current** | Today's audit; accurate |
| `FLAGSHIP_001_SPRINT_2026-06-12.md` | Multi-agent sprint plan for 001 fixes | **Current** | Active plan for fixing hook 001 |
| `LLM_KIRO_CLI_INVOCATION_PLAN.md` | How to invoke LLM via kiro-cli | **Current** | Accurate; implemented in llm_call.py |
| `M4_M10_ACCEPTANCE_TESTS.md` | Acceptance tests for M4-M10 pipeline | **Mostly current** | Some tests reference old models |
| `M4_M10_CREATIVE_CONTROL_WORKPLAN.md` | Full M4-M10 pipeline design | **Historical** | Valuable context; mostly implemented. Cross-check with PIPELINE_IMPLEMENTED.md |
| `M4_M10_IMPLEMENTATION_PROMPTS.md` | LLM prompts for M4-M10 implementation | **Historical** | Useful context; mostly superseded by actual code |
| `M4_M10_SCHEMA_DESIGN.md` | Schema designs for M4-M10 | **Historical** | Mostly implemented; some deferred |
| `M4_OPUS_REVIEW_FIXLIST.md` | M4 Opus review fixlist | **Historical** | Issues addressed in subsequent implementation |
| `M4_OPUS_REVIEW_REPORT.md` | M4 Opus review report | **Historical** | Valuable architecture review; mostly addressed |
| `OVERNIGHT_BLOCKERS.md` | Overnight session blockers | **Historical** | Session-specific; resolved |
| `OVERNIGHT_IMPLEMENTATION_LOG.md` | Overnight implementation log | **Historical** | Session-specific context |
| `OVERNIGHT_PARKED_ITEMS.md` | Empty file | **Placeholder** | File is empty |
| `OVERNIGHT_VALIDATION_REPORT.md` | Post-overnight test results | **Historical** | 50/50 tests then; now 137/157 pass |
| `REFERENCE_ASSET_GENERATION_PLAN.md` | Reference asset generation plan | **Planned-only** | Not yet fully executed |
| `TEASER_02_REBUILD_READINESS_REPORT.md` | Teaser 02 readiness | **Historical** | Superseded by flagship 001 production |
| `TELEGRAM_DELIVERY_LATER_PLAN.md` | Telegram delivery plan | **Planned-only** | Not yet implemented |
| `_baseline_tests.txt` | Baseline test output snapshot | **Historical** | From pre-M5 state |

### `docs/reviewer_prompts/`

| Path | Purpose | Status |
|---|---|---|
| `audience.md` | Audience retention reviewer prompt | **Current** |
| `filmmaker.md` | Filmmaker/narrative reviewer prompt | **Current** |
| `technical.md` | Technical production reviewer prompt | **Current** |
| `universe.md` | Universe/brand reviewer prompt | **Current** |
| `audio.md` | Audio pacing reviewer prompt | **Current** |

### `docs/prompts/`

| Path | Purpose | Status |
|---|---|---|
| `SCRIPT_PROMPT_LIBRARY.md` | Script writing prompt library | **Planned-only** | Documents prompt templates for script writing; no script_writer.py yet |

### `docs/reference_assets/`

| Path | Purpose | Status |
|---|---|---|
| `JAMES_10_VARIATION_EXPANSION_PLAN.md` | James reference image expansion | **Planned-only** |
| `JAMES_CONTINUITY_STRATEGY.md` | James visual continuity strategy | **Current** |
| `JAMES_IDENTITY_RECOVERY_REPORT.md` | Identity recovery after bad generation | **Historical** |
| `JAMES_MODEL_ASSESSMENT.md` | Higgsfield model assessment for James | **Mostly current** |
| `JAMES_REFERENCE_LOCK_PROTOCOL.md` | Protocol for locking James reference | **Current** |
| `REFERENCE_ASSET_GENERATION_RUNBOOK.md` | Reference generation runbook | **Current** |
| `REFERENCE_ASSET_INVENTORY.md` | Asset inventory | **Mostly current** |
| `REFERENCE_ASSET_QA_CHECKLIST.md` | QA checklist for reference assets | **Current** |
| `REFERENCE_GENERATION_RESULTS.md` | Results of generation runs | **Historical** |
| `REFERENCE_STILL_PROMPT_PACK.md` | Prompt pack for reference stills | **Current** |
| `STUDIO_LIBRARY_STILL_EXPANSION_PLAN.md` | Studio library expansion plan | **Planned-only** |

### `docs/` (top level)

| Path | Purpose | Status |
|---|---|---|
| `RESEARCH_SOP.md` | Research sourcing SOP | **Current** |
| `SYSTEM_OVERVIEW.md` | [NEW] System overview | **Current** |
| `ARCHITECTURE.md` | [NEW] Architecture | **Current** |
| `PIPELINE_IMPLEMENTED.md` | [NEW] Implemented pipeline | **Current** |
| `PIPELINE_GAPS_AND_PENDING_STEPS.md` | [NEW] Gap analysis | **Current** |
| `OPERATING_GUIDE.md` | [NEW] Operating guide | **Current** |
| `REVIEW_AND_QUALITY_SYSTEM.md` | [NEW] Quality system | **Current** |
| `DOCUMENTATION_AUDIT.md` | [NEW] This document | **Current** |
| `NEXT_LLM_HANDOVER.md` | [NEW] LLM handover | **Current** |

### `docs/` — Empty Placeholder Directories

| Path | Created | Status |
|---|---|---|
| `docs/llm/` | Overnight session | **Placeholder** — empty |
| `docs/pipeline/` | Overnight session | **Placeholder** — empty |
| `docs/media_qa/` | Overnight session | **Placeholder** — empty |
| `docs/storyboard/` | Overnight session | **Placeholder** — empty |
| `docs/audio/` | Overnight session | **Placeholder** — empty |
| `docs/media_prompting/` | Overnight session | **Placeholder** — empty |

These can be populated with detailed reference docs in future sprints, or removed.

### `scripts/` — Script READMEs

| Path | Purpose | Status |
|---|---|---|
| `scripts/ASSEMBLY_README.md` | Assembly CLI + manifest schema docs | **Current** |
| `scripts/TTS_README.md` | TTS CLI + script schema docs | **Current** |
| `scripts/MEDIA_README.md` | Media generation CLI docs | **Mostly current** |
| `scripts/MEDIA_PACK_README.md` | Media pack CLI docs | **Mostly current** |

### `strategy/`

| Path | Purpose | Status |
|---|---|---|
| `BUSINESS_PLAN.md` | Full business plan | **Current** |
| `TIMEPLAN.yaml` | Master timeplan with milestones | **Current** |
| `TIMEPLAN_GUIDE.md` | How to use the timeplan | **Current** |
| `ARCHITECTURE_MVP.md` | MVP architecture principles | **Current** |
| `AUTOMATION_PIPELINE.md` | Automation pipeline design | **Mostly current** |
| `IDEAS.md` | Idea bank | **Active** |
| `archive/ARCHITECTURE.md` | Old architecture doc | **Superseded** — by ARCHITECTURE_MVP.md |
| `archive/ARCHITECTURE_REVIEW.md` | Old architecture review | **Superseded** |
| `archive/M1_AUDIT.md` | M1 audit | **Historical** |

### `tools/`

| Path | Purpose | Status |
|---|---|---|
| `tools/AI_Influencer_Identity_Consistency_Plan.md` | Identity consistency plan | **Planned-only** |

### `brand/`

| Path | Purpose | Status |
|---|---|---|
| `brand/BRAND_SPEC.md` | Brand specification | **Current** |
| `brand/prompts/higgsfield_character.md` | Higgsfield character prompt | **Current** |

### `inspi/`

| Path | Purpose | Status |
|---|---|---|
| `inspi/YTextract.md` | Competitive analysis notes | **Active** |

---

## Contradictions Found

| # | Location | Contradiction | Impact |
|---|---|---|---|
| C1 | `docs/channel_universe/constraints.json:model_routing_policy.grounded_broll = wan2_7` | wan2_7 is banned per `generate_media.py:BANNED_MODELS` and `model_routing.yaml` | `compile_media_prompts.py` would route b-roll to banned model |
| C2 | `docs/plans/FLAGSHIP_001_PRODUCTION_STATUS.md` | Says media is not generated and seedance is blocked | Reality: 151 clips generated, video assembled |
| C3 | `tests/test_shot_router.py` | Expects `veo3` and `minimax_hailuo` models | Current config uses `seedance_2_0` and `kling3_0`; veo3 and minimax_hailuo are banned |
| C4 | `tests/test_m3e.py` | Expects `wan` as default b-roll model | Current default is `kling3_0` |
| C5 | `configs/james/voice_spec.yaml` | Documents Kling native TTS voice as a production approach | This is the CLI-only fallback, not used in production; ElevenLabs is canonical |
| C6 | `docs/channel_universe/constraints.json:audio_policy.final_video_narration_mode = continuous_voiceover` | States continuous_voiceover is the production mode | Flagship 001 was produced in segment_tts mode |

---

## Documentation Debt

1. Empty placeholder dirs (`docs/llm/`, `docs/pipeline/`, etc.) should either be populated or removed
2. `FLAGSHIP_001_PRODUCTION_STATUS.md` needs a final status update
3. `voice_spec.yaml` header needs a deprecation notice
4. `constraints.json` model_routing_policy needs the wan2_7 fix
5. Test files need updating to reflect current model config

---

## Archive Actions Taken

See `docs/archive/2026-06-12_system_mapping/ARCHIVE_INDEX.md` for documents moved to archive.

No documents were moved from `docs/plans/` — all are historical context worth preserving.
The strategy/archive/ directory already contains correctly-archived strategy docs.

## Wave 9 — Sprint Exit: Validated E2E Production Run

### TKT-901 — Sprint exit: full validated production run (human-authorized)

| Field | Value |
|-------|-------|
| Ticket | TKT-901 |
| Title | Sprint exit: full validated production run |
| Requirement IDs | R-E2E-1, F1..F6, all prior requirements |
| Priority | critical |
| Severity | high |
| Risk level | high |
| Execution class | REASONING_CRITICAL |
| Wave | 9 |
| Deps | W1..W8 accepted |
| Status | planned |

#### Observable outcome

A single production run (seed → publish) exercising:
- Reference-frame variation (TKT-201, TKT-202)
- Hybrid b-roll router (TKT-302)
- Pixel-level QC (TKT-303)
- Citation verification (TKT-401, TKT-402)
- Act-scored music (TKT-501)
- Paradigm-shift silence (TKT-502)
- EDL editorial (TKT-601, TKT-602)
- Multi-model reviewer cast (TKT-701) — default config only
- Budget allocator (TKT-802)
- Thumbnail + title candidates (TKT-703, TKT-704)
- Pre-publish checklist (TKT-705)
- Lipsync provider (TKT-102)

Every gate satisfied by production-produced evidence. Evidence bundle in `evidence/TKT-901/`.

#### Human authorization requirement

Any step requiring a REAL paid API call (Higgsfield Seedance/ElevenLabs, vision LLM at volume, stock API free-tier-exceeded, flagship budget tier) is BLOCKED until the user explicitly authorizes in the session prompt. If not authorized, each such step reports:
```
BLOCKED: <step> requires paid call — human must authorize before proceeding.
```
All zero-cost scaffolding (frame selection, citation check, audio scoring rules, budget allocation logic, thumbnail generation from existing frames, title candidate generation via existing LLM profile) runs regardless.

The human gate steps (content approval, final review) are presented with the AI-flagged issues from TKT-702 and the thumbnail/title candidates from TKT-703/TKT-704 so the human makes the final creative selections.

#### Preconditions and baseline

- Waves 0-8 fully accepted (all tickets in `accepted_tickets` in STATE.json).
- `YT_TEST_MODE=1 python3 -m pytest -q` passes on the post-W8 codebase.
- Environment: all required API keys present OR each paid step is BLOCKED.

#### Implementation steps

1. Human authorizes a seed + video type + format (short or explainer recommended for first run).
2. Enable all WCR config flags:
   ```
   VISUAL_VARIATION_MODE=chapter
   BROLL_ROUTER_MODE=hybrid
   PIXEL_QA_MODE=on
   CITATION_VERIFY_MODE=on
   UNSOURCED_CLAIM_MODE=block
   SOURCE_DIVERSITY_MODE=on
   AUDIO_SCORING_MODE=act
   SILENCE_MODE=on
   DUCKING_MODE=selective
   CHAPTER_MARKERS_MODE=on
   EDL_MODE=on
   LIPSYNC_PROVIDER_MODE=single
   DUCKING_MODE=selective
   ```
3. Run `produce_db.py run <production_id>` with the chosen seed.
4. At each stage, capture evidence.
5. At gate_a_content: review AI-flagged issues from TKT-702, select a thumbnail variant.
6. At gate_b_review: final human approval with all evidence surfaces.
7. At publish: present title candidates; human selects (if authorization given to publish).
8. Archive the full evidence bundle.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| production | full run with WCR flags | all gates satisfied | manual, evidence archived |
| inspect | `produce_db.py inspect <id>` | report contains all new flags | same |
| regression | `YT_TEST_MODE=1 python3 -m pytest -q` | 2,825+ pass | same |

#### Acceptance gates

- G1: All WCR rules operational on a single production (via inspect report).
- G2: All Wave gates W1..W8 re-verified on the post-W8 codebase.
- G3: Full pytest suite passes (2,825+).
- G4: Evidence bundle `evidence/TKT-901/` complete (gate reports, config flags, candidate selections, final publish decision).

#### Audit focus

- Gate-by-gate: verify each gate was satisfied by production-produced evidence, not review-only.
- Budget: verify total cost was within the configured cap.
- Any step requiring paid authorization was explicitly human-approved in the session.
- No `--force-unsafe` used at any gate.

#### Rollback and recovery

- Each WCR feature is behind a config flag. Rolling back to pre-WCR behavior = set all flags to their `off`/`generative`/`flat`/`single` defaults.
- Production artifacts are additive and persist; rollback only affects future productions.

#### Completion evidence

- Evidence archive: `evidence/TKT-901/`.
- Summarize: files changed across sprint, total tickets accepted, total cycle counts, residual risks.

---

## Wave 9 gate

- W9-G1: TKT-901 accepted by independent validator.
- W9-G2: All Wave gates W1..W8 re-verified on post-W8 codebase.
- W9-G3: Full pytest suite passes.
- W9-G4: Evidence archive complete.

---

## Sprint completion handoff

On sprint completion, the sprint achieves:

1. **Visual variation:** episodes rotate reference frames across acts; frame-gap and fatigue constraints block monotony (F1).
2. **B-roll diversification:** generative is the fallback, not the choice; pixel-level QC catches text/face contamination (F2, F6).
3. **Research credibility:** citations are programmatically verifiable; unsourced claims block script acceptance (F3).
4. **Audio craft:** act-scored music, paradigm-shift silence, chapter cues, frequency-selective ducking (F4).
5. **Editorial craft:** EDL overrides and emotional holds enable editor-level control without regenerating content.
6. **Reviewer diversity:** reviewer cast is config-driven; gate reports surface AI-flagged issues.
7. **Pre-publish optimization:** thumbnails + title candidates generated before publish.
8. **Budget optimization:** spend allocated by beat-attention-weight within cap (INV-6).
9. **Lipsync resilience:** provider interface + health monitor + failover path behind config flags (F5).

All improvements are programmatic (rule-driven, config-driven, or interface-driven). No manual creative steps introduced.

Residual risks: any paid-call-requiring path (stock API paid tier, secondary lipsync provider, multi-model reviewers, flagship budget tier) remains behind explicit human authorization.

---

*Wave 9 compiled 2026-07-07. Total: 9 Waves, 41 tickets, ~40 requirements, 6 failure modes covered, 8 invariants preserved.*

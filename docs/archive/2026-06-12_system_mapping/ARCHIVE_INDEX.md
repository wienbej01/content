# Archive Index — 2026-06-12 System Mapping Pass

**Date:** 2026-06-12
**Author:** System audit pass (Kiro/Sonnet)
**Purpose:** Documents the archiving decisions made during the 2026-06-12 documentation sprint.

---

## Summary

During this audit pass, no documents were moved to this archive directory. After review, all existing documentation was determined to have sufficient value to remain in place:

- `docs/plans/` files: mix of historical context and active plans — all preserved
- `strategy/archive/` files: already correctly archived prior to this pass
- `docs/channel_universe/` files: all active and in use

The `HIGH` confidence threshold for archiving was not met for any individual document. Instead, each document has been classified in `docs/DOCUMENTATION_AUDIT.md` with recommended actions.

---

## Candidate Archive Files (not moved — confidence < High)

The following files are candidates for archiving in a future cleanup pass, but were not moved because:
(a) They contain non-trivial historical context useful for continuity
(b) Archiving could lose traceability to past decisions

| Original Path | Reason for Candidacy | Confidence | Action |
|---|---|---|---|
| `docs/plans/OVERNIGHT_BLOCKERS.md` | Session-specific; resolved | Medium | Leave in place; nothing to lose by keeping |
| `docs/plans/OVERNIGHT_IMPLEMENTATION_LOG.md` | Session-specific; code now exists | Medium | Leave in place; historical context |
| `docs/plans/TEASER_02_REBUILD_READINESS_REPORT.md` | Superseded by flagship 001 work | Medium | Leave in place; teaser 02 may resume |
| `docs/plans/TELEGRAM_DELIVERY_LATER_PLAN.md` | Not yet implemented but still intended | Low | Leave in place; still a pending task |
| `docs/plans/_baseline_tests.txt` | Snapshot from old test run | Medium | Leave in place; regression reference |
| `docs/plans/M4_M10_IMPLEMENTATION_PROMPTS.md` | Mostly superseded by actual code | Medium | Leave in place; useful for future prompting |
| `docs/plans/M4_M10_ACCEPTANCE_TESTS.md` | References old models | Medium | Leave in place; update model names in next sprint |
| `strategy/archive/ARCHITECTURE.md` | Already in strategy/archive/ | — | Already archived; no action |
| `strategy/archive/ARCHITECTURE_REVIEW.md` | Already in strategy/archive/ | — | Already archived; no action |
| `strategy/archive/M1_AUDIT.md` | Already in strategy/archive/ | — | Already archived; no action |

---

## High-Confidence Archive Candidates (for future pass)

None identified at High confidence. All documents in the repo have at least some ongoing value or are harmless to keep.

---

## Stale Information (fix in place, not archive)

The following documents have stale content but should be **updated in place** rather than archived, because they are still referenced and active:

| Document | Stale Content | Fix Needed |
|---|---|---|
| `docs/plans/FLAGSHIP_001_PRODUCTION_STATUS.md` | Says media not generated, seedance blocked | Update to reflect: 151 clips generated, video assembled 2026-06-12 |
| `docs/channel_universe/constraints.json` | `model_routing_policy.grounded_broll = wan2_7` (banned) | Change to `kling3_0` |
| `configs/james/voice_spec.yaml` | Reads as production approach for Kling native TTS | Add deprecation notice in header |

---

## What Was Actually Archived

Nothing was moved in this pass. The archive directory was created as a structural placeholder for future archiving operations.

If a future LLM session archives documents, they should be listed here with:
- Original path
- New archive path  
- Reason archived
- Superseding document (if any)
- Confidence: High / Medium / Low

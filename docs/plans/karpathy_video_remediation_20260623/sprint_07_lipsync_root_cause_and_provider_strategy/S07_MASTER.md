# Sprint 07 Master — Lipsync Root Cause and Provider Strategy

## Goal
Determine the root cause of the canary lipsync failure before any further paid render.

## Tickets
1. S07_T001 — SyncNet or reliable lipsync metric
2. S07_T002 — Audio slice vs provider diagnostic alignment
3. S07_T003 — Canary visual forensics
4. S07_T004 — Root cause decision
5. S07_T005 — Next render strategy

## Render policy
No actual video render/provider generation. LLM calls allowed.
HIGGSFIELD_DRY_RUN=1, KARPATHY_LOOP_RENDER_LOCK=1.

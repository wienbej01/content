# Sprint 13 — Audio-island assembly for hero lip sync

## Objective

Fix the conflict between HERO_SYNC_LOCKED clips and global continuous voiceover. Hero lip-sync units must assemble as audio+video islands using compensated/provider-aligned artifacts.

## Sprint success criteria

- HERO_SYNC_LOCKED segments are never muted in continuous assembly.
- HERO_SYNC_LOCKED segments use compensated_artifact_path when present.
- If compensated_artifact_path is missing, assembly blocks.
- BROLL_FLEX and SILENT_GRAPHIC still use narration/music correctly.
- Final audio is built from hero audio islands + narration slices + music bed.
- Regression proves old global-overlay behavior cannot occur for hero segments.

## Ticket list

- `S13_T001` — Define audio-island contract
- `S13_T002` — Enforce compensated hero artifact requirement
- `S13_T003` — Implement audio-island assembly path
- `S13_T004` — Audio seam QA
- `S13_T005` — Sprint 13 integration regression

## Required agents

- Context Librarian
- Software Engineer
- Software Auditor
- Software Validator
- Steering Committee for sprint gate

## Model routing

Use `MODEL_ROUTING_GUIDE.md`. Critical tickets in this sprint should use `ZAI_BEST_REASONING` for audit/validation.

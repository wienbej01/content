# Karpathy Loop Plan — AI Influencer / Corporate Education Video Production

This package is a ready-to-copy planning bundle for the `wienbej01/content` repo branch:

`forensic/use_ai_to_manage_your_time_efficiently-20260620T151859Z`

It is designed for execution in Claude Code CLI connected to a Z.ai coding plan/model endpoint. It defines:

- global loop rules
- Claude Code agent definitions
- sprint-level master plans
- individual ticket files
- audit and validation gates
- model routing guidance
- loop-state templates
- a full execution prompt for Claude Code

## Purpose

Turn the current improved but not-yet-publish-grade AI video production system into a working end-to-end system for high-quality corporate education / self-improvement videos.

## Critical non-negotiables

1. Do not rebuild existing infrastructure.
2. Extend the current DB-native pipeline and validation architecture.
3. Hero lip-sync must be treated as audio+video islands, not blindly muted and overlaid with global narration.
4. Labels are not evidence. A segment labelled `BROLL_FLEX` must visually validate as b-roll.
5. Local graphics must be deterministic, template-rendered, semantically aligned, and visually professional.
6. Test-local artifacts must not be called publish-grade.
7. Every pass must be evidence-backed.
8. Every failure must fail loud with a `BLOCKED_*` reason.

## Existing repo context assumed

The current repo already has:

- DB-native production/render unit/artifact state
- `scripts/assemble.py`
- `scripts/assemble_db.py`
- provider job and artifact tracking
- SyncNet/audio-offset evaluator scripts
- compensated hero remux helper
- final QA / Gate B concepts
- render-lock/dry-run controls
- sprint loop report pattern

This package deliberately avoids building parallel infrastructure.


## Model routing update

Default routing is now optimized for Claude Code + Z.ai Coding Plan:

- GLM-4.7 for bulk coding tickets.
- GLM-4.7-FlashX / GLM-4.7-Flash for mechanical context, docs, and loop-state work.
- GLM-5.2[1m] for architecture-critical tickets, hard audits, publish-grade policy, and final integration.

See `MODEL_ROUTING_GUIDE.md`, `MODEL_ESCALATION_POLICY.md`, and `configs/claude_code_zai_settings.example.json`.

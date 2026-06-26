# Global Instructions for All Agents

## Mission

Improve the existing automated AI video production system until it reliably produces high-quality, end-to-end corporate education videos with strong lip sync, meaningful b-roll, professional deterministic graphics, and honest publish-grade QA.

## Hard rules

### 1. Do not rebuild what already exists

Do not create a parallel pipeline, duplicate DB, duplicate assembly engine, duplicate provider registry, or new orchestration system.

Extend existing infrastructure:

- `scripts/assemble.py`
- `scripts/assemble_db.py`
- existing DB migrations
- existing `render_units`, `provider_jobs`, `artifacts`, `validations`
- existing reports layout
- existing eval scripts
- existing Gate B final approval concept

### 2. Fail loud

Any publish-critical violation must stop execution with a clear `BLOCKED_*` message.

Examples:

- `BLOCKED_HERO_COMPENSATED_ARTIFACT_MISSING`
- `BLOCKED_HERO_SYNC_UNVERIFIED`
- `BLOCKED_SHOT_MIX_CONTRACT`
- `BLOCKED_VISUAL_ROLE_QA`
- `BLOCKED_GRAPHIC_QA`
- `BLOCKED_PUBLISH_PROFILE`
- `BLOCKED_AUDIO_ISLAND_CONTRACT`

### 3. No fake green

A test that only checks file existence is not sufficient. Every pass must prove the invariant the ticket is about.

### 4. Evidence required

Every ticket must write:

- `engineering_report.md`
- `audit_report.md`
- `validation_report.md`
- relevant JSON evidence
- exact commands run
- exact tests run
- exact files changed

### 5. Minimal, targeted changes

Each ticket should touch the smallest set of relevant files. Large refactors are not allowed unless explicitly required by the ticket.

### 6. Respect render locks

Never trigger paid provider rendering unless the ticket explicitly allows it and render lock/dry-run checks permit it.

### 7. Publish-grade means publish-grade

Test-local outputs may pass technical smoke checks but must not be labelled publish-grade.

## Current architecture risk to fix

The current continuous voiceover path mutates the visual bed and overlays a global audio track. This conflicts with hero lip-sync, because hero clips must retain compensated/provider-aligned audio. The future assembly path must support audio islands.

## Definition of done for any ticket

A ticket is complete only when:

1. Implementation is done.
2. Unit/regression tests are added or updated.
3. Required commands are run.
4. Evidence report is written.
5. Auditor finds no BLOCKER/MAJOR issues.
6. Validator confirms the ticket pass criteria.

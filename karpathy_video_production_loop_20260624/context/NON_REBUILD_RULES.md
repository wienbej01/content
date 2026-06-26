# Non-Rebuild Rules

## Existing infrastructure not to duplicate

Do not duplicate:

- production database
- artifact registry
- provider job registry
- validation table
- assembly engine
- report folder pattern
- final QA / Gate B concept
- render lock / dry-run pattern

## Allowed additions

Allowed:

- small DB migrations to add missing fields
- stricter validators
- new eval scripts that integrate with validations
- local deterministic graphics renderer
- configs for thresholds/provider capabilities/format contracts
- tests and regression fixtures
- prompt templates for Visual Director
- report templates

## Change discipline

Every code change must answer:

1. Which existing file or table am I extending?
2. Which invariant am I enforcing?
3. Which test proves it?
4. Which old behavior is now blocked?

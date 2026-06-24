# S02_T003 Hero No-Temporal-Edit Enforcement

## Purpose

Ensure HERO_SYNC_LOCKED visuals cannot be retimed, looped, frozen, or trimmed through speech in any assembly path.

## Failure classes addressed

```text
F-ASM-001
```

## Allowed files

```text
scripts/assemble.py
scripts/production_repo.py
tests/**
```

## Required tests

```text
- speed_change on hero raises BLOCKED
- loop on hero raises BLOCKED
- freeze_extension on hero raises BLOCKED
- trim_through_speech on hero raises BLOCKED
- non-hero b-roll still allows safe trim/pad where policy permits
```

## Pass gates

PASS if all hero temporal edits fail closed in tests and no actual render occurs.

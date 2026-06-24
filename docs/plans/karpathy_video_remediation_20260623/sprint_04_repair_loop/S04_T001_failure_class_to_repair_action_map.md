# S04_T001 Failure Class to Repair Action Map

## Purpose

Map each failure class to a deterministic repair action and target stage.

## Allowed files

```text
scripts/media_service.py
scripts/stage_runner.py
scripts/repair*.py
docs/**
tests/**
```

## Required mapping examples

```text
F-LIP-003 -> re-slice or regenerate hero unit after verifying source audio
F-LIP-004 -> re-run audio_timing/reconcile_timing/assemble, not provider render first
F-GFX-001 -> re-plan graphic duration or split graphic
F-TEXT-001 -> regenerate b-roll with stricter prompt or replace with local/still
F-QA-002 -> block pipeline, do not repair media
```

## Pass gates

PASS if every known failure class maps to one target stage and one change type.

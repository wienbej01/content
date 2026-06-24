# S01_T004 Lipsync Validation DB Records

## Purpose

Persist lipsync eval evidence into DB validations so QA cannot pass without it.

## Failure classes addressed

```text
F-QA-001
F-QA-002
F-LIP-001
```

## Allowed files

```text
scripts/media_service.py
scripts/assemble_db.py
scripts/production_repo.py
db/migrations/** only if necessary and approved by ticket evidence
tests/**
```

## Required behavior

For hero render units:

```text
- qa_media_contract must include lipsync eval evidence or explicit blocked_dependency
- final qa must include aggregate lipsync status for deliverable
- missing lipsync eval must not pass as green
```

## Pass gates

PASS if a hero unit with missing lipsync evidence cannot receive a full QA pass unless marked diagnostic-only with human gate required.

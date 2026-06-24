# S03_T001 Deterministic Graphics Eval

## Purpose

Verify local graphics render from deterministic specs and remain linked to DB/spec hashes.

## Failure classes addressed

```text
F-GFX-003
F-QA-001
```

## Allowed files

```text
scripts/render_graphics.py
scripts/media_service.py
scripts/evals/**
tests/**
```

## Required eval

Check:

```text
- deterministic_text_spec exists
- text hash matches rendered artifact metadata
- rendered image/video exists
- dimensions correct
- text length within safe bounds
```

## Pass gates

PASS if local graphics cannot pass QA without deterministic spec/provenance.

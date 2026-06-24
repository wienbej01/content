# S02_T004 Visual Bed Duration Contract

## Purpose

Tighten assembly duration checks so excessive mismatches cannot pass.

## Failure classes addressed

```text
F-ASM-002
F-GFX-001
```

## Allowed files

```text
scripts/assemble.py
scripts/assemble_db.py
tests/**
```

## Required behavior

```text
- visual bed duration delta threshold must be realistic, not 120 seconds
- hero spans use strict timing thresholds
- graphics/stills can use explicit hold policy
- excessive shortfall fails before mux
```

## Pass gates

PASS if a synthetic visual bed > threshold mismatch fails before final output.

# S03_T003 Static Graphic Hold Gate

## Purpose

Fail or warn when a static graphic/title card holds too long without explicit hold policy.

## Failure classes addressed

```text
F-GFX-001
F-ASM-003
```

## Required thresholds

Initial thresholds:

```text
warn_static_graphic_hold_sec: 4.0
fail_static_graphic_hold_sec: 6.0
allow longer only if explicit hold_policy=true and editorial justification exists
```

## Allowed files

```text
scripts/assemble_db.py
scripts/assemble.py
scripts/evals/**
tests/**
```

## Pass gates

PASS if the known bad final 7s static card fails or warns as expected.

# S04_T003 Rerun Minimal Affected Stages

## Purpose

Avoid expensive full reruns. Rerun only the stage(s) affected by the failure class.

## Required behavior

```text
- timing failure does not trigger provider render first
- source-slice mismatch can trigger re-slice before regenerate
- static graphic hold can re-render local graphic/assembly without provider video
- provider text-risk can target one b-roll render unit only, but actual render remains locked before Sprint 06
```

## Pass gates

PASS if change-request routing chooses minimal stage in tests.

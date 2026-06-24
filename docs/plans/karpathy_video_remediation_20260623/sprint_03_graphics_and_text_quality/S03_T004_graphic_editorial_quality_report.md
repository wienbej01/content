# S03_T004 Graphic Editorial Quality Report

## Purpose

Produce a structured report for graphic usefulness, not just render correctness.

## Failure classes addressed

```text
F-GFX-002
```

## Required behavior

Use LLM calls if helpful. LLM calls are allowed from the start. The report must be structured and tied to deterministic text specs.

Required fields:

```json
{
  "graphic_id": "",
  "text": "",
  "duration_sec": 0,
  "editorial_role": "setup|contrast|summary|callout|transition",
  "is_complete_thought": true,
  "hierarchy_ok": true,
  "recommended_revision": ""
}
```

## Pass gates

PASS if weak graphics are identified as editorial defects without touching provider render.

# S04_T004 Repair Audit Report

## Purpose

Produce an audit report showing what repair would do and whether it would spend/render.

## Required output

```json
{
  "production_id": "",
  "change_requests": [],
  "would_call_provider_render": false,
  "render_lock_status": "PASS",
  "minimality_ok": true,
  "issues": []
}
```

## Pass gates

PASS if repair audit prevents provider render before unlock and reports exact planned reruns.

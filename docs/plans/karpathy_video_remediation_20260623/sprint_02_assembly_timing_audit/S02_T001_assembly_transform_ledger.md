# S02_T001 Assembly Transform Ledger

## Purpose

Record exactly what assembly did to each clip: trim, scale, crop, mute, overlay, pad, concat, mix, loudnorm.

## Failure classes addressed

```text
F-ASM-001
F-ASM-002
F-PROV-001
```

## Allowed files

```text
scripts/assemble.py
scripts/assemble_db.py
tests/**
reports/karpathy_loop/sprint_02/S02_T001/**
```

## Required implementation

Create JSON ledger per assembled output:

```json
{
  "production_id": "",
  "deliverable": "",
  "clips": [
    {
      "render_unit_id": "",
      "timeline_span_id": "",
      "source_artifact": "",
      "start_ms": 0,
      "end_ms": 0,
      "operations": ["scale_crop", "mute", "trim"],
      "forbidden_hero_operation_detected": false
    }
  ]
}
```

## Pass gates

PASS if every output clip has a transform ledger and hero units show no forbidden operation.

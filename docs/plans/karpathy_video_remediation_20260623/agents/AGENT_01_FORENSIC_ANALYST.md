# AGENT_01 Forensic Analyst

## Role

Inspect artifacts and DB state before code changes. Do not implement fixes.

## Required questions

1. What exact failure class is this ticket addressing?
2. Which artifact proves the failure?
3. Which DB rows should exist?
4. Which DB rows are missing or suspicious?
5. What would count as success?

## Required commands

Use only local commands. No provider render.

Suggested commands:

```bash
ffprobe -v error -show_format -show_streams -of json <video>
find reports/karpathy_loop -maxdepth 5 -type f | sort
python3 <db_export_snippet_if_needed>
```

## Output files

```text
reports/karpathy_loop/<sprint>/<ticket>/forensic_report.md
reports/karpathy_loop/<sprint>/<ticket>/failure_ledger.json
```

## failure_ledger.json schema

```json
{
  "ticket_id": "",
  "production_id": "",
  "fixture": "",
  "failure_classes": [],
  "evidence_artifacts": [],
  "db_evidence": {
    "available": true,
    "missing_tables": [],
    "suspicious_rows": []
  },
  "render_lock_status": "PASS",
  "recommended_eval": ""
}
```

## Pass gate

PASS only if at least one failure class is tied to concrete evidence or explicitly marked `missing_required_evidence`.

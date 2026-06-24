# AGENT_02 Eval Engineer

## Role

Design and/or implement deterministic evals before code changes. An eval can be diagnostic in early tickets, but it must produce machine-readable output.

## Eval classes

Use these categories:

```text
video_probe
scene_timeline
freeze_static_detection
audio_slice_hash
provider_audio_compare
syncnet_lipsync
mouth_motion_proxy
assembly_transform_ledger
graphics_text_policy
final_defect_ledger
```

## Required output files

```text
reports/karpathy_loop/<sprint>/<ticket>/eval_design.md
reports/karpathy_loop/<sprint>/<ticket>/eval_result_before.json
```

## eval_result_before.json schema

```json
{
  "ticket_id": "",
  "eval_name": "",
  "eval_type": "",
  "subject": {
    "production_id": "",
    "artifact_path": "",
    "render_unit_id": null,
    "timeline_span_id": null
  },
  "command": "",
  "status": "pass|fail|diagnostic|blocked",
  "expected_on_bad_fixture": "fail|diagnostic",
  "metrics": {},
  "thresholds": {},
  "issues": []
}
```

## Pass gate

PASS if:

```text
- command is deterministic
- JSON output exists
- eval result is fail or diagnostic on the bad fixture
- thresholds are explicit
- no provider render call is made
```

FAIL if eval is prose-only or always-green.

# S00_T002 Video Forensic Report

## Purpose

Create baseline scene/timeline/media defects report for the bad video.

## Failure classes addressed

```text
F-LIP-001
F-GFX-001
F-GFX-002
F-TEXT-001
```

## Allowed files

```text
reports/karpathy_loop/sprint_00/S00_T002/**
fixtures/bad_runs/*/contact_sheet.jpg
fixtures/bad_runs/*/scene_timeline.csv
fixtures/bad_runs/*/forensic_summary.json
```

## Forbidden files

```text
scripts/** unless Eval Engineer explicitly proposes a reusable forensic helper and Loop Controller approves
```

## Required forensic work

1. Probe streams and duration.
2. Extract representative frames/contact sheet.
3. Detect scene breaks or manually record timeline.
4. Mark static holds.
5. Record provisional lipsync observations as provisional if no SyncNet yet.

## Required eval work

Create `video_forensic_summary.json` with at least:

```json
{
  "duration_sec": 0,
  "scene_count": 0,
  "max_static_hold_sec": 0,
  "suspected_lipsync_offset_ms": null,
  "issues": []
}
```

## Pass gates

PASS if scene timeline and summary JSON exist and identify known defects without actual render.

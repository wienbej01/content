# S07_T005 Next Fix Strategy

## Root Cause (from S07_T004)
**E_ASSEMBLY_MASTER_WINDOW_FAILURE** caused by **B_AUDIO_SLICE_SHIFTED_OR_PADDED**

The provider returns a video with internally-correct lip sync (SyncNet: -40ms), but the embedded audio is shifted/padded relative to the source slice (~335ms). When assembly strips this audio and overlays the raw source slice without compensation, the lip sync breaks (+400ms).

---

## 1. Preferred Fix Path

### Per-render-unit hero lipsync compensation

For each HERO_SYNC_LOCKED render unit:

```
1. Provider job completes → diagnostic audio extracted
2. Measure source slice vs provider diagnostic audio offset:
   offset_ms = cross_correlate(source_slice, diagnostic_audio)
3. Store offset_ms and confidence in provider_jobs table
4. Generate compensated remux candidate:
   ffmpeg -i provider_video -i source_slice
          -c:v copy -map 0:v:0 -map 1:a:0
          -af "adelay={offset_ms}|{offset_ms}" -shortest
          candidate_compensated.mp4
5. Run SyncNet on compensated candidate
6. Only ALLOW into assembly if SyncNet offset < 160ms threshold
7. Block with BLOCKED_HERO_SYNC_UNVERIFIED if compensation fails
```

### Compensation equation
```
compensation_ms = diagnostic_audio_offset_ms  (from cross-correlation)
                 = ~335ms for the current S000 canary
```

### Sign convention
```
- Negative offset means diagnostic audio LEADS source
- Compensation = apply adelay = diagnostic_offset_ms (positive delay aligns source)
  - offset = -575ms → adelay = 575ms (delay source by 575ms)
  - offset = -335ms → adelay = 335ms
```

---

## 2. Fallback Fix Paths

| Priority | Path | Condition | Risk |
|----------|------|-----------|------|
| 1 (preferred) | Per-unit offset compensation + SyncNet gate | SyncNet available, diagnostic audio extracted | SyncNet required for each unit |
| 2 | Preserve provider audio (no source overlay) | Provider audio passes SyncNet control | Non-deterministic audio in master |
| 3 | Block assembly + request re-slice | Offset > salvageable threshold (600ms) | Requires human intervention |
| 4 | Re-slice audio with padding matching provider offset | Source slice timing known | May not generalize |

---

## 3. Explicit Pass Gates for the Fix

| Gate | Criteria |
|------|----------|
| G1 | Provider diagnostic audio offset is measured and stored per render unit |
| G2 | Compensated remux candidate is generated locally (no provider render) |
| G3 | SyncNet passes on compensated candidate (< 160ms offset, or >= 5.0 confidence) |
| G4 | Assembly consumes compensated video (not raw source overlay) |
| G5 | SyncNet gates the assembly pipeline: missing SyncNet → BLOCKED_HERO_SYNC_UNVERIFIED |
| G6 | Regression suite includes compensated assembly test |
| G7 | No actual provider render in Sprint 08 implementation |
| G8 | Verification against S06_T004 regression suite |

---

## 4. DB Schema (new fields)

| Table | New Column | Type | Description |
|-------|-----------|------|-------------|
| `provider_jobs` | `source_slice_vs_diagnostic_offset_ms` | INTEGER | Cross-correlation offset between source slice and diagnostic audio |
| `provider_jobs` | `audio_offset_confidence` | REAL | Normalized correlation confidence (0.0-1.0) |
| `provider_jobs` | `compensated_artifact_path` | TEXT | Path to locally-generated compensated remux MP4 |
| `render_units` | `syncnet_offset_frames` | INTEGER | Most recent SyncNet offset for the best face track |
| `render_units` | `syncnet_confidence` | REAL | SyncNet confidence for the best face track |
| `render_units` | `syncnet_pass` | BOOLEAN | Whether SyncNet offset < 160ms threshold |

---

## 5. Exact Local Validation Command Expectations

```bash
# Measure offset
python3 scripts/evals/eval_audio_offset.py \
  --source <source_slice.wav> \
  --diagnostic <diagnostic_audio.wav> \
  --out /tmp/offset_result.json

# Generate compensated remux
python3 scripts/evals/remux_compensated_hero.py \
  --video <provider_video.mp4> \
  --source-audio <source_slice.wav> \
  --offset-ms <offset_ms> \
  --out /tmp/compensated.mp4

# Verify with SyncNet
cd syncnet_python
python3 run_pipeline.py --videofile /tmp/compensated.mp4 --reference compensated --data_dir /tmp/syncnet
python3 run_syncnet.py --reference compensated --data_dir /tmp/syncnet
# Expected: offset < 160ms, confidence >= 2.0

# Assembly gate check
python3 scripts/evals/check_hero_assembly_readiness.py \
  --render-unit-id <id> \
  --production-id prod_2f9bb58c0508465fb51ac6b4578bba92
# Expected: BLOCKED_HERO_SYNC_UNVERIFIED if no SyncNet pass
```

---

## 6. Rejected Blind Rerender

The strategy explicitly REJECTS:
- Blind provider rerender without offset measurement
- Retrying the same provider request hoping for different results
- Adjusting prompt/model parameters without first fixing assembly timing
- Full production rerender before single-unit fix is validated

---

## 7. Sprint 08 Ticket Plan

| Ticket | Title | Purpose |
|--------|-------|---------|
| T001 | provider_audio_offset_ledger | Add offset measurement columns + populate from existing data |
| T002 | compensated_hero_remux_helper | Local remux helper to apply offset compensation |
| T003 | assembly_uses_compensated_hero_units | Modify assembly to use compensated video instead of raw source overlay |
| T004 | syncnet_gate_for_hero_units | Add SyncNet gate that blocks assembly if hero lipsync unverified |
| T005 | full_local_assembly_regression | End-to-end regression with compensated assembly |
| GATE | exit_criteria | Sprint 08 exit criteria |

## 8. Strategy decision

| Field | Value |
|-------|-------|
| Preferred path | Per-unit hero lipsync compensation with SyncNet gate |
| Rejects | Blind provider rerender |
| DB evidence required | provider_jobs: offset_ms, confidence; render_units: syncnet_offset, syncnet_pass |
| Local validation | remux + SyncNet before assembly |
| Sprint 08 scope | Implementation of compensation pipeline + assembly gate |
| Render policy | No provider render in Sprint 08 — use existing canary + local remux only |

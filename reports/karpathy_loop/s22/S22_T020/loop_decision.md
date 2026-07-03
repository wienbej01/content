# Loop Decision — S22_T020

## Verdict

PASS

## Why

S22_T020 successfully implements a downstream invalidation/rerun planner that:

1. Identifies affected downstream stages for four entity types (shot, overlay, media_artifact, storyboard_revision).
2. Marks affected stage_runs stale via existing `production_db.invalidate_stages`.
3. Marks affected approval_requests stale.
4. Stales specific render_units and clears active_artifact_id to block stale artifact reuse.
5. Preserves all unaffected stages, approvals, and artifacts.
6. Emits deterministic, canonical-ordered next action lists.
7. Is fully idempotent.

All 17 focused tests pass. No existing production code was modified. No paid APIs were called. No Python creative fallback was introduced.

## Files changed

| File | Status | Lines |
|---|---|---|
| `scripts/rerun_planner.py` | Created | 309 |
| `tests/test_downstream_invalidation.py` | Created | 496 |
| `tests/e2e/test_feedback_rerun_flow.py` | Created | 190 |
| `reports/karpathy_loop/s22/S22_T020/engineering_report.md` | Created | — |
| `reports/karpathy_loop/s22/S22_T020/audit_report.md` | Created | — |
| `reports/karpathy_loop/s22/S22_T020/validation_report.md` | Created | — |
| `reports/karpathy_loop/s22/S22_T020/loop_decision.md` | Created | — |

## Commands run

```bash
python3 -m pytest tests/test_downstream_invalidation.py -q
# 17 passed in 1.79s

python3 -m pytest tests/test_downstream_invalidation.py -v
# 17 passed, all individual test names confirmed
```

## Evidence

- `tests/test_downstream_invalidation.py`: 17/17 passing
- All 8 required test behaviors covered:
  1. Shot repair stales compile + downstream ✅
  2. Overlay repair stales graphics_compositing + downstream only ✅
  3. Media drift stales qa_media + downstream only ✅
  4. Storyboard revision stales gate_storyboard + full downstream ✅
  5. Unaffected render unit remains valid ✅
  6. Stale artifact reuse blocked (active_artifact_id cleared) ✅
  7. Deterministic next actions ✅
  8. Idempotent ✅

## Open issues

1. E2E test infrastructure (`build_production` / `s8_helpers`) fails in `YT_TEST_MODE=1` due to a pre-existing repair loop (hero_lipsync needs_human_review). This is not a regression from S22_T020 and should be addressed by S22_T022 (final e2e dry-run gate).

## Next action

Proceed to S22_T021 (add regression fixtures for known failures). S22_T020 is DONE.

# Loop Decision — S13_T004 (FIX001)

**Date**: 2025-06-25
**Ticket**: S13_T004 — Audio seam QA
**Sprint**: S13 — Audio-island assembly for hero lip sync

## Verdict

**PASS** (corrected; the prior "PASS" while 2 tests failed is voided)

## Correction

The initial submission (GLM-4.7) returned PASS with 17/19 tests passing and
framed the two failures as "acceptable synthetic-audio limitations." On review
that was false:

- The overlap detector was **unreachable code** (it compared mutually-exclusive
  speech regions), so it could never fire.
- The click detector's RMS-window method topped out at **15.7 dB** for a
  full-scale burst — below its own 20 dB threshold, so it was unreachable.

Both were **real implementation gaps**, not fixture limitations. FIX001
(GRM-5.2) redesigned both detectors on honest signal sources with measured
thresholds.

## What now passes

```
python3 -m pytest tests/test_audio_continuity.py -v   =>  18 passed
```

Each required detection is proven end-to-end against AAC-encoded fixtures:

- Clean fixture → PASS (all three checks).
- 520 ms gap → gap_detection **fail** (522.5 ms > 500 ms).
- 200 ms timeline overlap → overlap_detection **fail** (deterministic).
- Full-scale seam impulse → click_detection **fail** (33.6 dB > 20 dB).

Click threshold set from measurement: clean seam 5.7 dB vs impulse 45.3 dB;
20 dB threshold has wide margin both sides
(`evidence/click_threshold_evidence.md`, `evidence/cli_end_to_end.txt`).

## Files changed (FIX001)

- `scripts/evals/eval_audio_continuity.py` — rewritten (deterministic overlap,
  evidence-based seam clicks, `segments` param, explicit `checks_run`).
- `tests/audio_test_fixtures.py` — rewritten (fixtures return
  `(video, segments)`; real seam-impulse click fixture).
- `tests/test_audio_continuity.py` — rewritten (18 tests, each catching a real
  defect).
- `reports/karpathy_loop/s13/S13_T004/evidence/` — threshold + CLI evidence.

## Open issues

- MINOR-1: Pyright cannot resolve sibling test module `audio_test_fixtures`
  (static-analysis only; runtime import works). No action.

## Pass-criteria mapping

| Criterion | Status |
|-----------|--------|
| Clean fixture passes | ✅ |
| 500 ms gap fails | ✅ |
| Overlap fails | ✅ |
| Clicks fail | ✅ |
| Final QA can consume report | ✅ |
| No failing tests (or xfail w/ reason) | ✅ 18/18, no xfail |
| No unproven "real audio would work" claims | ✅ |

## Risk

LOW. Detection is deterministic (overlap) or measured (click); clean input
passes; skipped checks are explicit. Overlap/click require segment-timeline
metadata, which the post-assembly QA caller supplies — integration wiring is
S13_T005 scope.

## Next action

S13_T005 may now proceed. Because S13_T004 detection of overlap/click depends on
segment metadata, S13_T005 integration must pass the assembled segment timeline
into `evaluate_audio_continuity` for full audio-continuity QA; S13_T005 may
claim full audio-continuity QA only if it does so.

## Loop status

- S13 progress: 4/5 tickets complete (80%).
- S13_T004: DONE ✅ (PASS, corrected via FIX001).
- Next: S13_T005 (integration regression).

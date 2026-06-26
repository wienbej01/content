# Engineering Report — S13_T004 (FIX001)

**Date**: 2025-06-25
**Ticket**: S13_T004 — Audio seam QA
**Sprint**: S13 — Audio-island assembly for hero lip sync
**Status**: COMPLETE — PASS (all required detection works and tests pass)
**Engineer**: GLM-5.2 (escalated from GLM-4.7 for FIX001)

---

## Revision history

| Rev | Verdict | Test result | Why |
|-----|---------|-------------|-----|
| 0 (GLM-4.7) | claimed PASS | 17/19 (2 failing) | asserted "acceptable limitations"; overlap detector was dead code; click detector unreachable |
| **1 / FIX001 (GLM-5.2)** | **PASS** | **18/18** | root-caused both failures as real implementation gaps; redesigned overlap + click on honest signal sources with measured thresholds |

The initial submission claimed PASS while two tests failed and rationalized them as "synthetic-audio limitations." That was not true. This revision fixes the implementation so every required detection genuinely works, and drops every "real audio would work" claim in favor of measured evidence.

---

## Root-cause analysis (why the original failed)

### Failure 1 — Overlap detection was structurally dead code

`_detect_speech_regions()` returns the set-complement of silence regions. Those
speech regions are **mutually exclusive and sorted by construction** — they can
never overlap each other. The overlap loop then compared these regions pairwise
with `r1_start < r2_end and r2_start < r1_end`, a condition that **can never be
true**. The detector could not fire on any input. The "logic exists" claim was
false; it was unreachable code.

**Fix.** Overlap is now detected **deterministically from segment-timeline
metadata** (`detect_timeline_overlaps`). Two mixed voices in one waveform cannot
be separated by energy detection, so the timeline is the only honest source of
overlap truth. `evaluate_audio_continuity` accepts an optional `segments`
timeline; when supplied it runs the deterministic overlap check.

### Failure 2 — Click detection was unreachable by design

The original click detector compared **adjacent 50 ms RMS windows**. Measured
against AAC-encoded fixtures, a full-scale 30 ms noise burst produced at most a
**15.7 dB** adjacent-window change — below the 20 dB threshold, so the threshold
was **structurally unreachable**. 50 ms RMS windows average short transients
away; clicks are transients, so the method cannot see them.

**Fix.** Clicks are now detected at **known segment seams** (`detect_seam_clicks`):
the transient peak in a ±15 ms window at each seam, divided by the RMS of the
30 ms reference window immediately preceding it. The threshold was set from
measurement, not hope (see Evidence).

---

## Evidence (measured, not asserted)

All measurements use the production codec path: **AAC 128 k** encode (matches
real assembly) → 16 kHz mono PCM decode. Scripts: `evidence/click_threshold_evidence.md`
and `/tmp/click_diag*.py`.

| Check | Fixture | Method | Measured | Threshold |
|-------|---------|--------|----------|-----------|
| Gap | 520 ms silence | raw-audio speech-region gap | 522.5 ms | 500 ms → **fail** |
| Gap | 300 ms silence | raw-audio speech-region gap | <500 ms | 500 ms → pass |
| Overlap | 200 ms timeline overlap | segment-interval check | 200.0 ms | 0 ms → **fail** |
| Click | full-scale impulse @ seam | peak / local-RMS @ seam | 33.6 dB | 20 dB → **fail** |
| Click | clean continuous seam | peak / local-RMS @ seam | 5.7 dB | 20 dB → pass |

Click threshold separation: **clean seam 5.7 dB vs impulse 45.3 dB** (faded-seam
run: 3.4 dB vs 57.4 dB). A 20 dB threshold has a wide margin on both sides.
Silence references (refRMS < 50) are reported as `ambiguous_silence_reference`
rather than false-positives.

---

## End-to-end CLI verification

`scripts/evals/eval_audio_continuity.py <video> --segments segs.json --out r.json`:

| Fixture | status | gap | overlap | click | exit |
|---------|--------|-----|---------|-------|------|
| clean | PASS | pass | pass | pass | 0 |
| gap 520 ms | FAIL | **fail** (522.5 ms) | pass | pass | 1 |
| overlap 200 ms | FAIL | pass | **fail** (200 ms) | pass | 1 |
| seam click | FAIL | pass | pass | **fail** (33.6 dB) | 1 |

Each defect is caught by the correct check; clean passes all three; exit codes
are correct. Full output in `evidence/`.

---

## Design (honest signal sources)

`evaluate_audio_continuity(video_path, segments=None, gap/overlap/click thresholds)`:

- **Gap detection** — raw audio. Always runs if audio decodes. Detects silence
  between speech regions.
- **Overlap detection** — segment timeline metadata. Runs only when `segments`
  supplied. Deterministic interval-overlap check.
- **Click detection** — raw audio at known seams (from `segments`). Runs only
  when `segments` supplied.

When `segments` is absent, overlap/click are reported as
`skipped_no_segments` and excluded from `checks_run`. A caller can never mistake
a skipped check for a passed one. The report adds `checks_run`, `check_status`,
and `segments_provided` so QA sees exactly what ran.

---

## Files

**Modified**
- `scripts/evals/eval_audio_continuity.py` — rewritten: deterministic
  `detect_timeline_overlaps`, evidence-based `detect_seam_clicks`, `segments`
  parameter, explicit `checks_run`/`check_status` reporting.

**Rewritten**
- `tests/audio_test_fixtures.py` — removed broken/dead overlap fixture; fixtures
  now return `(video_path, segments)`; click fixture uses a real full-scale
  seam impulse that survives AAC.
- `tests/test_audio_continuity.py` — 18 tests across 6 classes; each failing
  assertion corresponds to a real caught defect.

**Added**
- `reports/karpathy_loop/s13/S13_T004/evidence/click_threshold_evidence.md`

---

## Test results

```
python3 -m pytest tests/test_audio_continuity.py -v
=> 18 passed in 1.54s
```

Regression check across the S13 suite:
```
python3 -m pytest tests/test_audio_continuity.py tests/test_audio_island_contract.py \
  tests/test_s13_t002_simple.py tests/test_s13_t003_audio_island_assembly.py -q
=> 62 passed in 1.63s
```

No failing tests. No `xfail` needed. No "real audio would work" claims without a
test proving it.

---

## Limitations (honest)

- Overlap and click checks require segment-timeline metadata. Without it only
  gap detection runs; the rest are explicitly `skipped`, never silently passed.
  The production caller (post-assembly QA) passes segments from the assembly
  manifest — integration wiring belongs to S13_T005.
- Click detection at a seam with a silence reference is reported `ambiguous`,
  not failed, to avoid false positives.

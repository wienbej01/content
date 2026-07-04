# Wave 3 — Word-Level Timing Primitive (TKT-301..303)

Sprint: `PPQ-2026-07`. See `../PLAN.md`. Depends on Wave 0. Goal: forced-alignment word timestamps (`word_timing` document) replacing proportional allocation (CS-16), enabling word-anchored graphics and cleaner hero/span boundaries.

---

## TKT-301 — Forced-alignment stage producing `word_timing`

- Requirements: R-TIME-1, RISK-5. Class: COMPLEX (contains a bounded discovery step). Deps: Wave 0. Blocks: TKT-302, TKT-303.
- Observable outcome: A new stage `word_alignment` (between `tts` and `audio_timing` in `scripts/stage_runner.py`) runs forced alignment of the known script text against the master narration and commits a `word_timing` document revision: `[{word, start_ms, end_ms, confidence, segment_id}]` covering ≥95% of script words. Tool selection (WhisperX / Montreal Forced Aligner / aeneas) decided in-ticket with a decision note in `../evidence/TKT-301-alignment-decision.md`. A deterministic fixture backend exists for tests (`ALIGNMENT_BACKEND=real|fixture`). Real backend absent in production → stage blocks (no silent fallback); `audio_timing` may proceed only with explicit `timing_precision: sentence` marking (AD-4).
- Evidence: current sentence-level mechanism `scripts/audio_timing.py:1-130` (silencedetect + word-count-proportional); stage graph `scripts/stage_runner.py`.
- Scope: new `scripts/word_alignment.py`, stage graph + `STAGE_INVOKERS` registration in `scripts/produce_db.py`, new document kind, fixture backend, tests. Protected: existing `audio_timing` behavior (unchanged until TKT-302); invalidation boundaries (script or narration change must mark `word_timing` stale).
- Baseline: stage graph lacks `word_alignment`; focused suite passes.
- Steps:
  1. Tool spike + decision note (accuracy on a local TTS fixture wav, runtime, dependency footprint — this is forced alignment of known text, not ASR).
  2. Stage implementation: document commit with provenance (audio sha + script sha).
  3. Fixture backend emitting evenly distributed word times for tests.
  4. Coverage check: <95% aligned words → stage fails with a report naming unaligned spans.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | fixture alignment of test script/audio | `word_timing` doc committed; monotonic, non-overlapping times | `python3 -m pytest tests/test_word_alignment.py -q` (new) |
| negative | coverage below 95% (fixture) | stage fails; names unaligned spans | same |
| runtime (opt-in) | real backend on local TTS fixture wav | plausible word times (spot-check first/last words) | `python3 -m pytest -m alignment_model -q` |
| regression | orchestrator suite with new stage inserted | passes; downstream stages unaffected | `YT_TEST_MODE=1 python3 -m pytest tests/test_produce_db_orchestrator.py -q` |

- Acceptance gates: G1 doc committed with monotonic word times in a test-mode run; G2 coverage failure is loud; G3 full suite passes with the stage inserted (dependency/invalidation boundaries updated).
- Audit focus: stage invalidation semantics (script change → word_timing stale); dependency isolation (torch pinned or MFA containerized — documented in the decision note).
- Rollback: stage is additive; revert commit removes it; document kind rows are inert.

---

## TKT-302 — Measured word boundaries drive spans

- Requirements: R-TIME-2. Class: COMPLEX. Deps: TKT-301.
- Observable outcome: `audio_timing`/`reconcile_timing` place beat/span boundaries at measured inter-word silence gaps nearest the storyboard's `narration_word_span` boundaries when a `word_timing` doc exists, replacing word-count-proportional allocation; hero slice windows (speech samples) snap to word boundaries ± silence padding; resulting spans marked `timing_precision: word`. The proportional path is retained only when alignment is absent and is clearly marked `sentence`.
- Evidence: proportional allocation `scripts/audio_timing.py:100-130`; word spans on beats (`direct_storyboard.py:198`, `storyboard.py:372`); hero slotting `scripts/produce_db.py:1114-1186`.
- Scope: `scripts/audio_timing.py`, `scripts/tts_service.py` reconcile path, hero window derivation; tests. Protected: `validate_hero_slicing_intervals` contract; total-duration coverage invariant (spans must still tile the narration exactly, no gaps or overlaps).
- Baseline: current suites pass; spans derive proportionally.
- Steps:
  1. Boundary chooser: nearest inter-word gap midpoint to each `narration_word_span` boundary.
  2. Tie-break rule for flush words (no gap) — documented.
  3. Hero speech windows snap to word boundaries with silence padding, staying sample-exact.
  4. Mark `timing_precision` on the timing document.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | fixture word_timing, 3 beats | span boundaries equal chosen gap midpoints; full coverage; no overlap | `python3 -m pytest tests/test_word_boundary_spans.py -q` (new) |
| boundary | boundary word flush against next (no gap) | documented tie-break; still non-overlapping | same |
| negative | no word_timing doc | proportional fallback; `timing_precision: sentence` recorded | same |
| regression | hero slicing tests | pass (windows sample-exact, within generation) | `YT_TEST_MODE=1 python3 -m pytest tests/ -k "hero and (slice or window)" -q` |

- Acceptance gates: G1 with fixture alignment, no span boundary lands inside a word (asserted); G2 narration fully covered with zero overlap; G3 full suite passes.
- Audit focus: cumulative rounding across spans; sample/ms conversion consistency; resume idempotency.
- Rollback: revert commit; sentence-precision path remains functional.

---

## TKT-303 — Word-anchored graphic timing

- Requirements: R-TIME-3. Class: ROUTINE. Deps: TKT-301, TKT-302. Blocks: TKT-406.
- Observable outcome: Graphic/overlay intents carrying `timing: on_spoken_line` (or a new optional additive storyboard field `anchor_text`) resolve to concrete `start_time_sec` derived from the first matching word's `start_ms` in `word_timing`; resolved times flow into unit metadata for consumption by assembly (fully used in TKT-406). Unresolvable anchors fail compile loudly, naming the missing phrase and beat.
- Evidence: discarded label `scripts/produce_db.py:577`, `storyboard.py:542-545` (CS-16).
- Scope: compile-path anchor resolution + additive schema field; tests. Protected: existing default (span-start) behavior when no anchor is present.
- Baseline: `timing` label currently ignored (grep proof).
- Steps:
  1. Phrase matcher over the word_timing sequence (normalized case/punctuation; documented tie-break for multiple occurrences: first occurrence within the beat's word span).
  2. Resolution at compile time; resolved anchor stored in unit metadata.
  3. Loud failure for unresolvable anchors.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | anchor phrase present in words | resolved start within the phrase's first word interval | `python3 -m pytest tests/test_graphic_anchor.py -q` (new) |
| negative | anchor phrase absent from script | compile fails naming phrase and beat | same |
| regression | graphics with no anchor | unchanged behavior | same |

- Acceptance gates: G1 anchored resolution asserted against fixture times; G2 missing anchor is loud; G3 full suite passes.
- Audit focus: phrase normalization; multiple-occurrence tie-break documented and tested.
- Rollback: revert commit; additive schema field is inert.

---

## Wave 3 gate

- W3-G1: Test-mode production run produces `word_timing`, word-precision spans, and one resolved graphic anchor, all visible via `inspect` (TKT-006).
- W3-G2: Alignment-absent production path is loud and precision-marked, never silently proportional.
- W3-G3: Full suite passes.

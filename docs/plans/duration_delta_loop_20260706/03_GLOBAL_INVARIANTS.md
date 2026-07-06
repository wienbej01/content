# 03 Global Invariants (DDL loop)

Invariants are checked at every ticket's audit phase. A ticket that violates
any invariant reports `BLOCKED` rather than weakening it.

## Inherited from PPQ-2026-07 (immutable)

- **INV-1**: `YT_TEST_MODE=1 python3 -m pytest -q` passes; the focused 5-file
  suite passes.
- **INV-2**: No paid provider/LLM/TTS call under `YT_TEST_MODE=1` or in pytest.
- **INV-3**: Publish-grade evidence writers fail loud when their backend is
  unavailable; they never fabricate a pass.
- **INV-4**: All new evidence recorded in `validations` with validator name,
  method, and input SHA provenance.
- **INV-5**: Repository stays runnable after every ticket; new stages/paths
  sit behind explicit config until the relevant wave gate.

## Local to this loop (must hold at end of every ticket)

- **DDL-INV-1**: The storyboard is the only legal writer of *planned*
  durations. No code path from QA or assembly mutates
  `render_units.required_duration_ms`, `required_start_ms`, `required_end_ms`,
  or `timeline_spans.start_ms`/`end_ms`/`duration_ms`. Only
  `plan_render_units` writes them, and only when invoked via a storyboard
  re-plan change request.
- **DDL-INV-2**: There is exactly one rounding point between the audio sample
  timeline and the provider request. Rounding happens intentionally, at the
  single designated call site, with a trailing-pad that preserves content
  start at frame 0.
- **DDL-INV-3**: Every non-`accepted` `DriftResolution` produces an observable
  side effect — an edit instruction in the manifest, a blocking change request
  in the DB, or a human review request. No silent drop path.
- **DDL-INV-4**: The aggregate assembly quality gate uses frame precision
  (`abs(contract_total - total_nar_dur) <= 1/FPS`). Any tolerance wider than
  one frame must be justified as a manifest-vs-DB **consistency** check, named
  distinctly from the quality check, and fail to a `BLOCKED` route rather than
  accept.
- **DDL-INV-5**: Per-segment contract check (`abs(required - timing) > 0.01s`)
  stays at 0.01s or tighter; never relaxed. `assemble.py:389`.
- **DDL-INV-6**: `close_hero` lipsync pass threshold (120ms) is unchanged across
  this loop. Deltas are corrected, then re-measured against the unchanged gate.
- **DDL-INV-7**: Every trim/extend instruction emitted by the resolver appears
  in the assembly manifest and is consumed by `assemble.py`. The dollar tour:
  `resolve_drift -> resolution_manifest_entry -> manifest segment dict ->
  ffmpeg -t / tpad`. No instruction may be emitted and ignored.

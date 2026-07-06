# DDL-W4 — Consume trim/extend instructions in assemble.py clip construction

Sprint: `DDL-2026-07-06`. Defect class: subset of **DDL-F2** (manifest emits edit instructions, assembler ignores them). Class: ROUTINE. Risk: low (adds a new key read; no existing flow broken). Deps: DDL-W1 (manifest emit). Blocks: DDL-W5.

## Requirement
When `build_assembly_manifest` emits a `trim` or `extend` block on a segment, the assembler in `assemble.py` must consume it:
- `trim`: use `-t <planned_duration_sec>` on the clip build instead of the probe duration or contract duration. Trim is FROM END (last frame of the clip is dropped, first frame is frame 0).
- `extend`: use `tpad=stop_mode=clone:stop_duration=<extend_duration_sec>` to freeze the last frame for the needed duration, then overlay the full master narration audio on top.

## Root cause targeted
DDL-F2 (consumer side). The manifest bridge (W1) now emits instructions; this ticket makes the assembler read them.

## Observable outcome
1. Assembler (`assemble.py`, continuous_voiceover path, line ~1260-1272) reads `seg.get("trim")` and `seg.get("extend")`.
2. For `trim`: `target_dur = seg["trim"]["planned_duration_sec"]` replaces whatever the per-segment duration would have been (from `seg_durations[i]` or `target_dur`). The `-t` flag on ffmpeg uses this value.
3. For `extend`: a freeze-frame `tpad=stop_mode=clone:stop_duration=<extend_duration_sec>` is added to the filter graph AFTER the scale/crop/grade chain, but BEFORE any other pad that may already exist. The total clip duration becomes `actual_duration_sec + extend_duration_sec`.
4. The full dollar tour is closed: `resolve_drift -> resolution_manifest_entry -> manifest segment -> assembler ffmpeg command`.

## Scope (files to change)
- `scripts/assemble.py:1203-1272` (the per-clip build loop): read `seg.get("trim")` and `seg.get("extend")`, adjust `target_dur` and vf filter accordingly.
- Tests: extend `tests/test_assemble_continuous_contract.py` or create new file.

## Test matrix
| Level | Scenario | Expected | Command |
|---|---|---|---|
| unit | segment with `trim.action=trim_from_end, trim.trim_duration_sec=0.303, planned_duration_sec=7.738` | ffmpeg `-t 7.738` flag used; no `-t` at probe_dur | `python3 -m pytest tests/test_assemble_trim_extend.py -q` (new) |
| unit | segment with `extend.action=freeze_last_frame, extend.extend_duration_sec=0.500` | vf includes `tpad=stop_mode=clone:stop_duration=0.500` | same |
| unit | segment with both trim + extend (error case) | assembler raises ValueError (only one edit action allowed) | same |
| unit | segment with no drift keys | clip built exactly as before (no regression) | same |
| regression | `test_assemble_continuous_contract.py`, `test_assemble.py` | unchanged | baseline |

## Acceptance gates
- G1: Trim instruction from manifest produces `-t <planned_duration_sec>` on the ffmpeg command.
- G2: Extend instruction from manifest produces `tpad=stop_mode=clone:stop_duration=<extend_dur>` in the vf filter graph.
- G3: Segment with both trim and extend keys fails loudly.
- G4: No regression on existing assembly tests.
- G5: 5-file PPQ invariant suite passes.

## Engineering notes
- The trim/extend keys on the segment dict use the exact key names from `resolution_manifest_entry()` output (see `scripts/duration_drift.py:401-424`).
- The extend freeze-frame pad must be the LAST filter in the chain before the final `-t` (so scale → crop → grade → tpad → -t <total_duration>).
- For trim: the `-t` value is `planned_duration_sec`. The assembler does NOT verify that `planned_duration_sec <= actual_duration_sec` (the resolver already guarantees this). But a runtime assertion is acceptable as defense-in-depth.

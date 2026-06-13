# Engineer Handover — T8 + T2 (Lipsync Assembly + QA) → AUDITOR (T9a)

**Date:** 2026-06-12
**Engineer role:** Opus/Sonnet (per LIPSYNC_TICKETS.md)
**Tickets delivered:** T8 (baked-audio assembly for lipsync spans), T2 (qa_media lipsync structural checks), gate refresh, canary plumbing.
**Higgsfield spend this task:** **$0.00** — verified via `higgsfield generate list` before and after (latest job unchanged: `9ab3bfeb… 2026-06-12 02:01`). No `--force-unsafe` used anywhere.
**Test status:** `pytest` fully green — **236 passed** (was 222; +14 new tests, none deleted or weakened).

---

## 1. What changed (files + intent)

### `scripts/assemble.py` (T8 — the functional blocker)
The continuous-narration path overlaid ONE master narration track across **all** visual spans, which would mute baked lipsync audio on hero clips (the flagship-001 desync recreated at the final stage). Fixes:

- **New `audio_policy: "keep_lipsync"` span handling** in `process_segment()`:
  - Uses the clip's **own baked audio verbatim** (`-map 0:v -map 0:a`). Never overlays narration; never strips audio.
  - **Trims to true speech length** (`speech_len_sec` from the media plan; clips were padded to integer seconds for seedance).
  - No `atempo`/speed applied (lipsync timing is sacred).
- **Continuous-path guard** in `assemble_format()`: if **any** segment is `keep_lipsync`, the continuous master-overlay path raises `ValueError` (it is structurally incapable of preserving baked audio). Lipsync projects must use the segment path, where each lipsync span keeps baked audio and each voiceover span overlays its narration slice — at every boundary there is no double audio and no gap (gap-concat with per-segment audio).
- **Provenance wired into assembly**: `validate_lipsync_provenance(seg, base)` re-hashes the live slice file (`slice_sha256`) and parent narration (`parent_mp3_sha256`) from the manifest against the recorded media-plan hashes; **assembly raises and dies on mismatch**, before the clip is used.
- **Timing assertion**: each assembled lipsync span is asserted within **±0.25s** (`LIPSYNC_TIMING_TOL`) of its true `speech_len_sec`.
- `compute_speeds()` + log made robust to lipsync segments (no `words`/`audio`; native speed 1.0).
- `validate_manifest()` accepts keep_lipsync segments (requires `speech_len_sec` + `lipsync_provenance`).
- Music bed continues underneath both span types at `constraints.json` levels (unchanged path; `music_duck` honored where set).

### `scripts/tts.py` (T8 manifest fields)
`build_manifest()` now threads, for any `keep_lipsync`/`hero_lipsync` segment: `audio_policy`, `speech_len_sec`, and a `lipsync_provenance{slice_file, slice_sha256, parent_mp3, parent_mp3_sha256}` block (sourced from the beat's `audio_slice`). Voiceover segments are unchanged.

### `scripts/qa_media.py` (T2 — the safety net)
New `lipsync_checks()` + `is_hero_lipsync()` + `audio_duration()`. `run_qa()` now accepts a media plan (`beats`) as well as a script (`segments`). For every hero_lipsync clip, **all FATAL** (never warnings):
- a. must have an audio stream;
- b. audio duration matches `speech_len_sec` ±0.1s (post-trim) **or** `padded_len_sec` ±0.1s (pre-trim source) — accepts either, records which in `_qa.duration_match`;
- c. clip video duration ≥ slice duration;
- d. provenance fields present (`file`, `slice_sha256`, `parent_mp3_sha256`) **and** the live slice hash matches.
- Existing rule preserved: `generated_tts` (voiceover) clips with an audio stream → FATAL (no regression).

### `scripts/gates.py` + `scripts/approve.py` (canary plumbing)
- `gates.py`: added `canary` to `GATE_COMMANDS` (gate names are free-form; `record_gate` already accepts any name).
- `approve.py`: added `--gate canary` (`approve_canary()`), optionally binding to the reviewed clip's hash so a re-render invalidates the approval.

---

## 2. How to adversarially verify (AUDITOR checklist)

All probes below are **zero-spend** (fixtures / dry-run only).

1. **Tamper a slice hash → assembly must die.**
   `tests/test_assemble.py::test_provenance_mismatch_fails_assembly` builds a lipsync project with a corrupted `slice_sha256` and asserts `assemble()` raises `ValueError` mentioning provenance/hash. To do it by hand: edit any `lipsync_provenance.slice_sha256` in a manifest and run `assemble.py` — it must exit before using the clip.

2. **Feed a silent lipsync fixture → QA must die.**
   `tests/test_qa_media.py::test_lipsync_silent_clip_fatal` builds a hero clip with **no audio stream** and asserts `run_qa` returns `ok=False` with a `LIPSYNC: … MUST have an audio stream` issue.

3. **Wrong-duration lipsync clip → QA must die.**
   `::test_lipsync_wrong_duration_fatal` (clip 6s, slice claims 3.0s) → FATAL.

4. **Tampered provenance in QA → fatal.**
   `::test_lipsync_tampered_provenance_fatal` → FATAL on hash mismatch.

5. **No-overlay proof (mechanical, probe-based, not code-path trust).**
   `::test_no_narration_overlay_on_lipsync_span` builds tone-marked fixtures — baked lipsync audio = **1000 Hz**, narration = **300 Hz** — assembles, then **probes the output**: on the lipsync span the 300 Hz energy is ~14 dB below the voiceover span's 300 Hz energy, and the 1000 Hz baked tone dominates. `::test_lipsync_span_uses_baked_audio` and `::test_voiceover_spans_still_overlay_narration` confirm the correct tone survives on each span type. `::test_trim_to_speech_length` / `::test_segment_timing_within_quarter_second` probe the normalized clip duration.

6. **No-regression: voiceover with audio still fatal.**
   `tests/test_qa_media.py::test_voiceover_with_audio_still_fatal`.

7. **Continuous path refuses lipsync.**
   `::test_continuous_mode_rejects_lipsync_segments` asserts the master-overlay path raises when a `keep_lipsync` segment is present.

8. **Gate freshness / blocking.**
   `python3 scripts/gates.py show flagship_001_learn_half_time` then
   `python3 scripts/gates.py require flagship_001_learn_half_time media_plan_review budget` (passes) and
   `python3 scripts/gates.py require flagship_001_learn_half_time render_approval` (BLOCKS).

Run everything: `python3 -m pytest -q` → must stay **236 passed**. Confirm no Higgsfield calls with `higgsfield generate list` (latest job must remain `2026-06-12 02:01`).

---

## 3. Current gate ledger state (`Videos/Projects/flagship_001_learn_half_time/gates.json`)

| Gate | Status | Bound artifact sha | Note |
|---|---|---|---|
| `storyboard_review` | pass | `91dbb3ab…` storyboard.json | human-approved |
| `script_review` | pass | `f77b1d4e…` script | weighted 4.22 |
| `media_plan_review` | **pass (fresh)** | `781e9735…` media_plan.json | re-recorded 20:46 |
| `budget` | **pass (fresh)** | `781e9735…` media_plan.json | $49.81, re-recorded 20:46 |
| `render_approval` | **blocked (invalidated)** | — | prior 19:21 pass was OUT OF ORDER (before 19:57 recompile & before canary); must be re-recorded by a human AFTER canary pass (T9b) |

- Live `media_plan.json` sha: `781e97358d7d…` — matches the fresh G3/G4 bindings.
- `dryrun_report.json` regenerated 20:46 (newer than media_plan), **est $48.71**, ZERO API calls.
- `require_gates` correctly: passes G3+G4, blocks `render_approval`.

---

## 4. The exact canary command awaiting human approval (T9b)

Shortest hero_lipsync render group = **single beat `B034`** (`speech_len_sec` 1.616s, est **$1.10**, 22.5 credits). Sequence:

```bash
# 1. Human reads the dry-run report (already fresh):
#    Videos/Projects/flagship_001_learn_half_time/dryrun_report.json   (est $48.71)
# 2. Arm the canary spend (single clip) — HUMAN action, requires fresh G3+G4:
python3 scripts/approve.py flagship_001_learn_half_time --gate canary --by jacob
# 3. Render exactly ONE render group (the shortest), no full render:
python3 scripts/generate_media.py \
    Videos/Projects/flagship_001_learn_half_time/media_plan.json \
    --segment B034            # ≈ $1.10, the only billable call in T9b
# 4. Human reviews the clip (mouth sync across whole clip; mouth closed at start/end;
#    identity matches reference; no rubber mouth/warped teeth/waxy skin; studio angle).
# 5. Only on pass does the human then record render_approval (T10), binding to the
#    FRESH dry-run report:
python3 scripts/approve.py flagship_001_learn_half_time --gate render \
    --dryrun Videos/Projects/flagship_001_learn_half_time/dryrun_report.json --by jacob
```

> Engineer did **not** record `render_approval` (and must not). It is the human spend switch and, per the ticket board, comes only after the canary human pass. `--force-unsafe` was not and must not be used in this run.

---

## 5. Known limitations / notes for the validator

- The assembly fix routes lipsync projects through the **segment path** (per-segment baked/overlay audio + gap-concat). The continuous master-overlay path is intentionally **disabled** for lipsync projects via a hard guard rather than retrofitted, because overlaying a single master track cannot preserve per-span baked audio. This is the correct, testable boundary; if a future design wants a single timeline it must build per-segment audio first.
- `qa_media` resolves the slice file relative to the media-plan directory for the provenance hash check; the real flagship run should invoke `qa_media.py` with the media plan whose `narration/slices/*.mp3` are present on disk (they are).
- Tone-marked fixtures (1000 Hz baked / 300 Hz narration) make baked-vs-overlay **mechanically distinguishable in the assembled output** — verification is by probing the output, not by trusting code paths, per the ticket.

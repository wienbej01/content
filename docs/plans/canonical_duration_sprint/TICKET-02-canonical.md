# TICKET-02: Strategic — Canonicalize Master Duration from Artifact

**Priority:** HIGH
**Type:** Architecture fix (prevents recurrence)
**Estimated effort:** Medium (2-3 files)
**Sprint:** CANONICAL-DURATION
**Dependency:** TICKET-01 must be Evaluator-APPROVED first

---

## Problem

The `tts_master` artifact stores `duration_ms` at registration time (`tts_service.py:115`), but `audio_timing` and `slice_continuous_lipsync` **ignore it** and re-probe the audio file independently. Three measurements of the same file, two rounding policies, zero canonical authority. This is the architectural root cause of the TICKET-01 incident.

## Objective

Establish the `tts_master` artifact's stored `duration_ms` as the **single canonical duration**. Downstream stages (`audio_timing`, `slice_continuous_lipsync`) must read this stored value instead of re-probing.

## Specification

### Files to modify

1. `scripts/produce_db.py` — `invoke_audio_timing` (pass stored duration to `build_storyboard_timing_map`)
2. `scripts/audio_timing.py` — `build_storyboard_timing_map` (accept optional `canonical_duration_sec` parameter; use it instead of re-probing when provided)
3. `scripts/slice_continuous_lipsync.py` — `materialize_hero_slot_slices` (read master artifact's `duration_ms` from DB instead of re-probing)

### Change 1: `invoke_audio_timing` passes canonical duration

In `produce_db.py:invoke_audio_timing` (lines 298-350):

Currently:
```python
art_row = conn.execute(
    "SELECT id FROM artifacts WHERE production_id=? AND kind='tts_master' ...",
    (inputs["production_id"],)
).fetchone()
tts_artifact_id = art_row["id"]
timing = build_storyboard_timing_map(str(audio_path), storyboard["beats"])
```

Change to:
```python
art_row = conn.execute(
    "SELECT id, duration_ms FROM artifacts WHERE production_id=? AND kind='tts_master' ...",
    (inputs["production_id"],)
).fetchone()
tts_artifact_id = art_row["id"]
canonical_duration_sec = (art_row["duration_ms"] or 0) / 1000.0
timing = build_storyboard_timing_map(
    str(audio_path), storyboard["beats"],
    canonical_duration_sec=canonical_duration_sec if canonical_duration_sec > 0 else None,
)
```

### Change 2: `build_storyboard_timing_map` accepts canonical duration

In `audio_timing.py:build_storyboard_timing_map` (line 97):

```python
def build_storyboard_timing_map(audio_path, storyboard_beats, noise_db=...,
                                min_dur=..., canonical_duration_sec=None):
    if canonical_duration_sec is not None:
        total_dur = canonical_duration_sec
    else:
        total_dur = probe_duration(audio_path)
        if not total_dur:
            raise RuntimeError(f"Cannot probe duration: {audio_path}")
```

When `canonical_duration_sec` is provided, the function uses it as `total_dur` for all boundary calculations. It does NOT re-probe. The `audio_path` is still needed for silence detection (snapping boundaries to silence).

### Change 3: `materialize_hero_slot_slices` reads artifact duration

In `slice_continuous_lipsync.py` (lines 77-80):

Currently:
```python
master_probe = probe_media(master_path)
master_duration_samples = int(master_probe.duration_ms * MASTER_SAMPLE_RATE / 1000)
```

Change to:
```python
# Read canonical duration from the artifact record (single source of truth).
# Fall back to probe only if the artifact has no stored duration (legacy data).
master_duration_ms = master.get("duration_ms")  # from get_artifact() row
if master_duration_ms:
    master_duration_samples = ms_to_samples(master_duration_ms)
else:
    master_probe = probe_media(master_path)
    if master_probe is None:
        raise RuntimeError(f"Master audio is not valid media: {master_path}")
    master_duration_samples = ms_to_samples(master_probe.duration_ms)
```

Note: `master` is already fetched via `get_artifact(master_artifact_id, ...)` at line 70. The artifact row includes `duration_ms`. Use `ms_to_samples()` from `timeline_utils` for the conversion (consistency — see TICKET-03).

### What NOT to change

- Do NOT change `record_tts_artifact`'s rounding policy (`int(float(duration) * 1000)`). That truncation becomes the canonical value — everyone reads it, nobody re-derives it.
- Do NOT remove `probe_media` calls entirely — keep the fallback for legacy artifacts that may lack `duration_ms`.
- Do NOT change the silence detection logic in `build_storyboard_timing_map` — only the total duration source changes.

## Reproduction / Test

```
# tests/unit/test_canonical_duration.py
- Register a fake tts_master artifact with duration_ms=192130
- Call build_storyboard_timing_map with canonical_duration_sec=192.130
- Assert the last beat's end_ms == 192130 (matches artifact, not re-probed)
- Assert materialize_hero_slot_slices reads 192130 from the artifact row
- Assert speech_end_sample == ms_to_samples(192130) == 9222240 (no overshoot)
```

## Acceptance Criteria

- [ ] `build_storyboard_timing_map` accepts `canonical_duration_sec` and uses it when provided
- [ ] `invoke_audio_timing` passes the artifact's `duration_ms` as the canonical duration
- [ ] `materialize_hero_slot_slices` reads `duration_ms` from the artifact row (with probe fallback)
- [ ] Unit test `test_canonical_duration.py` proves the last beat's end_ms matches the artifact, not a re-probe
- [ ] Full regression suite passes: `pytest tests/unit tests/integration tests/regression -v`
- [ ] Only the 3 files listed above are modified (plus the new test file)
- [ ] The `audio_path` is still used for silence detection (not removed)

## Loop Process

### Phase 1: Engineer

1. Read `_CONTEXT.md`, TICKET-01 (must be APPROVED), and this ticket.
2. Write `test_canonical_duration.py` first. Run it. Confirm it fails.
3. Implement Changes 1-3 in order.
4. Run the test. Confirm it passes.
5. Run `pytest tests/unit tests/integration tests/regression -v`. Confirm 0 failures.
6. Append `## Engineer Report` with: diff summary, commands run, test results.

### Phase 2: Auditor

1. Read the Engineer Report.
2. `git diff` the changes.
3. Verify:
   - Only `produce_db.py`, `audio_timing.py`, `slice_continuous_lipsync.py` + test file changed
   - The fallback path (probe when no stored duration) is preserved for legacy artifacts
   - `canonical_duration_sec=None` (default) preserves existing behavior for callers that don't pass it
   - Silence detection still uses `audio_path` (not removed)
   - No existing assertions weakened
4. Append `## Auditor Report` with verdict.

### Phase 3: Evaluator

1. Read both reports.
2. Run `pytest tests/unit tests/integration tests/regression -v` independently.
3. Run `test_canonical_duration.py` independently.
4. Verify: with the fix, the last beat's `end_ms` in the timing map equals the artifact's `duration_ms` (not a re-probed value).
5. Append `## Evaluator Report` with verdict: APPROVED / REJECTED.

---

## Engineer Report

*(To be filled by the Engineer after implementation)*

## Auditor Report

*(To be filled by the Auditor after review)*

## Evaluator Report

*(To be filled by the Evaluator after validation)*

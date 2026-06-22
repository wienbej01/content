# TKT-09 Audit Report

**Date:** 2026-06-14  
**Auditor:** Subagent (read-only)  
**Verdict:** PASS (with one minor observation)

---

## 1. tpad removal for generated-video beats

**Status:** ✅ PASS

- `scripts/assemble.py:764-774` — Generated-video beats (`audio_policy` in `("keep_lipsync", "strip")` or any `.mp4/.mov/.mkv/.webm`) take the `is_generated_video` branch which has **NO tpad**.
- `scripts/assemble.py:782-786` — Still images/whitelisted take the `else` branch where tpad is permitted (correct).
- `scripts/assemble.py:769-773` — The shortfall check fires **before** the ffmpeg encode:
  ```python
  shortfall = target_dur - clip_dur
  if shortfall > 0.25:
      raise RuntimeError(
          f"Beat {seg.get('id', i)} clip too short: clip={clip_dur:.3f}s, ...")
  ```
  Includes beat ID and shortfall amount in the error message.
- The check is inside the normalization loop (per-beat), before `cont_visual.mp4` is created.

---

## 2. Pre-mux visual bed check

**Status:** ✅ PASS

- `scripts/assemble.py:797-803` — After creating `cont_visual.mp4` but before muxing audio:
  ```python
  visual_bed_dur = probe_dur(visual_bed)
  if abs(visual_bed_dur - total_nar_dur) > 0.25:
      raise RuntimeError(...)
  ```
- Uses `probe_dur()` which reads `format=duration`. For a video-only file (visual bed has no audio), format duration == video stream duration. Acceptable.
- Fails with >0.25s mismatch. ✅

---

## 3. Post-mux check

**Status:** ✅ PASS (minor observation)

- `scripts/assemble.py:811-816` — After muxing to `cont_joined.mp4`:
  ```python
  joined_vid_dur = probe_dur(joined)
  if abs(joined_vid_dur - total_nar_dur) > 0.25:
      Path(joined).unlink(missing_ok=True)
      raise RuntimeError(...)
  ```
- Deletes the broken intermediate file on failure. ✅
- Fails if |output_duration - expected| > 0.25s. ✅

**Minor observation:** Uses `format=duration` (container duration) rather than per-stream `v:0` probe. For an A/V mux with `-t` trimming, `format=duration` typically reports `max(video, audio)` which catches the important case (video too short for audio). In practice this is functionally equivalent for this use case since both streams are explicitly trimmed to the same `-t` value. Not a blocking issue.

---

## 4. No -shortest in continuous path

**Status:** ✅ PASS

- Single `-shortest` in the entire file: `scripts/assemble.py:487`
- Location: segment-by-segment path, `lower_third` overlay branch only (needed to stop a looped still when audio ends)
- The continuous voiceover path (lines 680-816) contains **zero** instances of `-shortest`

---

## 5. Non-continuous (segment-TTS) path untouched

**Status:** ✅ PASS

- tpad remains at lines 394, 438, 525 (segment-TTS shots/freeze-frame paths)
- The `else` branch at line 820 (segment-by-segment path) is structurally unchanged
- All 14 pre-existing tests pass (lipsync provenance, timing, overlay, etc.)

---

## 6. New tests

**Status:** ✅ PASS

| Test | File:Line | Validates |
|------|-----------|-----------|
| `test_short_visual_long_audio_fails_before_mux` | `test_assemble.py:511` | Single beat deficit (10s needed, 3s clip) → RuntimeError |
| `test_visual_bed_mismatch_fails` | `test_assemble.py:520` | Multi-beat aggregate shortfall → RuntimeError |
| `test_valid_continuous_fixture_assembles` | `test_assemble.py:530` | Matching clips succeed, `abs(dur - 6.0) <= 0.25s` |

- Uses `_load_assemble()` which imports `assemble.py` as a module (production entry point). ✅
- `test_short_visual_long_audio_fails_before_mux` asserts `not final.exists()`. ✅
- `test_visual_bed_mismatch_fails` asserts `not final.exists()`. ✅
- `test_valid_continuous_fixture_assembles` checks `abs(dur - 6.0) <= 0.25`. ✅

---

## 7. Early proof (production manifest)

```
$ python3 scripts/assemble.py Videos/Projects/using_ai_to_help_memory_retention_short/manifest.json --formats 16x9
ERROR: Beat B001 clip too short: clip=7.082s, required=13.994s (shortfall=6.912s). Regenerate a longer clip or split into multiple shots.
Exit code: 2
```

- Named beat (`B001`) ✅
- Shortfall reported (`6.912s`) ✅
- Exit non-zero (`2`) ✅
- Final file does NOT exist ✅

```
$ python3 -m pytest tests/test_assemble.py -v
17 passed in 19.26s
```

---

## Acceptance Criteria Compliance

| Criterion | Met? |
|-----------|------|
| 1. Production manifest fails before mux with named beat deficit | ✅ |
| 2. Valid fixture assembles successfully with <=0.25s stream parity | ✅ |
| 3. All tests pass | ✅ (17/17) |
| 4. No -shortest in continuous voiceover path | ✅ |
| 5. Non-continuous path unaffected | ✅ |
| 6. Final file NOT produced when assembly fails | ✅ |

---

## Verdict: **PASS**

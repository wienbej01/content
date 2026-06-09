# M1 Assembly Engine — Automation Audit Report

**Auditor:** Automation Auditor
**Scope:** scripts/assemble.py, scripts/sample_manifest.json, scripts/ASSEMBLY_README.md, tests/test_assemble.py
**Date:** 2026-06-08
**Verdict:** Functional for the current trailer case. Multiple defects that will cause failures on edge cases and general usage. Two critical issues block the "production-ready" claim.

---

## CRITICAL Issues

### C1: Zero input validation — any malformed manifest produces a Python traceback

**Evidence:** `assemble()` does `manifest = json.load(f)` then immediately accesses `manifest["segments"]`, `seg["media"]`, `seg["words"]` etc. with no validation.

**Impact:**
- Missing `id` → log filename becomes `None_log.json`
- Missing `segments` key → `KeyError` traceback
- Missing `words` on a segment → crash inside narrative_speed with opaque error
- Empty segments array → `IndexError` in compute_speeds (ref index out of range)
- `reference` index > len(segments) → `IndexError`
- `trim_end: 0` or negative → undefined ffmpeg behavior
- Non-existent media path → `narrative_speed.probe_duration` calls `sys.exit()` (kills process with misleading message instead of a catchable error)

**Fix:** Add a `validate_manifest()` function at the top of `assemble()`: check required keys exist, files resolve and exist, words > 0, reference in range, trim_end > 0 or null. Return structured errors, non-zero exit.

**Blocks MVP acceptance:** Yes — the acceptance criteria says "given a **valid** manifest" but doesn't address what happens with invalid ones, and the docs claim production-ready usage. A misspelled path will produce a `sys.exit("could not probe duration...")` with exit code 0 on some Python versions (sys.exit with a string prints to stderr and exits non-zero, but the error is opaque).

---

### C2: `test_no_long_silence` does not detect what it claims

**Evidence:** Lines 77–82 of test_assemble.py:
```python
gaps = silence_gaps(info["path"], threshold_db=-40, min_dur=2.0)
mid_gaps = [g for g in gaps if g < dur - 4]
```

`gaps` contains silence **durations** (how long each silence lasts). The filter `g < dur - 4` checks if a gap's DURATION is less than 21s (for a 25s video). Any gap shorter than 21s passes — which is every realistic gap. A 5-second dead-silence gap in the middle of the video would pass this test.

The test CANNOT detect the VO-overlap/dead-air failure it claims to catch.

**Impact:** False confidence. The "no silence gaps" test always passes, regardless of actual silence bugs.

**Fix:** Parse both `silence_start` and `silence_duration` from ffmpeg. Filter out gaps whose start position is within the endcard region (last `endcard_duration + 1` seconds). Assert no remaining gaps exceed the threshold.

**Blocks MVP acceptance:** Yes — one of 7 tests is ineffective, making the test suite unreliable as a quality gate.

---

## HIGH Issues

### H1: concat file list breaks on paths containing single quotes

**Evidence:** Line ~155:
```python
f.write(f"file '{p}'\n")
```

The ffmpeg concat demuxer parses this format. If `p` contains a `'` character (e.g., a folder named `james's clips`), the line becomes `file 'james's clips/...'` → parse error → ffmpeg crash with a confusing error about the concat file.

**Impact:** Any user working in a directory with an apostrophe in the path (common on macOS home directories like `/Users/O'Brien/`) will get a hard failure with no useful message.

**Fix:** Escape single quotes in paths: `p_safe = str(p).replace("'", "'\\''")` or use the concat demuxer's escape format.

**Blocks MVP:** No (current paths don't have quotes), but blocks "production-ready" claim for general use.

---

### H2: Triple re-encode of every segment degrades quality unnecessarily

**Evidence:** Each segment's video is encoded:
1. `process_segment` → seg_N.mp4 (encode #1)
2. `gap_concat` → prep_N.mp4 (re-encode #2, adding fade)
3. `gap_concat` → joined.mp4 via concat demuxer with `-c:v libx264` (re-encode #3)

Three lossy encode passes at CRF 18.

**Impact:** Measurable quality loss vs. a single-pass or two-pass approach. At CRF 18, each re-encode introduces quantization artifacts that compound. For text/graphics (kinetic text, lower-thirds), this creates visible ringing/blur.

**Fix:** The concat step can use `-c copy` since all prepped segments have identical codec parameters (same resolution, fps, crf, pixel format). This eliminates encode #3.

**Blocks MVP:** No — quality at CRF 18 × 3 passes is acceptable for web video. But a cheap fix.

---

### H3: No cleanup of temp files on failure; no atomic output writes

**Evidence:** If ffmpeg fails on segment 2 of 3:
- `seg_0.mp4`, `seg_1.mp4` remain in `_tmp/`
- If a PREVIOUS successful run's output exists at the final path, it remains (so "is the output current?" becomes ambiguous)
- If the script is interrupted during `loudnorm` writing the final file, a PARTIAL (corrupt) output MP4 exists at the final output path

**Impact:** User sees an output file but it's from a previous run, or it's partial/corrupt. Silent data corruption.

**Fix:** Write final output to a temp name (e.g., `.tmp_trailer_16x9.mp4`), then `os.rename()` atomically to the final name only after completion. On failure, delete the temp.

**Blocks MVP:** No — but a silent-corruption risk in practice.

---

### H4: `trim_end` applied to BOTH video and narration audio in the "separate audio" branch

**Evidence:** In the "plain video with audio replacement" branch:
```python
inputs = [*trim_args, "-i", str(media), *trim_args, "-i", str(audio_path)]
```
`trim_args` (e.g., `["-t", "6.65"]`) is applied as an input option to BOTH the video AND the separate narration audio.

**Impact:** If a segment has `trim_end: 6.65` to cut trailing dead air from the video, but the narration audio is a clean 8-second file with no dead air, the narration gets truncated to 6.65s — cutting off the end of the sentence. The audio and video are mismatched.

**Fix:** Apply `trim_args` only to the video input, not the audio input. The audio should be trimmed by the speed/atempo filter and the video duration, not by a video-specific trim parameter.

**Blocks MVP:** No (sample manifest doesn't use separate audio + trim_end together). Will bite on first real production use of that combination.

---

### H5: `narrative_speed.probe_duration` calls `sys.exit()` — kills the process un-recoverably

**Evidence:** In `tools/narrative_speed.py` line ~49:
```python
def probe_duration(path):
    ...
    sys.exit(f"could not probe duration: {path}")
```

This is called from `compute_speeds → measure_pace`. If ANY file path is wrong or unreadable, the entire process exits with no stack trace, no structured error, and (depending on the string passed to sys.exit) potentially a non-standard exit code.

**Impact:** A typo in one segment's media path kills the process with a confusing message. No opportunity for the caller to catch and report which segment/field was wrong.

**Fix:** Raise a `FileNotFoundError` or `RuntimeError` instead of `sys.exit()`. Let the caller handle it. (This is a fix in narrative_speed.py, not assemble.py.)

**Blocks MVP:** Partially — produces a confusing user experience on path errors. Combined with C1, the first-run experience for any user with a path typo is terrible.

---

## MEDIUM Issues

### M1: Music generated twice (once per format) — identical output, wasted compute

**Evidence:** `assemble_format` is called once per format. Each call generates music independently via `gen_music(duration, mood)`. Since duration is identical (same content, same concat), both formats produce the same music WAV redundantly.

**Impact:** ~5–6s of unnecessary computation per build (the music generator takes ~5.5s). Doubles music generation time.

**Fix:** Generate music once in `assemble()` (after computing speeds but before the format loop), pass it to `assemble_format` as a pre-made file. The music.file field already supports this pattern.

---

### M2: `atempo` filter limited to 0.5–2.0 range — no bounds check

**Evidence:** The code computes arbitrary speeds:
```python
speeds = [baseline * ref_wps / w for w in wps_list]
```
If a segment has very few words spoken very fast (high WPS) vs. a slow reference, the computed speed could be < 0.5. Example: segment with 3 words in 1s = 3.0 WPS, reference at 1.5 WPS, baseline 0.85 → speed = 0.85 * 1.5 / 3.0 = 0.425 (below atempo minimum).

ffmpeg's `atempo` silently clips or produces garbage below 0.5.

**Impact:** Distorted audio on extreme speed differences. Silent failure.

**Fix:** Check computed speeds. If outside [0.5, 2.0], either chain atempo filters (e.g., 0.4 → atempo=0.5,atempo=0.8) or warn and clamp.

---

### M3: Endcard uses plain `scale=W:H` — distorts non-matching aspect ratios

**Evidence:** In `make_endcard`:
```python
f"scale={w}:{h},fps={fps},fade=..."
```
Segments use `scale=W:H:force_original_aspect_ratio=increase,crop=W:H` (preserves AR). Endcard uses plain `scale=W:H` (stretches to fit).

**Impact:** If the endcard PNG isn't exactly the target resolution (e.g., the 16:9 endcard used for 9:16), it gets stretched/distorted. Currently mitigated by having separate endcard assets per format.

**Fix:** Use the same scale+crop approach as segments, or validate that endcard dimensions match target.

---

### M4: `has_video()` function defined but never called

**Evidence:** Line 52–57 defines `has_video(path)`. No other code calls it.

**Impact:** Dead code. Suggests the intent was to detect whether media is video vs. audio-only, but it's unused. If media is a video without an audio stream and no separate `audio` field, the `-map 0:a` will fail.

**Fix:** Either remove dead code or use it to validate that video segments have audio (or require the `audio` field if they don't).

---

### M5: The `os` module is imported but never used

**Evidence:** Line 4: `import os`. No `os.*` call anywhere.

**Impact:** None (dead import). Minor code hygiene.

---

### M6: Log filename uses `prefix` not `id` — inconsistent with docs/output

**Evidence:** 
```python
log_path = out_dir / f"{prefix}_log.json"
```
But the print in `main()` references `log['id']`:
```python
print(f"  log: {... / (log['id'] + '_log.json')}")
```
If `prefix != id` (e.g., prefix="trailer_leveragemind", id="trailer_v6"), the printed path is wrong.

**Impact:** Log filename printed to console doesn't match actual log file on disk. Confusing.

**Fix:** Use consistent naming — either always use prefix or always use id for the log.

---

## LOW Issues

### L1: Determinism claim is technically false (multi-threaded x264)

**Evidence:** Docstring says "Deterministic: same manifest + same assets = same output." Without `-threads 1`, x264 encoding is non-deterministic (thread scheduling affects bitstream).

**Impact:** Bit-for-bit comparison between runs will fail. Visually identical. Only matters for checksums/verification.

**Fix:** Document the limitation, or add `-threads 1` (slower but truly deterministic) as an option.

---

### L2: No `--version` or `--help` beyond argparse default

**Evidence:** No version tracking. Can't determine which version of assemble.py produced an output.

**Fix:** Add a `__version__` string logged in the execution log.

---

### L3: Lower-third position hardcoded to `overlay=70:H-h-70`

**Evidence:** In the lower-third branch, the overlay is positioned at fixed pixel coordinates. For 9:16 output (1080×1920), `H-h-70` means 70px from bottom. This might be too low or too high depending on the lower-third image size and the vertical format.

**Impact:** Lower-third may be poorly positioned in 9:16 format. Currently untested (sample manifest's lower-third is only on segment 1 which is produced in both formats).

---

## Adversarial Test Manifests

### 1. Paths containing spaces

```json
{
  "id": "spaces_test",
  "segments": [{"media": "../Videos/My Project Files/clip one.mp4", "words": 10}],
  "output": {"directory": "../Videos/Output Folder", "prefix": "test output"}
}
```
**Expected failure point:** `gap_concat` concat.txt — the file list uses single quotes which handle spaces, so this SHOULD work. The subprocess calls use list args (no shell splitting). **Likely passes.** But test to confirm.

### 2. Missing media asset

```json
{
  "id": "missing_test",
  "segments": [{"media": "../does_not_exist.mp4", "words": 10}]
}
```
**Expected failure:** `narrative_speed.probe_duration` calls `sys.exit("could not probe duration: ...")` — kills process with a confusing message, not a structured error. **Fails badly** (C1 + H5).

### 3. Narration longer than visual segment

```json
{
  "id": "long_narration",
  "segments": [{
    "media": "../Videos/short_clip.mp4",
    "audio": "../Videos/long_narration_30s.wav",
    "words": 50
  }]
}
```
**Expected failure:** Video is 5s, narration is 30s. `-map 0:v` gives 5s of video, `-map 1:a` gives 30s of audio (after atempo). Without `-shortest`, output is 30s with frozen/looping last frame? Actually — ffmpeg with concat won't extend video. The video stream ends at 5s; the audio continues. The output has mismatched durations (video 5s, audio 30s). The container duration will be 30s with a static last frame. **Produces garbage output with no error.**

### 4. Music file shorter than final video

```json
{
  "id": "short_music",
  "music": {"file": "../short_5s_track.wav", "level_db": -16},
  "segments": [...]  
}
```
**Expected behavior:** `make_music_bed` uses `-t {duration}` which EXTENDS the input with silence if the source is shorter (in some ffmpeg configurations) or just makes a shorter output. Then `amix=duration=first` uses the video's duration → music just ends and the tail has no bed. **Produces silent music after 5s.** Not a crash, but degraded quality with no warning.

### 5. 5-minute video duration

```json
{
  "id": "long_video",
  "segments": [
    {"media": "clip_300s.mp4", "words": 500}
  ]
}
```
**Expected issues:**
- Music generation for 300s: `gen_music(300, "calm")` generates 300*48000 = 14.4M samples. Build time ~30s (linear with duration). Acceptable.
- A/V drift from setpts/atempo: at speed 0.85 over 300s → 353s output. Drift risk: a few ms. Not audible.
- Temp disk usage: a single 5-min segment at 1080p CRF 18 ≈ 100–200MB. Three copies (seg, prep, joined) = 300–600MB. Plus 9:16 = 600MB–1.2GB total tmp. No tmp size check. Could fill disk silently.

### 6. Portrait-only asset in 16:9 output

Input: a 1080×1920 portrait video being assembled into 1920×1080 landscape.
```json
{"media": "portrait_9x16_clip.mp4", "words": 20}
```
**Expected behavior:** `scale=1920:1080:force_original_aspect_ratio=increase` → scales height to 1080, width becomes 1080*(1080/1920)=607... wait. force_original_aspect_ratio=increase means the output is AT LEAST 1920×1080. Input is 1080×1920 (portrait). To cover 1920×1080, it scales so the smaller dimension (width 1080) matches the target width (1920). Scale factor = 1920/1080 = 1.78. Result: 1920×3413. Then `crop=1920:1080` takes the CENTER 1920×1080 of this. **This is the top/middle portion of the portrait frame, cutting top and bottom.** For a talking head, the face may be in the upper third → gets preserved. For a full-body shot, legs and top of head are cut. **Works correctly** (center-crop is the defined behavior) but may produce aesthetically poor results that should be documented.

### 7. Landscape-only asset in 9:16 output

Input: a 1920×1080 landscape video being assembled into 1080×1920 vertical.
```json
{"media": "landscape_16x9_clip.mp4", "words": 20}
```
**Expected behavior:** `scale=1080:1920:force_original_aspect_ratio=increase` → scales height to 1920, width = 1920*(1920/1080) = 3413. Then `crop=1080:1920` center-crops. **This is a narrow vertical slice of the center of the landscape frame.** For a centered talking head, this takes the middle. For wide-angle or off-center compositions, important content is cropped out. **Works correctly but aggressively crops the sides.** This IS the current trailer behavior (validated). Documented behavior.

---

## Summary Table

| ID | Severity | Issue | Blocks MVP? |
|---|---|---|---|
| C1 | Critical | Zero input validation | Yes |
| C2 | Critical | test_no_long_silence is broken logic | Yes |
| H1 | High | Concat file breaks on single-quote paths | No |
| H2 | High | Triple re-encode degrades quality | No |
| H3 | High | No atomic output / no failure cleanup | No |
| H4 | High | trim_end applied to separate audio | No |
| H5 | High | narrative_speed sys.exit kills process | Partially |
| M1 | Medium | Music generated twice (redundant) | No |
| M2 | Medium | atempo range not checked | No |
| M3 | Medium | Endcard scale distorts non-matching AR | No |
| M4 | Medium | has_video() dead code | No |
| M5 | Medium | os import unused | No |
| M6 | Medium | Log filename inconsistency | No |
| L1 | Low | Determinism claim false (multi-thread x264) | No |
| L2 | Low | No version tracking | No |
| L3 | Low | Lower-third position hardcoded | No |

---

## Recommendation

Fix C1 and C2 before claiming "production-ready." Both are ~30 minutes of work each. The rest are real issues that will surface over the first 10 videos, but none block shipping the trailer-style content you're already producing.

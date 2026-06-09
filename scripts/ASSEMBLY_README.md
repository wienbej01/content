# Assembly Engine — Manifest Schema & CLI Documentation

## CLI Usage

```bash
# Produce both 16:9 and 9:16 outputs:
python scripts/assemble.py manifest.json

# Produce only one format:
python scripts/assemble.py manifest.json --formats 16x9

# Use a custom temp directory:
python scripts/assemble.py manifest.json --tmp /fast/disk/tmp
```

**Outputs** (in `output.directory`):
- `{prefix}_16x9.mp4`
- `{prefix}_9x16.mp4`
- `{prefix}_log.json` — execution log (durations, speeds, build times)

**Path resolution:** All paths in the manifest are relative to the manifest file's directory.

---

## Manifest Schema

```json
{
  "id": "string — unique identifier for this video",

  "segments": [
    {
      "media": "path — video clip (.mp4) or still image (.png/.jpg)",
      "audio": "path — optional narration audio (required if media is an image; replaces video audio if provided)",
      "words": "integer — word count of the narration (for WPS alignment)",
      "trim_end": "float|null — trim media to this many SOURCE seconds (cuts trailing dead air)",
      "lower_third": "path|null — overlay this PNG on the segment (fade in/out)"
    }
  ],

  "pacing": {
    "reference": "integer — 0-indexed segment to use as the WPS reference",
    "baseline_speed": "float — playback speed applied to the reference segment (others computed to match)"
  },

  "music": {
    "file": "path|null — pre-made music file. If null, generates original piano+violin bed.",
    "mood": "string — 'calm' or 'pensive' (used if file is null)",
    "level_db": "float — music level relative to narration (default -16)"
  },

  "brand": {
    "endcard_16x9": "path — endcard image for landscape",
    "endcard_9x16": "path — endcard image for vertical",
    "endcard_duration": "float — endcard duration in seconds (default 3.0)",
    "gap_seconds": "float — silent gap between segments (default 0.4)",
    "audio_fade": "float — fade duration on segment tails (default 0.3)"
  },

  "render": {
    "fps": "integer — output framerate (default 24)",
    "crf": "integer — H.264 quality (default 18, lower = better)",
    "grade": "string — ffmpeg video filter for color grading"
  },

  "output": {
    "directory": "path — where to write outputs",
    "prefix": "string — filename prefix for outputs"
  }
}
```

---

## Required vs Optional Fields

| Field | Required | Default |
|---|---|---|
| `id` | Yes | — |
| `segments` | Yes (≥1) | — |
| `segments[].media` | Yes | — |
| `segments[].words` | Yes | — |
| `segments[].audio` | Only if media is image | — |
| `segments[].trim_end` | No | null (full duration) |
| `segments[].lower_third` | No | null (no overlay) |
| `pacing.reference` | No | 0 |
| `pacing.baseline_speed` | No | 1.0 |
| `music.file` | No | null (auto-generate) |
| `music.mood` | No | "calm" |
| `music.level_db` | No | -16 |
| `brand.endcard_*` | No | omitted = no endcard |
| `brand.endcard_duration` | No | 3.0 |
| `brand.gap_seconds` | No | 0.4 |
| `brand.audio_fade` | No | 0.3 |
| `render.fps` | No | 24 |
| `render.crf` | No | 18 |
| `render.grade` | No | warm brand grade |
| `output.directory` | No | "." |
| `output.prefix` | No | same as `id` |

---

## How It Works

1. **Measure pacing:** Runs `narrative_speed.measure()` on each segment's audio to compute words-per-second. Derives per-segment playback speeds so all segments match the reference segment's WPS.

2. **Process segments (per output format):** Each segment is normalized to the target resolution (scale + center-crop), graded, speed-adjusted (video via setpts, audio via atempo), and optionally has a lower-third overlay.

3. **Endcard:** A still image is turned into a short video clip with fade in/out.

4. **Gap-concat:** Segments are concatenated with short silent black gaps between them. Audio fades out at the tail of each segment. This **guarantees zero narration overlap** between segments.

5. **Music:** Either loads a provided file or generates an original piano+violin ambient bed (royalty-free, no licensing risk). Applied at the configured level under the narration.

6. **Loudness normalization:** EBU R128 at -16 LUFS / -1.5 dBTP.

---

## Property Tests

Run after assembly to validate output quality:

```bash
python tests/test_assemble.py Videos/Completed/trailer_leveragemind_log.json
```

Tests:
- Both output files exist
- Durations are sane and match between formats
- Resolutions are correct (1920×1080 / 1080×1920)
- Audio stream is present
- Mean volume is in broadcast range (-22 to -12 dB)
- No long silence gaps (>2s) in the content region
- WPS alignment is within 15% of target across all segments

---

## Execution Log

Written to `{prefix}_log.json`:

```json
{
  "id": "trailer_v6",
  "manifest": "/path/to/manifest.json",
  "started_at": "2026-06-08T21:06:59+0800",
  "finished_at": "2026-06-08T21:08:07+0800",
  "formats": {
    "16x9": {"path": "...", "duration_s": 25.63, "build_time_s": 33.4},
    "9x16": {"path": "...", "duration_s": 25.63, "build_time_s": 34.2}
  },
  "pacing": {
    "wps_per_segment": [2.177, 3.05, 1.976],
    "speeds": [1.1909, 0.85, 1.312],
    "target_wps": 2.592
  }
}
```

# Media Pack — Asset Planning & Validation (M3)

## Overview

Not a media generator. A planning and validation tool that bridges the gap between a reviewed script and the assembly pipeline.

```
reviewed_script.json → media_pack.py --brief → media_brief.json
                                              → human creates assets
                     → media_pack.py --validate → pass/fail/warnings
                     → media_pack.py --write-ready-script → script_with_media.json
                     → tts.py → manifest.json → assemble.py → final MP4s
```

## CLI Usage

```bash
# Generate a media brief (what assets are needed, where they go):
python scripts/media_pack.py scripts/sample_script.json --brief

# Validate that media assets exist and are compatible:
python scripts/media_pack.py scripts/sample_script.json --validate

# Write a ready-to-use script (with validated media paths filled in):
python scripts/media_pack.py scripts/sample_script.json --write-ready-script

# All three in sequence:
python scripts/media_pack.py scripts/sample_script.json --brief --validate --write-ready-script
```

## Segment `audio_mode` (from M2-C)

| Mode | TTS generated? | Manifest audio field? | Use case |
|---|---|---|---|
| `generated_tts` | Yes | Yes | Images, B-roll with narration |
| `baked_in` | No | No (uses clip audio) | Higgsfield lipsync clips |
| `silent` | No | No | Title cards, transitions |

## Media Request Schema (optional per segment)

```json
"media_request": {
  "type": "lipsync_video" | "broll_video" | "image" | "title_card" | "chart" | "screen_recording",
  "description": "Visual description for human reference",
  "orientation": "landscape" | "portrait" | "either",
  "duration_policy": "match_audio" | "fixed" | "use_media_duration",
  "required": true
}
```

## Media Type → Audio Mode Mapping

| Scenario | `audio_mode` | `media_request.type` |
|---|---|---|
| Higgsfield lipsync clip | `baked_in` | `lipsync_video` |
| Image with voiceover | `generated_tts` | `image` |
| B-roll with irrelevant ambient audio | `generated_tts` | `broll_video` |
| Screen recording with narration | `generated_tts` | `screen_recording` |
| Silent title card | `silent` | `title_card` |
| Chart/diagram with narration | `generated_tts` | `chart` |

## Default File Naming Convention

Assets go in `Videos/Projects/<project_id>/media/`:

| Type | Expected filename |
|---|---|
| `lipsync_video` | `media/<segment_id>.mp4` |
| `broll_video` | `media/<segment_id>.mp4` |
| `screen_recording` | `media/<segment_id>.mp4` |
| `image` | `media/<segment_id>.png` |
| `title_card` | `media/<segment_id>.png` |
| `chart` | `media/<segment_id>.png` |

## Validation Checks

- File exists and is readable
- File extension matches expected type
- ffprobe succeeds on video files
- `baked_in` clips must have an audio stream
- Orientation mismatch → warning (not error, since assemble.py crops)
- Optional media → warning if missing (not error)
- Unknown type/extension → error

## Full Pipeline Example

```bash
# 1. Write your script (set audio_mode per segment)
# 2. Generate media brief
python scripts/media_pack.py my_script.json --brief
# 3. Create/download media assets per the brief
# 4. Validate
python scripts/media_pack.py my_script.json --validate
# 5. Generate ready script
python scripts/media_pack.py my_script.json --write-ready-script
# 6. Run TTS + assembly
python scripts/tts.py Videos/Projects/my_project/script_with_media.json --assemble
```

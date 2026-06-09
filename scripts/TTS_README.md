# TTS-to-Manifest Pipeline (M2)

## Overview

Bridges reviewed script text → ElevenLabs narration audio → assembly manifest.

```
reviewed_script.json → tts.py → narration/*.mp3 + manifest.json → assemble.py → final MP4s
```

## CLI Usage

```bash
# Validate script structure without API calls:
python scripts/tts.py scripts/sample_script.json --validate-only

# Generate narration + manifest (requires ELEVENLABS_API_KEY):
python scripts/tts.py scripts/sample_script.json

# Force-regenerate all narration (ignore cached files):
python scripts/tts.py scripts/sample_script.json --force

# Generate + immediately assemble:
python scripts/tts.py scripts/sample_script.json --assemble
```

## Setup

Add your ElevenLabs credentials to `~/.config/ytchannel/runtime.env`:
```
ELEVENLABS_API_KEY=sk_...your_key...
ELEVENLABS_VOICE_ID=...your_james_harrington_voice_id...
```

**Never commit runtime.env or API keys to git.** The `.gitignore` excludes `*.env` and `runtime.env`.

Voice ID resolution (first match wins):
1. `voice.voice_id` in the script JSON
2. `ELEVENLABS_VOICE_ID` from environment / runtime.env
3. If neither → clean error, no silent defaults

## Input Script Schema

```json
{
  "project_id": "first_video",
  "title": "Human-readable title",
  "output_dir": "Videos/Projects/first_video",
  "voice": {
    "voice_id": "your_elevenlabs_voice_id",
    "model_id": "eleven_multilingual_v2",
    "settings": {
      "stability": 0.50,
      "similarity_boost": 0.75,
      "style": 0.12
    }
  },
  "defaults": {
    "format": "mp3"
  },
  "segments": [
    {
      "id": "001_hook",
      "text": "The narration text for this segment.",
      "media": "path/to/video_or_image.mp4",
      "trim_end": null,
      "lower_third": null
    }
  ]
}
```

### Required Fields

| Field | Required | Notes |
|---|---|---|
| `project_id` | Yes | Used for output directory and manifest naming |
| `voice.voice_id` | Yes | ElevenLabs voice ID |
| `segments[].id` | Yes | Determines audio filename (`narration/{id}.mp3`) |
| `segments[].text` | Yes | Text sent to ElevenLabs |
| `segments[].media` | Yes | Video/image for assembly |

### Optional Fields

| Field | Default | Notes |
|---|---|---|
| `output_dir` | `Videos/Projects/{project_id}` | Where narration + manifest go |
| `voice.model_id` | `eleven_multilingual_v2` | ElevenLabs model |
| `voice.settings` | stability=0.5, similarity=0.75, style=0.12 | Voice parameters |
| `defaults.format` | `mp3` | Audio format |
| `segments[].trim_end` | null | Trim video to N source seconds |
| `segments[].lower_third` | null | PNG overlay path |

## Output

```
Videos/Projects/{project_id}/
├── narration/
│   ├── 001_hook.mp3
│   ├── 002_body.mp3
│   └── 003_cta.mp3
├── manifest.json          ← pass this to assemble.py
└── tts_log.json           ← generation metadata
```

## Behavior

- **Caching:** Existing narration files are reused unless `--force` is passed. No API calls wasted.
- **Durations:** Always probed from actual audio (ffprobe), never estimated from word count.
- **Word counts:** Computed from script text and written to manifest for WPS alignment.
- **Failure:** If TTS fails on segment N, already-generated segments are preserved. Re-run without `--force` to retry only the missing ones.
- **No fake audio:** Production paths never receive dummy/mock audio. If the API key is missing, the tool fails immediately with a clear error.

## Full Pipeline Example

```bash
# 1. Validate
python scripts/tts.py my_script.json --validate-only

# 2. Generate narration + manifest
python scripts/tts.py my_script.json

# 3. Review narration files (listen to them!)

# 4. Assemble
python scripts/assemble.py Videos/Projects/my_project/manifest.json

# Or combine steps 2+4:
python scripts/tts.py my_script.json --assemble
```

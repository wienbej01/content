# Media Generation Bridge (M3)

## Overview

Generates video clips from `visual_brief` descriptions via Higgsfield CLI, saving them to the paths specified in the script JSON.

```
script.json → generate_media.py → MP4s at segment media paths → tts.py → assemble.py
```

## Prerequisites

```bash
npm install @higgsfield/cli                                    # one-time
node node_modules/@higgsfield/cli/bin/higgsfield.js auth login  # one-time browser auth
```

## CLI Usage

```bash
# Check what media exists/is needed:
python3 scripts/generate_media.py script.json --validate-only

# See planned prompts without spending credits:
python3 scripts/generate_media.py script.json --dry-run

# Generate missing media (skips existing):
python3 scripts/generate_media.py script.json

# Force regenerate all media:
python3 scripts/generate_media.py script.json --force

# Generate + run TTS + assemble:
python3 scripts/generate_media.py script.json --assemble

# Use a specific model:
python3 scripts/generate_media.py script.json --model kling3_0
```

## Script JSON Requirements

Each segment needs:
- `id` — segment identifier (determines filename)
- `visual_brief` — text prompt for video generation
- `media` — target path where the MP4 will be saved
- `audio_mode` — how audio is handled downstream

## Available Video Models

| Model | Credits | Notes |
|---|---|---|
| `wan2_7` (default) | 7.5 | Good quality, fast |
| `kling3_0` | 10 | Higher quality |
| `seedance_2_0` | varies | Best for character motion |
| `veo3_1` | varies | Google Veo |

## Behavior

- **Caching:** Existing MP4s are reused unless `--force` is passed (no wasted credits)
- **Validation:** --validate-only checks schema + file existence without API calls
- **Dry-run:** Shows prompts/paths without spending credits
- **Cost:** Each segment = 1 generation job (~7-10 credits depending on model)
- **Output:** 1920×1080 MP4 clips (center-safe for 9:16 crop in assembly)

## Cost Control

Check balance: `node node_modules/@higgsfield/cli/bin/higgsfield.js account status`

8 segments × 7.5 credits (wan2_7) = 60 credits per video.

# Operating Guide

**Generated:** 2026-06-12
**Status:** Reflects the system as actually implemented on this date.

---

## Prerequisites

- Python 3.10+ (repo uses `python3`; GCE VM may need `python3.13`)
- Node.js (for Higgsfield CLI)
- ffmpeg + ffprobe (must be in PATH)
- kiro-cli (must have active session for LLM calls)
- Higgsfield CLI authenticated (see Setup)
- ElevenLabs API key

---

## Environment Variables

Create `~/.config/ytchannel/runtime.env`:

```
ELEVENLABS_API_KEY=your_key_here
ELEVENLABS_VOICE_ID=your_voice_id_here
```

Optional:
```
ELEVENLABS_SPEED=1.0
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

Scripts load this file at startup via `tts.py:load_runtime_env()`.

---

## Setup

```bash
# Authenticate Higgsfield CLI (one-time, or when token expires)
node node_modules/@higgsfield/cli/bin/higgsfield.js auth login

# Verify authentication
node node_modules/@higgsfield/cli/bin/higgsfield.js account status --json

# Check available models
node node_modules/@higgsfield/cli/bin/higgsfield.js model list --json | python3 -c "import json,sys; [print(m['job_set_type']) for m in json.load(sys.stdin) if m.get('type')=='video']"

# Verify Python dependencies
python3 -c "import yaml; print('yaml OK')"
```

---

## Common Commands

### Validate a script without making API calls
```bash
python3 scripts/tts.py scripts/generated/{project_id}.json --validate-only
python3 scripts/generate_media.py scripts/generated/{project_id}.json --validate-only
```

### Dry-run media generation (shows prompts, models, costs — no API calls)
```bash
python3 scripts/generate_media.py scripts/generated/{project_id}.json --dry-run
```

### Generate narration (ElevenLabs)
```bash
python3 scripts/tts.py scripts/generated/{project_id}.json
# force regenerate all:
python3 scripts/tts.py scripts/generated/{project_id}.json --force
```

### Generate video clips (Higgsfield)
```bash
python3 scripts/generate_media.py scripts/generated/{project_id}.json
# specific segments only:
python3 scripts/generate_media.py scripts/generated/{project_id}.json --segment 001_hook --segment 002_promise
# force regenerate:
python3 scripts/generate_media.py scripts/generated/{project_id}.json --force
```

### Assemble final video
```bash
python3 scripts/assemble.py Videos/Projects/{project_id}/manifest.json
# 16:9 only:
python3 scripts/assemble.py Videos/Projects/{project_id}/manifest.json --formats 16x9
# disable music:
python3 scripts/assemble.py Videos/Projects/{project_id}/manifest.json --no-music
# override music:
python3 scripts/assemble.py Videos/Projects/{project_id}/manifest.json --music assets/music/your_track.mp3 --music-volume-db -24
```

### Review scripts (LLM-based)
```bash
python3 scripts/review_script.py scripts/generated/{project_id}.json
python3 scripts/review_script.py scripts/generated/{project_id}.json --personas audience,filmmaker
python3 scripts/review_script.py scripts/generated/{project_id}.json --output review.json
```

### Generate storyboard
```bash
python3 scripts/storyboard.py scripts/generated/{project_id}.json --dry-run
python3 scripts/storyboard.py scripts/generated/{project_id}.json --output storyboard.json
# with LLM retention optimization:
python3 scripts/storyboard.py scripts/generated/{project_id}.json --optimize
```

### Generate content brief (pre-script)
```bash
python3 scripts/generate_content_brief.py --topic "How to learn faster" --pillar "Learning" --output briefs/001.json
```

### Generate hooks
```bash
python3 scripts/generate_hooks.py --topic "How compounding works for careers" --output hooks.json
```

### Media QA
```bash
python3 scripts/qa_media.py scripts/generated/{project_id}.json
python3 scripts/qa_media.py scripts/generated/{project_id}.json --segment 001_hook
```

### Extract review frames
```bash
python3 scripts/generate_media.py scripts/generated/{project_id}.json --review
```

### Run tests
```bash
python3 -m pytest tests/ --tb=short -q
```

---

## How to Produce a Video from Existing Assets

If you already have a completed `manifest.json` with all media and narration files:

```bash
cd ~/YTchannel
python3 scripts/assemble.py Videos/Projects/{project_id}/manifest.json
```

The assembler validates the manifest first. Fix any reported errors before running.

Output: `Videos/Projects/{project_id}/{project_id}_16x9.mp4` and `_9x16.mp4`.

---

## Full End-to-End Sequence (new video — V2 gated pipeline)

> The V2 pipeline introduced a hard gate chain. No Higgsfield spend is possible until four gates pass: `storyboard_review`, `media_plan_review`, `budget`, and `render_approval`. See `docs/RUNBOOK_PRODUCTION_V2.md` for the full command runbook with failure handling.

```bash
PROJECT=flagship_002_your_slug

# 1. Research + brief (manual — follow docs/RESEARCH_SOP.md)
python3 scripts/generate_content_brief.py --topic "..." --output research/briefs/${PROJECT}_brief.json
python3 scripts/generate_hooks.py --topic "..." --output research/briefs/${PROJECT}_hooks.json

# 2. [MANUAL] Write scripts/generated/${PROJECT}.json
python3 scripts/tts.py scripts/generated/${PROJECT}.json --validate-only

# 3. Script review (G1) — advisory exit code; record gate manually
python3 scripts/review_script.py scripts/generated/${PROJECT}.json \
  --output Videos/Projects/${PROJECT}/script_review.json
python3 scripts/gates.py record ${PROJECT} script_review pass \
  --artifact Videos/Projects/${PROJECT}/script_review.json

# 4. Narration (ElevenLabs)
python3 scripts/tts.py scripts/generated/${PROJECT}.json

# 5. Storyboard routing (directorial layer)
python3 scripts/storyboard.py scripts/generated/${PROJECT}.json \
  --output Videos/Projects/${PROJECT}/storyboard.json

# 6. Storyboard gate (G2) — hard: blocks compile_media_prompts.py
python3 scripts/review_storyboard.py \
  Videos/Projects/${PROJECT}/storyboard.json --record-gate

# 7. Compile media plan — hard: requires G2; exits 1 if lint fails
python3 scripts/compile_media_prompts.py \
  Videos/Projects/${PROJECT}/storyboard.json \
  --output Videos/Projects/${PROJECT}/media_plan.json

# 8. Media plan review (G3) — record gate (manual until review_media_plan.py is updated)
python3 scripts/gates.py record ${PROJECT} media_plan_review pass \
  --artifact Videos/Projects/${PROJECT}/media_plan.json

# 9. Budget gate (G4) — hard: blocks generate_media.py
python3 scripts/budget.py Videos/Projects/${PROJECT}/media_plan.json --record-gate

# 10. Dry-run — ZERO API calls; writes dryrun_report.json
python3 scripts/generate_media.py Videos/Projects/${PROJECT}/media_plan.json --dry-run

# 11. Human render approval (G5) — LAST GATE BEFORE SPEND; read dry-run report first
python3 scripts/approve.py ${PROJECT} --gate render \
  --dryrun Videos/Projects/${PROJECT}/dryrun_report.json --by "operator"

# 12. Generate media (Higgsfield) — hard: all four spend gates checked first
python3 scripts/generate_media.py Videos/Projects/${PROJECT}/media_plan.json

# 13. Media QA gate (G8)
python3 scripts/qa_media.py scripts/generated/${PROJECT}.json --scope source --record-gate

# 14. Assemble — hard: requires media_qa gate when --require-gates is passed
python3 scripts/assemble.py Videos/Projects/${PROJECT}/manifest.json \
  --require-gates --project-id ${PROJECT}

# 15. [MANUAL] Review final video against QA_RUBRIC.md, then publish
python3 scripts/gates.py record ${PROJECT} final_qa pass \
  --artifact Videos/Projects/${PROJECT}/${PROJECT}_16x9.mp4
```

---

## Legacy sequence (pre-V2, for reference only)

The original workflow drove `generate_media.py` directly from the script `visual_brief` field. That path is now **deprecated and blocked** in the default run mode (exits 1 with an instruction to route through the media plan first). It can be accessed with `--force-unsafe` for emergency use; that flag logs `forced:true` in the gate ledger.

```bash
# DEPRECATED — use V2 sequence above instead
python3 scripts/generate_media.py scripts/generated/${PROJECT}.json  # exits 1 (deprecated)
python3 scripts/generate_media.py scripts/generated/${PROJECT}.json --force-unsafe  # emergency only
```

---

## Expected Outputs

After a successful run:

```
Videos/Projects/{project_id}/
├── manifest.json                   ← generated by tts.py
├── narration/
│   ├── 001_hook.mp3
│   ├── 002_promise.mp3
│   └── ... (one per segment)
├── {project_id}_16x9.mp4           ← final output
├── {project_id}_9x16.mp4           ← final output
├── {project_id}_log.json           ← assembly log
├── tts_log.json
└── review_frames/                  ← if --review was run
    └── *.jpg

assets/media/{project}/
└── shots/
    ├── 001_hook.mp4                ← if baked_in lipsync
    ├── 002_promise_000.mp4         ← b-roll shots
    └── ...
```

---

## Validation Commands

```bash
# Check assembly log
cat Videos/Projects/{project_id}/{project_id}_log.json | python3 -m json.tool

# Check video duration and format
ffprobe -v error -show_entries format=duration,size -show_entries stream=width,height,codec_name \
  Videos/Projects/{project_id}/{project_id}_16x9.mp4

# Check narration exists
ls Videos/Projects/{project_id}/narration/

# Check shot count
ls assets/media/{project_id}/shots/ | wc -l

# Check git status (should be clean after a production run)
git status --short
```

---

## Troubleshooting

### "Not authenticated" from Higgsfield
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js auth login
```

### "ELEVENLABS_API_KEY not set"
Check `~/.config/ytchannel/runtime.env` has the key. No quotes needed around value.

### "Manifest validation failed: media not found"
All media paths in manifest.json must exist. If generating new media, run `generate_media.py` first, then re-run `tts.py` to regenerate the manifest.

### "ENG-04 QA gate: segment X duration mismatch"
A segment's video duration doesn't match its narration. Solutions:
1. If segment has `shots[]`: add more shots or increase their durations to cover narration
2. If single clip: regenerate a longer clip, or pass `--allow-looping`

### kiro-cli returns no response
kiro-cli session may have expired. Re-authenticate: `kiro-cli login` (or equivalent for your setup).

### Higgsfield returns "no result_url"
Rate limit or transient API failure. The script retries automatically (up to 3 times with 60s backoff). If it fails all retries, wait and rerun with `--segment {failed_id}`.

### Assembly produces only one format
Check `--formats` argument. Default is `16x9,9x16`. To produce both: omit the flag entirely.

---

## Key File Paths (Quick Reference)

| Purpose | Path |
|---|---|
| Sample script | `scripts/sample_script.json` |
| Sample manifest | `scripts/sample_manifest.json` |
| Flagship 001 script (v1) | `scripts/generated/flagship_001_learn_half_time.json` |
| Flagship 001 script (v2, with shots) | `scripts/generated/flagship_001_learn_half_time_v2.json` |
| Flagship 001 manifest | `Videos/Projects/flagship_001_learn_half_time/manifest.json` |
| Flagship 001 final 16x9 | `Videos/Projects/flagship_001_learn_half_time/flagship_001_learn_half_time_16x9.mp4` |
| Flagship 001 final 9x16 | `Videos/Projects/flagship_001_learn_half_time/flagship_001_learn_half_time_9x16.mp4` |
| Model routing config | `configs/james/model_routing.yaml` |
| LLM model config | `configs/llm_models.yaml` |
| Production constraints | `docs/channel_universe/constraints.json` |
| Universe bible | `docs/channel_universe/UNIVERSE_BIBLE.md` |
| API keys | `~/.config/ytchannel/runtime.env` (not in repo) |

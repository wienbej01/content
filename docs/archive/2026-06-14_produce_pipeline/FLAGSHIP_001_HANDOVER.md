# Handover Prompt — Flagship 001 Production Continuation

Use this prompt to resume the production session in a new kiro-cli chat on the GCE VM.

---

## Context Prompt (paste this into a new kiro-cli session)

```
You are continuing a video production session for a faceless YouTube channel project. Here is the full context:

## Project
- Faceless AI-native educational YouTube channel (brand: "Leverage Mind" / working title)
- Character: James Harrington (AI-generated presenter via Higgsfield lipsync)
- Business plan: strategy/BUSINESS_PLAN.md
- Master timeline: strategy/TIMEPLAN.yaml
- Current task: P6-02 "Produce flagship video #1 (first creative-final)"

## Flagship 001 — "Why Everything You Read Disappears (And How To Fix It)"
- 9 segments, ~1260 words, learning/retention pillar
- Script: scripts/generated/flagship_001_learn_half_time.json
- Narration: Videos/Projects/flagship_001_learn_half_time/narration/ (all 9 MP3s, ElevenLabs eleven_v3)
- Music: Night Snow - Asher Fulero at -24dB
- Model: seedance_2_0 (lipsync with --image + --audio)
- Canonical reference frames: assets/reference/studio_library/canonical/

## Current Status
Media generation was launched as a background process (PID 9335, /tmp/run_flagship.sh).
Check status: `tail -30 /tmp/flagship_001_media_gen2.log`
Check if running: `ps aux | grep run_flagship`

### If generation COMPLETED successfully:
1. Check `assets/media/flagship_001/` for 9 MP4 files
2. Check if assembly ran (look for final MP4 in Videos/Projects/flagship_001_learn_half_time/)
3. If no assembled video, run: `python3.13 scripts/assemble.py Videos/Projects/flagship_001_learn_half_time/manifest.json`
4. Send to Telegram: `python3.13 -c "import sys; sys.path.insert(0,'tools'); from send_telegram_message import send_telegram_video; print(send_telegram_video('PATH_TO_MP4', 'Flagship 001'))"`
5. Run Gate B QA (see below)

### If generation FAILED:
1. Check log: `tail -50 /tmp/flagship_001_media_gen2.log`
2. Common issue: Higgsfield lipsync needs --image + --audio together (already fixed in generate_media.py)
3. If credits exhausted: `node node_modules/@higgsfield/cli/bin/higgsfield.js account status --json`
4. Can retry specific segments: `python3.13 scripts/generate_media.py scripts/generated/flagship_001_learn_half_time.json --segment 001_hook`
5. To retry all: `python3.13 scripts/generate_media.py scripts/generated/flagship_001_learn_half_time.json --assemble`

### If generation is STILL RUNNING:
- Wait. Each segment takes 3-10 minutes. 9 segments = 30-90 min total.
- Monitor: `tail -f /tmp/flagship_001_media_gen2.log`

## Gate B QA Criteria
Gate B = visual/audio quality gate before publishing. Review the assembled video for:
1. **Lipsync quality** — mouth movement matches audio naturally (no desync, no rubber mouth)
2. **Identity consistency** — James looks the same across all 9 segments (same face, hair, clothing)
3. **Studio consistency** — same room (off-white bookshelves, brass lamp, mahogany desk) in every shot
4. **Audio timing** — no gaps between segments, transitions smooth, music doesn't clip
5. **Brand** — endcard present (3s), lower third if applicable
6. **Music mix** — Night Snow audible but not competing with narration (-24dB target)
7. **No AI artifacts** — no text hallucinations, no warped faces, no extra fingers, no glitchy frames

If ANY segment fails identity/lipsync badly: regenerate just that segment with --segment flag.
If most segments pass: proceed to publish.

## After Gate B passes:
1. Mark P6-02 as done in strategy/TIMEPLAN.yaml
2. Upload to YouTube (SEO title + description + tags from the media plan)
3. Atomize to Shorts/Reels/TikTok (use scripts for clip extraction)
4. Write newsletter issue (rewrite framework as essay for Beehiiv)
5. Commit + push: `git add -A && git commit -m "P6-02 DONE: flagship_001 published" && git push`

## Key Files
- Production status: docs/plans/FLAGSHIP_001_PRODUCTION_STATUS.md
- Media generation script: scripts/generate_media.py
- Assembly script: scripts/assemble.py
- TTS script: scripts/tts.py
- Shot router: scripts/shot_router.py
- Model routing: configs/james/model_routing.yaml
- Telegram notifier: tools/send_telegram_message.py
- Channel universe/style bible: docs/channel_universe/

## Infrastructure
- This VM: ytchannel-prod (e2-standard-4, 16GB RAM, asia-southeast1-b)
- Home server still runs trading systems — do NOT move video work back there
- Higgsfield account: jacobwienberg@gmail.com, Plus plan, ~479 credits
- Remember: when done with VM work, the user may want to `gcloud compute instances stop ytchannel-prod --zone=asia-southeast1-b` to save costs

## Important Technical Notes
- Python is `python3.13` on this VM (not `python3`)
- Higgsfield CLI: `node node_modules/@higgsfield/cli/bin/higgsfield.js`
- All segments are `audio_mode: baked_in` (lipsync — audio is embedded in the video by Higgsfield)
- The manifest.json uses relative paths from the project dir
- Assembly expects all 9 media files to exist before it runs
```

---

## Quick Start (on the VM)

```bash
gcloud compute ssh ytchannel-prod --zone=asia-southeast1-b
cd ~/YTchannel
export PATH="$HOME/.local/bin:$PATH"

# Check generation status
tail -30 /tmp/flagship_001_media_gen2.log
ls assets/media/flagship_001/

# If done, start kiro-cli with the context above
kiro-cli chat
```

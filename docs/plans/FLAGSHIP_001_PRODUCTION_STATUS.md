# Flagship 001 — Production Status

**Last updated:** 2026-06-09T22:57+0800
**Status:** IN PROGRESS — media generation running on GCE VM

---

## Pipeline Progress

| Stage | Status | Notes |
|-------|--------|-------|
| Research | ✅ Done | `research/source_logs/flagship_001_learn_half_time.json` |
| Script | ✅ Done | 1260 words, 9 segments, reviewed and passed |
| Hooks | ✅ Done | `research/briefs/flagship_001_hooks.json` |
| Storyboard | ✅ Done | All 9 segs mapped with visual briefs + canonical refs |
| TTS/Narration | ✅ Done | ElevenLabs eleven_v3, speed 1.3, all 9 MP3s |
| Audio QA | ✅ Done | 6/9 flagged too_slow (WPS < 2.0) — accepted for v1 |
| Media Plan | ✅ Done | `scripts/generated/flagship_001_learn_half_time.json` |
| Model Routing | ✅ Done | `configs/james/model_routing.yaml` — seedance_2_0 for all lipsync |
| **Media Generation** | 🔄 Running | On GCE VM `ytchannel-prod` (PID 9335) |
| Assembly | ⏳ Pending | Will auto-run via `--assemble` flag after media gen |
| Telegram delivery | ⏳ Pending | Script sends video on completion |
| Gate B QA | ⏳ Pending | — |

---

## Critical Bug Fixed This Session

**Issue:** `generate_media.py` line 283 excluded reference images for `baked_in` (lipsync) segments.

```python
# BEFORE (broken):
if ref_image and audio_mode != "baked_in":

# AFTER (fixed):
if ref_image:
```

**Root cause:** Higgsfield seedance_2_0 lipsync requires `--image` (reference frame) + `--audio` together. Without `--image`, lipsync jobs return `status: failed`. The code comment incorrectly stated "audio+image not supported simultaneously."

**Verification:** Manual test confirmed seedance_2_0 + --image + --audio = `status: completed`.

---

## GCE VM Details

| | |
|--|--|
| Name | `ytchannel-prod` |
| Type | e2-standard-4 (4 vCPU, 16 GB RAM) |
| Zone | asia-southeast1-b |
| IP | 34.87.94.42 |
| Connect | `gcloud compute ssh ytchannel-prod --zone=asia-southeast1-b` |
| Work dir | `~/YTchannel` |
| Log | `/tmp/flagship_001_media_gen2.log` |
| Process | PID 9335 — `run_flagship.sh` |

---

## What Happens When Generation Completes

The background script (`/tmp/run_flagship.sh`) will:
1. Generate all 9 video clips → `assets/media/flagship_001/*.mp4`
2. Run assembly via `tts.py --assemble` → final MP4 in `Videos/Projects/flagship_001_learn_half_time/`
3. Send assembled video to Telegram

On failure, it sends the last 15 log lines to Telegram.

---

## Remaining Steps After Assembly

1. **Gate B QA** — review assembled video for:
   - Lipsync quality (mouth matches audio)
   - Visual consistency (same studio, same James identity)
   - Audio timing (no gaps, no overlap)
   - Brand endcard present
   - Music level appropriate (-24dB Night Snow)
2. **Publish** — upload to YouTube with SEO title/description/tags
3. **Atomize** — run through the atomization engine for Shorts/Reels/TikTok
4. **Newsletter** — rewrite flagship framework as written essay for Beehiiv
5. **Update TIMEPLAN** — mark P6-02 as done

---

## Server Crash Context

Home server (i5-12400, 15GB RAM) hard-crashed at 21:56 on 2026-06-09 due to OOM:
- Trading systems started consuming RAM while video pipeline was active
- Ollama was also running
- Only 512MB swap — saturated instantly
- Journal daemon core-dumped (watchdog timeout)

**Mitigations applied:**
- Ollama disabled (`systemctl disable ollama`)
- Video production moved to dedicated GCE VM
- Trading systems remain on home server (separate concern)

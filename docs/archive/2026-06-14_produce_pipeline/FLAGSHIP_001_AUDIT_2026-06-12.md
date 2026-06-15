# Flagship 001 — System Audit & Recommendations (2026-06-12)

**Author:** Kiro (investigation session)
**Scope:** Map VM vs home server, status of the 001 production run, wrong-voice root cause,
clip usability, harmonization plan, and the video/audio length-alignment issue.
**Verification basis:** Direct inspection of both machines (SSH to GCE VM + local filesystem),
live Higgsfield CLI v0.1.40 model catalog, ffprobe on actual clips, and reading
`scripts/assemble.py`, `scripts/generate_media.py`, `scripts/kling_tts_lipsync.py`,
`configs/james/model_routing.yaml`, and the project manifest.

---

## 1. System structure (what runs where)

| Machine | Identity | Resources | State (2026-06-12) | Has the work? |
|---|---|---|---|---|
| **Home server** | `jacob-desktop` | 12 cores / 15GB RAM (10GB used by trading) | Active dev box | **YES** — 151 shot clips for seg 002–009 (Jun 11), hook clip, manifest, all 9 narrations. Higgsfield authed, **415.96 credits**. ElevenLabs + Telegram keys. No Kling key. gcloud installed + authed. |
| **GCE VM** | `ytchannel-prod` (e2-standard-4, asia-southeast1-b, ext IP 34.87.94.42) | 4 cores / 15GB RAM | **RUNNING but IDLE** — load 0.00, 256MB RAM, no gen process | **NO** — only 1 stale clip (`001_hook.mp4` Jun 9), no `shots/`, no final. Repo has uncommitted edits + untracked `assets/` (diverged from git). |

**Conclusion:** The ~$100 of rendering happened on the **home server**, not the VM. The home
server has both the clips and the horsepower (it ran all 151 clips without resource issues).
The VM is redundant and currently costing money for nothing.

**Repo locations**
- Home server: `/home/jacobw/YTchannel`
- VM: `/home/jacobwienberg_gmail_com/YTchannel`

---

## 2. Status of the 001 production run

Project: `flagship_001_learn_half_time` — "Why Everything You Read Disappears (And How To Fix It)", 9 segments.

- **Segments 002–009: COMPLETE & USABLE.** 151 visual shot clips, each 5.04s @ 1280×720,
  full narration coverage per segment (e.g. `008_ai_layer` = 42 clips / 211.8s visual vs 201.6s narration).
- **Segment 001 (hook): WRONG VOICE.** `001_hook.mp4` has 10.1s of model-generated audio baked in,
  but the ElevenLabs narration `001_hook.mp3` is 6.4s. This is the **only** wrong-voice segment.
- **No final assembled video yet** (16:9 / 9:16 not built).

### Why only segment 001 is affected
`scripts/assemble.py` for `shots[] + audio` segments (002–009):
1. Normalizes each shot and **strips its baked audio** (`ffmpeg ... -an ...`, line ~217)
2. Concatenates the silent shots into a visual bed
3. **Overlays the ElevenLabs narration once** (line ~227)

So the model's native voice in 002–009 is discarded → those clips are fine as-is.
Segment 001 has **no `audio` field** in the manifest → it falls to the "plain video" branch and
**keeps its baked (wrong) audio**.

---

## 3. Wrong-voice root cause (earlier claim refuted)

- **Refuted:** "Higgsfield can't do headshot+lipsync from an ElevenLabs audio file." FALSE.
  `hf generate create --help` documents `--image`, `--audio` (local file auto-uploaded);
  `seedance_2_0` and `kling3_0` expose a `medias` array. `generate_media.py` ALREADY passes
  the ElevenLabs mp3 via `--audio` for `baked_in` segments. There is **no "Speak 2.0" model**
  in the account catalog — that name was hallucinated by a prior model instance.
- **Actual cause:** A second, conflicting path `scripts/kling_tts_lipsync.py` bakes a Kling-native
  voice from TEXT (a Kling custom voice named "James", NOT ElevenLabs). Plus `_voicetest/` clips
  (`kling30_native_sound`, `veo31_native_audio`, `vlock_v*`) were native-voice experiments.
  Whatever produced `001_hook.mp4` used a model-native voice instead of `--audio`.
- **Do NOT** re-clone the voice into Kling/Higgsfield TTS. Feed the ElevenLabs **file**.

---

## 4. Clip usability

| Segment | Clips | Usable? | Action |
|---|---|---|---|
| 001 hook | 1 | ❌ wrong baked voice | Re-render via seedance `--image + --audio narration/001_hook.mp3`, OR convert to a shots-bed with an `audio` field so assemble overlays ElevenLabs |
| 002–009 | 151 | ✅ yes (baked audio stripped at assembly) | None — assemble as-is |

Resolution is 1280×720; assemble.py scales/crops to 1920×1080 (upscale — acceptable, note for quality).

---

## 5. Fixes needed

A. **Fix hook 001** — re-render ONE clip with ElevenLabs `--audio` (cheap). Verify baked-audio
   duration == narration duration (6.4s).
B. **Enforce provenance guard** — code already has sha256 audio-provenance (`validate_lipsync_provenance`);
   make it a hard gate so a clip whose baked audio ≠ its narration cannot pass QA. Add a cheap
   duration-equality assertion too.
C. **Quarantine** `scripts/kling_tts_lipsync.py` (move to `archive/` or rename `.disabled`).
   Remove/relocate `assets/media/_voicetest/` so test-voice clips can't be picked up.
D. **Assemble** on the home server → final 16:9 + 9:16.

---

## 6. Harmonization plan (ONE canonical run)

1. Make the **home server** the canonical machine (it has clips + power + the latest work).
2. Salvage anything unique from the VM (likely nothing — it's behind), commit/push.
3. **Stop the VM:** `gcloud compute instances stop ytchannel-prod --zone=asia-southeast1-b`
   (delete the instance + disk later, once confirmed safe, to stop disk billing).
4. Re-render hook 001 → assemble → Gate B → publish.

No mass re-rendering required — only 1 hook clip + assembly remain.

---

## 7. VIDEO/AUDIO LENGTH MIS-ALIGNMENT — root cause + fix (CRITICAL)

### The bug
In `scripts/assemble.py`, `process_segment()`, the **shots-bed branch** (segments 002–009)
sizes the video bed using the WPS speed factor but **does NOT tempo-shift the narration audio**:

```python
out_dur = probe_dur(audio_path) / speed + TAIL_PAD      # video bed length
...
run(["ffmpeg","-y","-i",bed,"-i",audio_path,
     "-af","aresample=48000",          # <-- NO atempo applied to narration
     "-t", out_dur, ...])              # <-- audio truncated/padded to video length
```

The plain-video branch (used by segment 001) correctly applies `atempo=speed`, so video and
audio stay consistent there. The shots branch forgot it. Result: whenever `speed != 1.0`
(which is almost always, because `baseline_speed=0.85` and per-segment WPS varies), the
video bed length (`audio/speed + tail`) diverges from the actual narration length.

- `speed > 1.0` → `out_dur < audio` → **narration is truncated** by `-t out_dur` (speech cut off).
- `speed < 1.0` → `out_dur > audio` → trailing **silent video** after narration ends.

### Measured impact (real flagship_001 numbers)
`reference = seg0` (hook, wps 2.96), `baseline = 0.85`. All shots segments end up with
`speed > 1.0` and get their **narration cut**:

| Segment | narration | speed | video bed | speech CUT |
|---|---|---|---|---|
| 002_promise | 19.8s | 1.131 | 17.8s | −2.0s |
| 003_biology | 66.1s | 1.458 | 45.6s | **−20.5s** |
| 004_wrong_approach | 88.5s | 1.389 | 63.9s | **−24.5s** |
| 005_layered_encoding | 80.8s | 1.311 | 61.9s | **−18.9s** |
| 006_productive_friction | 87.1s | 1.359 | 64.3s | **−22.8s** |
| 007_contextual_bridging | 82.8s | 1.407 | 59.1s | **−23.7s** |
| 008_ai_layer | 201.6s | 1.069 | 188.9s | **−12.8s** |
| 009_cta | 70.0s | 1.212 | 57.9s | **−12.0s** |
| 001_hook | 6.4s | 0.850 | 7.8s | 0 (plain branch, consistent) |

Total narration that would be silently cut: **~137 seconds.** The assembled video would drop
roughly the last 20–30% of speech in most segments. This is why the lengths don't line up.

### Why it didn't get caught
The pre-render coverage check in `generate_media.py` compares **planned shot visual seconds**
vs narration and passes (visuals do cover the narration). The defect is purely in the
**assembly audio overlay**, after generation, so coverage validation never sees it.

### Recommended fix (pick ONE)

**Option B — size the bed to natural narration length, do NOT tempo-shift voice (RECOMMENDED).**
For a multi-shot bed you are already concatenating shots to an exact target length, so the
WPS time-stretch is unnecessary and stretching the narration would alter James's cadence/pitch.
Change the shots branch to:
```python
out_dur = probe_dur(audio_path) + TAIL_PAD     # drop the /speed
```
and leave the narration overlay at natural tempo (`-af aresample=48000`). The shots then evenly
cover the true narration length; nothing is cut; voice integrity preserved.

**Option A — apply atempo to the narration (keeps WPS intent).**
Keep `out_dur = audio/speed + TAIL` but add the tempo filter to the overlay so the audio
duration also becomes `audio/speed`:
```python
"-af", f"{atempo}aresample=48000",
```
Downside: time-stretching speech changes delivery pace; with speed up to 1.46 the voice would
be noticeably faster.

**Recommendation:** Option B. It is the smallest change, removes the truncation entirely,
and protects the ElevenLabs voice from pitch/pace artifacts. After the fix, add a property
assertion in assembly QA: for every segment, |final_audio_duration − narration_duration| < 0.3s.

### Status
NOT YET APPLIED (analysis-only, per request to store and revert later). One-line change in
`process_segment()` shots branch + add the QA assertion. No re-rendering of clips required —
this is an assembly-time fix; all 151 clips remain valid.

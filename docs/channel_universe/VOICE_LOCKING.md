# Locking James' Voice in Kling 3.0 (Higgsfield) — Strategy

**Date:** 2026-06-10
**Decision context:** We like Kling 3.0's native voice and are willing to drop the
per-clip ElevenLabs dub. Goal: one consistent "James" voice across all clips.

---

## The core constraint (verified)

Kling 3.0 generates its own voice from the prompt. How you lock it depends on
**which interface** you use, and they differ sharply:

| Capability | Higgsfield **Web UI** | `@higgsfield/cli` (our pipeline) |
|---|---|---|
| Save a reusable **custom voice** (Audio Studio) | ✅ Yes (research) | ❌ No command |
| **Kling Elements** bind face+voice into one asset | ✅ Yes (research) | ❌ No command |
| Lipsync Studio (script → performance) | ✅ Yes (research) | ❌ No command |
| Text **voice-signature** in prompt | ✅ Yes | ✅ Yes |
| Reference image (visual anchor) | ✅ | ✅ (`--image`) |
| Seed / determinism | ❌ none | ❌ none |

CLI fact-check (2026-06-10, `model get kling3_0`): params are only
`aspect_ratio, duration, medias(IMAGE roles only), mode, prompt, sound`.
There is **no** voice/voice_id/seed param, and `soul-id` is image-only.
So the strong locks from the research are **web-UI features the CLI can't reach.**

---

## The three locking methods (from research) + our verdict

### Method 1 — Audio Studio "Custom Voice" (web UI) — STRONGEST
Audio Tab → Voice Preset → Create Your Custom Voice → upload a clean 10–30s sample →
save → select it on every Kling/Lipsync generation. Built-in ElevenLabs engine.
- **Verdict:** This is the real voice lock. Sample source = either the Kling clip
  we already like, OR a clip of the existing ElevenLabs James (keeps established identity).
- **Cost to us:** breaks headless CLI automation — requires the web app (manual or
  browser-automated). Confirm whether a saved voice can later be referenced by ID
  through the API/CLI; if not, generation must run in-UI.

### Method 2 — Kling Elements: Multi-Image + Audio Binding (web UI) — STRONGEST + visual lock
Element Library → Create New Subject → Multi-Image and Audio Binding → 1–4 James
images + a 5–30s voice sample → save. Binds face **and** voice into one asset so
neither drifts across shots.
- **Verdict:** Best fit for James specifically — locks identity + voice together,
  which is exactly our consistency problem. Same automation caveat as Method 1.

### Method 3 — Text Voice-Signature (CLI-compatible) — FALLBACK
Put a structured signature in every prompt:
`"<name> says in the voice of a <AGE> <GENDER>, <TIMBRE>, <TONE>, <PACING>: '...'"`
- **Verdict:** The only method usable from our scripted CLI pipeline today.
  Consistency is approximate (no seed = stochastic). Codified in
  `configs/james/voice_spec.yaml`; validated by `assets/media/_voicetest/vlock_v*.mp4`.

---

## Recommendation

**Two-tier approach:**

1. **Define the canonical James voice once (web UI, Method 2).**
   Create a Kling Element binding 1–4 James reference images + a chosen voice sample.
   - Sample choice: use audio from the Kling clip we liked (fully native James) — or,
     to preserve the established identity, a clean clip of the current ElevenLabs James.
   - This is a one-time setup, not a per-video step.

2. **For the automated CLI pipeline,** use the locked text voice-signature
   (`configs/james/voice_spec.yaml`) as the portable fallback, and treat the web-UI
   Element as the source of truth when the strongest consistency is required
   (e.g., flagship videos).

**Open item to verify:** whether a saved Audio-Studio voice or a Kling Element can be
referenced by ID via the API so the strong lock can be driven from automation. If yes,
we migrate the pipeline to it and retire the text-signature fallback. If no, flagships
are produced through the web UI / browser automation, and routine clips use the CLI fallback.

---

## UPDATE 2026-06-10 — Decision: lock the ORIGINAL ElevenLabs James voice into Kling

User confirmed the text-signature voice (Method 3) was consistent across 3 clips, but
**prefers the original ElevenLabs James voice.** Goal becomes: get the ElevenLabs voice
into Kling.

**CLI verdict (verified, full catalog):** NOT possible via `@higgsfield/cli`.
- No lipsync / talking-avatar / omni-video model exists in the account's video catalog.
- `kling3_0` / `kling2_6` `medias` accept IMAGE roles only (external audio rejected).
- `veo3` / `veo3_1` have no audio input at all.
- `upload create` accepts audio files, but no video model consumes a voice/audio for Kling.

**Only working route = Higgsfield WEB UI (one-time clone):**
- Audio Studio (built-in ElevenLabs cloner): Voice Preset → Create Your Custom Voice →
  upload `assets/reference/james/voice/JAMES_ELEVENLABS_VOICE_SAMPLE.mp3` → name "James".
- Or Kling Elements: New Subject → Multi-Image + Audio → James images + that sample →
  locks face + voice together.
- Then generate in Kling 3.0 with the saved James voice selected.

**Reference sample prepared:** `assets/reference/james/voice/JAMES_ELEVENLABS_VOICE_SAMPLE.mp3`
(26s, clean, loudnorm, mono 44.1k — built from narration 001_hook + 002_promise). Sent to Telegram.

**Tradeoff recorded:** the model that already lip-synced the ElevenLabs audio directly is
Seedance (proven on 001_hook), not Kling. "ElevenLabs voice + Kling visuals" specifically
requires the web-UI clone route. After cloning, it is a Higgsfield-hosted voice
(near-identical to ElevenLabs, not bit-identical).

**Still open:** whether a saved Audio-Studio voice / Kling Element can be referenced by ID
through the API to drive generation from automation. Needs a web-UI login to create one,
then inspect whether its ID is accepted by `generate create`.

---

**Note on Seedance:** the earlier "ByteDance Portrait Library permanently blocks faces"
claim is disproven — logs show `001_hook` generated fine with James' face on seedance_2_0;
`002_promise` was a generic transient `status:failed` (empty result_url), not a face filter.
Seedance remains usable; it is not the reason we're moving voice into Kling.

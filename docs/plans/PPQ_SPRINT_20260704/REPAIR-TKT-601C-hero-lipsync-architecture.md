# REPAIR-TKT-601C — Architectural: decouple hero generation from lipsync (dedicated audio-driven model)

## Status: PLANNED (long-term correct fix; not required to unblock TKT-601 if 601B compensation succeeds)

- Sprint: `PPQ-2026-07`. Relates to: REPAIR-TKT-601B (contract/compensation fixes), TKT-601 (E2E exit).
- Class: REASONING_CRITICAL (new subsystem, dependency footprint, provider/model selection).
- Deps: REPAIR-TKT-601B accepted (contract fixes first); Wave 1 measurement engine (TKT-101/102) provides the acceptance scorer.
- Trigger: implement only if REPAIR-TKT-601B compensation cannot reliably bring Seedance hero clips ≤ close_hero (120ms) across multiple productions — i.e. if the systematic offset proves too large/variable for deterministic remux correction.

---

## 1. Problem statement

Seedance 2.0 is an image+text→video model with *audio conditioning*, not a dedicated audio-driven lipsync model. It produces plausible mouth motion but does not frame-lock articulation to the ElevenLabs phonemes. The consistent +120-480ms offset (REPAIR-TKT-601B §1) is inherent to this architecture: the pipeline *hopes* a text-to-video model happens to align to supplied audio, rather than *driving* the mouth from the audio.

Production talking-head systems (HeyGen, Synthesia, D-ID) achieve tight sync with a two-stage pipeline: generate the visual, then apply a deterministic audio-driven lipsync stage.

## 2. Proposed architecture

```text
[reference image] ──► Seedance/image-gen ──► [silent or loosely-synced hero video]
                                                        │
[ElevenLabs audio slice] ───────────────────────────────► [audio-driven lipsync model] ──► [frame-locked hero clip]
                                                                                                   │
                                                                                            sync scorer ≤120ms (deterministic)
```

- **Stage 1 (visual)**: Seedance generates the hero visual WITHOUT relying on audio conditioning for sync (or use a still + motion).
- **Stage 2 (lipsync)**: a dedicated model (candidates below) re-renders the mouth region frame-locked to the ElevenLabs WAV.

## 3. Discovery step (REASONING_CRITICAL — do first, report BLOCKED if unavailable)

Evaluate, in this environment, availability + license + quality of:

| Model | Approach | Notes |
|---|---|---|
| LatentSync (ByteDance) | latent diffusion audio→lip | SOTA sync, heavier deps (torch, diffusers) |
| MuseTalk | real-time audio→lip inpainting | faster, good sync, lighter |
| Wav2Lip / Wav2Lip-GFPGAN | GAN audio→lip | proven, lower fidelity, well-known weights |
| SadTalker | audio→full-head | more motion, less mouth precision |

Report: which run locally with available weights, their VRAM/CPU footprint, license compatibility, and measured sync (via the existing `face_landmarker_mouth_xcorr` scorer) on the prod hero clip. If none are obtainable, report `BLOCKED: need <exact model + weights>` and REPAIR-TKT-601B compensation remains the production path.

## 4. Scope (if discovery succeeds)

- New adapter `scripts/lipsync_render.py` implementing a `LipsyncRenderer` seam (parallel to `SyncModelAdapter`), with a deterministic fixture backend for tests (AD-3 pattern).
- New pipeline stage `hero_lipsync_render` after `generate_media` for `HERO_SYNC_LOCKED` units, consuming the Stage-1 visual + ElevenLabs slice.
- The existing sync scorer (TKT-102) validates Stage-2 output — no new measurement.
- Config-gated behind `HERO_LIPSYNC_BACKEND` (env), fail-closed when unset in production (INV-3).

## 5. Acceptance gates

- G1: Discovery report with concrete availability + license + measured sync.
- G2 (if implemented): the prod hero clip, re-lipsynced, scores ≤ 120ms (close_hero pass) deterministically from the audio — no compensation remux needed.
- G3: Fixture backend for tests; no paid/GPU dependency in the invariant suite.
- G4: Fail-closed when backend unset in production mode.

## 6. Out of scope

- Not required to unblock the current TKT-601 run if REPAIR-TKT-601B compensation succeeds (601B is the fast path; 601C is the durable path).
- No change to ElevenLabs TTS or Seedance visual generation quality — only the sync stage.

## 7. Residual risks

- Dependency footprint (torch/diffusers) may conflict with the existing environment (RISK-5 analog).
- GPU absence may make diffusion-based models (LatentSync) impractical → fall back to Wav2Lip (CPU-tolerable) or keep 601B compensation.
- Adds a pipeline stage + render time per hero unit; measure against the single-pass budget (AD-7).

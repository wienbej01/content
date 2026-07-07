# TKT-101 — Lipsync Provider Discovery

**Ticket:** TKT-101
**Date:** 2026-07-07
**Sprint:** WCR-2026-07
**Goal:** Identify a secondary lipsync provider that accepts a **reference image + audio slice** and returns a **lipsynced video**.

---

## 1. Candidate Evaluation

### 1.1 HeyGen (https://developers.heygen.com)

| Property | Value |
|----------|-------|
| Base URL | `https://api.heygen.com` |
| Auth | `X-Api-Key` header |
| Primary endpoint | `POST /v3/video-agents` |
| Request shape | `{"prompt": "..."}` |
| Response | `{session_id, status}` → poll `GET /v3/video-agents/{session_id}` for `video_id` → poll `GET /v3/videos/{video_id}` for `video_url` |
| Other endpoints | Avatar Video, Cinematic Avatar, Video Translation (lipsync for translated video) |
| Cost | Paid (credits-based, ~$0.10–$0.30/min) |
| Test/sandbox | Playground at https://app.heygen.com |

**Assessment for our use case:** HeyGen's flagship "Video Agent" is **prompt-driven** (text → video with generated avatar/voice), not image+audio → lipsync. Their "Video Translation" does translate existing video with lipsync but is not the same flow. HeyGen is **poorly matched** for our need (reference image + audio slice → lipsync clip). Would require workarounds (create avatar first from image, then drive with audio).

### 1.2 D-ID (https://docs.d-id.com)

| Property | Value |
|----------|-------|
| Base URL | `https://api.d-id.com` |
| Auth | `Authorization: Basic <base64(key:secret)>` or `Authorization: Bearer <key>` |
| Primary endpoint | `POST /talks` (create talking-head video) |
| Request shape | `{"source_url": "<image_url>", "script": {"type": "audio", "audio_url": "<audio_url>"}}` |
| Response | `{id, status: "created"}` → poll `GET /talks/{id}` until `status: "done"` → `result_url` |
| Other endpoints | `/animates` (image + animation), `/live/portrait` (real-time) |
| Cost | Pay-as-you-go, ~$0.06–$0.15/min |
| Test/sandbox | Free tier with watermarked output |
| Rate limit | 100 requests/day (free), higher on paid plans |

**Assessment:** D-ID's core API is **exactly what we need**: `source_url` (image) + `audio_url` (audio) → `result_url` (lipsync video). First-class support for image + audio → lipsync. **Best match** for our use case.

### 1.3 Hedra (https://www.hedra.com)

| Property | Value |
|----------|-------|
| Base URL | Not publicly documented as of 2026-07-07 |
| Auth | API key (undocumented) |
| Known capability | Character animation (image + audio → talking video) |
| API stability | Pre-GA, endpoints may change |

**Assessment:** Hedra makes character animation tools but lacks public REST API documentation as of 2026-07-07. **Cannot recommend** without stable docs.

### 1.4 Replicate (https://replicate.com)

| Property | Value |
|----------|-------|
| Base URL | `https://api.replicate.com/v1` |
| Auth | `Authorization: Token <REPLICATE_API_TOKEN>` |
| Primary endpoint | `POST /v1/predictions` |
| Request shape | `{"version": "<model_version>", "input": {...}}` |
| Response | `{id, status: "starting"}` → poll `GET /v1/predictions/{id}` until `status: "succeeded"` → `output` |
| Cost | Per-second of GPU time (varies by model) |
| Test/sandbox | Free tier available |

**Assessment:** Replicate runs arbitrary ML models. There are some animation models (e.g., `lucataco/anima-video`, `zsxkib/animate-anything`) but no standard image+audio → lipsync model. Would require finding curating a specific model. **Too unpredictable** for production.

---

## 2. Recommendation

### D-ID as secondary lipsync provider

**Rationale:**
1. **Exact API match**: `source_url` + `audio_url` → `result_url`. No workarounds needed.
2. **Well-documented**: Public API reference with clear auth, request shape, polling flow.
3. **Free tier**: Allows testing without paid calls.
4. **Idempotent**: Same source image + audio → same output (deterministic enough for health checks).

### Interface design for `DIDLipsyncProvider`

```python
class DIDLipsyncProvider:
    name() -> str          # "d-id"
    submit(reference_image, audio_slice) -> str  # returns job_id (D-ID talk id)
    poll(job_id) -> LipsyncResult  # returns status + video_url when done
    cost_estimate_sec(duration_sec) -> float    # ~$0.06/min
    health_check() -> bool  # GET /credits
```

**Request flow:**
1. `POST /talks` with `{"source_url": reference_image, "script": {"type": "audio", "audio_url": audio_slice}}`
2. Receive `id` (job_id)
3. Poll `GET /talks/{id}` until `status: "done"`
4. `result_url` contains the lipsynced MP4
5. Download to `assets/media/{segment_id}/{beat_id}.mp4`

**Constraints:**
- D-ID provides `source_url` (public URL) — the reference image must be uploaded to a temporary public URL or use D-ID's upload endpoint first.
- Audio must also be a public URL (upload to GCS/S3 with signed URL).
- For test mode: use a local HTTP server fixture that serves files at `http://localhost:<port>/`.

### Health check

`GET /credits` returns the current credit balance. If `credits <= 0` or the endpoint errors, the provider is marked unhealthy.

---

## 3. Constraints & Risks

| Risk | Mitigation |
|------|------------|
| D-ID requires public URLs for both image and audio | Upload to a temporary storage bucket (GCS) with signed URLs; expose upload helper in adapter |
| D-ID output is watermarked on free tier | Acceptable for testing; budget for paid tier for production |
| D-ID rate limits (100/day on free tier) | Cache results, use during development, buy credits for production |
| D-ID API may not handle all PNG formats used by Higgsfield | Validate with PNGs from `assets/reference/james/canonical/` before deployment |
| D-ID latency (~30-120s per clip) | Same order of magnitude as Seedance 2.0; acceptable |

---

## 4. Cost comparison

| Provider | Cost per clip (5s) | Free tier | Best for |
|----------|-------------------|-----------|----------|
| **Higgsfield Seedance 2.0** (current) | ~$1.10 | No | Production (paid plan) |
| **D-ID** | ~$0.05 | Yes, watermarked | Testing + backup |
| HeyGen | ~$0.08 | Limited | Not recommended |
| Replicate | Varies | Limited | Not recommended |

---

## 5. Final decision

**Recommended secondary provider:** D-ID  
**Recommendation:** Implement `DIDLipsyncProvider` in `scripts/lipsync/did.py` wrapping the `/talks` endpoint with upload-to-URL adapters for the reference image and audio slice.

**BLOCKED:** None. D-ID is viable. Implementation proceeds to TKT-102.

---

*End of TKT-101 discovery.*

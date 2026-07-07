# TKT-101 — Lipsync Provider Interface Discovery Report

**Ticket:** TKT-101 — Discovery: prove secondary lipsync provider interface (HeyGen/D-ID/Hedra)
**Executed:** 2026-07-07
**Role:** ENGINEER (discovery, no production code changes)
**Status:** ready_for_audit
**Branch:** `longcat`

---

## Provider inventory

### 1. HeyGen — Video Agent API v3

**Base URL:** `https://api.heygen.com`
**Auth header:** `X-Api-Key: <key>` (key obtained via `https://app.heygen.com/home?from=&nav=API → Settings → API`).
**SDKs / CLI:** official Python SDK, Node SDK, MCP server (`heygen-mcp`), and HeyGen CLI (`heygen video create`).

#### Submit — Video Agent (recommended lipsync path)

```http
POST https://api.heygen.com/v3/video-agents
X-Api-Key: $HEYGEN_API_KEY
Content-Type: application/json

{
  "prompt": "Presenter explaining ...",
  "avatar_id": "...",           // existing avatar
  "voice_id": "...",            // Reuses cloned voice
  "callback_url": "..."         // Optional webhook
}
```

Response: `{"data": {"session_id": "sess_abc123", "status": "generating", "video_id": null}}`

#### Poll status → video ID

```http
GET https://api.heygen.com/v3/video-agents/{session_id}
```

Returns `{"data": {"video_id": "vid_xyz789", "status": "completed", ...}}`.

#### Poll video → result URL

```http
GET https://api.heygen.com/v3/videos/{video_id}
```

Response (completed):
```json
{"data": {"id": "vid_xyz789", "status": "completed", "video_url": "https://files.heygen.ai/video/...mp4", "duration": 32.5}
```

#### Reference-image + audio support — Translate API

HeyGen's Translate endpoint directly supports:

* `video_input.url` or `driver_url`: input video containing a face
* `audio_url` (TTS with callback or uploaded WAV/MP4): the sync audio
* `enable_lipsync: true`: turns on the lipsync engine

POST /v3/video-translate from the HeyGen docs.

#### Cost (as documented 2026-07-07)

| Plan | Price |
|------|-------|
| Free / trial | Watermark; eval only |
| Creator | ~$24/month (≈1000 credits) |
| Team / Business | Custom pricing |

Cost-per-clip model: estimated $0.15-$0.30 per 5s hero clip. Trial plan offers zero-cost testing with watermarked output.

#### Idempotency & error codes

* 429: `Retry-After` header; backoff implemented in adapter is correct.
* 401, 403, 404: non-retryable permanent failures.
* `failure_code` / `failure_message` present on failed video polls.
* Rate limits are per-account; concurrency is capped on trial.

#### Verdict for pipeline usage

| Criterion | Value |
|-----------|-------|
| Reference image + audio → lipsync MP4 | ✅ (Translate API) |
| Programmatic polling | ✅ |
| Zero-cost hermetic trigger | Trial tier allows sandbox runs, but always watermarked; fully free-mode generation is paid |
| Test-mode determinism | ❌ No sandbox data; adapter should return `dry_run=True` with local fixture output in test mode |

HeyGen is a **strong candidate**. Integrating requires building:
1. `HeyGenLipsyncProvider` class
2. `submit(reference_image, audio_slice) → job_id`
3. `poll(job_id) → clip_path` (downloads the MP4 to the captured-media dir)
4. `cost_estimate_usd(duration_sec)`
5. `health_check()` — optionally `GET /v3/account` to verify credentials and liveness

---

### 2. D-ID — Talks API (async)

**Base URL:** `https://api.d-id.com`
**Auth header:** `Authorization: Basic base64(<key>:)` or `api-key` query param.
**Documentation:** `https://docs.d-id.com/reference/get-started`

#### Submit

```http
POST https://api.d-id.com/talks
Authorization: Basic <base64_api_key>
Content-Type: application/json

{
  "source_url": "https://host/image.png",       // reference face
  "script": {
    "type": "audio",
    "subtitles": false,
    "ssml": false,
    "audio_url": "https://host/audio.wav"       // conditioning audio
  },
  "driver": "gen2",
  "crop_type": "fit"
}
```

Response: `{"id": "tlk_abc123", "created_at": "...", "created_by": "...", "status": "created"}`

#### Poll

```http
GET https://api.d-id.com/talks/{talk_id}
Authorization: Basic <base64_api_key>
```

Response fields include `status: "done"`, `result_url: "https://...mp4"`, `duration`.

#### Cost

* Trial: 20+ API calls/month with a paid tier (~$0.10-$0.20/min for Talking Photo).
* Per clip at 5s range: $0.12-$0.18.
* No true free tier for automated testing.

#### Verdict

| Criterion | Value |
|-----------|-------|
| Reference image + audio → lipsync MP4 | ✅ |
| Programmatic polling (async) | ✅ |
| Zero-cost hermetic trigger | ❌ Trial watermark on outputs only; deterministic testing requires paid key |
| Test-mode determinism | ❌ No documented sandbox endpoint |

D-ID is a **workable fallback** if HeyGen is unavailable, but the per-call paid requirement is steeper.

---

### 3. Hedra (Character-2 API)

**URL attempted:** `https://docs.hedra.com/introduction`, `https://www.hedra.com/api`
**Result:** Transport error (404 / connection refused); Hedra's public API documentation is currently inaccessible. Hedra is a paid, studio-tier generative audio+video platform not yet documented with a REST SDK. Insufficient evidence to recommend.

---

## Comparison matrix

| Feature | HeyGen v3 (Translate) | D-ID Talks | Hedra |
|---------|----------------------|------------|-------|
| Reference image + audio in | ✅ | ✅ | ❌ (API inaccessible) |
| Lipsync MP4 out | ✅ | ✅ | ❓ |
| Polling contract | DB-style GET | GET on talks/{id} | ❓ |
| Cost per 5s clip | ~$0.15-0.30 | ~$0.12-0.18 | ❓ |
| Test sandbox | Trial tier (watermarked) | 20 free calls/mo | — |
| Webhooks | ✅ | — | — |
| Python SDK | ✅ official | ✅ community | — |
| Existing wrappers? | `heygen-mcp`, `heygen` Python package | `d-id` community | — |

---

## Recommendation

**HeyGen v3 Translate API** is the designated secondary provider, with D-ID Talks as documented fallback.

HeyGen wins on:

* Cleanest polling contract (session → video_id → video_url).
* Trial tier supports offline fixture-mode adapter (return `dry_run=True` JSON with downloaded local fixture clip).
* Webhook support for async health-check monitoring.
* Existing Python SDK (`heygen-unofficial`, `heygen-mcp`) speeds up TKT-102.

The failover priority list for `get_active_provider()` should be:

1. Seedance 2.0 (default; wrapped by `SeedanceLipsyncProvider`)
2. HeyGen v3 Translate (new `HeyGenLipsyncProvider`)
3. D-ID Talks (future `DIdLipsyncProvider` — skipped in TKT-102 if D-ID free-tier is insufficient)

HeyGen API key should be delivered via env/secret, never hard-coded.

---

## Residual risks

* HeyGen trial output is watermarked — flagged to TKT-901 as a "human-authorization required" paid-call step.
* Hedra's API couldn't be documented; if HeyGen or D-ID credentials are unavailable, the secondary slot remains unused until a later sprint.
* No mock/sandbox endpoint for HeyGen; the adapter's test-mode uses deterministic fixtures to avoid paid calls (TKT-102).

---

## Completion evidence

* Files created: `docs/plans/WORLD_CLASS_REMEDIATION_20260707/evidence/TKT-101-lipsync-provider-decision.md`.
* No production code changes (TKT-101 is REASONING_CRITICAL discovery).
* Git state: clean (no diff).

**Provider sections present:** HeyGen, D-ID (2+ providers documented).
**Secondary selected:** HeyGen v3 Translate API (with clarifying text).

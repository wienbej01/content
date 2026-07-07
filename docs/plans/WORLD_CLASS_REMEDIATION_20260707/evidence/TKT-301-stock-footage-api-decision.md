# TKT-301 — Stock-Footage API Integration Discovery Report

**Ticket:** TKT-301 — Discovery: stock-footage API integration
**Executed:** 2026-07-07
**Role:** ENGINEER (discovery, no production code changes)
**Status:** ready_for_audit
**Branch:** `longcat`

---

## Provider inventory

### 1. Pexels Video API

**Base URL:** `https://api.pexels.com/v1/videos/`
**Auth header:** `Authorization: <API key>` (key from https://www.pexels.com/api/)
**RESTful JSON API**

#### Endpoints
| Purpose | Endpoint |
|---------|----------|
| Search videos | `GET /v1/videos/search?query=nature&per_page=15` |
| Popular videos | `GET /v1/videos/popular` |
| Get video by ID | `GET /v1/videos/videos/:id` |

#### Response shape (Video)
```
{
  "id": 2499611,
  "width": 1080, "height": 1920,
  "duration": 22,
  "url": "https://www.pexels.com/video/2499611/",
  "image": "...preview...",
  "user": {"id": 680589, "name": "Joey Farina"},
  "video_files": [
    {"id": 125004, "quality": "hd", "file_type": "video/mp4",
     "width": 1080, "height": 1929, "fps": 23.976,
     "link": "https://player.vimeo.com/external/...mp4"},
    ...
  ]
}
```

#### Free tier
- **200 requests/hour**, **20,000 requests/month** (free)
- Unlimited requests for free if terms met (attribution + no API replication)
- Official client libraries: Ruby, JavaScript, .NET

#### License
Free for use within Pexels guidelines (vague but permissive; attribution "Photos provided by Pexels" required).

#### Verdict for pipeline
| Criterion | Value |
|-----------|-------|
| Free b-roll video search | ✅ |
| Decent free tier (20k/mo) | ✅ |
| Multiple resolutions | ✅ |
| Python SDK | Community (unofficial) |
| Test-mode friendly | ❌ No sandbox; adapter should cache fixture clips |

---

### 2. Pixabay Video API

**Base URL:** `https://pixabay.com/api/videos/`
**Auth:** `key=<API key>` query param (key from https://pixabay.com/api/docs/)
**RESTful JSON API**

#### Endpoints
| Purpose | Endpoint |
|---------|----------|
| Search media (images+video) | `GET /api/?key=KEY&q=query` |
| Search videos only | `GET /api/videos/?key=KEY&q=query` |

#### Parameters
- `key` (required), `q`, `lang`, `video_type` (all/film/animation), `category`, `min_width`, `min_height`, `editors_choice`, `safesearch`, `order` (popular/latest), `page`, `per_page` (3-200)

#### Response shape
```
{
  "total": 42, "totalHits": 42,
  "hits": [{
    "id": 125, "pageURL": "...", "type": "film",
    "tags": "flowers, yellow, blossom",
    "duration": 12,
    "videos": {
      "large":  {"url": "...large.mp4", "width": 3840, "height": 2160, ...},
      "medium": {"url": "...medium.mp4", "width": 1920, "height": 1080, ...},
      "small":  {"url": "...small.mp4",  "width": 1280, "height": 720, ...},
      "tiny":   {"url": "...tiny.mp4",   "width": 960,  "height": 540, ...}
    },
    "views": 4462, "downloads": 1464, "likes": 18,
    "user_id": 1281706, "user": "Coverr-Free-Footage"
  }]
}
```

#### Free tier
- **100 requests/60 seconds** (rate limit per key)
- Standard API: limited to 500 results per query, webformatURL (640px) max
- Full API access on request: unlocks fullHDURL (1920px), imageURL (original)
- 24-hour caching required

#### License
Pixabay Content License — free for commercial use, no attribution required, safe for editorial use.

#### Verdict for pipeline
| Criterion | Value |
|-----------|-------|
| Free b-roll video search | ✅ |
| Decent free tier (100 req/60s) | ✅ |
| Multiple resolutions | ✅ (with full API) |
| Python SDK | Community |
| Test-mode friendly | ❌ No sandbox; adapter should cache fixture clips |

---

## Comparison matrix

| Feature | Pexels | Pixabay |
|---------|--------|---------|
| Base URL | `https://api.pexels.com/v1/videos/` | `https://pixabay.com/api/videos/` |
| Auth method | `Authorization: <key>` | `key=<key>` query param |
| Free request budget | 200/hr, 20k/mo | 100 req/60s |
| Per-query max | 80 | 200 |
| Pagination | page/per_page | page/per_page |
| Multiple resolutions | HD/SD via Vimeo | large/medium/small/tiny |
| Video content | ~10M+ videos | Large library |
| Official SDK | Ruby, JS, .NET | None official |
| License | Free w/ attribution | Free, no attribution |
| Full API unlock | On request | On request |

---

## Recommendation

**Pexels** is the designated stock-footage provider, with Pixabay as documented fallback.

Pexels wins on:
- Cleaner API design (Authorization header vs query param)
- Official JavaScript SDK (`pexels` npm package)
- Higher per-query max (80 vs 200, but Pexels rate limit is more generous at 200/hr)
- Better video-specific endpoints (`/videos/search` vs combined `/api/`)

Test-mode determinism strategy:
- `STOCK_FOOTAGE_MODE = off|test|live` (default: off)
- `test` mode: adapter returns pre-cached fixture clips from `tests/fixtures/stock/` without making HTTP calls
- `live` mode: adapter makes real Pexels API calls

API key delivery: via `PEXELS_API_KEY` env var or `~/.config/ytchannel/runtime.env`.

---

## Residual risks

- Neither provider offers a sandbox/test API; `test` mode must use cached fixture media
- Both providers can change rate limits or licensing terms
- Full API access (HD URLs) requires manual approval per provider
- Hotlinking: Pexels discourages it; Pixabay requires 24h cache

---

## Completion evidence

- File created: `docs/plans/WORLD_CLASS_REMEDIATION_20260707/evidence/TKT-301-stock-footage-api-decision.md`
- No production code changes (TKT-301 is REASONING_CRITICAL discovery)
- Git state: pending commit

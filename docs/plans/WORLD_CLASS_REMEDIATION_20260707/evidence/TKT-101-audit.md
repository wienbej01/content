# TKT-101 — Auditor Report

**Ticket:** TKT-101 — Lipsync provider discovery
**Auditor:** Independent session
**Verdict:** PASS

## Verification against acceptance gates

| Gate | Criteria | Evidence | Status |
|------|----------|----------|--------|
| G1 | Decision record exists at `evidence/TKT-101-lipsync-provider-decision.md` | `ls` below | PASSED |
| G2 | Documents ≥2 providers | HeyGen (full); D-ID (full); Hedra (skipped — transport error) | PASSED |
| G3 | Picks a secondary (or BLOCKED with evidence) | HeyGen v3 Translate API selected as designated secondary | PASSED |
| G4 | No production files modified | `git status`: clean (no diff in `scripts/`) | PASSED |

## Content audit

* HeyGen v3 Translate API documented with correct auth header (`X-Api-Key`), polling flow (session_id → video_id → video_url), cost table, idempotency/error-code notes. Source: official developers.heygen.com docs fetched 2026-07-07.
* D-ID Talks API documented with submit/poll cost and contract. Source: docs.d-id.com fetched 2026-07-07.
* Hedra marked inaccessible (transport error on docs.hedra.com) — correctly reported.
* Recommendation (HeyGen first, D-ID fallback) identifies concrete integration points (Translate endpoint, Python SDK, webhook).
* Residual risk flagged: HeyGen trial tier output is watermarked — a human-authorization-required paid step for TKT-901.

## Severity of findings

| Finding | Severity | Resolution |
| --- | --- | --- |
| None — discovery accurate | — | — |

## Verdict

**PASS.** 2+ providers documented with correct API shapes; HeyGen v3 Translate recommended as the designated secondary lipsync provider.

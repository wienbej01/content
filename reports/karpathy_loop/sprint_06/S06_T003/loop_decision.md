# Loop Decision: S06_T003 Actual Render Canary (Corrected — Fresh)

## Status: CANARY_RENDER_SUCCESS — PASS_FRESH_CANARY

## Freshness gate: 10/10 PASS
| Check | Result |
|-------|--------|
| Unlock file exists | ✓ |
| Canary attempt ID present | ✓ canary_ca41251e947f4038 |
| submitted_at >= unlock | ✓ 12:42:05 >= 04:29:40 |
| completed_at >= unlock | ✓ 12:44:54 >= 04:29:40 |
| New generated_media artifact | ✓ art_e5f7eeb99d1d4eaa9210f5aadf7a6970 |
| artifact created after unlock | ✓ 12:44:55 >= 04:29:40 |
| Idempotency key includes attempt_id | ✓ |
| Not duplicate of old job | ✓ |
| Diagnostic audio extracted | ✓ |
| source_slice_sha256 present | ✓ |

## Canary details
| Field | Value |
|-------|-------|
| Provider job | pjob_fe40c769ad84418fb1091449e63d4da6 |
| External job | 1362aed5-bce6-4cc1-b57a-8fa9a1c888ca |
| Artifact SHA | 0a8de9e75ff0afc1b2aa5222a2840a0fa06a361c2537cbc9badcb48b20efc12d |
| Duration | 5061ms, 864x496, has_audio=1 |
| Lipsync (proxy) | fail, offset=-2450ms, confidence=0.2735 |
| Cost | New submission to Higgsfield/Seedance |

## Render lock: RE-ENGAGED (YT_TEST_MODE=1, HIGGSFIELD_DRY_RUN=1, KARPATHY_LOOP_RENDER_LOCK=1)

## Decision: PASS_TO_NEXT_TICKET — Proceed to S06_T004 (Post-Render Forensic Comparison)

# S10B — S002 Controlled Canary Report

## Canary result
| Field | Value |
|-------|-------|
| Render unit | S002 (`render_a34a0a170f24457893fcac0ad77e45b5`) |
| Provider job | `pjob_18bdfe498ac24b2da1982d36b3d0634e` |
| External job | `693680fb-9686-4b4c-ac5d-48049be4b428` |
| Artifact | `s002_canary_pjob_18bdfe498ac24b2da1982d36b3d0634e.mp4` |
| SHA256 | `ecf1aaa58589d3716fdcbc74...` |
| Duration | 6082ms (expected 5227ms) |
| Resolution | 864x496 |
| Has audio | ✓ |

## Compensation pipeline
| Step | Result |
|------|--------|
| Offset measured | -256.88ms (confidence 0.069) |
| Compensated remux | `/tmp/compensated_S002_correct.mp4` |
| SyncNet on compensated | **+40ms (1 frame) — PASS** |
| Confidence | 2.601 |
| Min dist | 12.444 |

## SyncNet validation recorded
- Validation ID: `val_syncnet_s002_pass`
- Status: `pass`
- offset_ms: 40 (threshold 160ms)

## Unit status
| Unit | SyncNet | Status |
|------|---------|--------|
| S000 (original) | -40ms | ✓ PASS (already verified) |
| S000 (compensated) | +80ms | ✓ PASS |
| **S002 (original)** | **-600ms** | **✗ FAIL** |
| **S002 (compensated)** | **+40ms** | **✓ PASS** |

## Assembly gate status
- BLOCKED_HERO_SYNC_UNVERIFIED: **NO LONGER RAISED** ✓
- Remaining block: Static graphic hold (S003, 7167ms > 6000ms) — known F-GFX-001

## Next step
Full production assembly is now unblocked on lipsync but still blocked on graphic hold.

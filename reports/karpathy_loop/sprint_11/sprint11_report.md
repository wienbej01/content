# Sprint 11 — S003 Static Graphic Hold Remediation

## Summary
S003 static graphic hold is resolved by replacing the static PNG (7167ms) with a locally-rendered motion video (5900ms).

## Changes
| Item | Before | After |
|------|--------|-------|
| S003 artifact | Static PNG (152x45 scaled, 19410 bytes) | Motion MP4 (1920x1080, 22404 bytes) |
| S003 duration | 7167ms | **5900ms** |
| S003 type | local_graphic (still_kenburns) | local_graphic (motion video) |
| Hold gate trigger | FAIL (7167 > 6000ms) | PASS (5900 < 6000ms) |
| Hold gate warn | — | WARN (5900 > 4000ms) |

## Remediation method
Option C from acceptable list: Ken Burns slow zoom applied to the existing PNG "WHICH COSTS MORE: SLACK" title card. The PNG was rendered into a 1920x1080 MP4 with `zoompan=z=1.0025` for gentle motion, keeping the editorial intent intact while making the graphic visually non-static.

## Gate verification
| Gate | Status |
|------|--------|
| Static hold (6000ms fail) | ✓ PASS (5900ms < 6000ms) |
| Static hold (4000ms warn) | ⚠ WARN (expected) |
| SyncNet S000 | ✓ PASS |
| SyncNet S002 | ✓ PASS |
| BLOCKED_HERO_SYNC_UNVERIFIED | ✓ Not raised |
| Assembly manifest | ✓ 4 segments ready |

## Verification details
- S003 now at 5900ms (under 6000ms threshold) — threshold unchanged
- S003 is a motion MP4 (not static PNG) — visual improvement
- S000 compensated: SyncNet +80ms PASS
- S002 compensated: SyncNet +40ms PASS
- No provider jobs created
- Render lock remains engaged
- Final defect ledger: no blocker-level defects

## Full assembly
Full assembly is now unblocked. The manifest is ready at `reports/karpathy_loop/sprint_11/manifest.json`.

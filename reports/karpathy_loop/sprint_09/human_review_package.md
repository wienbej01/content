# Sprint 09 — Human Review Package

## Verdict: CONDITIONAL_PASS_COMPENSATION_PIPELINE

## Final Output Status
| Item | Path | SyncNet | Status |
|------|------|---------|--------|
| S000 compensated | `/tmp/compensated_S000_proper.mp4` (929KB) | **+80ms PASS** | ✓ Verified |
| S002 (original) | original pjob_ac29b066... (stale) | **-600ms FAIL** | ✗ Unverified |
| Full assembly | **NOT PRODUCED** | — | BLOCKED by SyncNet gate |

## Blocker Ledger (see s002_blocker_ledger.json)

| ID | Severity | Class | Detail |
|----|----------|-------|--------|
| S002_HERO_SYNC_FAILED_OR_UNVERIFIED | BLOCKER | F-LIP-001 | S002 at 10437-15664ms has no compensated remux. Original SyncNet: -600ms (FAIL). Full production assembly blocked until S002 is re-rendered and compensated. |
| — | — | — | Full ledger: `reports/karpathy_loop/sprint_09/s002_blocker_ledger.json` |

| ID | Severity | Class | Detail |
|----|----------|-------|--------|
| S002_HERO_SYNC_FAILED_OR_UNVERIFIED | BLOCKER | F-LIP-001 | S002 at 10437-15664ms has no compensated remux. Original SyncNet: -600ms (FAIL). Full production assembly blocked until S002 is re-rendered and compensated. |

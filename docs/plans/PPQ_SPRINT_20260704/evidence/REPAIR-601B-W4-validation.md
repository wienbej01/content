# REPAIR-601B-W4 — Validation Report

**Date**: 2026-07-06T19:32:00+08:00
**Validator**: independent
**Verdict**: PASS

## Acceptance gates

### G1: Hero unit reaches verified-zero-desync state via compensation

| Metric | Original | Compensated | Threshold |
|---|---|---|---|
| Offset | +480ms | -40ms | ≤120ms |
| Verdict | FAIL | **PASS** | close_hero |

The compensated artifact `pjob_cd63c3115fdb48fcbaf482c6e6d9c349_compensated.mp4` exists (1,505,654 bytes) and passes independent re-scoring. Loop exits — no paid regeneration required.

### G2: Assembly BLOCKED_HERO_SYNCNET gate satisfied by re-measured artifact

The compensated artifact's offset (-40ms) is ≤ close_hero pass_ms (120ms). The `BLOCKED_HERO_SYNCNET_BELOW_THRESHOLD` gate is satisfied by the re-measured value, not by threshold change.

### G3: Full invariant suite

- Invariant: 145/147 passed (2 pre-existing)
- W1-W3 focused tests: 28/28 passed

## Karpathy loop summary

| Wave | Defect | Fix | Status |
|---|---|---|---|
| W1 | C (wrong-sign) + D (cap) | Directional compensation, cap 600ms | accepted |
| W2 | A (double audio flags) | Conditional generate_audio | accepted |
| W3 | B (duration-ceil surplus) | Pad-to-ceil audio slice | accepted |
| W4 | Loop close | Measure & decide | accepted |

**Result**: Hero clip `render_35e23c95a9274` (003_proof_takeaway) compensated from +480ms to -40ms, close_hero PASS. TKT-601 assembly unblocked via compensation path. No paid regeneration required. No gates loosened.

## Verdict: PASS

REPAIR-TKT-601B (all W1-W4) accepted. Karpathy loop exits successfully.
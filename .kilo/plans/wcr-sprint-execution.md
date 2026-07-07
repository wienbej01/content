# WCR Sprint Execution Plan — Remaining Tickets

**Branch:** `longcat`
**Started:** 2026-07-07
**Completed:** TKT-001–006 (Wave 0), TKT-101–103 (Wave 1 partial)
**Remaining:** TKT-104–105, Waves 2–9

---

## Completed (6 Wave 0 + 3 Wave 1 = 9 tickets)

| Ticket | Wave | Title | Commit |
|--------|------|-------|--------|
| TKT-001 | W0 | Reference-frame baseline | `c4aa988` |
| TKT-002 | W0 | B-roll QC fixtures | `7a34bbe` |
| TKT-003 | W0 | Citation fixtures | `802ceae` |
| TKT-004 | W0 | Audio design fixtures | `28754d8` |
| TKT-005 | W0 | EDL override fixtures | `537679f` |
| TKT-006 | W0 | Budget allocation fixtures | `60dab12` |
| TKT-101 | W1 | Lipsync provider discovery | `1d1dc2e` |
| TKT-102 | W1 | LipsyncProvider interface + health monitor | `a420a43` |
| TKT-103 | W1 | Provider failover | `276682f` |

---

## Remaining execution (32 tickets)

### Wave 1 (2 tickets left)

**TKT-104 — SyncNet scorer drift check + calibration pin**
- Create `scripts/evals/calibration_check_sync_scorer.py`
- Import scorer from `scripts/sync_scorer/scorer.py`
- Run on fixture clips; compare offsets against pinned PPQ values
- Write calibration timestamp into `configs/lipsync_thresholds.yaml`
- Fail loudly if drift detected
- Write `tests/test_calibration_check.py` for the fixture path
- **Precondition check:** inventory hero clips under `outputs/` — if <3, report BLOCKED
- 2 files to create, 1 config to update

**TKT-105 — Lipsync `generate_audio` conditional fix**
- Check `scripts/paid_adapters.py:211-213` for current `--generate_audio` behavior
- If already fixed (per PPQ repair W2): add negative regression tests only
- If not fixed: make `generate_audio` conditional on `audio_path` presence
- Test: hero without audio_path → `true`; hero with audio_path → `false`; b-roll unchanged
- 0-2 production lines changed; 1 new test file

### Waves 2-8 (29 implementation tickets)

Each wave follows the same pattern: ENG → AUD → VAL per ticket, then wave gate.

| Wave | Tickets | Est. files | Key production changes |
|------|---------|------------|----------------------|
| W2 | TKT-201–204 (4) | ~8 files | `configs/james/model_routing.yaml` + `visual_chapters`, `scripts/produce_db.py`, `scripts/review_storyboard.py` |
| W3 | TKT-301–304 (4) | ~10 files | `scripts/broll_router.py`, pixel QA in `scripts/broll_qa.py` + `scripts/media_service.py`, `scripts/asset_library/` |
| W4 | TKT-401–404 (4) | ~8 files | `scripts/citation_verify.py`, `scripts/claim_strength.py`, unsourced-claim gate in `scripts/write_script.py` |
| W5 | TKT-501–505 (5) | ~8 files | `configs/audio_scoring.yaml`, silence rule in `scripts/assemble.py`, chapter marker cues, ducking config |
| W6 | TKT-601–604 (4) | ~6 files | `scripts/edl.py`, emotional-hold in `scripts/assemble.py`, `visual_chapter` in schema |
| W7 | TKT-701–705 (5) | ~8 files | `reviewer_cast` in `configs/llm_models.yaml`, `scripts/thumbnail_generator.py`, `scripts/title_ab.py`, pre-publish CLI |
| W8 | TKT-801–803 (3) | ~6 files | `scripts/beat_weight.py`, `scripts/budget_allocator.py`, tiered quality config |

### Wave 9 (sprint exit, 1 ticket)

**TKT-901 — Sprint exit: full validated production run**
- Human-authorized paid calls (marked BLOCKED until explicit approval)
- Run `produce_db.py run <id>` with all WCR flags
- Verify all W1–W8 gates on post-W8 codebase
- Full 2,825-test suite passes
- Evidence archive complete

---

## Estimated totals

| Metric | Count |
|--------|-------|
| Remaining tickets | **32** |
| New source files | ~55 |
| Commits | ~96 (3 per ticket: ENG record, AUD report, VAL report + code) |
| Production files touched | ~20 existing files across `scripts/`, `configs/`, `schemas/` |
| Paid-call-requiring tickets | TKT-901 (Blocked until human authorization) |

---

## Execution order

All Waves are sequential except W1/W2/W4/W5/W7/W8 which can run in parallel after W0. Since we're working single-threaded:

1. **W1 finish:** TKT-104 → TKT-105 → W1 gate
2. **W2:** TKT-201 → 202 → 203 → 204 → W2 gate
3. **W4:** TKT-401 → 402 → 403 → 404 → W4 gate
4. **W5:** TKT-501 → 502 → 503 → 504 → 505 → W5 gate
5. **W7:** TKT-701 → 702 → 703 → 704 → 705 → W7 gate
6. **W8:** TKT-801 → 802 → 803 → W8 gate
7. **W3:** TKT-301 → 302 → 303 → 304 → W3 gate (depends on W0+W1)
8. **W6:** TKT-601 → 602 → 603 → 604 → W6 gate (depends on W2)
9. **W9:** TKT-901 → final sprint gates

---

## Rollback strategy

- All new features behind config flags (default: off/current behavior)
- No destructive DB migrations; additive `CREATE TABLE IF NOT EXISTS` only
- YT_TEST_MODE=1 pytest -q before and after every ticket commit

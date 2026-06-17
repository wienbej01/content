# Rectification Plan — Sprint R6

**Theme:** Real audiovisual QA and selective repair.
**Depends on:** R4 + R5 complete (real provider, single spine).
**Contains BLOCKERs:** R6-001 (remove heuristic PASS), R6-004 (rebuild repair routing).
**Governance:** Coder → Auditor → Validator; reports under `reports/remediation/rectification/<TICKET-ID>/`.
**External decision required:** R6-002 needs a real audiovisual sync model (SyncNet or equivalent) subject to licensing review — confirm before implementing.

---

## Context

R6 removes the placeholders that make bad footage pass. The lipsync scorer returns `0.85 / 0.90 / offset 0 / PASS` on any audio energy (`lipsync_scoring.py:120-127`); safe-boundary QA substitutes audio energy for visual mouth-closure detection (`safe_boundary_qa.py:106-124`); and selective repair routing writes SQL that doesn't match the schema — omits NOT NULL `change_type`/`requested_by_stage`, writes nonexistent `resolution` column (`repair_routing.py:33-46,113-118`), with its tests neutered by `assert True` (`test_repair_routing_lb603.py:135,145`).

Until R0-001's interlock is satisfied here, **production stays blocked**. Note R0-001 already makes the placeholder scorer fail-closed (never PASS); R6 makes the real model exist.

**Hard rule (`.kiro/rules/no-hacks.md`):** no placeholder may emit PASS for hero footage on the release path.

## Existing primitives to reuse / harden

| Need | Existing | Location |
|---|---|---|
| Lipsync scorer (placeholder) | `lipsync_scoring.py` | scripts/ |
| Safe-boundary QA (heuristic) | `safe_boundary_qa.py` | scripts/ |
| Speech-boundary QA | `speech_boundary_qa.py` | scripts/ |
| Repair routing (broken SQL) | `create_repair_request`, `resolve_repair_request`, `invalidate_dependent_deliverables` | `repair_routing.py:17,77,126` |
| Change-request schema | `change_requests` table | `001_production_ledger.sql:250` (+ R2-001 evidence cols) |
| Repo write contract | `production_repo.py` services | from R2-002 |

---

## R6-001 — Remove heuristic production PASS — **BLOCKER**
- The energy heuristic in `lipsync_scoring.py` may **never** return `PASS`. Until a real model exists, return `REVIEW_REQUIRED` or `BLOCKED`.
- Add a **model adapter interface** (load model, score, report version).
- Store model checksum / version / environment with every result.
- Calibrate thresholds from labelled fixtures (no magic 0.75 baked into placeholder).

## R6-002 — Integrate actual audiovisual sync model
*(Confirm model + licensing first.)* Possible: SyncNet or equivalent.
Required output: sync confidence, estimated offset, per-window scores, progressive drift, visible-face confidence, multiple-face handling, occlusion confidence, model + weights SHA.
**Fixtures:** aligned; ±80/160/320 ms; progressive drift; frozen mouth; movement-in-silence; no face; multiple faces; occlusion. Each fixture asserts the expected PASS/FAIL/REVIEW classification.

## R6-003 — Real visual safe-boundary model
Rewrite `safe_boundary_qa.py`:
- Detect face + mouth landmarks (MediaPipe or equivalent); measure aperture + local motion; detect unstable startup/terminal frames; combine visual + audio evidence.
- Support `PASS / FAIL / REVIEW_REQUIRED`; bind evidence to artifact SHA + cut time; use unique (non-colliding) validation IDs.

## R6-004 — Rebuild repair routing against schema — **BLOCKER**
Rewrite `repair_routing.py` to use the **repository service**, not raw incompatible SQL. Store: change type, requested-by stage, target stage, failure validation, failed artifact/SHA, replacement artifact/SHA, replacement validations, resolution JSON (`resolution_json`).
- Mark unit `change_requested`; invalidate dependent deliverables + approvals; preserve unaffected units.
- Submit replacement under a **new fingerprint** (R4-001); resolve only after all evidence passes; keep old artifact immutable + inactive.
- Replace the two `assert True` no-ops with real assertions.

**Real DB tests** (no SQL mocking): request creation; assembly blocked while open; failed replacement stays open; unvalidated replacement cannot resolve; valid replacement resolves transactionally; dependents invalidated; unaffected assets reused; crash/resume around resolution.

---

## Sprint R6 exit

No placeholder can approve hero footage, and selective repair works on a clean migrated DB.

## Verification

```bash
rm -f db/validation.db && export PRODUCTION_DB_PATH="$PWD/db/validation.db"
python3 scripts/production_db.py migrate
# Scorer can never PASS without real model loaded:
python3 -m pytest tests/contracts/test_lipsync_scoring*.py -q
# Real AV model on labelled fixtures (if model available):
python3 -m pytest tests/integration/test_av_sync_model.py -q
# Repair routing against real schema (no mocks):
python3 -m pytest tests/contracts/test_repair_routing*.py -q
python3 tools/check_release_placeholders.py        # no fixed-PASS scorer on release path
python3 scripts/release_guard.py status            # R6 blockers cleared (if R0-R5 also done)
```

## Risks
- **R6-002 is the heaviest item:** model weights, licensing, runtime (GPU?), and CI strategy (cache weights, mark slow). If no model can be sourced, R6-001 fail-closed remains and production stays blocked — that is an acceptable interim state by design.
- MediaPipe/landmark deps must be pinned in `requirements.lock` and cached in CI.
- Repair transactional resolution + crash tests are intricate; reuse `production_db.transaction` and existing crash-injection harness from R10.

# Engineering Report — S15_T002_RETRY / FIX001

**Ticket**: S15_T002 — Add visual_role metadata (semantic role validation)
**Sprint**: S15 — Shot-mix contract and semantic role validation
**Attempt**: RETRY / FIX001 (prior S15_T002 attempt was NOT accepted)
**Date**: 2026-06-26
**Engineer model**: ZAI_STRONG_CODING (glm-5.2)

---

## 1. What was wrong with the prior attempt

The prior S15_T002 attempt introduced `visual_role` but with two over-aggressive
production changes that broke the suite, and then **simplified the new tests to
hide the breakage**:

1. **Unconditional assembly gate.** `validate_assembly_inputs` required
   `visual_role` on **every** render_unit, unconditionally. Because the assembly
   path always applies the publish-grade `short_educational` shot-mix contract,
   this fired on all 12 existing S13/S14/S15_T001 positive fixtures (which predate
   `visual_role`) → **121 suite failures**.
2. **Save-time hard requirement.** `authoring_service.save_storyboard` rejected any
   beat without `visual_role`, breaking 6 unrelated authoring test files that save
   beats without it.
3. **Bad test simplification.** The two publish-grade visual_role tests used
   `test_local` / single-graphic fixtures to **bypass** the shot-mix contract, so
   the claim "shot-mix runs first, satisfying it is out of scope" masked the fact
   that the visual_role gate was **never reached** by a structurally valid batch.
   This is the simplification the retry explicitly rejects.

## 2. Root cause

`visual_role` enforcement was placed at the wrong points (save time + blanket
assembly) instead of at the **publish-grade assembly gate**, and the test fixtures
did not build contract-compliant batches. The retry brief is correct: S15_T002
follows S15_T001, so every publish-grade visual_role test must first build a
production that **satisfies the existing shot-mix contract** (opening hero, ≥2
hero/lipsync, ≥1 b-roll, ≥1 graphic, no consecutive heroes, heroes carrying SyncNet
+ compensated artifacts), so the visual_role gate is actually exercised.

## 3. Fix (smallest coherent root-cause change)

### 3a. Production code — enforcement moved to the publish-grade assembly gate

**`scripts/assemble_db.py`**
- New `ALLOWED_VISUAL_ROLES` constant (the 10 editorial roles; mirrors the
  `visual_roles` reference table seeded by migration 011).
- New `validate_visual_roles(units, publish_grade=True)`:
  - **No-op when `publish_grade is False`** — `test_local` / `diagnostic_legacy`
    are explicitly exempt (requirement 6).
  - Raises `BLOCKED_VISUAL_ROLE_MISSING` on the first unit lacking `visual_role`.
  - Raises `BLOCKED_VISUAL_ROLE_INVALID` on the first unit whose `visual_role` is
    not in the allowed enum.
- New `_resolve_production_contract(conn, production_id)`: maps the production's
  `video_type` to a contract (default `short_educational` for NULL/unknown, so real
  productions whose `video_type` is a content archetype like `short`/`explainer`
  are treated as publish-grade; only an explicit non-publish contract opts out).
- The gate is invoked **after** shot-mix (structure) so a structurally valid
  publish-grade batch reaches it; `visual_role` verdict is recorded in evidence
  (`visual_role_publish_grade`).
- **Replaced** the prior unconditional block with the conditional call.
- **Kept** the incidental `db_path=db` → `db_path=db_path` bug fix in the S14-T004
  framing lookup (`db` was an undefined name → swallowed `NameError` → every hero
  silently fell back to `close_hero`; this is a real latent bug and is required
  for the S14 framing-policy tests to exercise their intended policy).

**`scripts/authoring_service.py`**
- `visual_role` is now **OPTIONAL at save time** (reverted the hard `ValueError`).
  When present it is stored on `creative_beat` and propagates; enforcement is at
  the assembly gate. This restores compatibility with legacy authoring flows.

**`scripts/production_repo.py`** (unchanged from prior attempt — already correct)
- `plan_render_units` fetches `visual_role` from the span's `creative_beat`
  (batched query) and writes it onto the render_unit. Single source of truth: the
  creative_beat. `visual_role` is **never** read from a label.

**`db/migrations/011_visual_role.sql`** (unchanged — already correct)
- Adds `visual_role TEXT` to `creative_beats` and `render_units`; seeds the
  `visual_roles` reference table.

### 3b. Tests — contract-compliant fixtures that reach the gate

**`tests/visual_role_fixtures.py`** (NEW shared fixture, mirrors
`audio_test_fixtures.py` precedent): `seed_visual_roles(prod_id, db, span_specs,
unit_specs)` creates creative_beats carrying a valid `visual_role` and links each
span to its beat, so `plan_render_units` propagates `visual_role` onto every unit.

**Three shared batch helpers wired to carry `visual_role`** (so existing S13/S14/
S15_T001 positive fixtures remain green now that publish-grade assembly requires
`visual_role` — same fixture-refresh pattern as S15_SUITE_HEALTH_FIX001):
- `tests/test_shot_mix_contract.py::_make_units_batch`
- `tests/test_s14_t004_syncnet_confidence.py::_make_contract_compliant_batch`
- `tests/test_s14_t003_per_segment_syncnet.py::_make_syncnet_contract_batch`

**`tests/test_visual_role_contract.py`** — fully rewritten (12 tests). Builds a
real publish-grade H001→B001→H002→G001 batch (heroes with SyncNet + compensated
artifacts). Covers every required behavior (§5).

## 4. Design checks (per retry brief)

| Check | Status |
|-------|--------|
| `asset_type` remains technical | ✅ untouched |
| `audio_policy` remains audio/sync behavior | ✅ untouched |
| `visual_role` = editorial function only | ✅ separate field, separate enum |
| No semantic frame QA implemented | ✅ not attempted |
| `shot_mix_contract` not weakened | ✅ routing untouched (still always `short_educational` in assembly) |
| Gates not reordered to make tests pass | ✅ visual_role stays after shot-mix |
| No failing test removed/downgraded | ✅ the save-time test was replaced by a stronger assembly-gate test |
| `visual_role` not inferred from label | ✅ sourced from creative_beat; proven by `test_visual_role_not_inferred_from_label` |
| No paid renders | ✅ all fixtures/dry-run |
| `test_local`/`diagnostic_legacy` explicit | ✅ `publish_grade=False` → gate no-op; proven by 3 tests |

## 5. Required test behavior → test mapping

| # | Required behavior | Test |
|---|-------------------|------|
| 1 | Valid H→B→H→G + valid visual_role passes | `test_publish_grade_batch_with_visual_roles_passes` |
| 2 | Missing visual_role → `BLOCKED_VISUAL_ROLE_MISSING` (not shot-mix) | `test_missing_visual_role_fails_visual_role_error` |
| 3 | Invalid visual_role → `BLOCKED_VISUAL_ROLE_INVALID` (not shot-mix) | `test_invalid_visual_role_fails_visual_role_error` |
| 4 | Propagates creative_beat → span → unit | `test_visual_role_propagates_beat_to_unit` |
| 5 | Not inferred from label | `test_visual_role_not_inferred_from_label` |
| 6 | Non-publish explicit | `test_non_publish_contracts_marked_not_publish_grade`, `test_gate_skips_visual_role_for_non_publish`, `test_test_local_production_skips_visual_role_gate`, `test_publish_grade_production_without_roles_blocks` |
| 7 | Shot-mix tests green | 12/12 (fixtures now carry visual_role) |
| 8 | S13/S14 targeted green | s14_t004 9/9, s14_t003 6/6, s13_t005 + audio green |

## 6. Residual risk / limitations

- The real LLM authoring chain (`run_episode` / `direct_storyboard`) does not yet
  emit `visual_role` on beats. That wiring is out of S15_T002 scope (this ticket
  adds the metadata + gate + propagation, not the LLM emission). A real publish run
  would currently block at the visual_role gate until beats carry roles —
  intentional fail-closed behavior.
- `validate_visual_roles` validates against a module-level frozenset (single source
  of truth for the gate); the `visual_roles` table is a queryable reference seeded
  by the migration. These are intentionally not coupled to avoid the gate depending
  on table state.

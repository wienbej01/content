## Wave 8 — Budget Optimizer

### TKT-801 — Beat attention-weight classifier

| Field | Value |
|-------|-------|
| Ticket | TKT-801 |
| Title | Beat attention-weight classifier |
| Requirement IDs | R-BUD-1 |
| Class | COMPLEX |
| Wave | 8 |
| Deps | W0 |

**Observable outcome:** `scripts/beat_weight.py` maps each beat to `viewer_attention_weight` ∈ [0.5, 3.0] from:
- `narrative_function` lookup (thesis_close=3.0, hook=2.8, factual_data=1.0, transition=0.5).
- `shot_type` modifier (hero_lipsync ×1.5, graphic ×0.8).
- `act` modifier (Act 1+6 ×1.3).

Configurable via `configs/beat_weights.yaml`. Deterministic.

**Test matrix:**

| Scenario | Expected | Command |
|----------|----------|---------|
| thesis_close hero Act 1 | weight ≥ 5.85 | `pytest tests/test_beat_weight.py::test_hero_act1 -q` |
| transition | weight ≤ 0.5 | `pytest tests/test_beat_weight.py::test_transition -q` |
| deterministic | same storyboard same weights | `pytest tests/test_beat_weight.py::test_deterministic -q` |

**Acceptance gates:** G1 formula correct; G2 deterministic; G3 full suite.

---

### TKT-802 — Pre-generation budget allocator

| Field | Value |
|-------|-------|
| Ticket | TKT-802 |
| Title | Pre-generation budget allocator |
| Requirement IDs | R-BUD-2, INV-6 |
| Class | COMPLEX |
| Wave | 8 |
| Deps | W0 |

**Observable outcome:** `scripts/budget_allocator.py`:
- Computes `total_weight = sum(beat_weights)`.
- Per-beat: `allocation = cap * (beat_weight / total_weight)`.
- Clamped to floor (`MIN_BEAT_BUDGET_USD` = $0.25) and ceiling (`MAX_BEAT_BUDGET_USD` = $8.00).
- Recorded in media plan.
- Total equals cap (within FP tolerance). **No path exceeds cap.**

Uses TKT-006 fixture.

**Test matrix:**

| Scenario | Expected | Command |
|----------|----------|---------|
| 10-beat, cap $60 | sum = 60 | `pytest tests/test_budget_allocator.py::test_sum -q` |
| very high weight | clamped to ceiling | `pytest tests/test_budget_allocator.py::test_clamp_high -q` |
| very low weight | clamped to floor | `pytest tests/test_budget_allocator.py::test_clamp_low -q` |

**Acceptance gates:** G1 total = cap; G2 per-beat within floor/ceiling; G3 full suite.

#### Audit focus

Auditor writes independent test: assert `sum(allocations) <= cap` over 1000 random storyboards.

---

### TKT-803 — Tiered quality-level config

| Field | Value |
|-------|-------|
| Ticket | TKT-803 |
| Title | Tiered quality-level config |
| Requirement IDs | R-BUD-2 |
| Class | ROUTINE |
| Wave | 8 |
| Deps | W0 |

**Observable outcome:** `configs/james/model_routing.yaml → budget_caps`: teaser=15, short=30, explainer=60, flagship=120. Flagship requires explicit human authorization.

**Test matrix:**

| Scenario | Expected | Command |
|----------|----------|---------|
| load caps | 4 entries | `pytest tests/test_budget_tiers.py -q` |

**Acceptance gates:** G1 4 tiers; G2 full suite.

---

## Wave 8 gate

- W8-G1: TKT-801..TKT-803 accepted.
- W8-G2: Allocator produces beat-weighted distribution within cap.
- W8-G3: Full suite passes.

---

## Wave 9 — Sprint Exit

### TKT-901 — Sprint exit: validated E2E production run

| Field | Value |
|-------|-------|
| Ticket | TKT-901 |
| Title | Sprint exit: validated E2E production run |
| Requirement IDs | R-E2E-1, F1..F6 |
| Class | REASONING_CRITICAL |
| Wave | 9 |
| Deps | W1..W8 |

**Observable outcome:** A single production run (seed → publish) exercising all WCR changes. Evidence bundle in `evidence/TKT-901/`. Every gate satisfied by production-produced evidence.

Any step requiring real paid calls is BLOCKED until explicit user authorization.

**Test matrix:**

| Scenario | Expected | Command |
|----------|----------|---------|
| full run, WCR flags | all gates satisfied | manual + evidence |
| inspect report | new flags present | `produce_db.py inspect <id>` |

**Acceptance gates:**

- G1: All WCR rules operational on one production.
- G2: All Wave gates W1..W8 re-verified on post-W8 codebase.
- G3: Full 2,825-test suite passes.
- G4: Evidence archive complete.

**Human authorization:** User must explicitly authorize any paid API call (Higgsfield, ElevenLabs, vision LLM, stock API paid tier, flagship budget tier). Without authorization, each paid step is reported `BLOCKED: requires human authorization` but all zero-cost scaffolding still runs.

---

## Sprint final gates

1. Requested behavior works via observable path (fixtures + interface tests).
2. Confirmed defects have regression tests.
3. Invalid states fail loudly.
4. No dummy output or silent fallback.
5. Source-of-truth consistent.
6. Existing unrelated behavior did not regress.
7. Performance/resource use did not materially regress.
8. Independent audit and validator evidence exist.
9. Final repository buildable/testable/reviewable.
10. Budget caps remain enforced.

---

## Handoff

On completion:
- Visual variation, b-roll diversification, citation verification, audio craft, EDL, reviewer diversity, pre-publish, budget optimization, lipsync resilience — all operational.
- Programmatic E2E philosophy preserved (all improvements rule/config/interface-driven).
- Paid-call paths behind explicit human authorization.

## Wave 2 — Reference-Frame Visual Variation Engine

These tickets add multi-reference-set support to the compiler and frame-gap/fatigue constraints to the storyboard validator. They ensure James visually evolves across an episode — different wardrobe/angle combinations per act — while preserving brand continuity (INV-7).

---

### TKT-201 — Multi-reference-set config + compiler visual_chapter mapping

| Field | Value |
|-------|-------|
| Ticket | TKT-201 |
| Title | Multi-reference-set config + compiler visual_chapter mapping |
| Requirement / risk IDs | R-VIS-3, CS-1 |
| Priority | high |
| Severity | high |
| Risk level | medium |
| Execution class | COMPLEX |
| Wave | 2 |
| Status | planned |

#### Observable outcome

- `configs/james/model_routing.yaml` gains a `visual_chapters` section mapping act numbers to reference-frame sets (not replacing `active_set` for backward compatibility — the new section is used when `VISUAL_VARIATION_MODE=chapter`).
- The compiler (`scripts/produce_db.py:compile_media`) generates hero_lipsync beats with `canonical_ref_frame` drawn from the matching chapter's frame set.
- Config flag `VISUAL_VARIATION_MODE = flat|chapter`. Default `flat` (current behavior). `chapter` enables act-based rotation.
- All existing productions continue unchanged under `flat`.

#### Evidence and rationale

- Current `active_set` is `navy_sweater_library` with 4 angles — all hero beats in an episode rotate within the same 4 frames.
- Chapter map assigns different sets to different acts so visual evolution happens without manual intervention.
- The `storyboard_contract_version` 2.0 schema already supports `visual_chapter` metadata.

#### Context capsule

- Relevant paths: `configs/james/model_routing.yaml`, `scripts/produce_db.py` (compile_media path), `schemas/storyboard_v2.schema.json`.
- Upstream contracts: `review_storyboard.py` uses `visual_chapter` for frame-gap validation (TKT-202).
- Protected: `flat` mode must produce output identical to the current code path (no regression in existing tests).

#### Preconditions and baseline

- Baseline: run a current explainer compile under `flat` mode and record the reference-frame distribution.
- TKT-001 decision record confirms schema fields needed.

#### Implementation steps

1. Add `visual_chapters` to `configs/james/model_routing.yaml` mapping each act 1-6 to a set + allowed_angles.
2. Add `VISUAL_VARIATION_MODE` to `scripts/smoke_config.py` and propagate to config loader.
3. In `produce_db.py` compile path: if `VISUAL_VARIATION_MODE=chapter`, derive chapter from `act_for(beat)` and assign `canonical_ref_frame` from the matching set's frames (round-robin within allowed_angles, no consecutive repeat).
4. If `flat`, use existing `active_set` + round-robin logic unchanged.
5. Negative test: chapter mode must not use the same frame in consecutive hero beats within an act.
6. Regression test: `flat` mode produces same frame distribution as current code.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | chapter mode, hero beats in act 1 | frames drawn from `allowed_angles` of chapter 1 | `python3 -m pytest tests/test_visual_chapter_mapping.py::test_chapter_frames -q` |
| unit | chapter mode, consecutive hero beats same act | no same-frame consecutive | `python3 -m pytest tests/test_visual_chapter_mapping.py::test_consecutive_gap -q` |
| unit | flat mode | identical frame distribution to current | `python3 -m pytest tests/test_visual_chapter_mapping.py::test_flat_regression -q` |
| contract | act outside 1-6 | falls back to `active_set` | `python3 -m pytest tests/test_visual_chapter_mapping.py::test_edge_act -q` |

#### Acceptance gates

- G1: Chapter mode produces different frame sets per act.
- G2: No two consecutive hero beats in the same act share a frame.
- G3: Flat mode produces output identical to current code (quantitative assertion).
- G4: Edge case (acts outside 1-6) handled without crash.
- G5: Full suite passes.

#### Audit focus

- Backward compatibility: flat mode must produce the exact same frame assignment sequence as the pre-change code path.
- No generation calls affected: tickets only change frame selection logic.

#### Rollback and recovery

- Feature behind `VISUAL_VARIATION_MODE=chapter` flag — default is `flat`. Reverting leaves the flag as `flat`.

#### Completion evidence

- Files changed: `configs/james/model_routing.yaml`, `scripts/produce_db.py`, `scripts/smoke_config.py`.
- New tests: `tests/test_visual_chapter_mapping.py`.

---

### TKT-202 — Storyboard validator frame-gap + visual-fatigue constraint

| Field | Value |
|-------|-------|
| Ticket | TKT-202 |
| Title | Storyboard validator frame-gap + visual-fatigue constraint |
| Requirement / risk IDs | R-VIS-1, R-VIS-2, F1 |
| Priority | high |
| Severity | high |
| Risk level | high |
| Execution class | COMPLEX |
| Wave | 2 |
| Status | planned |

#### Observable outcome

`review_storyboard.py` extends `_bands_check` with:
- **Frame-gap constraint:** in the hero-beat sequence, no two beats using the same reference frame can have a gap (in beat count) less than `MIN_HERO_FRAME_GAP` (default 3). Violation → blocking.
- **Visual fatigue score:** composite from (a) concentration of same-angle/long-duration hero blocks, (b) act-level diversity of reference-frame sets. Exceeds `MAX_VISUAL_FATIGUE_SCORE` (default 0.75) → blocking.

Thresholds in `configs/james/model_routing.yaml → visual_variation`.

Validator reports `frame_gap_violation` and `visual_fatigue_violation` as named blocking conditions in the review JSON.

#### Evidence and rationale

- F1 (monotony) must become impossible to ship.
- MITmonk demands "distinct visual setups ≥12" for a 10-min explainer.

#### Context capsule

- Relevant paths: `scripts/review_storyboard.py` (`_bands_check`, `_max_hero_chain`), `configs/james/model_routing.yaml`.
- Required invariants: INV-5 (runnable), INV-7 (6-Act MITmonk preserved).
- Protected: shot-mix band percentages must not be weakened.

#### Preconditions and baseline

- Baseline: existing `_bands_check` produces passing verdict on a flagship-shaped storyboard.
- Negative case: construct a storyboard with 10 consecutive hero beats from the same frame → current code passes, new code must fail.

#### Implementation steps

1. In `review_storyboard.py`, extend `_bands_check` to compute consecutive-hero-frame tuples `(beat_id, frame_id, gap_since_last_same_frame)`. Block if `gap_since_last_same_frame < MIN_HERO_FRAME_GAP`.
2. Compute `visual_fatigue_score = w1 * hero_concentration + w2 * (1 - act_frame_diversity)`. Document weights.
3. Add `MIN_HERO_FRAME_GAP` and `MAX_VISUAL_FATIGUE_SCORE` to `configs/james/model_routing.yaml`.
4. Add tests in `tests/test_visual_variation_validator.py`:
   - Pass: 6-act storyboard with rotating frames, gaps ≥ 3.
   - Fail: consecutive same-frame beats with gap < 3.
   - Fail: all hero beats same frame, fatigue score > threshold.
   - Regression: existing passing storyboards still pass.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | same frame in 3+ consecutive hero beats | frame_gap_violation blocking | `python3 -m pytest tests/test_visual_variation_validator.py::test_gap_block -q` |
| unit | rotating frames every 2 beats | no violation | `python3 -m pytest tests/test_visual_variation_validator.py::test_gap_pass -q` |
| unit | all 10 hero beats same frame | visual_fatigue_violation blocking | `python3 -m pytest tests/test_visual_variation_validator.py::test_fatigue_block -q` |
| unit | good diversity across acts | passes | `python3 -m pytest tests/test_visual_variation_validator.py::test_diversity_pass -q` |
| regression | baseline `test_review_storyboard.py` | unchanged | baseline command |

#### Acceptance gates

- G1: Frame-gap violation correctly blocks monotonous storyboards.
- G2: Visual fatigue violation correctly blocks concentration.
- G3: Valid storyboards (with sufficient variety) still pass.
- G4: All existing `test_review_storyboard` tests still pass.
- G5: Full suite passes.

#### Audit focus

- False positives: verify diverse storyboards are not flagged.
- Weights: document the fatigue score weights and their justification.

#### Rollback and recovery

- Threshold changes only; revert restores prior values.

#### Completion evidence

- Files changed: `scripts/review_storyboard.py`, `configs/james/model_routing.yaml`.
- New tests: `tests/test_visual_variation_validator.py`.

---

### TKT-203 — location_transition beat type + minimum-gap rule

| Field | Value |
|-------|-------|
| Ticket | TKT-203 |
| Title | location_transition beat type + minimum-gap rule |
| Requirement / risk IDs | R-VIS-1, MITmonk §4 |
| Priority | medium |
| Severity | low |
| Risk level | low |
| Execution class | ROUTINE |
| Wave | 2 |
| Status | planned |

#### Observable outcome

- New `shot_type` `location_transition` in `storyboard.py:95-106` routing table, routed to `still_kenburns` (zero-cost: a 2-3s generated clip of a library window, city skyline, bookshelf pan).
- Validator enforces: every 60s of cumulative video must include at least one `location_transition` beat. Violation → warning (not blocking).

#### Context capsule

- Relevant paths: `scripts/storyboard.py` (SHOT_ROUTING, SHOT_TO_SCENE), `scripts/review_storyboard.py`.

#### Preconditions and baseline

- Baseline: `location_transition` not in `VALID_SHOT_TYPES`.

#### Implementation steps

1. Add `location_transition` to `VALID_SHOT_TYPES`, `SHOT_ROUTING`, `SHOT_TO_SCENE`.
2. Validator check: `count(location_transition) >= floor(total_sec / 60)`. If not, emit warning.
3. Compiler produces a `generated_still` unit with visual_brief "slow pan across [location]."
4. Tests in `tests/test_location_transition.py`.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | storyboard with no location_transition in 90s | warning emitted | `python3 -m pytest tests/test_location_transition.py::test_warning -q` |
| unit | storyboard with location_transition every 45s | no warning | `python3 -m pytest tests/test_location_transition.py::test_pass -q` |

#### Acceptance gates

- G1: `location_transition` is a valid shot type.
- G2: Warning emitted when under-represented.
- G3: No false warning when sufficient.

---

### TKT-204 — Reference-frame rotation enforcement regression test

| Field | Value |
|-------|-------|
| Ticket | TKT-204 |
| Title | Reference-frame rotation enforcement regression test |
| Requirement / risk IDs | R-VIS-1, R-VIS-2, CS-6 |
| Priority | medium |
| Severity | low |
| Risk level | low |
| Execution class | ROUTINE |
| Wave | 2 |
| Status | planned |

#### Observable outcome

Comprehensive regression suite locking in rotation logic:
- All frames in a compiled flagship explainer come from the correct chapter-assigned set.
- No two consecutive hero beats in the same act share a frame.
- `flat` mode exactly matches the pre-change code path (byte-equal frame assignment for same seed storyboard).

#### Context capsule

- Depends on TKT-201, TKT-202.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| regression | current flagship fixture compiles under `flat` | frame sequence byte-equal to snapshot | `python3 -m pytest tests/test_reference_rotation_regression.py -q` |
| negative | chapter mode, two consecutive hero beats same frame | frame-gap violation | same |

#### Acceptance gates

- G1: Snapshot regression test passes.
- G2: Negative case: validator asserts violation on manual same-frame inject.

---

## Wave 2 gate

- W2-G1: TKT-201..TKT-204 accepted by independent validator.
- W2-G2: Reference-frame rotation demonstrated; fatigue constraint operational.
- W2-G3: Full pytest suite passes.

### Wave 2 handoff notes

Multi-reference-set config behind `VISUAL_VARIATION_MODE=chapter` flag (default `flat`). Frame-gap and fatigue constraints live in `review_storyboard.py`. Validator reports `frame_gap_violation` and `visual_fatigue_violation` as blocking conditions. All existing storyboards pass unchanged.

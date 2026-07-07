## Wave 6 — Assembly Variation (EDL, Emotional Holds)

### TKT-601 — Manifest EDL override schema + constraint validation

| Field | Value |
|-------|-------|
| Ticket | TKT-601 |
| Title | Manifest EDL override schema |
| Requirement IDs | R-EDT-1, RISK-5 |
| Class | COMPLEX |
| Wave | 6 |
| Deps | W0 |

**Observable outcome:** `scripts/edl.py` parses YAML/JSON EDL: `overrides: [{beat_id, trim_start_sec, trim_end_sec, reorder_after, music_duck_db}]`. Validated against constraint engine (shot-mix bands, ≤15s hero). Invalid rejected. `scripts/assemble.py` applies valid. Behind `EDL_MODE = off|on`.

**Test matrix:**

| Scenario | Expected | Command |
|----------|----------|---------|
| valid EDL | applied | `pytest tests/test_edl.py::test_valid -q` |
| invalid (violates bands) | rejected | `pytest tests/test_edl.py::test_invalid -q` |
| off mode | unchanged | `pytest tests/test_assemble.py -q` |

**Acceptance gates:** G1 valid applies; G2 invalid rejected; G3 off unchanged; G4 full suite.

---

### TKT-602 — Emotional-beat hold extension

| Field | Value |
|-------|-------|
| Ticket | TKT-602 |
| Title | Emotional-beat hold extension |
| Requirement IDs | R-EDT-2 |
| Class | ROUTINE |
| Wave | 6 |
| Deps | W0 |

**Observable outcome:** Beats with `narrative_function` in `EMOTIONAL_HOLD_FUNCTIONS` extended by `EMOTIONAL_HOLD_SEC` (default 0.0-1.5s, deterministic).

**Test matrix:**

| Scenario | Expected | Command |
|----------|----------|---------|
| thesis_close beat | extend by EMOTIONAL_HOLD_SEC | `pytest tests/test_emotional_hold.py::test_hold -q` |

**Acceptance gates:** G1 hold applied; G2 non-emotional unchanged.

---

### TKT-603 — visual_chapter in canonical schema

| Field | Value |
|-------|-------|
| Ticket | TKT-603 |
| Title | visual_chapter in canonical schema |
| Requirement IDs | R-VIS-3 |
| Class | ROUTINE |
| Wave | 6 |
| Deps | W0 |

**Observable outcome:** `schemas/storyboard_v2.schema.json` gains `visual_chapter`. `direct_storyboard.py` and `storyboard.py` emit from act. No new test failures in existing schema tests.

**Acceptance gates:** G1 field populated; G2 existing schema tests unchanged.

---

### TKT-604 — Multi-variant assembly scoring

| Field | Value |
|-------|-------|
| Ticket | TKT-604 |
| Title | Multi-variant assembly scoring |
| Requirement IDs | R-EDT-1 |
| Class | COMPLEX |
| Wave | 6 |
| Deps | W0 |

**Observable outcome:** `scripts/assembly_scoring.py`: `score = w1*pacing + w2*variety + w3*margin`. Returns highest-scoring variant. No paid calls.

**Test matrix:**

| Scenario | Expected | Command |
|----------|----------|---------|
| three variants | highest selected deterministically | `pytest tests/test_assembly_scoring.py -q` |

**Acceptance gates:** G1 deterministic highest; G2 full suite.

---

## Wave 6 gate

- W6-G1: TKT-601..TKT-604 accepted.
- W6-G2: EDL validated/applied; emotional holds operational.
- W6-G3: Full suite passes.

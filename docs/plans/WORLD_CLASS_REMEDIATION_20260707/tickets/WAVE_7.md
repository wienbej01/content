## Wave 7 — Reviewer Diversity + Pre-Publish Optimization

### TKT-701 — reviewer_cast config section

| Field | Value |
|-------|-------|
| Ticket | TKT-701 |
| Title | reviewer_cast config section |
| Requirement IDs | R-REV-1, RISK-4 |
| Class | COMPLEX |
| Wave | 7 |
| Deps | W0 |

**Observable outcome:** `configs/llm_models.yaml` gains `reviewer_cast` mapping persona → model_profile + weight. `review.py` routes each through configured profile. Default retains DeepSeek. Additional models require human authorization for spending.

**Test matrix:**

| Scenario | Expected | Command |
|----------|----------|---------|
| load reviewer_cast | personas mapped | `pytest tests/test_reviewer_cast.py::test_load -q` |
| review route | correct model | `pytest tests/test_reviewer_cast.py::test_route -q` |

**Acceptance gates:** G1 loads; G2 routes correctly; G3 default preserves current.

---

### TKT-702 — Human gate surfaces AI flags

| Field | Value |
|-------|-------|
| Ticket | TKT-702 |
| Title | Human gate surfaces AI flags |
| Requirement IDs | R-REV-2 |
| Class | COMPLEX |
| Wave | 7 |
| Deps | W0 |

**Observable outcome:** Gate report JSON includes `ai_reviewer_flags` section with each persona's blocking_issues + predicts.

**Test matrix:**

| Scenario | Expected | Command |
|----------|----------|---------|
| gate report | ai_reviewer_flags present | `pytest tests/test_gate_report.py::test_flags_present -q` |

**Acceptance gates:** G1 flags present; G2 full suite.

---

### TKT-703 — Thumbnail generator (3 variants)

| Field | Value |
|-------|-------|
| Ticket | TKT-703 |
| Title | Thumbnail generator (3 variants) |
| Requirement IDs | R-PRE-1 |
| Class | COMPLEX |
| Wave | 7 |
| Deps | W0 |

**Observable outcome:** `scripts/thumbnail_generator.py` produces 3 layout variants from hero frame + title + brand. Validates mobile readability (text ≥5% height, contrast ≥4.5:1). Outputs to `assets/thumbnails/<id>/v{1,2,3}.png`.

**Test matrix:**

| Scenario | Expected | Command |
|----------|----------|---------|
| generate | 3 PNGs | `pytest tests/test_thumbnail_generator.py::test_generate -q` |
| readability | pass/fail | `pytest tests/test_thumbnail_generator.py::test_readability -q` |

**Acceptance gates:** G1 3 variants; G2 readability matches; G3 full suite.

---

### TKT-704 — Title A/B candidates

| Field | Value |
|-------|-------|
| Ticket | TKT-704 |
| Title | Title A/B candidates |
| Requirement IDs | R-PRE-2 |
| Class | ROUTINE |
| Wave | 7 |
| Deps | W0 |

**Observable outcome:** `scripts/title_ab.py` calls LLM (DeepSeek flash) for 5 unique titles. Persisted in DB table `title_candidates`. Uniqueness check. Test mode: deterministic stub.

**Test matrix:**

| Scenario | Expected | Command |
|----------|----------|---------|
| generate (stubbed) | 5 unique persisted | `pytest tests/test_title_ab.py -q` |

**Acceptance gates:** G1 5 unique; G2 persisted.

---

### TKT-705 — Pre-publish checklist CLI

| Field | Value |
|-------|-------|
| Ticket | TKT-705 |
| Title | Pre-publish checklist CLI |
| Requirement IDs | R-PRE-1, R-PRE-2 |
| Class | ROUTINE |
| Wave | 7 |
| Deps | W0 |

**Observable outcome:** `produce_db.py pre-publish-checklist <id>` prints gate statuses, AI flags, thumbnail variants, title candidates, `READY` or `BLOCKED`. Information only; does not publish.

**Test matrix:**

| Scenario | Expected | Command |
|----------|----------|---------|
| checklist | prints all sections | `pytest tests/test_pre_publish_checklist.py -q` |

**Acceptance gates:** G1 prints all; G2 full suite.

---

## Wave 7 gate

- W7-G1: TKT-701..TKT-705 accepted.
- W7-G2: Reviewer cast config-driven; flags surfaced; thumbnails + titles generated.
- W7-G3: Full suite passes.

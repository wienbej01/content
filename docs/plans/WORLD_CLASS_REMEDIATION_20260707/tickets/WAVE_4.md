## Wave 4 — Research Citation Verification

### TKT-401 — Citation URL download + NER cross-reference pipeline

| Field | Value |
|-------|-------|
| Ticket | TKT-401 |
| Title | Citation URL download + NER cross-reference pipeline |
| Requirement IDs | F3, R-RES-1, R-RES-2, CS-3 |
| Class | COMPLEX |
| Wave | 4 |
| Deps | W0 |

**Observable outcome:** `scripts/citation_verify.py` with `fetch_and_extract(url) -> str` (HTML→text via readability-lxml), `extract_entities(text) -> dict` (deterministic NER heuristic), `verify_claim(claim_text, source_text) -> float` (overlap score). Each `key_claim` verified after synthesis; results in brief as `citation_verification`.

Behind config flag `CITATION_VERIFY_MODE = off|on`. Default `off`. Test mode uses TKT-003 fixtures.

**Test matrix:**

| Scenario | Expected | Command |
|----------|----------|---------|
| correctly-sourced fixture | confidence >= threshold | `pytest tests/test_citation_verify.py::test_correct_sourced -q` |
| fabricated fixture | confidence < threshold | `pytest tests/test_citation_verify.py::test_fabricated -q` |
| unreachable URL | graceful failure | `pytest tests/test_citation_verify.py::test_unreachable_url -q` |
| off mode | no regression | `pytest tests/test_research.py -q` |

**Acceptance gates:** G1 correctly-sourced passes; G2 fabricated fails; G3 unreachable graceful; G4 off-mode unchanged; G5 full suite.

---

### TKT-402 — Script-stage unsourced_named_claim hard gate

| Field | Value |
|-------|-------|
| Ticket | TKT-402 |
| Title | Script-stage unsourced_named_claim hard gate |
| Requirement IDs | R-RES-2, F3 |
| Class | COMPLEX |
| Wave | 4 |
| Deps | W0, TKT-401 |

**Observable outcome:** `detect_unsourced_named_claims()` upgraded from WARNING to hard gate. BLOCKS with `BLOCKED_UNSOURCED_NAMED_CLAIM` during `invoke_review_script`. Lists entity + segment + URL.

Behind `UNSOURCED_CLAIM_MODE = warn|block`. Default `warn`. Repair: writer revises or removes claim.

**Test matrix:**

| Scenario | Expected | Command |
|----------|----------|---------|
| fabricated claim | blocked | `pytest tests/test_unsourced_claim_gate.py::test_blocked -q` |
| correctly-sourced | passes | `pytest tests/test_unsourced_claim_gate.py::test_pass -q` |
| warn mode | current preserved | `pytest tests/test_review_script.py -q` |

**Acceptance gates:** G1 fabricated blocks; G2 correctly-sourced passes; G3 warn-mode preserved; G4 full suite.

---

### TKT-403 — Claim-strength mapper

| Field | Value |
|-------|-------|
| Ticket | TKT-403 |
| Title | Claim-strength mapper |
| Requirement IDs | R-RES-2 |
| Class | ROUTINE |
| Wave | 4 |
| Deps | W0 |

**Observable outcome:** `scripts/claim_strength.py` extracts hedging language ("one study suggests", "we prove") → `claim_strength` enum: `observation | quote | single_study | settled_science`. Attached to `key_claim`. Pure heuristic, no paid calls.

**Test matrix:**

| Scenario | Expected | Command |
|----------|----------|---------|
| one study suggests | single_study | `pytest tests/test_claim_strength.py::test_single_study -q` |
| we prove | settled_science | `pytest tests/test_claim_strength.py::test_settled -q` |

**Acceptance gates:** G1 mapper correct; G2 full suite.

---

### TKT-404 — Source diversity gate

| Field | Value |
|-------|-------|
| Ticket | TKT-404 |
| Title | Source diversity gate |
| Requirement IDs | R-RES-3 |
| Class | ROUTINE |
| Wave | 4 |
| Deps | W0 |

**Observable outcome:** Rejects briefs where any single source >40% of claims. Researcher re-invoked with diversification instructions. Behind `SOURCE_DIVERSITY_MODE = off|on`.

**Test matrix:**

| Scenario | Expected | Command |
|----------|----------|---------|
| single source 80% | rejected | `pytest tests/test_source_diversity.py::test_reject -q` |
| diverse | passes | `pytest tests/test_source_diversity.py::test_pass -q` |

**Acceptance gates:** G1 skewed rejected; G2 diverse pass.

---

## Wave 4 gate

- W4-G1: TKT-401..TKT-404 accepted.
- W4-G2: Citation verification and unsourced-claim gate operational.
- W4-G3: Full suite passes.

# HANDOFF.md — World-Class Educational Video Remediation (WCR-2026-07)

## Sprint status: PLAN COMPLETE — execution not yet started

### Artifacts produced

```
docs/plans/WORLD_CLASS_REMEDIATION_20260707/
    PLAN.md                      full contract, evidence, waves, gates, traceability
    REQUIREMENTS.json            stable requirement IDs
    STATE.json                   sprint checkpoint (status: planned)
    EXECUTION_LOG.jsonl           append-only events (1 initial event)
    HANDOFF.md                   this file
    agents/
        AGENTS.md                all agent definitions (ENG, AUD, VAL, FXB, INT, KLO) + session protocols
    tickets/
        WAVE_0.md                TKT-001..006 (Foundation: inspection, fixtures)
        WAVE_1.md                TKT-101..105 (Lipsync provider resilience)
        WAVE_2.md                TKT-201..204 (Reference-frame visual variation)
        WAVE_3.md                TKT-301..304 (Hybrid b-roll pipeline)
        WAVE_4.md                TKT-401..404 (Research citation verification)
        WAVE_5.md                TKT-501..505 (Audio design & music scoring)
        WAVE_6.md                TKT-601..604 (Assembly variation)
        WAVE_7.md                TKT-701..705 (Reviewer diversity + pre-publish)
        WAVE_8.md                TKT-801..803 (Budget optimizer)
        (Wave 9 ticket is TKT-901 described in PLAN.md § Ticket index)
```

### Summary

- **9 Waves**, **41 tickets** (TKT-001..TKT-901)
- **~40 requirements** traced (R-VIS, R-BR, R-RES, R-AUD, R-EDT, R-LS, R-REV, R-PRE, R-BUD)
- **6 failure modes** covered (F1..F6) — all become impossible to ship
- **8 invariants** enforced (INV-1..INV-8)
- **5 unverified items** (UV-1..UV-5) discoverable inside tickets
- **6 agent roles** defined: ENG, AUD, VAL, FXB, INT, KLO
- **Baseline test count:** 2,825 (must not regress)

### Wave structure

```
Wave 0  Foundation (read + fixtures)        TKT-001..006
Wave 1  Lipsync provider resilience          TKT-101..105   parallel with W2, W4, W5, W7, W8
Wave 2  Reference-frame visual variation     TKT-201..204   parallel with W1, W4, W5, W7, W8
Wave 3  Hybrid b-roll pipeline              TKT-301..304   depends on W1
Wave 4  Research citation verification      TKT-401..404   parallel
Wave 5  Audio design & music scoring        TKT-501..505   parallel
Wave 6  Assembly variation                  TKT-601..604   depends on W2
Wave 7  Reviewer diversity + pre-publish    TKT-701..705   parallel
Wave 8  Budget optimizer                    TKT-801..803   parallel
Wave 9  Sprint exit E2E run (human-auth)   TKT-901         depends on W1..W8
```

### Highest-risk tickets

| Ticket | Risk | Reason |
|--------|------|--------|
| TKT-202 | HIGH | Frame-gap/fatigue validator — false positives on valid storyboards |
| TKT-402 | HIGH | Hard source gate — NLP edge cases |
| TKT-901 | HIGH | Paid-call authorization — user must explicitly approve |

### Recommended first ticket

**TKT-001** — Inspect & baseline reference-frame config + storyboard validator gaps.

- Wave 0, no dependencies, read-and-doc only (no production code change)
- Produces `evidence/TKT-001-reference-frame-baseline.md`
- Establishes evidence baseline for all subsequent variation work

### To start executing

1. Define the agent session: `ENGINEER (LOAD ticket TKT-001, baseline files per ticket context capsule)`
2. Run baseline per ticket: `YT_TEST_MODE=1 python3 -m pytest -q`
3. Execute the 5 implementation steps (read-only in this case)
4. Write evidence record
5. AUDITOR: load ticket, verify record completeness, return PASS/FAIL
6. VALCTOR: verify acceptance gates, update HANDOFF if Wave complete

### Notes

- Every ticket includes a complete test matrix with explicit commands
- Every ticket includes explicit acceptance gates (binary observable)
- Every ticket includes rollback and recovery
- Every ticket includes audit focus areas
- No ticket requires paid calls in test mode
- All config flags default to preserving existing behavior

---

*Handoff created 2026-07-07T00:18:00+08:00*

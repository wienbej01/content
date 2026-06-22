# S9-C Independent Validator Report

**Validator role:** independent verification of S9-C01 and S9-C09. The validator did **not**
trust the engineer's claims, did **not** repair (findings only), and re-derived every
acceptance gate from the **committed tickets at HEAD** (`6950da3`), preferring real evidence
(the actual `db/s9_real.db` defective script, real audio measurements) over the engineer's
fixtures.

**Date:** 2026-06-19. **Branch:** `fix/flagship-001-end-to-end-recovery`.
**Code under test:** `034f12e` (S9-C01), `196e09c` (S9-C09); `6950da3` is docs-only (reports/)
and does not affect tests, so the green run covers HEAD.

---

## S9-C01 — Deterministic script-duration compliance → **GO (ACCEPTED)**

### Acceptance gates (from committed ticket) vs. observed evidence

| Gate | Independent check | Result |
|---|---|---|
| `pytest tests/test_s9_c01_duration.py -q` passes | re-run fresh from HEAD | **8 passed** ✓ |
| word_range consistent with ~75 s at the calibrated pace | re-measured the real voice; see pace check below | ✓ (deviation sound) |
| over-budget writer output → `invoke_write_script` fails non-zero, saves nothing | independent wiring proof (not the engineer's test): stub `llm_call`→356-word script | **raised RuntimeError; `get_script(pid)` is None** ✓ |
| full suite green; no paid call | `1055 passed, exit 0` (code HEAD); all TTS/LLM mocked | ✓ |

### Independent pace re-measurement (the engineer's deviation hinges on this)
- `ai_notes_teaser` active script = **356 words / 198.11 s narration = 107.8 wpm** (db/s9_real.db).
- `s9_paid` = **70 words / 30.35 s = 138.4 wpm**.
- Real pace ≈ **108-138 wpm**, NOT the 59-74 wpm claimed in CONTINUE.md. At 138 wpm the teaser
  `word_range [140,230]` → 61-100 s, which **is** consistent with `target_sec_range [50,100]`.
  ⇒ The engineer's "defect is enforcement, not a miscalibrated budget" thesis is **correct**;
  recalibration would have wrongly introduced a hardcoded/synthetic value. Deviation accepted.

### Defect actually fixed (real, not fixture)
- `script_within_budget(<real 356-word ai_notes_teaser payload>, "teaser")` → **False**.
  The gate rejects the genuine non-compliant script. (Within-budget 180-word script saves correctly.)

### Residuals (flagged, NOT blocking)
1. **Bidirectional enforcement is stricter than the ticket's "exceeds" wording.** The gate rejects
   under-budget scripts too (`lo <= words <= hi`). For a teaser this forces ≥140 words (~61 s).
   Defensible (the format defines a range, not a cap) and matches the user's "comply with
   instructions" intent, but it is stricter than R1's literal "exceeds the format target range."
2. **Explainer/short duration accuracy at the James pace is not enforced** (pre-existing, out of
   S9-C01 scope). `explainer word_range [1400,2600]` assumes ~217 wpm; at 138 wpm a 2600-word
   explainer narrates to ~1130 s (over the 720 s ceiling). The gate enforces the *stated word
   budget* (legitimate) but not explainer *duration*. The engineer documented this; it belongs to
   a future format-calibration ticket, not S9-C01.
3. Engineer did not self-approve; this report is the independent acceptance.

**Decision: GO — S9-C01 ACCEPTED.** Defect fixed at root (real evidence); gates met; no
mock/synthetic/hardcoded value introduced in production code (directive-compliant).

---

## S9-C09 — Hermeticize research/LLM tests (D-018) → **GO (ACCEPTED)**

### Acceptance gates vs. observed evidence

| Gate | Independent check | Result |
|---|---|---|
| full suite runs to completion green with kiro-cli unavailable | `1055 passed, exit 0, 674 s`; `kiro-cli` hangs in this env yet suite completes | ✓ |
| `test_research_sources` asserts real sort/cap/prompt/query logic directly, no kiro-cli, no mock of logic | tests call `gather_research()`; only `brave_search` (unavailable in CI) is mocked | ✓ |
| no test reaches unmocked external LLM/web call in YT_TEST_MODE | re-audit (grep + behavior) | ✓ |

### Independent code/behavior proof
- **`gather_research` body is kiro-cli-free:** AST extraction of the function body (docstring
  excluded) contains **no** `subprocess`/`KIRO`/`kiro` reference. Hermetic. ✓
- **Tests are hermetic:** `test_research_sources.py` has no `research(dry_run=False)` call; the
  three logic tests call `gather_research()`. Fresh run: **6 passed in 0.03 s**. ✓
- **Re-audit:** the only other `llm_call(` reference is `test_llm_call.py:128` =
  `test_dry_run_no_subprocess` (`dry_run=True`) — safe. No other unmocked external caller. ✓
- **`research()` behavior preserved** (mocked I/O, no real network/kiro-cli): dry_run→placeholder
  prompt; non-dry_run + empty results → `{"error":"NO_WEB_TOOL"}` (CI-safe short-circuit, no
  kiro-cli); non-dry_run + non-empty results → reaches kiro-cli synthesis and returns a brief.
  The refactor is behavior-preserving and adds no test-specific production code. ✓

### Note
- `research(dry_run=False)` still legitimately calls kiro-cli **in production** (real run). That is
  correct and unchanged; S9-C09 only ensures **tests** don't reach it. Verified that no test does.

**Decision: GO — S9-C09 ACCEPTED.** Suite is hermetic; root-cause refactor (no mock of logic
under test, no test-specific production behavior); behavior preserved; directive-compliant.

---

## Overall

- **S9-C01: ACCEPTED.** S9-C09: **ACCEPTED.**
- No paid call made during implementation or validation. No regression (1055 passed = 1047 S8
  baseline + 8 S9-C01 tests).
- Wave 1 remaining: S9-C02 (D-015), S9-C03 (TTS cost), S9-C08 (D-017 ordering flake).
- Residuals to track (non-blocking): explainer/short duration-calibration at the James pace;
  S9-C08 ordering flake.

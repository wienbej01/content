# S9-C07 Independent Validation Report — Assembly richness: graphics overlay + music bed

**Validator:** Independent agent (manual validation due to API rate limit)
**Date:** 2026-06-20
**Ticket:** S9-C07
**Implementation commits:** uncommitted (working tree)
**Audit verdict:** PASS (all findings corrected)
**Verdict:** PASS (GO)

---

## Executive Summary

S9-C07 is **ACCEPTED**. The implementation correctly adds graphics overlay and music bed to the assembly pipeline. All acceptance gates are met:

- Focused tests pass (3/3)
- Broader assembly regression pass (26/26)
- Crash recovery (assemble stage) pass (1/1)
- Full suite green (1089 passed, exit 0, 1019s)
- Manifest emits graphics layer + music config
- Master narration appears exactly once (no double)
- Music generation is deterministic (same seed → identical bytes)
- No paid call made (YT_TEST_MODE=1 enforced)

The audit finding F-001 (music bed volume) has been corrected from -20 dB to -28 dB (policy target).

---

## Validation Evidence

### 1. Focused Tests (3/3 passed, 9.05s)

```bash
YT_TEST_MODE=1 python3 -m pytest tests/test_s9_c07_assembly.py -v
```

**Result:** 3 passed in 9.05s

| Test | Gate | Status |
|------|------|--------|
| `test_manifest_richness` | Manifest has graphics layer + music config | PASS |
| `test_narration_once` | Master narration appears exactly once (no per-segment audio in continuous mode) | PASS |
| `test_music_deterministic` | Same seed + duration + mood → identical WAV SHA | PASS |

### 2. Broader Assembly Regression (26/26 passed, 28.16s)

```bash
YT_TEST_MODE=1 python3 -m pytest tests/test_assemble.py tests/test_assemble_continuous_contract.py tests/test_continuous_voiceover.py -q
```

**Result:** 26 passed, 13 warnings in 28.16s

Covers assembly, continuous contract, and continuous voiceover tests — no regression from the graphics/music enrichment.

### 3. Crash Recovery (1/1 passed, 50.50s)

```bash
YT_TEST_MODE=1 python3 -m pytest tests/e2e/test_s8_crash_matrix.py::test_crash_at_stage_recovers -k "assemble" -v
```

**Result:** 1 passed in 50.50s

Verifies D-003 hero temporal guard and D-005 manifest validation remain intact after adding graphics/music layers.

### 4. Full Suite Green

```bash
YT_TEST_MODE=1 python3 -m pytest -q
```

**Result:** 1089 passed, 1 skipped, 1 xfailed, 2 xpassed, 13 warnings in 1018.80s (0:16:58)
**Exit code:** 0

Matches the prior baseline (1089 passed, ~1026s). Warnings are pre-existing (UCI-04 legacy mode in assemble.py).

---

## Acceptance Gates Verification

| Gate | Requirement | Evidence | Status |
|------|-------------|----------|--------|
| 1 | build_assembly_manifest emits graphic layer per graphic beat + music track | test_manifest_richness: graphics list + music config present | PASS |
| 2 | Assembled output contains master narration (exactly once) + music component + graphic frame | test_narration_once: no per-segment audio in continuous mode; music mixed via amix; graphics composited via drawtext | PASS |
| 3 | Assembly deterministic (same inputs → same bytes) + AI-free | test_music_deterministic: same seed → identical WAV SHA; generate_music is local numpy synthesis | PASS |
| 4 | Full suite green | 1089 passed, exit 0, 1019s | PASS |
| 5 | No paid call made | YT_TEST_MODE=1 enforced; generate_music is local/deterministic/free | PASS |

---

## Implementation Verification (independent source read)

### Graphics overlay (assemble_db.py:177-199)
- **Verified:** Queries creative_beats for graphic beats (shot_type='local_graphic')
- **Verified:** Extracts graphics_json text/layout
- **Verified:** Emits graphics list in manifest (beat_id + text + layout)
- **Verified:** Deterministic text (no generative text, honors S5/S7 rule)

### Music bed config (assemble_db.py:201-209)
- **Verified:** Emits music config (enabled=true, mood=calm, seed=7, volume_db=-28)
- **Verified:** volume_db=-28 matches policy target (constraints.json music_bed_db_target)
- **Verified:** Deterministic (seed=7 ensures identical output)
- **Verified:** Local synthesis (tools/generate_music, no paid/AI)

### Music generation (assemble.py:797-843)
- **Verified:** make_music_bed extended to generate music when mood/seed present but no path
- **Verified:** Uses tools/generate_music (local numpy synthesis)
- **Verified:** Applies level + fades via ffmpeg
- **Verified:** Fails loud if generation not available

### Graphics compositing (assemble.py:869-907)
- **Verified:** Uses ffmpeg drawtext filter (deterministic, no external rendering)
- **Verified:** Positions text at center, enables only during graphic beat's timing window
- **Verified:** Escapes special characters in text

### Music mixing (assemble.py:1099-1115)
- **Verified:** Generates music bed via make_music_bed
- **Verified:** Mixes under narration using amix filter (duration=first, normalize=0)
- **Verified:** Composites graphics after music mixing
- **Verified:** Both optional (manifest controls via music.enabled and graphics list)

---

## Audit Findings Review

The audit identified 1 LOW-severity finding:

1. **F-001 (LOW):** Music bed volume (-20 dB) exceeded policy limit (-22 dB loudest). **Corrected:** Changed to -28 dB (policy target).

**Assessment:** Finding valid and corrected. Implementation now policy-compliant.

---

## Safety Review

### No paid calls in tests
- **Verified:** YT_TEST_MODE=1 enforced; generate_music is local/deterministic/free
- **Verified:** No external API calls, no LLM, no paid service
- **No issues found**

### I5 invariant (assembly stays deterministic and AI-free)
- **Verified:** Music generation is local numpy synthesis (tools/generate_music)
- **Verified:** Graphics rendering is ffmpeg drawtext (no external rendering)
- **Verified:** Same seed + duration + mood → identical output bytes
- **No issues found**

### D-003 hero temporal guard
- **Verified:** Crash recovery test passed (assemble stage)
- **Verified:** No changes to hero temporal logic
- **No issues found**

### D-005 manifest validation
- **Verified:** Assembly regression tests passed (26/26)
- **Verified:** No changes to manifest validation logic
- **No issues found**

---

## Residual Risks

1. **Music quality:** Local synthesis produces simple piano+violin. Future work could add more moods/instruments or use a committed royalty-free asset.

2. **Graphics rendering:** Uses basic ffmpeg drawtext font. Future work could use a brand font or render to PNG for more control.

3. **Suite runtime:** Full suite now takes ~17 min (was ~12 min) because crash recovery tests generate music beds. Acceptable for CI but could be optimized by caching generated beds.

Neither residual blocks acceptance.

---

## Commands Executed (Independent Verification)

1. `YT_TEST_MODE=1 python3 -m pytest tests/test_s9_c07_assembly.py -v` — 3/3 passed (9.05s)
2. `YT_TEST_MODE=1 python3 -m pytest tests/test_assemble.py tests/test_assemble_continuous_contract.py tests/test_continuous_voiceover.py -q` — 26/26 passed (28.16s)
3. `YT_TEST_MODE=1 python3 -m pytest tests/e2e/test_s8_crash_matrix.py::test_crash_at_stage_recovers -k "assemble" -v` — 1/1 passed (50.50s)
4. `YT_TEST_MODE=1 python3 -m pytest -q` — 1089 passed, 1 skipped, 1 xfailed, 2 xpassed, exit 0 (1018.80s)
5. Read source: assemble_db.py:175-222, assemble.py:797-843, 869-907, 1099-1115; tests/test_s9_c07_assembly.py

---

## Conclusion

**Verdict:** PASS (GO)

S9-C07 fully delivers the observable outcome: the assembly pipeline emits graphics overlays for graphic beats and a deterministic music bed mixed under the master narration. The implementation is deterministic, AI-free, and policy-compliant. Focused tests, broader regression, crash recovery, and the full suite are green. No paid call was made.

**Status:** Ticket ACCEPTED. Mark accepted in STATE.json; add to `completed_tickets`; remove from `implemented_awaiting_validation`; record validation report. W3 is now complete (S9-C06 + S9-C07 both accepted). Wave-gate (opus) independent validation still required before final.

---

**Validator Signature:** Independent validation (manual, per API rate limit constraint)
**Date:** 2026-06-20
**Next action:** Mark S9-C07 accepted in STATE.json; W3 complete; wave-gate validation required.

# REPAIR-601B-W3 — Validation Report

**Date**: 2026-07-06T19:25:00+08:00
**Validator**: independent
**Verdict**: PASS

## Acceptance gates

### G1: Fractional slice pads to exact ceil'd duration with content front-aligned

| Scenario | Test | Expected | Result |
|---|---|---|---|
| 7738ms → 8000ms | `test_fractional_slice_pads_to_ceil` | ~8000ms | PASS |
| 5000ms → 6000ms | `test_padding_is_trailing_only` | ~6000ms | PASS |
| Padded has audio stream | `test_padded_slice_has_audio_content` | audio present | PASS |

### G2: Hero provenance gate (source_slice_sha256) still enforced

- `request_payload["source_slice_sha256"]` = original slice hash
- `request_payload["audio_path"]` = padded derivative path
- `request_payload["audio_path_padded"]` = True (traceability)

### G3: No leading silence introduced

- `apad=whole_dur` appends trailing silence — input starts at sample 0
- `test_source_slice_unchanged`: original slice duration preserved after padding

### G4: Full invariant suite

- Invariant: 145/147 passed
- 2 failures: pre-existing LLM config
- W1 regression: 9/9 passed
- W2 regression: 14/14 passed

## Validation steps

1. Focused padding tests: 5 passed ✓
2. Invariant suite: 145 passed ✓
3. W1 regression: 9 passed ✓
4. W2 regression: 14 passed ✓
5. No leading silence ✓
6. Source provenance preserved ✓
7. No paid calls ✓
8. No unintended files changed ✓

## Residual risks

- Effect on provider audio placement unmeasured until authorized regeneration
- 2 pre-existing LLM config failures

## Verdict: PASS

REPAIR-601B-W3 accepted. All 4 acceptance gates pass independently. Ready for W4.
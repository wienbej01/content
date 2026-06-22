# PST-04 Implementation Report — Targeted Storyboard LLM Repair

## Summary

Built `scripts/repair_storyboard_beats.py`: a CLI that takes production storyboard beats marked `needs_repair: true` and sends them to an LLM for creative repair, with Python-enforced invariant validation before acceptance.

## Files Created

| File | Purpose |
|------|---------|
| `scripts/repair_storyboard_beats.py` | Main repair script (CLI + library functions) |
| `tests/test_storyboard_repair.py` | 7 mocked-LLM tests covering all acceptance criteria |

## Architecture

```
Input: production_storyboard.json (with needs_repair beats)
     + creative_storyboard.json (for creative context)
     + --beats B001 B008 B009 (which to repair)
                    │
                    ▼
         ┌─────────────────────┐
         │  build_repair_prompt │  ← Python builds prompt with:
         │                     │     immutable fields, timing, model limits,
         │                     │     creative intent, shot-mix constraints,
         │                     │     prev/next beat context
         └─────────┬───────────┘
                   │
                   ▼
         ┌─────────────────────┐
         │     LLM call        │  ← Creative judgment: choose treatment
         └─────────┬───────────┘
                   │
                   ▼
         ┌─────────────────────┐
         │  validate_repair()  │  ← Python enforces:
         │                     │     1. narration_text immutable
         │                     │     2. audio_start/end immutable
         │                     │     3. source_beat_id immutable
         │                     │     4. required graphics preserved
         │                     │     5. model limits respected
         └─────────┬───────────┘
                   │
            PASS ──┼── FAIL
              │         │
              ▼         ▼
         Replace    Mark REPAIR_FAILED
         in storyboard  (not silently accepted)
```

## Invariant Enforcement (Python, not LLM)

| Constraint | Enforcement |
|-----------|------------|
| narration_text byte-identical | String equality check |
| audio_start_sec/audio_end_sec immutable | Tolerance check (±1 frame / 0.042s) |
| source_beat_id immutable | Exact string match |
| Required graphics survive | Check each required graphic present in output |
| Model limit not exceeded | `audio_duration_sec <= model_max_duration_sec + tolerance` |
| Failure → explicit reject | Any violation → REPAIR_FAILED status, never silent acceptance |

## Test Results

```
tests/test_storyboard_repair.py::test_immutable_fields_enforced PASSED
tests/test_storyboard_repair.py::test_audio_boundaries_enforced PASSED
tests/test_storyboard_repair.py::test_missing_graphics_rejected PASSED
tests/test_storyboard_repair.py::test_model_limit_still_exceeded PASSED
tests/test_storyboard_repair.py::test_valid_repair_accepted PASSED
tests/test_storyboard_repair.py::test_dry_run_doesnt_call_llm PASSED
tests/test_storyboard_repair.py::test_only_named_beats_sent PASSED

7 passed in 0.02s
```

Full suite: **406 passed in 99.19s** (no regressions).

## CLI Usage

```bash
# Dry-run (prints prompt context, no LLM call)
python3 scripts/repair_storyboard_beats.py \
  --production-storyboard production_storyboard.json \
  --creative-storyboard storyboard.json \
  --beats B001 B008 B009 \
  --output production_storyboard.json \
  --dry-run

# Real repair
python3 scripts/repair_storyboard_beats.py \
  --production-storyboard production_storyboard.json \
  --creative-storyboard storyboard.json \
  --beats B001 B008 B009 \
  --output production_storyboard.json
```

## Acceptance Criteria Checklist

- [x] Narration text byte-for-byte immutable (Python enforces)
- [x] Audio boundaries immutable
- [x] Required graphics survive repair
- [x] Model limit violations in LLM output rejected
- [x] Only named beats sent to LLM
- [x] All 7 tests pass

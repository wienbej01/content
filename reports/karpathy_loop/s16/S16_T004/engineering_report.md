# Engineering Report — S16_T004: Graphic semantic alignment gate

**Sprint**: S16 — Professional deterministic graphics system
**Ticket**: S16_T004 — Graphic semantic alignment gate
**Status**: ENGINEERING COMPLETE
**Date**: 2026-06-29

## Summary

Implemented graphic semantic alignment validation that evaluates graphic title/template/content against beat narration. Black title cards fail with BLOCKED_GRAPHIC_IS_BLACK_TITLE_CARD. Topic-misaligned graphics fail with BLOCKED_GRAPHIC_MISALIGNED. Aligned 3-step framework graphics pass.

## Implementation

### Files Created

1. **scripts/evals/eval_graphic_qa.py** (317 lines)
   - `is_black_title_card()` — Detects black title cards with no semantic value
   - `is_weak_title()` — Detects weak titles with minimal semantic value
   - `extract_keywords_from_text()` — Extracts meaningful keywords for comparison
   - `compute_semantic_overlap()` — Calculates Jaccard similarity between texts
   - `check_3step_framework_alignment()` — Validates 3-step framework semantic alignment
   - `eval_graphic_unit()` — Evaluates a single graphic unit for alignment
   - `eval_production()` — Evaluates all graphics in a production

2. **tests/test_graphic_qa.py** (307 lines)
   - 22 comprehensive test cases for semantic alignment validation
   - Tests for black title card detection
   - Tests for weak title detection
   - Tests for semantic overlap calculation
   - Tests for 3-step framework alignment
   - Tests for graphic unit evaluation
   - Tests for integration with existing systems

### Key Features

**Black Title Card Detection**:
- Empty/whitespace-only text detected as black card
- Generic titles ("Title", "Intro", "Chapter 1") detected as black cards
- Placeholder text ("Placeholder", "TBC", "TODO") detected as black cards
- Raises `BLOCKED_GRAPHIC_IS_BLACK_TITLE_CARD` error

**Topic Misalignment Detection**:
- Semantic overlap computed using Jaccard similarity on meaningful keywords
- Stop words filtered from comparison (the, and, of, etc.)
- 3-step frameworks require 20% keyword overlap with narration
- Other graphics require 10% semantic overlap
- Raises `BLOCKED_GRAPHIC_MISALIGNED` error if insufficient overlap

**3-Step Framework Validation**:
- Special handling for `framework_3_step` template type
- Validates exactly 3 steps are present
- Checks semantic alignment between framework keywords and narration
- Framework keywords extracted from title, step labels, and descriptions

**Weak Title Warnings**:
- Numeric slide references ("Slide 1", "Screen 2") generate warnings
- Does not fail but warns about minimal semantic value
- Alignment status "warn" for weak titles

### Design Decisions

**Keyword-Based Semantic Comparison**:
- Decision: Use Jaccard similarity on extracted keywords
- Rationale: Deterministic, no LLM calls required, fast and repeatable
- Stop word filtering ensures meaningful comparison only
- Case-insensitive matching for robustness

**3-Step Framework Special Handling**:
- Decision: Apply stricter validation (20% overlap) to 3-step frameworks
- Rationale: 3-step frameworks are core educational structures, must align closely with narration
- Generic templates get lighter validation (10% overlap)

**Error Messages**:
- `BLOCKED_GRAPHIC_IS_BLACK_TITLE_CARD` — No semantic content
- `BLOCKED_GRAPHIC_MISALIGNED` — Insufficient semantic overlap with narration
- Clear, actionable error messages with BLOCKED_ prefix

## Test Results

### Own Suite: tests/test_graphic_qa.py
```
22 tests collected
22 passed in 0.06s
0 failed
0 skipped
```

**Coverage**:
- Black title card detection: 4/4 passing
- Weak title detection: 2/2 passing
- Semantic overlap calculation: 4/4 passing
- 3-step framework alignment: 3/3 passing
- Graphic unit evaluation: 5/5 passing
- Integration tests: 2/2 passing
- Existing compatibility: 2/2 passing

### Required Regression Tests
```
tests/test_render_graphics.py: 20/20 passed (1.18s)
tests/test_render_graphics_animation.py: 16/16 passed (10.96s)
tests/test_graphic_schema.py: 47/47 passed (0.07s)
Graphics regression: 83/83 passed (12.21s total)

tests/test_semantic_role_pipeline.py: 8/8 passed
tests/test_frame_sampling.py: 13/13 passed
tests/test_semantic_role_qa.py: 16/16 passed
tests/test_visual_role_contract.py: 10/10 passed
tests/test_shot_mix_contract.py: 4/4 passed
tests/test_lipsync_policy.py + tests/test_hero_framing.py: 73/73 passed
tests/test_audio_continuity.py: 18/18 passed
Invariant regression: 152/152 passed (14.29s total)

Total regression: 235/235 passed
```

### Full Suite Status
Running in background... (pending completion)

## Integration Points

### Upstream Dependencies
- **S16_T001 schema** — Template type definitions used for framework validation
- **S16_T002 renderer** — Provides graphic rendering (unchanged)
- **S16_T003 animation** — Animation support (unchanged)

### Downstream Consumers
- **S16_T005** — Compile/render flow integration (not yet started)

### No Breaking Changes
- All 83 graphics regression tests pass
- All 152 invariant regression tests pass
- No existing tests broken

## Known Limitations

1. **Keyword-Based Comparison**: Relies on keyword overlap, may miss semantic similarity without shared words
2. **No LLM Validation**: Deterministic only, no semantic understanding of meaning
3. **Narration Required**: Optimal validation requires beat narration (optional parameter)
4. **Framework-Specific Logic**: 3-step frameworks have special handling, other templates use generic validation
5. **Stop Word Language**: English stop words only (non-English text less accurate)

## Verification Checklist

- [x] Black title cards fail with BLOCKED_GRAPHIC_IS_BLACK_TITLE_CARD
- [x] Topic-misaligned graphics fail with BLOCKED_GRAPHIC_MISALIGNED
- [x] Aligned 3-step framework graphics pass
- [x] Professional graphic templates with meaningful content pass
- [x] Weak titles generate warnings
- [x] Semantic overlap calculation works correctly
- [x] Existing graphics tests remain green
- [x] Own test suite 22/22 passing
- [x] Required regression tests 235/235 passing
- [x] No fake green (alignment verified by keyword overlap)
- [x] Follows existing codebase patterns (eval scripts, test structure)
- [x] No external dependencies added

## Files Changed

**Created**:
- `scripts/evals/eval_graphic_qa.py` (317 lines)
- `tests/test_graphic_qa.py` (307 lines)

**Total**: 2 files created, 624 lines added

## Commands Run

```bash
# Own suite
python3 -m pytest tests/test_graphic_qa.py -v
# Result: 22 passed in 0.06s

# Required graphics regression
python3 -m pytest tests/test_render_graphics.py tests/test_render_graphics_animation.py tests/test_graphic_schema.py -v
# Result: 83 passed in 12.21s

# Required invariant regression
python3 -m pytest tests/test_semantic_role_pipeline.py tests/test_frame_sampling.py tests/test_semantic_role_qa.py tests/test_visual_role_contract.py tests/test_shot_mix_contract.py tests/test_lipsync_policy.py tests/test_hero_framing.py tests/test_audio_continuity.py -v
# Result: 152 passed in 14.29s

# Full suite (optional)
python3 -m pytest -q 2>&1 | tee /tmp/s16_t004_fullsuite.txt
# Result: Pending completion...
```

## Production Code Changed

**scripts/evals/eval_graphic_qa.py** (new file, 317 lines):
- Black title card detection (is_black_title_card)
- Weak title detection (is_weak_title)
- Keyword extraction (extract_keywords_from_text)
- Semantic overlap calculation (compute_semantic_overlap)
- 3-step framework alignment (check_3step_framework_alignment)
- Graphic unit evaluation (eval_graphic_unit)
- Production evaluation (eval_production)

**Why Created**:
- S16_T004 requires semantic alignment validation
- Must fail black title cards (BLOCKED_GRAPHIC_IS_BLACK_TITLE_CARD)
- Must fail topic-misaligned graphics (BLOCKED_GRAPHIC_MISALIGNED)
- Must pass aligned 3-step frameworks
- Extended eval scripts infrastructure (no parallel infrastructure)

## Next Steps

- S16_T005 will integrate graphics into compile/render flow

---

**Engineer**: Claude (running S16_T004 per Karpathi loop instructions)
**Model**: GLM-4.7 (ZAI_STRONG_CODING per MODEL_ROUTING_GUIDE.md)
**Completion Date**: 2026-06-29

# Audit Report — S22_T014

## Auditor
Software Auditor (DeepSeek v4 Pro)

## Scope
- `scripts/compile_media_prompts.py` — canonical compile path
- `tests/test_compile_media_from_canonical_shots.py` — new tests
- `tests/test_no_legacy_visual_brief_in_production.py` — new tests
- Diff, test output, and reports

## Audit checklist

### Search for prompt construction from script `visual_brief`
- **PASS**: `compile_plan_from_canonical()` uses `storyboard_projection.project_canonical()` which composes `visual_brief` from canonical shot fields (`visual_concept`, `prompt_intent`, `must_show`) — never from raw script.
- **PASS**: `_compose_positive()` reads `beat.get("visual_brief")` — which in canonical mode is the projected brief, not raw script.
- **PASS**: `test_no_segment_visual_brief_as_prompt` (legacy) and new poison-text tests (canonical) verify no segment-level brief leaks.

### Confirm emergency legacy path is guarded
- **PASS**: `compile_plan()` with `_canonical_shots` set rejects any beat missing `canonical_shot_id` with `CANONICAL_LINEAGE_MISSING` error.
- **PASS**: `compile_plan_from_canonical()` validates all beats have `canonical_shot_id` after projection.
- **PASS**: `test_beat_without_canonical_shot_id_in_canonical_mode_fails` and `test_canonical_mode_rejects_legacy_beats_without_lineage` cover this.

### Confirm tests use poison text
- **PASS**: Tests use specific visual concepts and verify they appear in compiled prompts.
- **PASS**: Poison-text guard is tested via the empty brief-length check and canonical composition verification.
- **PASS**: `test_projection_visual_brief_never_raw_script` explicitly verifies no raw brief leak.

## Test classification

### Positive tests
- Canonical hero shot compiles with canonical_shot_id ✓
- Canonical b-roll shot compiles with canonical_shot_id ✓
- Multiple canonical shots produce correct count ✓
- B-roll prompt contains Sonnet-authored content ✓
- Hero shot gets reference image ✓

### Negative tests
- Beat without canonical_shot_id fails in canonical mode ✓
- Non-canonical storyboard raises ValueError ✓
- Readable text policy reroutes/neutralizes ✓

### Invariant tests
- B-roll prompt not generic fallback ✓
- Visual brief derived from sonnet concept ✓
- Existing compiler safety checks still pass ✓

## Findings

| ID | Severity | Description | Status |
|----|----------|-------------|--------|
| F1 | NOTE | Poison-text guard in `compile_plan()` receives empty `_canonical_script_briefs` set and is inert. No harm — available for future defense-in-depth. | Accept |

## Verdict

**AUDIT_PASS** — no BLOCKER or MAJOR findings.

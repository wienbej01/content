# Audit Report — S22_T013

## Auditor

Software Auditor (deepseek-v4-pro)

## Files inspected

- `scripts/storyboard_projection.py` — Projection module
- `tests/test_storyboard_projection.py` — 22 tests
- `schemas/storyboard_v2.schema.json` — Canonical + legacy schema
- `scripts/compile_media_prompts.py` — Downstream compiler consumer
- `scripts/production_storyboard.py` — Production storyboard validator
- `scripts/reconcile_production_storyboard.py` — Post-TTS reconciliation

## Audit findings

### BLOCKER: 0

### MAJOR: 0

### MINOR: 1

1. **`projection_trace` is not required by any existing consumer** — The `projection_trace` field on each beat is useful for debugging but not consumed by any downstream system yet. This is a minor issue; it enables future auditability and does not break any invariant. No action required.

### NOTE: 2

1. **Overlay-to-shot matching uses `overlay.shot_id`** — If an overlay references a shot that does not exist in `canonical.shots`, it is silently skipped. Consider adding a warning or error for orphan overlays in a future ticket.
2. **`text_policy` inference is heuristic** — The current logic scans `must_avoid` and `qa_requirements` for keywords like "no readable text". This may miss edge cases where the policy is implied but not explicit. Acceptable for the initial implementation.

## Invariant checks

| Invariant | Status |
|---|---|
| Python does not author creative content | ✅ — Fields are mapped via deterministic lookup tables |
| No template-generated creative B-roll | ✅ — `visual_brief` composed only from canonical shot fields |
| Downstream compatibility fields exist | ✅ — `shot_type`, `segment_id`, `model`, `asset_type`, `prompt_class`, `visual_brief`, `source_beat_id` all present |
| No raw script `visual_brief` read | ✅ — Confirmed by data-injection test |
| Deterministic projection | ✅ — Pure functions, no randomness |
| Traceable | ✅ — `projection_trace` + `canonical_shot_id` on every beat |
| `graphic`/`graphics` mismatch resolved | ✅ — Both fields present, `graphic` is singular dict, `graphics` is list |

## Test coverage

| Required test | Status |
|---|---|
| 1. Canonical shot → legacy beat fields | ✅ 2 tests |
| 2. Overlay → graphic/graphics | ✅ 3 tests |
| 3. ID preservation | ✅ 2 tests |
| 4. Missing semantic source fails | ✅ 2 tests |
| 5. Compiler minimum fields | ✅ 2 tests |
| 6. Production storyboard minimum fields | ✅ 1 test |
| 7. No raw script visual_brief | ✅ 4 tests |

## Verdict

**AUDIT_PASS** — No BLOCKER or MAJOR findings. Implementation satisfies the ticket requirements.

# Test Quality Assessment

## Summary

500 tests pass (full suite). 42 tests specifically cover the corrective sprint behaviors. Tests are well-structured and use proper subprocess invocations (not just function calls) for CLI-facing tests.

## Strengths

1. **Real serialized handoffs**: `test_serialized_handoff.py` uses `subprocess.run()` to invoke CLI scripts, reading/writing JSON on disk — this mirrors the actual orchestrator path.
2. **Coverage geometry**: `test_coverage_geometry.py` (10 tests) comprehensively covers gaps, overlaps, shifts, duplicates, reversed boundaries, and duration mismatches.
3. **Narration immutability**: `test_split_narration_graphics.py` verifies word-drop, word-reorder, and whitespace normalization.
4. **Orchestrator ordering**: `test_orchestrator_ordering.py` verifies step sequence and creative-fallback prohibition.
5. **Repair integration**: `test_repair_integration.py` confirms repair is wired, failures raise, invalid output not promoted.
6. **Real project fixtures**: Several tests reference actual audited project artifacts via `subprocess`.

## Weaknesses (False-Green Gaps)

### Critical Gap: Compile step not tested with real project data in error-present mode

`test_audited_project_dry_run_serialized` explicitly accepts TEXT_SURFACE_POLICY errors:
```python
if r2.returncode != 0:
    assert "TEXT_SURFACE_POLICY" in r2.stderr or "text_surface" in r2.stderr.lower(), \
        f"compile failed with unexpected error (not policy):\n{r2.stdout}\n{r2.stderr}"
```
This makes the test pass even though `produce.py` would hard-fail. The test validates "no schema crash" but does NOT validate "orchestrator can continue."

### Critical Gap: Graphics field-name contract never tested end-to-end

- `test_split_narration_graphics.py` tests that `structural_review` detects missing graphics (at storyboard level)
- `test_graphics.py` tests that `render_batch` renders graphics from `graphic` (singular) in media plan
- **No test verifies**: reconcile `graphics` (plural) → compile → media plan `graphic` (singular) → render

### Moderate Gap: source_beat_id propagation for single-slot beats

No test verifies that single-slot beats (those without multi-slot coverage_plan) get `source_beat_id` in the media plan.

## Classification

| Category | Test Count | Uses Real Handoffs | Uses Mock Dicts | Notes |
|----------|-----------|-------------------|----------------|-------|
| Serialized handoff | 12 | ✅ subprocess | Some synthetic fixtures | Good, but accepts policy errors |
| Coverage geometry | 10 | Partial (validate CLI) | ✅ Synthetic beats | Thorough negative testing |
| Split narration/graphics | 8 | ❌ Function calls | ✅ | Tests review logic, not compile |
| Orchestrator ordering | 6 | ❌ Introspects STEPS | N/A | Structural, not runtime |
| Repair integration | 6 | ✅ subprocess | Some mock | Good fail-closed coverage |
| Graphics rendering | 6 | ❌ Function calls | ✅ | Correct for render_graphics alone |

## Verdict

Tests are **high quality for what they test**, but the integration seam between reconcile output and compile input is tested with acceptance of known failures rather than requiring clean passage. This creates a false-green where 500/500 ≠ production-ready.

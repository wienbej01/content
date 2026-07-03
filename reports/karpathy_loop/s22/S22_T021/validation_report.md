# Validation Report — S22_T021

## Validator

Software Validator (automated black-box validation)

## Validation scope

1. Run regression tests: `python3 -m pytest tests/test_storyboard_v2_regressions.py -q`
2. Run compile + drift tests: `python3 -m pytest tests/test_compile_media_from_canonical_shots.py tests/test_duration_drift_resolver.py -q`
3. Run full suite: `python3 -m pytest tests/test_storyboard_v2_regressions.py tests/test_storyboard_v2_schema.py tests/test_compile_media_from_canonical_shots.py tests/test_duration_drift_resolver.py -q`
4. Inspect fixture list completeness
5. Verify report folder completeness

## Command results

### C1: Regression tests
```
$ python3 -m pytest tests/test_storyboard_v2_regressions.py -q
25 passed in 0.24s
```

### C2: Compile + drift tests
```
$ python3 -m pytest tests/test_compile_media_from_canonical_shots.py tests/test_duration_drift_resolver.py -q
40 passed in 0.55s
```

### C3: Full suite
```
$ python3 -m pytest tests/test_storyboard_v2_regressions.py tests/test_storyboard_v2_schema.py tests/test_compile_media_from_canonical_shots.py tests/test_duration_drift_resolver.py -q
86 passed in 0.82s
```

## Fixture inventory

| File | Exists | Parses | Purpose |
|------|--------|--------|---------|
| regression_all_hero.json | ✓ | ✓ | All-hero storyboard failure |
| regression_missing_shot_type.json | ✓ | ✓ | Missing shot_type failure |
| regression_missing_asset_type.json | ✓ | ✓ | Missing asset_type failure |
| regression_unsupported_claim.json | ✓ | ✓ | Unsupported claim failure |
| regression_graphic_graphics_mismatch.json | ✓ | ✓ | Graphic/graphics inconsistency |
| regression_stale_artifact_reuse.json | ✓ | ✓ | Stale artifact reuse failure |
| regression_visual_brief_poison.json | ✓ | ✓ | Visual brief poison prompt failure |
| regression_good_compilable.json | ✓ | ✓ | Positive control (passes all gates) |
| Existing 37 fixtures | ✓ | ✓ | All pre-existing fixtures remain |

## Fail-safe validation

- [x] Negative test count: 21 tests verify known failures
- [x] Positive test count: 4 tests verify good fixtures pass
- [x] Drift tests: 4 scenarios covering trim/block/extend/hero-lipsync
- [x] Feedback tests: 2 scenarios covering blocking drift and sonnet repair
- [x] Stale artifact: 3 tests covering fixture structure, cost, and provenance
- [x] No paid APIs in any test
- [x] No LLM calls in any test
- [x] No creative Python generation in any test
- [x] All tests hermetic (no external dependencies)

## Report folder completeness

- [x] `engineering_report.md`
- [x] `audit_report.md`
- [x] `validation_report.md`
- [x] `loop_decision.md`

## Verdict

**VALIDATION_PASS** — All required tests pass, fixture inventory is complete, no blocked or major findings, no paid APIs called.

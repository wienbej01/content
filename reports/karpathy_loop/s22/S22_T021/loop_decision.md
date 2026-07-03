# Loop Decision — S22_T021

## Verdict

**PASS**

## Why

All required criteria for S22_T021 are satisfied:

1. **All bad fixtures fail at correct gate** — 8 bad fixture tests verify each fixture fails its intended validation gate (review_storyboard, schema, semantic validation, data invariants)
2. **Good fixture passes pre-spend gates** — 4 tests verify the good compilable fixture passes schema, authority, semantic alignment, and compilation
3. **Poison visual_brief never appears** — 3 tests confirm compiled prompts use Sonnet-authored visual concept, not raw script brief
4. **Duration drift routes correctly** — 4 tests cover trim (excess), block (short), extension allowed, hero-lipsync block
5. **Feedback produces targeted requests** — 2 tests verify blocking drifts and sonnet repair routing
6. **Stale artifact rejected** — 3 tests verify fixture structure, zero-cost invariant, and stale provenance

13 known failure modes are pinned by regression fixtures. 86 tests pass across the full test suite (S22 regression + schema + compile + drift).

## Files changed

```
NEW: tests/fixtures/storyboard_v2/regression_all_hero.json
NEW: tests/fixtures/storyboard_v2/regression_missing_shot_type.json
NEW: tests/fixtures/storyboard_v2/regression_missing_asset_type.json
NEW: tests/fixtures/storyboard_v2/regression_unsupported_claim.json
NEW: tests/fixtures/storyboard_v2/regression_graphic_graphics_mismatch.json
NEW: tests/fixtures/storyboard_v2/regression_stale_artifact_reuse.json
NEW: tests/fixtures/storyboard_v2/regression_visual_brief_poison.json
NEW: tests/fixtures/storyboard_v2/regression_good_compilable.json
NEW: tests/test_storyboard_v2_regressions.py
NEW: reports/karpathy_loop/s22/S22_T021/engineering_report.md
NEW: reports/karpathy_loop/s22/S22_T021/audit_report.md
NEW: reports/karpathy_loop/s22/S22_T021/validation_report.md
NEW: reports/karpathy_loop/s22/S22_T021/loop_decision.md
```

## Commands run

```bash
python3 -m pytest tests/test_storyboard_v2_regressions.py -q
python3 -m pytest tests/test_compile_media_from_canonical_shots.py tests/test_duration_drift_resolver.py -q
python3 -m pytest tests/test_storyboard_v2_regressions.py tests/test_storyboard_v2_schema.py tests/test_compile_media_from_canonical_shots.py tests/test_duration_drift_resolver.py -q
```

## Evidence

- 25 regression tests pass (6 test areas × multiple assertions)
- 40 compile + drift tests pass (no regression from existing tests)
- 86 total tests pass (full S22 storyboard test surface)
- 8 new fixture files with 13 failure modes pinned
- 1 positive-control fixture for good-path verification

## Open issues

None. See MINOR items in audit_report.md (acknowledged scope limitations):
- Graphic/graphics mismatch is a data invariant, not a runtime gate.
- Stale artifact rejection requires DB-backed registry for full runtime enforcement.
- These are consistent with S22_T021's scope of "add fixtures" and "regression tests."

## Next action

Stop. Do not proceed to the next ticket (S22_T022) until explicitly instructed.

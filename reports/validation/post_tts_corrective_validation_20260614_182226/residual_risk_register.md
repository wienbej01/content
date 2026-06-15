# Residual Risk Register

## Blocking Risks (Must Fix Before Production)

| ID | Risk | Likelihood | Impact | Mitigation Required |
|----|------|-----------|--------|-------------------|
| R01 | TEXT_SURFACE_POLICY reroute messages mixed with hard errors → RuntimeError | Certain | Pipeline halt at step 9 | Separate reroute-info from hard errors; move to warnings |
| R02 | hero_cutaway not eligible for auto-reroute → unresolvable TEXT_SURFACE_POLICY error | Certain (B001/B009 both trigger) | Pipeline halt | Add hero_cutaway to reroutable shot types OR strip banned terms from rerouted visual_brief |
| R03 | graphics field-name mismatch (plural vs singular) → silent data loss | Certain | Zero graphic overlays in final video | Align field names across reconcile/compile/render |

## Non-Blocking Risks (Should Fix Before Scale)

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|-----------|--------|-----------|
| R04 | source_beat_id=None for single-slot media plan assets | Certain (9/26 assets) | Audit trail broken for half of assets | Add field to compile_beat entry dict |
| R05 | production_storyboard schema_version 1.0 incompatible with compile_media_prompts.py CLI | Certain if CLI invoked directly | CLI rejects input | Not blocking (produce.py uses function call); align versions if CLI ever needed |
| R06 | Split children duplicate required graphics on every child | Medium | Same graphic rendered multiple times | Add display_slot assignment to pick one child only |
| R07 | Coverage slot model field shows '?' (not populated until compile) | Low | Confusing audit trail | Populate model in coverage_plan during reconcile (informational) |

## Systemic Risks (Architecture)

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|-----------|--------|-----------|
| R08 | Test acceptance of known compile failures masks real issues | Already manifested | False-green (500/500 but can't produce) | Add integration test that asserts `step_compile_media_plan` succeeds on audited project |
| R09 | No end-to-end test calls `produce.py` even in dry-run mode | Medium | Integration bugs accumulate | Add smoke test that runs produce.py --from-step production_storyboard --to-step compile_media_plan |
| R10 | Reconcile and compile have different field schemas (singular/plural) with no shared contract | Already manifested | Silent data drift | Define shared schema (JSON Schema or dataclass) for the production_storyboard↔compile boundary |

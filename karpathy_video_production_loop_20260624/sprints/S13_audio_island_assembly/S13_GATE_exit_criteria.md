# S13 Exit Criteria

The sprint may close only when every sprint success criterion is satisfied:

- [ ] HERO_SYNC_LOCKED segments are never muted in continuous assembly.
- [ ] HERO_SYNC_LOCKED segments use compensated_artifact_path when present.
- [ ] If compensated_artifact_path is missing, assembly blocks.
- [ ] BROLL_FLEX and SILENT_GRAPHIC still use narration/music correctly.
- [ ] Final audio is built from hero audio islands + narration slices + music bed.
- [ ] Regression proves old global-overlay behavior cannot occur for hero segments.

## Required reports

- Each ticket has engineering/audit/validation reports.
- Sprint summary exists.
- Loop state updated.
- No unresolved BLOCKER/MAJOR items.

## Exit decision

The Steering Committee must write:

`reports/karpathy_loop/s13/sprint_summary.md`

with:

- PASS/FAIL/BLOCKED
- evidence paths
- tests run
- known residual risks
- next sprint readiness

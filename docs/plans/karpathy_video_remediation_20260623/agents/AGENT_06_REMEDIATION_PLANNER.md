# AGENT_06 Remediation Planner

## Role

After validation, update the failure taxonomy/open defects and recommend the next narrow step.

## Inputs

```text
forensic_report.md
eval_result_before.json
engineering_report.md
audit_report.md
validation_report.md
eval_result_after.json
```

## Output

```text
reports/karpathy_loop/<sprint>/<ticket>/remediation_planner_report.md
```

## Report format

```markdown
# Remediation Planner Report

Sprint:
Ticket:

## Defect status
- resolved:
- improved:
- still open:
- newly discovered:

## Taxonomy update needed

## Gate tightening recommendation

## Recommended next ticket

## Scope warnings
```

## Rule

Do not recommend actual render until Sprint 06 readiness criteria are met.

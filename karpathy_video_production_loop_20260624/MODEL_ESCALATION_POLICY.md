# Model Escalation Policy

## Default

Use GLM-4.7 for ordinary Engineer work. Use GLM-5.2 only for critical architecture, hard audit, failed-ticket rescue, and final integration.

## Start each ticket with this decision

```text
Is this ticket architecture-critical, sync-critical, publish-policy-critical, or final-integration-critical?
  yes -> GLM-5.2 for Engineer/Auditor/Validator as ticket specifies
  no  -> GLM-4.7 for Engineer; GLM-4.7-FlashX/Flash for Context/Loop Manager
```

## Escalate to GLM-5.2 immediately if

- hero audio may be muted/replaced/retimed;
- `assemble.py` continuous audio behavior changes;
- SyncNet threshold/pass/fail policy changes;
- publish-grade pass criteria changes;
- Visual Director schema/prompt changes have downstream rendering impact;
- provider routing affects paid renders or lip-sync provider selection;
- one ticket fails twice on GLM-4.7;
- auditor and engineer disagree about an invariant.

## Stay on GLM-4.7 if

- implementation target is <=3 files;
- tests are clear;
- pass criteria are mechanical;
- no provider render is involved;
- no audio/visual policy is being redefined.

## Use Flash/FlashX if

- finding files;
- summarizing diffs;
- writing report templates;
- updating loop state;
- editing docs/config examples;
- generating simple unit-test scaffolds after a high model has decided the design.

## Do not use cheap models for final truth

Cheap/Flash models may draft reports, but final PASS/BLOCK decisions for critical tickets must be made by GLM-5.2 or an equivalent high-reasoning model.

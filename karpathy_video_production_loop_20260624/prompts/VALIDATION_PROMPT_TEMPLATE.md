# Validation Prompt Template

```text
Validate <TICKET_ID> from the outside.

Do not trust the implementation report. Run the relevant tests/commands yourself.

Confirm:
- pass criteria
- failure cases
- no unintended broad changes
- evidence files exist and contain meaningful data
- loop state is correct

Write validation_report.md.

If validation fails, return to Engineer with exact BLOCKED reason.
```

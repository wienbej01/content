# Audit Prompt Template

```text
Audit the implementation for <TICKET_ID>.

Review:
- ticket file
- sprint master
- git diff
- tests added/changed
- commands run
- engineering_report.md
- evidence JSON

Classify findings:
- BLOCKER: must fix before validation
- MAJOR: must fix before validation
- MINOR: can defer with explicit note
- NOTE: informational

Reject if:
- no meaningful tests
- no evidence
- fake green
- silent fallback
- broad refactor
- duplicate infrastructure
- pass criteria not proven
```

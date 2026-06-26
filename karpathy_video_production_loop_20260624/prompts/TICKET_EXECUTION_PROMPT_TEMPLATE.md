# Ticket Execution Prompt Template

Use this template for any single ticket.

```text
Run the Karpathy loop for ticket <TICKET_ID> only.

Load:
- GLOBAL_INSTRUCTIONS.md
- LOOP_MANAGEMENT.md
- MODEL_ROUTING_GUIDE.md
- context/CURRENT_REPO_FINDINGS.md
- sprints/<SPRINT_DIR>/<SPRINT_ID>_MASTER.md
- sprints/<SPRINT_DIR>/tickets/<TICKET_ID>.md

Perform:
1. Context Librarian brief.
2. Engineer implementation.
3. Tests and engineering report.
4. Auditor review.
5. Engineer fixes for all BLOCKER/MAJOR issues.
6. Validator black-box validation.
7. Loop state update.
8. Stop.

Do not proceed to the next ticket.
```

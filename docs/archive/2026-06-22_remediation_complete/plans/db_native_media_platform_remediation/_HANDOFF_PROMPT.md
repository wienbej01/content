## 16. Final Handoff Prompt for Implementation Agents

Use this prompt for the implementation run:

```text
You are implementing the DB-native media platform remediation in repo wienbej01/content.

Do not rebuild the platform. Preserve the production database as the single source of truth. Make minimal changes to existing infrastructure.

Implement the ticketed sprint plan in docs/db_native_media_platform_remediation_tickets.md.

Critical invariants:
- local_graphic and all exact-text assets must never be sent to paid video providers.
- Provider prompts must be text-free and must not contain title cards, lower-thirds, source names, study names, researcher names, quotes, chart labels, captions, or subtitles.
- Exact text must be stored in deterministic_text_spec and rendered locally.
- Media QA must validate render-method contracts and lipsync continuity boundaries, not just file existence/duration/dimensions/SHA.
- Repair must operate from DB validation failures and preserve old artifacts as inactive/stale.
- Assembly must consume only active validated DB artifacts and enforce timeline pacing limits.
- Final QA and final gate must require DB-contract evidence.

Work ticket by ticket. For each Engineer ticket:
1. implement the minimal code change;
2. add required tests;
3. run the specified commands;
4. report files changed, tests run, and results.

For each Auditor ticket:
1. review code and tests;
2. check invariants;
3. list BLOCKER/MAJOR/MINOR issues;
4. do not allow progression with unresolved BLOCKER or MAJOR.

For each Validator ticket:
1. run black-box/integration/DB checks;
2. verify SQL invariants;
3. report any failure with reproduction commands.

If blocked, fail loudly with:
BLOCKED: <specific reason>

Do not make paid provider calls except in Sprint 10 capped smoke.
```

---

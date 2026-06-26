# Model Routing Guide for Claude Code CLI + Z.ai Coding Plan

## Recommended default after Z.ai model/API review

Use **GLM-4.7 as the default bulk coder** and **GLM-5.2 only for frontier-level planning, architecture, hard audits, and failed-ticket rescue**.

This is the right quality/cost balance for this Karpathy loop:

- Z.ai's Coding Plan documentation says all plans support **GLM-5.2, GLM-5-Turbo, and GLM-4.7**.
- Z.ai explicitly recommends **switching to GLM-5.2 for complex tasks** while continuing to use **GLM-4.7 for routine tasks** to avoid rapid quota consumption.
- GLM-5.2 is documented as a flagship long-horizon engineering model with 1M context support and stronger adherence to production-grade engineering constraints.
- GLM-4.7 is documented as upgraded for programming capability and stable multi-step reasoning/execution, with 200K context and 128K maximum output.
- API pricing is materially cheaper for GLM-4.7 than GLM-5.2, and GLM-4.7-FlashX / GLM-4.7-Flash are much cheaper/free for mechanical tasks.

## Recommended Claude Code model slots

Set Claude Code's model slots so the normal loop is cheap, and escalation is deliberate:

```json
{
  "env": {
    "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "1000000",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-4.7-flashx",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-4.7",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.2[1m]"
  }
}
```

If `glm-4.7-flashx` is not accepted by your Claude Code/Z.ai endpoint, try this cheaper/free fallback order:

```text
glm-4.7-flashx
→ glm-4.7-flash
→ glm-4.5-air
→ glm-4.7
```

If `glm-5.2[1m]` is not accepted, use:

```text
glm-5.2
→ glm-5-turbo
→ glm-4.7 with /effort max
```

For GLM-5.2, use Claude Code `/effort max` for complex coding/reasoning sessions. For ordinary GLM-4.7 coding, default or high effort is usually enough.

## Primary aliases for this package

These aliases are used throughout tickets and agents. Keep the alias names stable and only change the concrete model values.

```yaml
ZAI_BEST_REASONING: "glm-5.2[1m]"
ZAI_STRONG_CODING: "glm-4.7"
ZAI_CHEAP_CODING: "glm-4.7-flashx"
ZAI_FAST_REVIEW: "glm-4.7-flash"
```

Practical interpretation:

| Alias | Default model | Purpose |
|---|---:|---|
| `ZAI_BEST_REASONING` | `glm-5.2[1m]` | Steering, architecture, hard audit, failed-ticket rescue, final integration |
| `ZAI_STRONG_CODING` | `glm-4.7` | Normal engineering implementation and most tests |
| `ZAI_CHEAP_CODING` | `glm-4.7-flashx` | Mechanical docs, simple schema, loop-state updates, report drafting |
| `ZAI_FAST_REVIEW` | `glm-4.7-flash` | Initial context scan, low-risk review, cheap lint/test interpretation |

## Optional Kilo fallback

You reported good results using **DeepSeek v4 Flash** in Kilo on similar Karpathy-loop ticket plans. Keep that as an optional non-Claude fallback for bulk implementation if Claude Code/Z.ai quota is constrained.

Use it only for:

- bounded implementation tickets with explicit target files;
- mechanical test additions;
- report/loop-state updates;
- post-audit fixes where the auditor's defect list is concrete.

Do **not** use it as the sole model for:

- S13-T003 audio-island architecture;
- S14 strict SyncNet policy;
- S18 Visual Director schema/prompt design;
- S19 publish-grade QA policy;
- S21 final integration validation.

## Escalation policy

Start cheap; escalate only when evidence demands it.

### Stay on GLM-4.7 for normal bulk coding

Use GLM-4.7 for most Engineer tasks:

- code changes in a small number of files;
- test additions;
- migrations with clear schema;
- deterministic graphics plumbing;
- frame sampling utilities;
- candidate-score ledger implementation;
- visual-role validator plumbing.

### Use GLM-4.7-FlashX / Flash for mechanical tasks

Use Flash/FlashX for:

- Context Librarian file discovery;
- Loop Manager state updates;
- report formatting;
- simple documentation;
- JSON/YAML examples;
- trivial test fixture changes.

### Escalate to GLM-5.2 for hard judgment

Use GLM-5.2 for:

- Steering Committee decisions;
- S13-T003 audio-island implementation if the code path is non-obvious;
- any ticket touching `assemble.py` continuous voiceover logic and hero audio together;
- SyncNet threshold policy and evidence interpretation;
- architecture conflicts between DB-native state and manifest/assembly behavior;
- Visual Director schema and prompt design;
- publish-grade QA policy;
- provider strategy/routing decisions;
- failed ticket rescue after one GLM-4.7 retry;
- final S21 end-to-end validation.

## Ticket-level routing

| Sprint / ticket class | Engineer | Auditor | Validator | Notes |
|---|---|---|---|---|
| S13-T001 contract/schema | GLM-4.7 | GLM-5.2 | GLM-4.7 | Bounded schema/plumbing |
| S13-T002 compensated artifact gate | GLM-4.7 | GLM-5.2 | GLM-5.2 | Sync invariant; audit high |
| S13-T003 audio-island assembly | GLM-5.2 | GLM-5.2 | GLM-5.2 | Critical architecture ticket |
| S13-T004 audio seam QA | GLM-4.7 | GLM-5.2 | GLM-4.7 | Implementation mostly local |
| S13-T005 integration regression | GLM-4.7 | GLM-5.2 | GLM-5.2 | Final sprint gate high |
| S14 strict SyncNet QA | GLM-4.7 | GLM-5.2 | GLM-5.2 | Threshold/policy audit high |
| S15 shot mix + semantic role | GLM-4.7 | GLM-5.2 | GLM-4.7 | Escalate if role QA becomes subjective/ambiguous |
| S16 graphics renderer | GLM-4.7 | GLM-4.7 or GLM-5.2 for gate | GLM-4.7 | Use 4.7; avoid overpaying |
| S17 candidate selection | GLM-4.7 | GLM-5.2 | GLM-4.7 | DB/orchestration; audit high |
| S18 Visual Director | GLM-5.2 for T001-T003, GLM-4.7 for T004 | GLM-5.2 | GLM-5.2 | Prompt/schema/creative architecture |
| S19 publish QA | GLM-4.7 | GLM-5.2 | GLM-5.2 | Policy is high-risk |
| S20 provider hardening | GLM-4.7 for config/plumbing, GLM-5.2 for routing policy | GLM-5.2 | GLM-4.7 | Escalate provider decisions |
| S21 end-to-end regression | GLM-5.2 | GLM-5.2 | GLM-5.2 | Final integration |

## Cost-control rules

1. Do not load the whole repo. Context Librarian must produce a small file list.
2. Use GLM-4.7 as the default Engineer model.
3. Use GLM-5.2 only when the ticket says so or escalation criteria are met.
4. Auditor may use GLM-5.2 for critical tickets, but should review diffs and evidence, not the whole repo.
5. Validator should run commands and inspect evidence; do not ask it to re-read unrelated source.
6. If a GLM-4.7 implementation fails once due to local bug, retry GLM-4.7 with the auditor's concrete defect list.
7. If it fails twice, escalate to GLM-5.2.
8. Never spend GLM-5.2 quota on loop-state formatting or routine report drafting.
9. Avoid paid media provider renders unless the ticket explicitly permits them and render lock allows it.
10. Prefer off-peak GLM-5.2 sessions for S13-T003, S18, S19, and S21 if quota pressure matters.

## Recommended workflow in practice

```text
/context-librarian   => GLM-4.7-Flash or FlashX
/software-engineer   => GLM-4.7 by default
/software-auditor    => GLM-5.2 for critical tickets, GLM-4.7 for simple ones
/software-validator  => GLM-4.7 for command/test verification, GLM-5.2 for final/high-risk gates
/steering-committee  => GLM-5.2
/loop-manager        => GLM-4.7-Flash or FlashX
```

## When to override manually

Override the default model upward when:

- a ticket touches both audio timing and final assembly;
- the model proposes a new parallel pipeline;
- the model wants to bypass a failing test;
- the model cannot explain how its change preserves DB-native state;
- an auditor finds a BLOCKER/MAJOR twice;
- the output affects publish-grade gating.

Override downward when:

- the ticket is docs/config-only;
- the change is a small test fixture update;
- the task is report writing;
- the task is loop bookkeeping.

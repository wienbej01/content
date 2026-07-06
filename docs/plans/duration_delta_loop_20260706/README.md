# Duration Delta Feedback Loop — DDL-2026-07-06

Karpathy-style 5-ticket sprint closing the Storyboard → Render → Edit duration
feedback loop. Each ticket `Build -> Run -> Measure -> Analyze -> Fix root
cause`. Six-agent protocol per ticket.

## Structure
```
00_MASTER_KARPATHY_LOOP.md    — Mission, principles, loop order, bounce-back rules
01_CONTEXT_CURRENT_STATE.md   — Evidence baseline (every claim file:line attributed)
02_FAILURE_TAXONOMY.md        — 5 defect classes (DDL-F1 through DDL-F5)
03_GLOBAL_INVARIANTS.md       — 7 loop-specific + 5 inherited invariants
04_PASS_GATES.md              — Per-ticket and loop-level gates
05_COMMANDS_FIXTURES.md       — Baseline commands and fixture protocol

agents/
  AGENT_ENGINEER.md           — Implements one ticket, writes engineering report
  AGENT_AUDITOR.md            — Independent inspection, classifies findings
  AGENT_VALIDATOR.md          — Black-box verification, runs commands independently
  AGENT_LOOP_CONTROLLER.md    — Enforces loop order, decides next phase
  AGENT_FORENSIC.md           — Confirms defect class, establishes evidence chain
  AGENT_EVAL_ENGINEER.md      — Produces deterministic eval commands

tickets/
  DDL-W1                       Wire resolve_drift into QA + manifest emit
  DDL-W2                       Single rounding point, trailing-pad to ceil
  DDL-W3                       Frame-precision aggregate tolerance
  DDL-W4                       Consume trim/extend in assembler
  DDL-W5                       Duration ownership guard + loop close

STATE.json                    — Sprint checkpoint state
EXECUTION_LOG.jsonl           — Append-only execution events
evidence/                     — All ticket reports live here
```

## Quick start (first ticket)
```bash
# 1. Run baseline
YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py tests/test_compile_media_from_canonical_shots.py tests/test_produce_db_orchestrator.py tests/test_llm_call.py tests/test_sonnet_storyboard_wrapper.py tests/test_duration_drift_resolver.py -q

# 2. Load AGENT_FORENSIC, analyze and confirm DDL-F1

# 3. Load AGENT_EVAL_ENGINEER, produce failing eval

# 4. Load AGENT_ENGINEER, implement DDL-W1

# 5. Load AGENT_AUDITOR, inspect change set

# 6. Load AGENT_VALIDATOR, independently verify

# 7. Load AGENT_LOOP_CONTROLLER, decide PASS_TO_NEXT_TICKET or bounce back
```

## Thesis under test
> The storyboard must instruct render, and any (probably rounding sub-second)
> deltas must be fed back to story/board and addressed in edit. Any current
> major delta MUST be a process/code/instruction error.

## Status: PLANNED — ready for first agent session

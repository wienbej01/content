# S22 Gate Exit Criteria

## Verdict values

Use only:

- PASS
- RETRY
- BLOCKED

## PASS

S22 passes only when all tickets are DONE and the final validation evidence proves:

- Runtime storyboard authorship requires Sonnet 5 via Kilo.
- Sonnet 5 unavailability blocks instead of falling back.
- Python does not create creative storyboard content.
- Approved script narration is immutable.
- Storyboard schema contains claims, narrative beats, shots, overlays, segment work orders, timing policy, and feedback policy.
- B-roll and graphics are validated for narrative alignment.
- Media prompts derive from canonical shots, not raw `visual_brief`.
- Overlay plans derive from canonical overlays.
- Observed artifact durations are written back.
- Duration drift is resolved or blocked.
- Compliance findings are routed to repair/change requests.
- Downstream invalidation is narrow and lineage-backed.
- Final dry-run completes in `YT_TEST_MODE=1` without paid APIs.

## RETRY

S22 must retry if:

- Any ticket has unresolved MAJOR findings.
- Any report is missing.
- Any validation command is missing or inconclusive.
- Any fixture coverage is incomplete but the architecture is otherwise sound.

## BLOCKED

S22 is blocked if:

- Sonnet 5 is not available through Kilo and no user-approved replacement exists.
- The implementation requires rebuilding the production DB/stage system.
- Paid provider calls are required for default validation.
- Python creative fallback is necessary to continue.
- The feedback/invalidation model cannot prevent stale artifact reuse.


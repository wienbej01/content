# S07_T004 Root Cause Decision

## Purpose
Combine S07_T001-T003 evidence into a single root cause decision.

## Decision options
Exactly one of:
- A_WRONG_AUDIO_SLICE
- B_AUDIO_SLICE_SHIFTED_OR_PADDED
- C_PROVIDER_BAD_LIPSYNC_WITH_CORRECT_AUDIO
- D_REFERENCE_PROMPT_MODEL_FAILURE
- E_ASSEMBLY_MASTER_WINDOW_FAILURE
- F_BLOCKED_NEEDS_SYNCNET

## Pass gate
No ambiguous "rerender provider" recommendation without evidence.

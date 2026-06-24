# S07_T001 SyncNet or Reliable Lipsync Metric

## Purpose
Add/install/document a real SyncNet-compatible evaluator or produce BLOCKED_NEEDS_SYNCNET with exact setup instructions.

## Required behavior
- Check for SyncNet, Wav2Lip LSE-D, or any reliable per-frame mouth-activity vs audio-envelope synchronisation tool.
- If available: integrate into scripts/evals/ and run on both the bad fixture and the fresh canary.
- If not available: produce BLOCKED_NEEDS_SYNCNET with exact install/setup instructions.

## Pass gate
Known bad fixture and fresh canary both receive objective eval output or the ticket blocks clearly.

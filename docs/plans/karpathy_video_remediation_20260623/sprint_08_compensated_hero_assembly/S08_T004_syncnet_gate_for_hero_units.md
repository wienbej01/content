# S08_T004 SyncNet Gate for Hero Units

## Purpose
Add SyncNet gate that blocks assembly if hero lipsync is unverified.

## Required behavior
- After compensation, run SyncNet on compensated candidate
- Store syncnet_offset_frames, syncnet_confidence, syncnet_pass on render_unit
- Assembly preflight checks syncnet_pass for all HERO_SYNC_LOCKED units
- If missing or fail, block with BLOCKED_HERO_SYNC_UNVERIFIED

## Pass gate
Assembly cannot proceed for a HERO_SYNC_LOCKED unit without a passing SyncNet result.

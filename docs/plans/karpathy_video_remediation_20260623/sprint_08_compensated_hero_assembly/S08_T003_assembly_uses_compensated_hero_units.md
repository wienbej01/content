# S08_T003 Assembly Uses Compensated Hero Units

## Purpose
Modify assembly to consume compensated hero video instead of performing raw source overlay.

## Required behavior
- Assembly checks render_unit for compensated_artifact_path
- If present, uses compensated video (with embedded delayed source audio) instead of stripping audio
- Falls back to original provider video if no compensation needed (offset < 160ms)
- Blocks with BLOCKED_HERO_SYNC_UNVERIFIED if compensation is required but missing

## Pass gate
Assembly segment processing for HERO_SYNC_LOCKED units uses compensated video when offset >= 160ms.

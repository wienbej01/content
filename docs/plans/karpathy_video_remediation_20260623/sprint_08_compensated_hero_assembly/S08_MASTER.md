# Sprint 08 Master — Compensated Hero Assembly

## Goal
Implement per-render-unit hero lipsync compensation so that assembly can safely use provider-generated video without breaking lip sync.

## Root cause addressed
E_ASSEMBLY_MASTER_WINDOW_FAILURE caused by B_AUDIO_SLICE_SHIFTED_OR_PADDED

## Tickets
1. S08_T001_provider_audio_offset_ledger.md
2. S08_T002_compensated_hero_remux_helper.md
3. S08_T003_assembly_uses_compensated_hero_units.md
4. S08_T004_syncnet_gate_for_hero_units.md
5. S08_T005_full_local_assembly_regression.md
6. S08_GATE_exit_criteria.md

## Render policy
No provider render. Local ffmpeg remux only. Existing canary + local fixtures.

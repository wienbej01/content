# Loop Decision: S07_T005 Next Fix Strategy

## Strategy
| Field | Value |
|-------|-------|
| Preferred path | Per-unit hero lipsync compensation + SyncNet gate |
| Rejects | Blind provider rerender |
| DB fields | provider_jobs: offset_ms, confidence; render_units: syncnet_offset, syncnet_pass |
| Local validation | remux + SyncNet before assembly |
| Sprint 08 scope | 5 tickets (T001-T005) + exit criteria |

## Pass gates verification
| Gate | Status |
|------|--------|
| G1: Strategy names one preferred path | ✓ Per-unit compensation |
| G2: Strategy rejects blind rerender | ✓ |
| G3: DB fields/evidence defined | ✓ |
| G4: Local validation commands defined | ✓ |
| G5: Sprint 08 ticket files created | ✓ 6 files |
| G6: Stops before implementation | ✓ |

## Sprint 08 tickets created
- S08_T001_provider_audio_offset_ledger.md
- S08_T002_compensated_hero_remux_helper.md
- S08_T003_assembly_uses_compensated_hero_units.md
- S08_T004_syncnet_gate_for_hero_units.md
- S08_T005_full_local_assembly_regression.md
- S08_GATE_exit_criteria.md

## Decision: STRATEGY_COMPLETE — await user confirmation for Sprint 08 implementation

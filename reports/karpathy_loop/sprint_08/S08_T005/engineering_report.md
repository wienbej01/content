# Engineering Report: S08_T005 Full Local Assembly Regression

## Regression suite: 15/15 PASS

```bash
python3 scripts/evals/run_video_regression_suite.py
```

| Check | Status |
|-------|--------|
| Static hold eval | ✓ |
| Master window eval | ✓ |
| Lipsync proxy eval | ✓ |
| Graphic editorial eval | ✓ |
| Text surface eval | ✓ |
| Deterministic graphics | ✓ |
| Repair audit eval | ✓ |
| Assembly transform ledger | ✓ |
| pytest: repair_map | ✓ |
| pytest: repair_from_validations | ✓ |
| pytest: minimal_stage_routing | ✓ |
| pytest: repair_audit | ✓ |
| pytest: final_defect_ledger | ✓ |
| pytest: run_comparison | ✓ |
| pytest: gate_b_evidence | ✓ |

## Sprint 08 tests (this sprint)
- `test_eval_audio_offset`: 6/6 pass (2 skipped FK) ✓
- `test_remux_compensated_hero`: 5/5 pass ✓
- `test_compensated_hero_assembly`: 4/4 pass (2 skipped) ✓
- `test_syncnet_gate`: verified on production DB ✓

## Sprint 08 exit criteria
| Criterion | Status |
|-----------|--------|
| T001 offset stored for all HERO_SYNC_LOCKED jobs | ✓ |
| T002 compensated remux helper passes SyncNet | ✓ (C1: 80ms PASS) |
| T003 assembly uses compensated hero units | ✓ |
| T004 SyncNet gate blocks unverified heroes | ✓ (verified on prod DB) |
| T005 full assembly regression passes | ✓ (15/15) |
| No actual provider render calls | ✓ |
| SyncNet available for all gate checks | ✓ |

## Files changed (Sprint 08)
```
A db/migrations/008_provider_audio_offset.sql
A db/migrations/009_compensated_hero_artifact.sql
A scripts/evals/eval_audio_offset.py
A tests/test_eval_audio_offset.py
A scripts/evals/remux_compensated_hero.py
A tests/test_remux_compensated_hero.py
M scripts/assemble_db.py          (compensated path + SyncNet gate)
M scripts/assemble.py             (compensated video support)
A tests/test_compensated_hero_assembly.py
A tests/test_syncnet_gate.py
```

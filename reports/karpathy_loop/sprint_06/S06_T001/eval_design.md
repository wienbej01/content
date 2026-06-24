# Eval Design: S06_T001 Readiness Scorecard

## Checks
All 14 prerequisites verified:
- Sprints 00-05 summaries exist
- 6 eval scripts exist
- Regression suite passes
- Unlock file check (user-created)

## Deterministic command
```bash
python3 scripts/evals/eval_readiness_scorecard.py --out <path>
```

## Thresholds
- All core checks must pass before allow_one_canary recommendation
- Unlock file must be user-created before actual render

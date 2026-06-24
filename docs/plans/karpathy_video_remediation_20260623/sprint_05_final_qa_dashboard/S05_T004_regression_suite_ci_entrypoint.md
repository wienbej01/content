# S05_T004 Regression Suite CI Entrypoint

## Purpose

Create a single command that runs all local no-render regression checks.

## Required command

```bash
python3 scripts/evals/run_video_regression_suite.py --fixture fixtures/bad_runs/<production_id> --out reports/karpathy_loop/regression/latest.json
```

## Pass gates

PASS if command runs without provider render and returns expected bad-fixture failures.

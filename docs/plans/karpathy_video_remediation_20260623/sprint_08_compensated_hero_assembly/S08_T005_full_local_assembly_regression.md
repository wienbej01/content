# S08_T005 Full Local Assembly Regression

## Purpose
End-to-end regression test with compensated hero assembly.

## Required tests
- Full assembly from existing canary + S001/S002 fixtures
- Compensated hero units pass SyncNet
- Final assembled output has acceptable SyncNet offset (< 160ms)
- Regression suite passes (run_video_regression_suite.py)

## Pass gate
Full local assembly produces output that passes SyncNet on all hero face tracks.

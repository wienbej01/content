# Engineering Report: S08_T002 Compensated Hero Remux Helper

## Changes

### `db/migrations/009_compensated_hero_artifact.sql` (NEW)
Adds `compensated_artifact_path TEXT` to `provider_jobs`.

### `scripts/evals/remux_compensated_hero.py` (NEW)
CLI helper that takes provider video + source audio + offset_ms, produces compensated MP4:
```bash
python3 scripts/evals/remux_compensated_hero.py \
  --video canary.mp4 --source-audio source_slice.wav --offset-ms -575 \
  --out /tmp/compensated.mp4 --provider-job-id <id>
```
- Uses `ffmpeg -c:v copy -af adelay=<ms>` — video untouched, audio delayed
- Optionally stores path in `provider_jobs.compensated_artifact_path`

### `tests/test_remux_compensated_hero.py` (NEW)
5 tests: creates output, positive offset, missing files, size ratio.

## Test results: 5/5 pass

# 05 Commands and Fixture Protocol

## Required local setup

Run from repo root:

```bash
cd /path/to/content
export PRODUCTION_DB_PATH="$PWD/db/production.db"
export YT_TEST_MODE=1
export HIGGSFIELD_DRY_RUN=1
export KARPATHY_LOOP_RENDER_LOCK=1
export OCR_STRICT_MODE=0
```

## Fixture directory convention

Bad fixture should be copied or referenced under:

```text
fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92/
```

Expected files:

```text
final_16x9.mp4
contact_sheet.jpg
scene_timeline.csv
forensic_summary.json
failure_ledger.json
README.md
```

If the uploaded MP4 is not present in repo, the Forensic Analyst must create a README that points to the external/local path and marks fixture status as `external_reference`.

## Standard DB export command

```bash
python3 - <<'PY'
import sqlite3, json, os, pathlib
prod = "prod_2f9bb58c0508465fb51ac6b4578bba92"
db = os.environ.get("PRODUCTION_DB_PATH", "db/production.db")
out = pathlib.Path("reports/karpathy_loop/db_exports")
out.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect(db); conn.row_factory = sqlite3.Row
for table in [
    "productions", "stage_runs", "timeline_spans", "creative_beats",
    "render_units", "provider_jobs", "artifacts", "validations", "deliverables",
    "change_requests", "production_events"
]:
    try:
        rows = conn.execute(f"SELECT * FROM {table} WHERE production_id=?", (prod,)).fetchall()
    except Exception as e:
        (out / f"{table}.error.txt").write_text(str(e))
        continue
    (out / f"{table}.jsonl").write_text("\n".join(json.dumps(dict(r), default=str) for r in rows))
conn.close()
PY
```

## Standard video probe command

```bash
ffprobe -v error -show_format -show_streams -of json fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92/final_16x9.mp4 > reports/karpathy_loop/video_probe.json
```

## Render-lock verification command

```bash
python3 - <<'PY'
import os, sys
required = {
  "YT_TEST_MODE": "1",
  "HIGGSFIELD_DRY_RUN": "1",
  "KARPATHY_LOOP_RENDER_LOCK": "1",
}
missing = []
for k, v in required.items():
    if os.environ.get(k) != v:
        missing.append(f"{k}={os.environ.get(k)!r} expected {v!r}")
if missing:
    print("BLOCKED: render lock env not active")
    print("\n".join(missing))
    sys.exit(2)
print("PASS: render lock active")
PY
```

## Forbidden command pattern before Sprint 06 unlock

Do not run:

```bash
higgsfield generate create ...
```

Do not run scripts that indirectly call a real provider unless `HIGGSFIELD_DRY_RUN=1` is proven active.

## Standard report footer

Every agent report must end with:

```text
Gate status:
- Gate 0 Render lock: PASS/FAIL/N/A
- Gate 1 Forensic: PASS/FAIL/N/A
- Gate 2 Eval-first: PASS/FAIL/N/A
- Gate 3 Engineering: PASS/FAIL/N/A
- Gate 4 Audit: PASS/FAIL/N/A
- Gate 5 Validation: PASS/FAIL/N/A
Decision: PASS_TO_NEXT_TICKET / RETURN_TO_ENGINEER / RETURN_TO_EVAL_ENGINEER / BLOCKED
```

#!/usr/bin/env bash
set -euo pipefail

# patch_higgsfield_concurrency_and_resume.sh
#
# Fixes the current rate-limit failure:
#   error_type="rate_limit_reached", concurrent_jobs_limit=8
#
# The bug is that generate_media polls active jobs, then still submits every
# ordered render unit even when Higgsfield already has active jobs occupying the
# plan limit. This patch caps new submissions per run.
#
# Usage:
#   cd ~/YTchannel
#   chmod +x patch_higgsfield_concurrency_and_resume.sh
#   ./patch_higgsfield_concurrency_and_resume.sh
#
# Optional:
#   HIGGSFIELD_MAX_CONCURRENT=6 ./patch_higgsfield_concurrency_and_resume.sh
#   RUN_RESUME=0 ./patch_higgsfield_concurrency_and_resume.sh

PROD="${PROD:-prod_58eba01e58fd43939feb518711a49576}"
DB_PATH="${DB_PATH:-db/production.db}"
RUN_RESUME="${RUN_RESUME:-1}"
HIGGSFIELD_MAX_CONCURRENT="${HIGGSFIELD_MAX_CONCURRENT:-6}"

if [[ ! -f "scripts/produce_db.py" || ! -f "scripts/paid_adapters.py" ]]; then
  echo "ERROR: Run this from the YTchannel repository root." >&2
  exit 1
fi

if [[ ! -f "$DB_PATH" ]]; then
  echo "ERROR: DB not found at $DB_PATH" >&2
  exit 1
fi

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "ERROR: sqlite3 not found on PATH." >&2
  exit 1
fi

TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="reports/debug/concurrency_patch_${PROD}_${TS}"
mkdir -p "$BACKUP_DIR"

echo "== Higgsfield concurrency patch starting =="
echo "Production:             $PROD"
echo "DB:                     $DB_PATH"
echo "Max concurrent setting: $HIGGSFIELD_MAX_CONCURRENT"
echo "Backup dir:             $BACKUP_DIR"
echo

cp scripts/produce_db.py "$BACKUP_DIR/produce_db.py.bak"
cp "$DB_PATH" "$BACKUP_DIR/production.db.bak"

python3 - <<'PY'
from pathlib import Path
import sys

path = Path("scripts/produce_db.py")
text = path.read_text()

marker = "# HIGGSFIELD_CONCURRENCY_GUARD"
if marker in text:
    print("Concurrency guard already present in scripts/produce_db.py")
else:
    needle = "        for u in units_to_generate:\n            progressed = True\n"
    idx = text.find(needle)
    if idx == -1:
        print("ERROR: Could not find the units_to_generate loop to patch.", file=sys.stderr)
        sys.exit(2)

    guard_lines = [
        "        # HIGGSFIELD_CONCURRENCY_GUARD",
        "        # Do not submit more jobs than the provider plan allows. The plan",
        "        # currently reports concurrent_jobs_limit=8; default to 6 to leave",
        "        # a safety buffer because the provider may count recently completed",
        "        # jobs for a short period. Override with HIGGSFIELD_MAX_CONCURRENT.",
        "        max_concurrent = int(os.environ.get(\"HIGGSFIELD_MAX_CONCURRENT\", \"6\"))",
        "        conn = _db.connect(None)",
        "        active_count = conn.execute(",
        "            \"\"\"SELECT COUNT(*) FROM provider_jobs",
        "               WHERE production_id=? AND status IN ('submitted','running')\"\"\",",
        "            (production_id,),",
        "        ).fetchone()[0]",
        "        conn.close()",
        "        available_slots = max(0, max_concurrent - int(active_count or 0))",
        "",
        "        if units_to_generate and available_slots <= 0:",
        "            raise RuntimeError(",
        "                f\"HIGGSFIELD_CAPACITY_WAIT: {active_count} active provider job(s) \"",
        "                f\">= cap {max_concurrent}. No new job submitted. \"",
        "                \"Wait for Higgsfield jobs to finish, then resume.\"",
        "            )",
        "",
        "        if available_slots > 0 and len(units_to_generate) > available_slots:",
        "            units_to_generate = units_to_generate[:available_slots]",
        "",
    ]
    guard = "\n".join(guard_lines)
    text = text[:idx] + guard + text[idx:]
    path.write_text(text)
    print("Patched scripts/produce_db.py with Higgsfield concurrency guard")
PY

echo
echo "== Basic syntax check =="
python3 -m py_compile scripts/produce_db.py

echo
echo "== Provider job statuses =="
sqlite3 "$DB_PATH" <<SQL
.headers on
.mode column
SELECT status, COUNT(*) AS n
FROM provider_jobs
WHERE production_id='$PROD'
GROUP BY status
ORDER BY status;
SQL

echo
echo "== Render unit statuses =="
sqlite3 "$DB_PATH" <<SQL
.headers on
.mode column
SELECT status, COUNT(*) AS n
FROM render_units
WHERE production_id='$PROD' AND status!='stale'
GROUP BY status
ORDER BY status;
SQL

echo
echo "== Active provider jobs by model/job_set hint =="
sqlite3 "$DB_PATH" <<SQL
.headers on
.mode column
SELECT
  pj.status,
  COALESCE(json_extract(pj.request_json, '$.model'), 'unknown') AS model,
  COUNT(*) AS n
FROM provider_jobs pj
WHERE pj.production_id='$PROD'
  AND pj.status IN ('submitted','running')
GROUP BY pj.status, model
ORDER BY pj.status, model;
SQL

echo
echo "== Staling failed/running generate stage so it can resume cleanly =="
sqlite3 "$DB_PATH" <<SQL
BEGIN;

-- If any provider job status still contains Higgsfield table output, poll it again.
UPDATE provider_jobs
SET status='running'
WHERE production_id='$PROD'
  AND status NOT IN ('submitted','running','completed','failed');

-- Failed active render units can be regenerated, but the concurrency guard
-- prevents them from being submitted while capacity is full.
UPDATE render_units
SET status='ordered', updated_at=datetime('now')
WHERE production_id='$PROD'
  AND status='failed';

-- Rerun generate and downstream false-success stages.
UPDATE stage_runs
SET status='stale', updated_at=datetime('now')
WHERE production_id='$PROD'
  AND stage_name IN (
    'generate_media',
    'qa_media',
    'repair',
    'graphics_compositing',
    'assemble',
    'qa_final',
    'gate_b_review',
    'publish',
    'analytics'
  )
  AND status IN ('succeeded','failed','running');

COMMIT;
SQL

echo
echo "== Render unit statuses after DB cleanup =="
sqlite3 "$DB_PATH" <<SQL
.headers on
.mode column
SELECT status, COUNT(*) AS n
FROM render_units
WHERE production_id='$PROD' AND status!='stale'
GROUP BY status
ORDER BY status;
SQL

if [[ "$RUN_RESUME" == "1" ]]; then
  echo
  echo "== Resuming production with capped concurrency =="
  HIGGSFIELD_MAX_CONCURRENT="$HIGGSFIELD_MAX_CONCURRENT" \
    python3 scripts/produce_db.py resume "$PROD"
else
  echo
  echo "RUN_RESUME=0 set; skipping resume."
  echo "Run manually later:"
  echo "  HIGGSFIELD_MAX_CONCURRENT=$HIGGSFIELD_MAX_CONCURRENT python3 scripts/produce_db.py resume \"$PROD\""
fi

echo
echo "== Concurrency patch script completed =="
echo "Backups are in: $BACKUP_DIR"

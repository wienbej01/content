#!/usr/bin/env bash
set -euo pipefail

# recover_assembly_block.sh
#
# Purpose:
#   Recover prod_58eba01e58fd43939feb518711a49576 from the DB assembly block where
#   Higgsfield CLI table output left externally-completed jobs stuck as "generating".
#
# Usage:
#   cd ~/YTchannel
#   chmod +x recover_assembly_block.sh
#   ./recover_assembly_block.sh
#
# Optional:
#   PROD=prod_xxx DB_PATH=db/production.db ./recover_assembly_block.sh
#   RUN_RESUME=0 ./recover_assembly_block.sh   # patch + DB reset only, no resume
#
# Notes:
#   - This can trigger new Higgsfield calls for failed units reset to ordered.
#   - The DB and adapter file are backed up before mutation.
#   - The patch is designed for the current branch state and refuses to continue
#     if expected adapter patterns are not found.

PROD="${PROD:-prod_58eba01e58fd43939feb518711a49576}"
DB_PATH="${DB_PATH:-db/production.db}"
RUN_RESUME="${RUN_RESUME:-1}"

if [[ ! -f "scripts/paid_adapters.py" || ! -f "scripts/produce_db.py" ]]; then
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
BACKUP_DIR="reports/debug/recovery_${PROD}_${TS}"
mkdir -p "$BACKUP_DIR"

echo "== Recovery starting =="
echo "Production: $PROD"
echo "DB:         $DB_PATH"
echo "Backup dir: $BACKUP_DIR"
echo

cp scripts/paid_adapters.py "$BACKUP_DIR/paid_adapters.py.bak"
cp "$DB_PATH" "$BACKUP_DIR/production.db.bak"

echo "== Patching scripts/paid_adapters.py =="

python3 - <<'PY'
from pathlib import Path
import sys

path = Path("scripts/paid_adapters.py")
text = path.read_text()

# Ensure regex support is imported.
if "import re" not in text.splitlines()[:20]:
    text = text.replace(
        "import hashlib, json, os, subprocess, tempfile, time",
        "import hashlib, json, os, re, subprocess, tempfile, time",
    )

old_submit_tail = """        r = subprocess.run(args, capture_output=True, text=True)
        if r.returncode != 0:
            raise ProviderAdapterError(f"Higgsfield submit failed: {r.stderr[:500]}")
        job_id = r.stdout.strip()
        return {"external_job_id": job_id, "status": "submitted",
                "raw_request": json.dumps(payload, sort_keys=True, default=str)}
"""

new_submit_tail = """        r = subprocess.run(args, capture_output=True, text=True)
        if r.returncode != 0:
            raise ProviderAdapterError(f"Higgsfield submit failed: {r.stderr[:500]}")

        # Higgsfield CLI may return a table or extra text, not just the UUID.
        # Store only the UUID so later `higgsfield generate get <id>` calls work.
        m = re.search(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            r.stdout,
        )
        if not m:
            raise ProviderAdapterError(
                f"Higgsfield submit returned no UUID: stdout={r.stdout[:500]} stderr={r.stderr[:500]}"
            )
        job_id = m.group(0)

        return {"external_job_id": job_id, "status": "submitted",
                "raw_request": json.dumps(payload, sort_keys=True, default=str)}
"""

if old_submit_tail in text:
    text = text.replace(old_submit_tail, new_submit_tail)
elif "Higgsfield submit returned no UUID" in text:
    pass
else:
    print("ERROR: Could not find expected submit() tail to patch.", file=sys.stderr)
    sys.exit(2)

old_poll = """    def poll(self, external_job_id: str) -> dict:
        r = subprocess.run(["higgsfield", "generate", "get", external_job_id],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return {"status": "failed", "error": r.stderr[:500]}
        try:
            data = json.loads(r.stdout)
        except json.JSONDecodeError:
            data = {"state": r.stdout.strip()}
        state = data.get("state", data.get("status", "running"))
        state_map = {"completed": "completed", "done": "completed", "running": "running",
                     "failed": "failed", "submitted": "submitted", "processing": "running"}
        return {"status": state_map.get(state, state), "raw_response": json.dumps(data, default=str)}
"""

new_poll = """    def poll(self, external_job_id: str) -> dict:
        r = subprocess.run(["higgsfield", "generate", "get", external_job_id],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return {"status": "failed", "error": r.stderr[:500]}

        raw = r.stdout.strip()

        # Preferred path: JSON output from the CLI/API.
        try:
            data = json.loads(raw)
            state = str(data.get("state", data.get("status", "running"))).lower()
            state_map = {
                "completed": "completed",
                "done": "completed",
                "running": "running",
                "failed": "failed",
                "submitted": "submitted",
                "processing": "running",
                "waiting": "running",
                "queued": "running",
            }
            return {
                "status": state_map.get(state, "running"),
                "raw_response": json.dumps(data, default=str),
            }
        except json.JSONDecodeError:
            pass

        # Observed path: Higgsfield CLI returns a human-readable table, e.g.
        # ID DATE MODEL STATUS URL ... completed ...
        lowered = raw.lower()
        padded = f" {lowered} "

        if " failed " in padded or "\\nfailed" in lowered:
            return {"status": "failed", "raw_response": raw, "error": raw[:500]}

        if " completed " in padded or "\\ncompleted" in lowered:
            return {"status": "completed", "raw_response": raw}

        if (
            " waiting " in padded
            or " running " in padded
            or " processing " in padded
            or " submitted " in padded
            or " queued " in padded
        ):
            return {"status": "running", "raw_response": raw}

        # Unknown non-JSON text: do not poison provider_jobs.status with the raw table.
        # Treat as running so the next resume can poll again.
        return {"status": "running", "raw_response": raw}
"""

if old_poll in text:
    text = text.replace(old_poll, new_poll)
elif "Observed path: Higgsfield CLI returns a human-readable table" in text:
    pass
else:
    print("ERROR: Could not find expected poll() body to patch.", file=sys.stderr)
    sys.exit(3)

path.write_text(text)
print("Patched scripts/paid_adapters.py")
PY

echo
echo "== Basic syntax check =="
python3 -m py_compile scripts/paid_adapters.py

echo
echo "== Current render unit status before DB normalization =="
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
echo "== Normalizing DB states =="
sqlite3 "$DB_PATH" <<SQL
BEGIN;

-- Provider statuses polluted by Higgsfield table output must be polled again.
UPDATE provider_jobs
SET status='running'
WHERE production_id='$PROD'
  AND status NOT IN ('submitted','running','completed','failed');

-- Reset failed active render units for regeneration. This may trigger paid calls.
UPDATE render_units
SET status='ordered', updated_at=datetime('now')
WHERE production_id='$PROD'
  AND status='failed';

-- Rerun downstream stages that were falsely marked succeeded/failed.
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
  AND status IN ('succeeded','failed');

COMMIT;
SQL

echo
echo "== Current render unit status after DB normalization =="
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
echo "== Outstanding invalid units =="
sqlite3 "$DB_PATH" <<SQL
.headers on
.mode column
SELECT ordinal, label, slot_index, slot_total, id, status, asset_type, model, active_artifact_id
FROM render_units
WHERE production_id='$PROD'
  AND status!='stale'
  AND status NOT IN ('valid','local_graphic')
ORDER BY ordinal;
SQL

if [[ "$RUN_RESUME" == "1" ]]; then
  echo
  echo "== Resuming production =="
  python3 scripts/produce_db.py resume "$PROD"
else
  echo
  echo "RUN_RESUME=0 set; skipping resume."
  echo "Run manually later:"
  echo "  python3 scripts/produce_db.py resume \"$PROD\""
fi

echo
echo "== Recovery script completed =="
echo "Backups are in: $BACKUP_DIR"

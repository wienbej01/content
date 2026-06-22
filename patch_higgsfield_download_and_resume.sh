#!/usr/bin/env bash
set -euo pipefail

# patch_higgsfield_download_and_resume.sh
#
# Fixes HiggsfieldSeedanceAdapter.download() for CLI versions where:
#   higgsfield generate download <id> --output <path>
# fails with:
#   Error: unknown flag: --output
#
# Usage:
#   cd ~/YTchannel
#   chmod +x patch_higgsfield_download_and_resume.sh
#   ./patch_higgsfield_download_and_resume.sh
#
# Optional:
#   RUN_RESUME=0 ./patch_higgsfield_download_and_resume.sh

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
BACKUP_DIR="reports/debug/download_patch_${PROD}_${TS}"
mkdir -p "$BACKUP_DIR"

echo "== Higgsfield download patch starting =="
echo "Production: $PROD"
echo "DB:         $DB_PATH"
echo "Backup dir: $BACKUP_DIR"
echo

cp scripts/paid_adapters.py "$BACKUP_DIR/paid_adapters.py.bak"
cp "$DB_PATH" "$BACKUP_DIR/production.db.bak"

python3 - <<'PY'
from pathlib import Path
import sys

path = Path("scripts/paid_adapters.py")
text = path.read_text()

if "import re" not in text.splitlines()[:20]:
    text = text.replace(
        "import hashlib, json, os, subprocess, tempfile, time",
        "import hashlib, json, os, re, subprocess, tempfile, time",
    )

start = text.find("    def download(self, external_job_id: str, output_path: Path) -> Path:")
if start == -1:
    print("ERROR: Could not find HiggsfieldSeedanceAdapter.download() start.", file=sys.stderr)
    sys.exit(2)

# The next class starts immediately after HiggsfieldSeedanceAdapter.
end_marker = "\n\nclass ElevenLabsAdapter"
end = text.find(end_marker, start)
if end == -1:
    print("ERROR: Could not find end of HiggsfieldSeedanceAdapter before ElevenLabsAdapter.", file=sys.stderr)
    sys.exit(3)

new_download = """    def download(self, external_job_id: str, output_path: Path) -> Path:
        # Download a completed Higgsfield video to output_path.
        #
        # Some Higgsfield CLI versions do not accept:
        #   higgsfield generate download <id> --output <path>
        # They do expose the final CloudFront MP4 URL in:
        #   higgsfield generate get <id>
        # So this method prefers direct URL download, then falls back through
        # common CLI download syntaxes.
        import shutil
        import urllib.request

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        def _accept_candidate(candidate: Path) -> Path | None:
            candidate = Path(candidate)
            if candidate.exists() and candidate.stat().st_size > 0:
                if candidate.resolve() != output_path.resolve():
                    shutil.copy2(candidate, output_path)
                if output_path.exists() and output_path.stat().st_size > 0:
                    return output_path
            return None

        get_result = subprocess.run(
            ["higgsfield", "generate", "get", external_job_id],
            capture_output=True,
            text=True,
        )
        get_raw = (get_result.stdout or "") + "\\n" + (get_result.stderr or "")

        m = re.search(r"https?://[^\\s]+?\\.mp4(?:\\?[^\\s]+)?", get_raw)
        if m:
            url = m.group(0).rstrip(" ,;|)]}")
            try:
                urllib.request.urlretrieve(url, str(output_path))
                accepted = _accept_candidate(output_path)
                if accepted:
                    return accepted
            except Exception as e:
                last_url_error = str(e)
            else:
                last_url_error = "downloaded URL but output file was missing or empty"
        else:
            last_url_error = f"no .mp4 URL found in generate get output: {get_raw[:500]}"

        attempts = [
            ["higgsfield", "generate", "download", external_job_id, str(output_path)],
            ["higgsfield", "generate", "download", external_job_id, "-o", str(output_path)],
            ["higgsfield", "generate", "download", external_job_id, "--path", str(output_path)],
            ["higgsfield", "generate", "download", external_job_id, "--dir", str(output_path.parent)],
        ]

        errors = [f"url_download: {last_url_error}"]
        for cmd in attempts:
            r = subprocess.run(cmd, capture_output=True, text=True)
            accepted = _accept_candidate(output_path)
            if accepted:
                return accepted

            candidates = sorted(
                output_path.parent.glob("*.mp4"),
                key=lambda p: p.stat().st_mtime if p.exists() else 0,
                reverse=True,
            )
            for candidate in candidates:
                accepted = _accept_candidate(candidate)
                if accepted:
                    return accepted

            errors.append(
                f"{' '.join(cmd)} -> rc={r.returncode} stderr={r.stderr[:250]} stdout={r.stdout[:250]}"
            )

        with tempfile.TemporaryDirectory(prefix="hf_download_") as td:
            td_path = Path(td)
            r = subprocess.run(
                ["higgsfield", "generate", "download", external_job_id],
                capture_output=True,
                text=True,
                cwd=str(td_path),
            )
            candidates = sorted(
                td_path.glob("*.mp4"),
                key=lambda p: p.stat().st_mtime if p.exists() else 0,
                reverse=True,
            )
            for candidate in candidates:
                accepted = _accept_candidate(candidate)
                if accepted:
                    return accepted
            errors.append(
                f"cwd temp download -> rc={r.returncode} stderr={r.stderr[:250]} stdout={r.stdout[:250]}"
            )

        raise ProviderAdapterError(
            "Higgsfield download failed for "
            f"{external_job_id}: " + " | ".join(errors)[:1200]
        )
"""

# Avoid double-patching if already applied.
current_body = text[start:end]
if "Some Higgsfield CLI versions do not accept" in current_body:
    print("download() patch already present")
else:
    text = text[:start] + new_download + text[end:]
    path.write_text(text)
    print("Patched HiggsfieldSeedanceAdapter.download()")
PY

echo
echo "== Basic syntax check =="
python3 -m py_compile scripts/paid_adapters.py

echo
echo "== Provider job statuses before normalization =="
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
echo "== Render unit statuses before normalization =="
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
echo "== Normalizing provider statuses and stale downstream runs =="
sqlite3 "$DB_PATH" <<SQL
BEGIN;

UPDATE provider_jobs
SET status='running'
WHERE production_id='$PROD'
  AND status NOT IN ('submitted','running','completed','failed');

UPDATE render_units
SET status='ordered', updated_at=datetime('now')
WHERE production_id='$PROD'
  AND status='failed';

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
echo "== Provider job statuses after normalization =="
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
echo "== Render unit statuses after normalization =="
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
  echo "== Resuming production =="
  python3 scripts/produce_db.py resume "$PROD"
else
  echo
  echo "RUN_RESUME=0 set; skipping resume."
  echo "Run manually later:"
  echo "  python3 scripts/produce_db.py resume \"$PROD\""
fi

echo
echo "== Download patch script completed =="
echo "Backups are in: $BACKUP_DIR"

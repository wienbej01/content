#!/usr/bin/env python3
"""Canary freshness gate for S06_FIX_T003.

Validates that a canary render produced a genuinely NEW artifact after unlock.

Usage (dry-run):
  python3 scripts/evals/eval_canary_freshness.py --render-unit-id <id> --out <json> --unlock-path <path>

Usage (after render):
  python3 scripts/evals/eval_canary_freshness.py --post-render --render-unit-id <id> --out <json>
"""
import argparse
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

UNLOCK_PATH = Path("ops/ACTUAL_RENDER_UNLOCK.json")
CANARY_RU_ID = "render_f91a245c14b341b6a7975e2a8d5716fc"
PRODUCTION_ID = "prod_2f9bb58c0508465fb51ac6b4578bba92"


def load_unlock(path: Path) -> dict:
    data = json.loads(path.read_text()) if path.exists() else {}
    return data


def check_freshness(ru_id: str, db_path: str, unlock_path: Path) -> dict:
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    checks = []
    issues = []

    def add_check(name: str, passed: bool, detail: str):
        checks.append({"check": name, "pass": passed, "detail": detail})

    # 1. Unlock file exists and has timestamps
    unlock = load_unlock(unlock_path)
    unlock_ts = unlock.get("created_at", "")
    attempt_id = unlock.get("canary_attempt_id", "")
    has_attempt_id = bool(attempt_id) and len(attempt_id) >= 8
    add_check("unlock_file_exists", unlock_path.exists(), str(unlock_path))
    add_check("unlock_has_canary_attempt_id", has_attempt_id,
              f"attempt_id={'set' if has_attempt_id else 'NOT SET'}")

    if not has_attempt_id:
        issues.append("Unlock file missing canary_attempt_id — required for fresh idempotency key")

    # 2. Provider job for this render unit exists after unlock
    pj = conn.execute("""
        SELECT id, submitted_at, completed_at, status, external_job_id, idempotency_key
        FROM provider_jobs WHERE render_unit_id=?
        ORDER BY rowid DESC LIMIT 1
    """, (ru_id,)).fetchone()

    if not pj:
        add_check("provider_job_exists", False, "No provider job found")
        issues.append("No provider job exists for canary unit")
        conn.close()
        return {"checks": checks, "issues": issues, "fresh": False,
                "overall": "BLOCKED_NEEDS_FRESH_CANARY_RENDER"}

    pj = dict(pj)
    sub_at = pj.get("submitted_at", "") or ""
    comp_at = pj.get("completed_at", "") or ""
    status = pj.get("status", "")
    ext_id = pj.get("external_job_id", "") or ""
    idem_key = pj.get("idempotency_key", "") or ""
    pj_id = pj["id"]

    # 3. submitted_at >= unlock_created_at
    sub_ok = bool(sub_at) and (sub_at >= unlock_ts[:19])
    add_check("submitted_at_after_unlock", sub_ok,
              f"submitted_at={sub_at} unlock_ts={unlock_ts[:19]}")

    # 4. completed_at >= unlock_created_at (if completed)
    if status == "completed":
        comp_ok = bool(comp_at) and (comp_at >= unlock_ts[:19])
        add_check("completed_at_after_unlock", comp_ok,
                  f"completed_at={comp_at} unlock_ts={unlock_ts[:19]}")
    else:
        add_check("completed_at_after_unlock", False,
                  f"status={status} — not yet completed")

    # 5. generated_media artifact created after unlock
    art = conn.execute("""
        SELECT id, created_at, sha256 FROM artifacts
        WHERE kind='generated_media' AND provider_job_id=?
        ORDER BY created_at DESC LIMIT 1
    """, (pj_id,)).fetchone()

    if art:
        art_ts = art["created_at"] or ""
        art_ok = art_ts >= unlock_ts[:19]
        add_check("artifact_created_after_unlock", art_ok,
                  f"artifact.created_at={art_ts} unlock={unlock_ts[:19]}")
    else:
        art = None
        art_ok = False
        add_check("artifact_created_after_unlock", False,
                  "No generated_media artifact found")

    # 6. artifact.provider_job_id matches new provider_job.id
    if art:
        add_check("artifact_job_id_matches", True,
                  f"artifact linked to job {pj_id[:24]}...")
    else:
        add_check("artifact_job_id_matches", False, "No artifact to check")

    # 7. Idempotency key includes canary_attempt_id
    if has_attempt_id and idem_key:
        idem_has_attempt = attempt_id in idem_key
    else:
        idem_has_attempt = False
    add_check("idempotency_key_includes_attempt_id", idem_has_attempt,
              f"key={idem_key[:60]}... attempt={attempt_id[:12] if attempt_id else 'N/A'}")

    # 8. This is a new provider_job (not reused from before unlock)
    # Check if there's an OLDER job with the same external_job_id
    older_jobs = conn.execute("""
        SELECT COUNT(*) as cnt FROM provider_jobs
        WHERE external_job_id=? AND rowid < (
            SELECT MAX(rowid) FROM provider_jobs WHERE external_job_id=?
        )
    """, (ext_id, ext_id)).fetchone()
    is_new_job = (older_jobs["cnt"] if older_jobs else 0) == 0
    # Actually this checks if there are older jobs with the SAME external ID
    # For a genuinely NEW job, there should be NO old jobs with the same external ID
    dup_check = conn.execute("""
        SELECT COUNT(*) as cnt FROM provider_jobs
        WHERE external_job_id=? AND id != ?
    """, (ext_id, pj_id)).fetchone()
    is_duplicate = (dup_check["cnt"] if dup_check else 0) > 0

    add_check("new_provider_job_not_duplicate", not is_duplicate,
              f"external_job_id={ext_id[:24]}... duplicate={is_duplicate}")

    # 9. Diagnostic audio extracted
    diag = conn.execute("""
        SELECT id, created_at FROM artifacts
        WHERE kind='provider_diagnostic_audio' AND provider_job_id=?
        ORDER BY created_at DESC LIMIT 1
    """, (pj_id,)).fetchone()
    diag_ok = diag is not None
    add_check("diagnostic_audio_extracted", diag_ok,
              f"diag_audio={'found' if diag_ok else 'MISSING'}")

    if not diag_ok:
        issues.append("Diagnostic audio not extracted for HERO_SYNC_LOCKED unit")

    # 10. Source_slice_sha256 exists on render unit
    ru = conn.execute("""
        SELECT source_slice_sha256 FROM render_units WHERE id=?
    """, (ru_id,)).fetchone()
    slice_sha = ru["source_slice_sha256"] if ru and ru["source_slice_sha256"] else ""
    add_check("source_slice_sha256_present", bool(slice_sha),
              f"sha256={slice_sha[:24] if slice_sha else 'MISSING'}")

    conn.close()

    # Freshness decision
    freshness_checks = ["submitted_at_after_unlock", "completed_at_after_unlock",
                        "artifact_created_after_unlock", "artifact_job_id_matches",
                        "new_provider_job_not_duplicate", "diagnostic_audio_extracted",
                        "source_slice_sha256_present"]
    fresh_checks = [c for c in checks if c["check"] in freshness_checks]
    fresh_pass = all(c["pass"] for c in fresh_checks)

    if is_duplicate:
        overall = "ACTUAL_CANARY_RENDER_NOT_EXECUTED"
    elif fresh_pass:
        overall = "PASS_FRESH_CANARY"
    else:
        overall = "BLOCKED_NEEDS_FRESH_CANARY_RENDER"

    return {
        "eval_id": "S06_FIX_T003_canary_freshness",
        "production_id": PRODUCTION_ID,
        "render_unit_id": ru_id,
        "canary_attempt_id": attempt_id,
        "unlock_created_at": unlock_ts,
        "fresh": fresh_pass,
        "overall": overall,
        "checks": checks,
        "issues": issues,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Canary freshness gate")
    ap.add_argument("--render-unit-id", default=CANARY_RU_ID)
    ap.add_argument("--out", type=Path, default=Path("reports/karpathy_loop/sprint_06/S06_FIX_T003/eval_result_before.json"))
    ap.add_argument("--db-path", default=None)
    ap.add_argument("--unlock-path", type=Path, default=UNLOCK_PATH)
    args = ap.parse_args(argv)

    db_path = args.db_path or os.environ.get("PRODUCTION_DB_PATH", "db/production.db")
    result = check_freshness(args.render_unit_id, db_path, args.unlock_path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))

    print(f"Canary freshness gate for {args.render_unit_id}:")
    print(f"  Overall: {result['overall']}")
    print(f"  Fresh: {result['fresh']}")
    for c in result["checks"]:
        mark = "✓" if c["pass"] else "✗"
        print(f"  [{mark}] {c['check']}: {c['detail']}")
    for iss in result["issues"]:
        print(f"  ! {iss}")
    return 0


def _generate_attempt_id() -> str:
    """Generate a unique canary_attempt_id for the unlock file."""
    return f"canary_{uuid.uuid4().hex[:16]}"


if __name__ == "__main__":
    raise SystemExit(main())

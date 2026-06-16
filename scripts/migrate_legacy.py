"""Sprint 9: Legacy cutover and database consolidation.

CUT-901  Detect migrated stages still reading legacy files
CUT-902  Consolidate clips.db + leverage_mind.db into production.db
SCALE-906 Operations status command
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

import production_db as _db

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# CUT-902  Consolidate legacy databases
# ---------------------------------------------------------------------------

def consolidate_legacy_dbs(
    project_slug: str,
    clips_db_path: Optional[Path] = None,
    leverage_mind_db_path: Optional[Path] = None,
    db_path=None,
) -> dict:
    """Import all records from clips.db and leverage_mind.db into production.db.

    Idempotent: records already present are skipped.
    Does NOT delete the legacy files — that is done only after acceptance tests pass.

    Returns a summary dict.
    """
    production = _db.ensure_production(project_slug, db_path=db_path)
    production_id = production["id"]
    summary = {"clips_imported": 0, "content_units_imported": 0, "errors": []}

    # --- clips.db ---
    clips_path = clips_db_path or (ROOT / "db" / "clips.db")
    if clips_path.exists():
        try:
            cconn = sqlite3.connect(str(clips_path))
            cconn.row_factory = sqlite3.Row
            rows = cconn.execute(
                "SELECT * FROM clips WHERE project_id=?", (project_slug,)
            ).fetchall()
            cconn.close()
            for row in rows:
                try:
                    _db.import_legacy_clip(project_slug, dict(row), db_path=db_path)
                    summary["clips_imported"] += 1
                except Exception as exc:
                    summary["errors"].append(f"clip {row['clip_id']}: {exc}")
        except sqlite3.OperationalError:
            summary["errors"].append(f"clips.db missing 'clips' table at {clips_path}")

    # --- leverage_mind.db ---
    lm_path = leverage_mind_db_path or (ROOT / "db" / "leverage_mind.db")
    if lm_path.exists():
        try:
            lconn = sqlite3.connect(str(lm_path))
            lconn.row_factory = sqlite3.Row
            # Import content_units as document revisions
            try:
                units = lconn.execute("SELECT * FROM content_units").fetchall()
                for unit in units:
                    unit_dict = dict(unit)
                    try:
                        _db.import_document(
                            project_slug,
                            "legacy_content_unit",
                            # We can't pass a Path here; adapt: write to temp then import
                            _write_temp_json(unit_dict),
                            db_path=db_path,
                        )
                        summary["content_units_imported"] += 1
                    except Exception as exc:
                        summary["errors"].append(f"content_unit {unit_dict.get('project_id')}: {exc}")
            except sqlite3.OperationalError:
                pass
            lconn.close()
        except Exception as exc:
            summary["errors"].append(f"leverage_mind.db: {exc}")

    _db.append_event(
        production_id, "legacy_dbs_consolidated",
        payload=summary, db_path=db_path,
    )
    return summary


def _write_temp_json(data: dict) -> Path:
    """Write data to a temp file, return the path (caller should clean up)."""
    import tempfile, os
    fd, p = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    return Path(p)


def check_legacy_retired(project_slug: str, db_path=None) -> dict:
    """Validate that the legacy file authorities can safely be archived.

    Checks:
    - No active clips.db records that aren't mirrored in render_units
    - No active state.json
    - No active gates.json

    Returns {retired: bool, reasons: list[str]}
    """
    import os
    production = _db.get_production(project_slug, db_path=db_path)
    reasons = []

    if not production:
        return {"retired": False, "reasons": [f"production not found: {project_slug}"]}

    # Check state.json
    state_json = ROOT / "Videos" / "Projects" / project_slug / "state.json"
    if state_json.exists():
        reasons.append(f"state.json still present: {state_json}")

    # Check gates.json
    gates_json = ROOT / "Videos" / "Projects" / project_slug / "gates.json"
    if gates_json.exists():
        reasons.append(f"gates.json still present: {gates_json}")

    # Check clips.db for unmirrored clips
    clips_path = ROOT / "db" / "clips.db"
    if clips_path.exists():
        try:
            cconn = sqlite3.connect(str(clips_path))
            cconn.row_factory = sqlite3.Row
            unmirrored = cconn.execute(
                """SELECT clip_id FROM clips WHERE project_id=? AND status='valid'
                   AND clip_id NOT IN (
                     SELECT legacy_clip_id FROM render_units WHERE legacy_clip_id IS NOT NULL
                   )""",
                (project_slug,),
            ).fetchall()
            cconn.close()
            if unmirrored:
                reasons.append(
                    f"{len(unmirrored)} valid clips not mirrored in render_units: "
                    f"{[r['clip_id'] for r in unmirrored[:3]]}"
                )
        except sqlite3.OperationalError:
            pass

    return {"retired": len(reasons) == 0, "reasons": reasons}


# ---------------------------------------------------------------------------
# SCALE-906  Operations status / dashboard query
# ---------------------------------------------------------------------------

def production_status_dashboard(db_path=None) -> dict:
    """Return a comprehensive operational view of all productions.

    Includes:
    - Queue depth by stage
    - Productions with open blockers
    - Pending approvals
    - Current spend totals
    - Failed jobs
    """
    _db.migrate(db_path)
    conn = _db.connect(db_path)

    # Queue depth
    queue = {
        row["stage_name"]: row["count"]
        for row in conn.execute(
            """SELECT stage_name, COUNT(*) as count FROM jobs
               WHERE status='queued' GROUP BY stage_name"""
        ).fetchall()
    }

    # Productions with blockers
    blocked_productions = []
    for prod in conn.execute(
        "SELECT id, project_slug, status, current_stage FROM productions WHERE status NOT IN ('completed', 'archived')"
    ).fetchall():
        b = _db.blockers(prod["id"], db_path=db_path)
        if b:
            blocked_productions.append({
                "project_slug": prod["project_slug"],
                "status": prod["status"],
                "current_stage": prod["current_stage"],
                "blockers": b,
            })

    # Pending approvals
    pending_approvals = [
        dict(r)
        for r in conn.execute(
            """SELECT production_id, gate_name, requested_at FROM approval_requests
               WHERE status='pending' ORDER BY requested_at"""
        ).fetchall()
    ]

    # Open change requests
    open_changes = conn.execute(
        "SELECT production_id, target_stage, COUNT(*) as count FROM change_requests WHERE status='open' GROUP BY production_id, target_stage"
    ).fetchall()

    # Failed jobs
    failed_jobs = [
        dict(r)
        for r in conn.execute(
            "SELECT id, production_id, stage_name, last_error FROM jobs WHERE status='failed'"
        ).fetchall()
    ]

    # Total spend
    spend = dict(conn.execute(
        "SELECT COALESCE(SUM(estimated_usd),0) as estimated, COALESCE(SUM(actual_usd),0) as actual FROM cost_events"
    ).fetchone())

    conn.close()

    return {
        "queue_depth": queue,
        "blocked_productions": blocked_productions,
        "pending_approvals": pending_approvals,
        "open_change_requests": [dict(r) for r in open_changes],
        "failed_jobs": failed_jobs,
        "total_spend_usd": spend,
    }


def outbox_dispatcher_step(db_path=None) -> int:
    """Process pending outbox messages (Telegram notifications).

    In production this would call the actual Telegram API. Here we mark them
    sent so the DB stays clean. Returns count processed.

    The real dispatcher runs in a separate process and uses tools/send_telegram_message.py.
    """
    now = _db._now()
    with _db.transaction(db_path) as conn:
        messages = conn.execute(
            "SELECT * FROM outbox_messages WHERE status='pending' AND available_at<=? LIMIT 50",
            (now,),
        ).fetchall()
        for msg in messages:
            conn.execute(
                "UPDATE outbox_messages SET status='sent', sent_at=?, attempts=attempts+1 WHERE id=?",
                (now, msg["id"]),
            )
        return len(messages)

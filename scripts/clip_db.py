#!/usr/bin/env python3
"""clip_db.py — Clip/Slot Authority Database manager.

Single source of truth for clip IDs, canonical paths, status, and change requests.
No pipeline step may derive clip paths independently — they must ask this module.

Usage:
  python3 scripts/clip_db.py init
  python3 scripts/clip_db.py list <project_id> [--status STATUS]
  python3 scripts/clip_db.py show <clip_id>
  python3 scripts/clip_db.py coverage <project_id> <source_beat_id>
  python3 scripts/clip_db.py requests <project_id> [--step STEP]
  python3 scripts/clip_db.py assert-valid <project_id>
"""
import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "clips.db"

# Allow tests to override via env var or module-level assignment
_db_path_override = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS clips (
    clip_id            TEXT PRIMARY KEY,
    project_id         TEXT NOT NULL,
    source_beat_id     TEXT NOT NULL,
    production_beat_id TEXT NOT NULL,
    slot_id            TEXT,
    split_index        INTEGER,
    split_total        INTEGER,
    output_path        TEXT NOT NULL,
    asset_type         TEXT NOT NULL,
    model              TEXT,
    audio_policy       TEXT NOT NULL,
    lipsync_required   INTEGER NOT NULL,
    required_start_sec REAL NOT NULL,
    required_end_sec   REAL NOT NULL,
    required_dur_sec   REAL NOT NULL,
    audio_slice_path   TEXT,
    audio_slice_sha256 TEXT,
    speech_len_sec     REAL,
    status             TEXT NOT NULL,
    status_reason      TEXT,
    actual_dur_sec     REAL,
    actual_width       INTEGER,
    actual_height      INTEGER,
    actual_has_audio   INTEGER,
    actual_sha256      TEXT,
    plan_sha256        TEXT,
    upstream_sha256    TEXT,
    created_at         TEXT NOT NULL,
    created_by_step    TEXT,
    generated_at       TEXT,
    last_validated_at  TEXT,
    invalidated_at     TEXT,
    UNIQUE(project_id, production_beat_id, slot_id)
);

CREATE TABLE IF NOT EXISTS clip_access_log (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    clip_id TEXT NOT NULL,
    step    TEXT NOT NULL,
    action  TEXT NOT NULL,
    detail  TEXT,
    at      TEXT NOT NULL,
    FOREIGN KEY (clip_id) REFERENCES clips(clip_id)
);

CREATE TABLE IF NOT EXISTS clip_change_requests (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    clip_id       TEXT NOT NULL,
    change_type   TEXT NOT NULL,
    requested_by  TEXT NOT NULL,
    target_step   TEXT NOT NULL,
    reason        TEXT NOT NULL,
    status        TEXT NOT NULL,
    requested_at  TEXT NOT NULL,
    resolved_at   TEXT,
    resolved_by   TEXT,
    outcome       TEXT,
    FOREIGN KEY (clip_id) REFERENCES clips(clip_id)
);
"""


def _get_db_path():
    if _db_path_override:
        return Path(_db_path_override)
    env = os.environ.get("CLIP_DB_PATH")
    if env:
        return Path(env)
    return DB_PATH


def get_db(db_path=None):
    """Return a connection to the clips database."""
    p = Path(db_path) if db_path else _get_db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path=None):
    """Create tables if they don't exist."""
    conn = get_db(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def _now():
    """ISO timestamp."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _clip_id(project_id, production_beat_id, slot_id=None):
    """Canonical clip ID."""
    suffix = slot_id if slot_id else "whole"
    return f"{project_id}::{production_beat_id}::{suffix}"


def _canonical_path(project_id, segment_id, production_beat_id, slot_id=None):
    """THE single path rule. All clip paths are computed here and nowhere else."""
    filename = f"{production_beat_id}_{slot_id}.mp4" if slot_id else f"{production_beat_id}.mp4"
    return f"assets/media/{project_id}/{segment_id}/{filename}"


def _sha256_file(path):
    """Compute SHA-256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _row_to_dict(row):
    if row is None:
        return None
    return dict(row)


# --- Ordering authority ---

def order_clip(project_id, source_beat_id, production_beat_id, segment_id, asset_type, model,
               audio_policy, lipsync_required, required_start_sec, required_end_sec,
               slot_id=None, split_index=None, split_total=None, speech_len_sec=None,
               plan_sha256=None, created_by_step='compile_media_plan', db_path=None):
    """Upsert a clip row with canonical clip_id + output_path. Returns clip dict."""
    cid = _clip_id(project_id, production_beat_id, slot_id)
    opath = _canonical_path(project_id, segment_id, production_beat_id, slot_id)
    required_dur_sec = required_end_sec - required_start_sec
    now = _now()

    conn = get_db(db_path)
    conn.execute("""
        INSERT INTO clips (clip_id, project_id, source_beat_id, production_beat_id, slot_id,
            split_index, split_total, output_path, asset_type, model, audio_policy,
            lipsync_required, required_start_sec, required_end_sec, required_dur_sec,
            speech_len_sec, plan_sha256, status, created_at, created_by_step)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(clip_id)
        DO UPDATE SET output_path=excluded.output_path, asset_type=excluded.asset_type,
            model=excluded.model, audio_policy=excluded.audio_policy,
            lipsync_required=excluded.lipsync_required,
            required_start_sec=excluded.required_start_sec,
            required_end_sec=excluded.required_end_sec,
            required_dur_sec=excluded.required_dur_sec,
            speech_len_sec=excluded.speech_len_sec,
            plan_sha256=excluded.plan_sha256,
            source_beat_id=excluded.source_beat_id,
            split_index=excluded.split_index, split_total=excluded.split_total
    """, (cid, project_id, source_beat_id, production_beat_id, slot_id,
          split_index, split_total, opath, asset_type, model, audio_policy,
          int(lipsync_required), required_start_sec, required_end_sec, required_dur_sec,
          speech_len_sec, plan_sha256, "ordered", now, created_by_step))
    conn.commit()
    log_access(cid, created_by_step, "order", detail=f"path={opath}", db_path=db_path)
    row = conn.execute("SELECT * FROM clips WHERE clip_id=?", (cid,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def order_clips(project_id, plan_beats, created_by_step='compile_media_plan', db_path=None):
    """Bulk order from a list of media-plan beat dicts. Returns list of clip dicts."""
    results = []
    for beat in plan_beats:
        r = order_clip(
            project_id=project_id,
            source_beat_id=beat.get("source_beat_id", beat.get("production_beat_id", beat["beat_id"])),
            production_beat_id=beat.get("production_beat_id", beat["beat_id"]),
            segment_id=beat["segment_id"],
            asset_type=beat.get("asset_type", "generated_video"),
            model=beat.get("model"),
            audio_policy=beat.get("audio_policy", "strip"),
            lipsync_required=beat.get("lipsync_required", 0),
            required_start_sec=beat.get("required_start_sec", 0.0),
            required_end_sec=beat.get("required_end_sec", beat.get("required_dur_sec", 5.0)),
            slot_id=beat.get("slot_id"),
            split_index=beat.get("split_index"),
            split_total=beat.get("split_total"),
            speech_len_sec=beat.get("speech_len_sec"),
            plan_sha256=beat.get("plan_sha256"),
            created_by_step=created_by_step,
            db_path=db_path,
        )
        results.append(r)
    return results


# --- Reuse authority ---

def can_reuse(clip_id, tolerance=0.25, db_path=None):
    """Check if a clip can be reused. Returns (bool, reason)."""
    conn = get_db(db_path)
    row = conn.execute("SELECT * FROM clips WHERE clip_id=?", (clip_id,)).fetchone()
    if not row:
        conn.close()
        return False, "clip not found in DB"

    clip = _row_to_dict(row)

    # Status check
    if clip["status"] in ("stale", "change_requested", "failed"):
        conn.close()
        return False, f"status is {clip['status']}"

    # File existence
    full_path = ROOT / clip["output_path"]
    if not full_path.exists():
        conn.close()
        return False, "file missing at output_path"

    # SHA check
    if clip["actual_sha256"]:
        current_sha = _sha256_file(full_path)
        if current_sha != clip["actual_sha256"]:
            conn.close()
            return False, "file sha256 mismatch (modified outside DB)"

    # Duration check
    if clip["actual_dur_sec"] is not None:
        if clip["actual_dur_sec"] < clip["required_dur_sec"] - tolerance:
            conn.close()
            return False, f"actual_dur {clip['actual_dur_sec']:.2f}s < required {clip['required_dur_sec']:.2f}s - tolerance"

    # Audio policy check for lipsync
    if clip["lipsync_required"] and not clip.get("actual_has_audio"):
        conn.close()
        return False, "lipsync required but clip has no audio"

    # Plan sha unchanged (if we have one recorded and a current plan_sha)
    # This check is implicit: if plan_sha changed, the clip should already be marked stale.

    conn.close()
    return True, "reusable"


# --- Status transitions ---

def record_generated(clip_id, actual_dur_sec, actual_width, actual_height, actual_has_audio,
                     actual_sha256, generated_by_step='generate_media', db_path=None):
    """Record generation results."""
    conn = get_db(db_path)
    now = _now()
    conn.execute("""
        UPDATE clips SET status='generated', actual_dur_sec=?, actual_width=?, actual_height=?,
            actual_has_audio=?, actual_sha256=?, generated_at=?, status_reason=NULL
        WHERE clip_id=?
    """, (actual_dur_sec, actual_width, actual_height, int(actual_has_audio),
          actual_sha256, now, clip_id))
    conn.commit()
    log_access(clip_id, generated_by_step, "generate", db_path=db_path)
    conn.close()


def mark_valid(clip_id, validated_by='qa_media', db_path=None):
    """Mark clip as valid (QA passed)."""
    conn = get_db(db_path)
    now = _now()
    conn.execute("UPDATE clips SET status='valid', last_validated_at=? WHERE clip_id=?", (now, clip_id))
    conn.commit()
    log_access(clip_id, validated_by, "validate", db_path=db_path)
    conn.close()


def mark_failed(clip_id, error, db_path=None):
    """Mark clip as failed."""
    conn = get_db(db_path)
    conn.execute("UPDATE clips SET status='failed', status_reason=? WHERE clip_id=?", (error, clip_id))
    conn.commit()
    log_access(clip_id, "system", "invalidate", detail=error, db_path=db_path)
    conn.close()


def mark_stale(clip_id, reason, db_path=None):
    """Mark clip as stale (upstream changed)."""
    conn = get_db(db_path)
    now = _now()
    conn.execute("UPDATE clips SET status='stale', status_reason=?, invalidated_at=? WHERE clip_id=?",
                 (reason, now, clip_id))
    conn.commit()
    log_access(clip_id, "system", "invalidate", detail=reason, db_path=db_path)
    conn.close()


# --- Interactive change-request loop ---

def request_change(clip_id, requested_by, target_step, change_type, reason, db_path=None):
    """Record a change request; sets clip status to change_requested."""
    conn = get_db(db_path)
    now = _now()
    conn.execute("""
        INSERT INTO clip_change_requests (clip_id, change_type, requested_by, target_step, reason, status, requested_at)
        VALUES (?,?,?,?,?,?,?)
    """, (clip_id, change_type, requested_by, target_step, reason, "open", now))
    conn.execute("UPDATE clips SET status='change_requested', status_reason=? WHERE clip_id=?",
                 (reason, clip_id))
    conn.commit()
    log_access(clip_id, requested_by, "invalidate", detail=f"change_request: {change_type} -> {target_step}", db_path=db_path)
    conn.close()


def open_change_requests(project_id, target_step=None, db_path=None):
    """Get open change requests, optionally filtered by target_step."""
    conn = get_db(db_path)
    if target_step:
        rows = conn.execute("""
            SELECT cr.* FROM clip_change_requests cr
            JOIN clips c ON cr.clip_id = c.clip_id
            WHERE c.project_id=? AND cr.target_step=? AND cr.status='open'
        """, (project_id, target_step)).fetchall()
    else:
        rows = conn.execute("""
            SELECT cr.* FROM clip_change_requests cr
            JOIN clips c ON cr.clip_id = c.clip_id
            WHERE c.project_id=? AND cr.status='open'
        """, (project_id,)).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def resolve_change(clip_id, resolved_by, outcome, db_path=None):
    """Resolve open change request(s) for a clip."""
    conn = get_db(db_path)
    now = _now()
    conn.execute("""
        UPDATE clip_change_requests SET status='resolved', resolved_at=?, resolved_by=?, outcome=?
        WHERE clip_id=? AND status='open'
    """, (now, resolved_by, outcome, clip_id))
    # Return clip to ordered so it can re-flow through generation
    conn.execute("UPDATE clips SET status='ordered', status_reason=NULL WHERE clip_id=?", (clip_id,))
    conn.commit()
    log_access(clip_id, resolved_by, "validate", detail=f"resolved: {outcome}", db_path=db_path)
    conn.close()


def apply_human_override(clip_id, decision, note, db_path=None):
    """Logged human override."""
    conn = get_db(db_path)
    now = _now()
    conn.execute("UPDATE clips SET status_reason=? WHERE clip_id=?", (f"human_override: {decision} — {note}", clip_id))
    conn.commit()
    log_access(clip_id, "human", "validate", detail=f"override: {decision} — {note}", db_path=db_path)
    conn.close()


def assert_all_valid(project_id, db_path=None):
    """GATE: True only if every clip is valid with no open change requests."""
    conn = get_db(db_path)
    invalid = conn.execute(
        "SELECT clip_id, status, status_reason FROM clips WHERE project_id=? AND status != 'valid'",
        (project_id,)).fetchall()
    open_reqs = conn.execute("""
        SELECT cr.* FROM clip_change_requests cr
        JOIN clips c ON cr.clip_id = c.clip_id
        WHERE c.project_id=? AND cr.status='open'
    """, (project_id,)).fetchall()
    conn.close()

    problems = [_row_to_dict(r) for r in invalid] + [_row_to_dict(r) for r in open_reqs]
    if problems:
        return False, problems
    return True, []


# --- Coverage authority ---

def coverage_for_beat(project_id, source_beat_id, db_path=None):
    """Sum required/actual durations of all clips with this source_beat_id."""
    conn = get_db(db_path)
    rows = conn.execute(
        "SELECT * FROM clips WHERE project_id=? AND source_beat_id=?",
        (project_id, source_beat_id)).fetchall()
    conn.close()

    clips = [_row_to_dict(r) for r in rows]
    required = sum(c["required_dur_sec"] for c in clips)
    available = sum(c["actual_dur_sec"] for c in clips if c["actual_dur_sec"])
    all_present = all(c["status"] in ("generated", "valid") and c["actual_dur_sec"] for c in clips)
    deficit = max(0.0, required - available)
    return {
        "required": required,
        "available": available,
        "slots": [c["clip_id"] for c in clips],
        "deficit": deficit,
        "all_present": all_present and len(clips) > 0,
    }


# --- Lookups ---

def get_clip(clip_id, db_path=None):
    """Get a single clip by ID."""
    conn = get_db(db_path)
    row = conn.execute("SELECT * FROM clips WHERE clip_id=?", (clip_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def get_path(clip_id, db_path=None):
    """Get canonical path for a clip."""
    clip = get_clip(clip_id, db_path=db_path)
    return clip["output_path"] if clip else None


def list_clips(project_id, status=None, db_path=None):
    """List clips for a project, optionally filtered by status."""
    conn = get_db(db_path)
    if status:
        rows = conn.execute("SELECT * FROM clips WHERE project_id=? AND status=?",
                            (project_id, status)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM clips WHERE project_id=?", (project_id,)).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def log_access(clip_id, step, action, detail='', db_path=None):
    """Record an access log entry."""
    conn = get_db(db_path)
    conn.execute("INSERT INTO clip_access_log (clip_id, step, action, detail, at) VALUES (?,?,?,?,?)",
                 (clip_id, step, action, detail, _now()))
    conn.commit()
    conn.close()


# --- CLI ---

def main():
    ap = argparse.ArgumentParser(description="Clip/Slot Authority Database manager.")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("init", help="Create/migrate database schema")

    p_list = sub.add_parser("list", help="List clips for a project")
    p_list.add_argument("project_id")
    p_list.add_argument("--status", default=None)

    p_show = sub.add_parser("show", help="Show a clip")
    p_show.add_argument("clip_id")

    p_cov = sub.add_parser("coverage", help="Coverage for a source beat")
    p_cov.add_argument("project_id")
    p_cov.add_argument("source_beat_id")

    p_req = sub.add_parser("requests", help="Open change requests")
    p_req.add_argument("project_id")
    p_req.add_argument("--step", default=None)

    p_av = sub.add_parser("assert-valid", help="Gate: assert all clips valid")
    p_av.add_argument("project_id")

    args = ap.parse_args()

    if args.cmd == "init":
        init_db()
        print(f"Clip DB initialized: {_get_db_path()}")
    elif args.cmd == "list":
        init_db()
        clips = list_clips(args.project_id, status=args.status)
        if not clips:
            print("  (no clips)")
            return
        for c in clips:
            print(f"  {c['clip_id']:50s} {c['status']:20s} {c['output_path']}")
    elif args.cmd == "show":
        init_db()
        c = get_clip(args.clip_id)
        if not c:
            print(f"  not found: {args.clip_id}")
            sys.exit(1)
        for k, v in c.items():
            print(f"  {k}: {v}")
    elif args.cmd == "coverage":
        init_db()
        cov = coverage_for_beat(args.project_id, args.source_beat_id)
        print(json.dumps(cov, indent=2))
    elif args.cmd == "requests":
        init_db()
        reqs = open_change_requests(args.project_id, target_step=args.step)
        if not reqs:
            print("  (no open requests)")
            return
        for r in reqs:
            print(f"  [{r['id']}] {r['clip_id']} {r['change_type']} -> {r['target_step']}: {r['reason']}")
    elif args.cmd == "assert-valid":
        init_db()
        ok, problems = assert_all_valid(args.project_id)
        if ok:
            print("PASS: all clips valid, no open change requests.")
        else:
            print(f"FAIL: {len(problems)} problem(s):")
            for p in problems:
                if "clip_id" in p and "status" in p and "change_type" not in p:
                    print(f"  clip {p['clip_id']}: status={p['status']}")
                else:
                    print(f"  request: {p}")
            sys.exit(1)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""content_db.py — SQLite content + performance-data logging.

Logs every content unit's attributes at production time. Performance metrics
added later when analytics are wired. Seeds the learning loop + micro-tool.

Usage:
  python3 scripts/content_db.py init                          # create/migrate schema
  python3 scripts/content_db.py log-unit script.json          # log a produced unit
  python3 scripts/content_db.py list                          # list all units
  python3 scripts/content_db.py show <project_id>             # show one unit
  python3 scripts/content_db.py stats                         # summary stats
"""
import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "leverage_mind.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS content_units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT UNIQUE NOT NULL,
    title TEXT,
    pillar TEXT,
    format_archetype TEXT,
    narration_mode TEXT,
    duration_s REAL,
    word_count INTEGER,
    segment_count INTEGER,
    james_presence_pct REAL,
    music_track TEXT,
    source_count INTEGER,
    has_original_framework INTEGER,
    created_at TEXT NOT NULL,
    published_at TEXT,
    -- Performance metrics (added later via update)
    views INTEGER,
    watch_time_hours REAL,
    avg_view_pct REAL,
    ctr REAL,
    subs_gained INTEGER,
    likes INTEGER,
    comments INTEGER,
    newsletter_signups INTEGER,
    product_conversions INTEGER,
    revenue_attributed REAL,
    metrics_updated_at TEXT
);

CREATE TABLE IF NOT EXISTS unit_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    segment_id TEXT NOT NULL,
    audio_mode TEXT,
    duration_s REAL,
    wps REAL,
    model_used TEXT,
    shot_count INTEGER DEFAULT 1,
    FOREIGN KEY (project_id) REFERENCES content_units(project_id)
);
"""


def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print(f"DB initialized: {DB_PATH}")


def log_unit(script_path):
    """Log a produced content unit from its script JSON."""
    script = json.load(open(script_path))
    pid = script["project_id"]
    segments = script["segments"]

    # Compute attributes
    total_words = sum(len(seg.get("text", "").split()) for seg in segments)
    james_segs = sum(1 for s in segments if s.get("audio_mode") == "baked_in")
    james_pct = round(100 * james_segs / len(segments)) if segments else 0
    music = script.get("music", {}).get("path", "")

    # Source log
    source_log = ROOT / "research" / "source_logs" / f"{pid}.json"
    source_count = 0
    has_framework = 0
    if source_log.exists():
        sl = json.load(open(source_log))
        source_count = len(sl.get("primary_sources", []))
        has_framework = 1 if sl.get("original_framework") else 0

    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO content_units
        (project_id, pillar, narration_mode, word_count, segment_count,
         james_presence_pct, music_track, source_count, has_original_framework, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (pid, script.get("pillar", ""), script.get("narration_mode", "segment_tts"),
          total_words, len(segments), james_pct, music,
          source_count, has_framework, time.strftime("%Y-%m-%dT%H:%M:%S")))

    # Log segments
    conn.execute("DELETE FROM unit_segments WHERE project_id = ?", (pid,))
    for seg in segments:
        shot_count = len(seg.get("shots", [])) or 1
        wc = len(seg.get("text", "").split())
        conn.execute("""
            INSERT INTO unit_segments (project_id, segment_id, audio_mode, shot_count)
            VALUES (?, ?, ?, ?)
        """, (pid, seg["id"], seg.get("audio_mode", "generated_tts"), shot_count))

    conn.commit()
    conn.close()
    print(f"Logged: {pid} ({len(segments)} segments, {total_words} words, {source_count} sources)")


def list_units():
    conn = get_db()
    rows = conn.execute("SELECT project_id, pillar, word_count, segment_count, created_at FROM content_units ORDER BY created_at DESC").fetchall()
    conn.close()
    if not rows:
        print("  (no units logged yet)")
        return
    for r in rows:
        print(f"  {r['project_id']:40s} {r['pillar'] or '-':20s} {r['word_count'] or 0:5d}w {r['segment_count'] or 0:2d}seg {r['created_at']}")


def show_unit(pid):
    conn = get_db()
    r = conn.execute("SELECT * FROM content_units WHERE project_id = ?", (pid,)).fetchone()
    if not r:
        print(f"  not found: {pid}")
        return
    for k in r.keys():
        print(f"  {k}: {r[k]}")
    segs = conn.execute("SELECT * FROM unit_segments WHERE project_id = ?", (pid,)).fetchall()
    if segs:
        print(f"\n  Segments ({len(segs)}):")
        for s in segs:
            print(f"    {s['segment_id']:20s} {s['audio_mode']:15s} shots={s['shot_count']}")
    conn.close()


def stats():
    conn = get_db()
    r = conn.execute("SELECT COUNT(*) as n, SUM(word_count) as words, SUM(segment_count) as segs FROM content_units").fetchone()
    conn.close()
    print(f"  Units: {r['n']} | Total words: {r['words'] or 0} | Total segments: {r['segs'] or 0}")


def main():
    ap = argparse.ArgumentParser(description="Content + performance data logging.")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("init", help="Create/migrate database schema")
    p_log = sub.add_parser("log-unit", help="Log a produced content unit")
    p_log.add_argument("script", help="Path to script JSON")
    sub.add_parser("list", help="List all logged units")
    p_show = sub.add_parser("show", help="Show details for one unit")
    p_show.add_argument("project_id")
    sub.add_parser("stats", help="Summary statistics")
    args = ap.parse_args()

    if args.cmd == "init":
        init_db()
    elif args.cmd == "log-unit":
        init_db()  # ensure schema exists
        log_unit(args.script)
    elif args.cmd == "list":
        list_units()
    elif args.cmd == "show":
        show_unit(args.project_id)
    elif args.cmd == "stats":
        stats()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()

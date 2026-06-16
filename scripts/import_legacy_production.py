#!/usr/bin/env python3
"""Import legacy project files and databases into the unified production ledger."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db

DOCUMENT_FILES = {
    "research_brief.json": "research_brief",
    "script.json": "script",
    "storyboard.json": "creative_storyboard",
    "production_storyboard.json": "production_storyboard",
    "review_report.json": "production_storyboard_review",
    "media_plan.json": "media_plan",
    "media_qa_report.json": "media_qa_report",
    "manifest.json": "manifest_export",
    "final_qa_report.json": "final_qa_report",
    "run_quality_report.json": "quality_report",
}

ARTIFACT_PATTERNS = {
    "narration/*.mp3": "audio",
    "narration/*.wav": "audio",
    "narration/*.json": "timing_export",
    "*.mp4": "deliverable_or_media",
    "*.srt": "captions",
    "*.ass": "captions",
    "duration_reconciliation.csv": "duration_report",
}


def _read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return default


def _legacy_content_row(project_slug, content_db_path):
    path = Path(content_db_path)
    if not path.exists():
        return None
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM content_units WHERE project_id=?", (project_slug,)
        ).fetchone()
        return dict(row) if row else None
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def _legacy_clips(project_slug, clips_db_path):
    path = Path(clips_db_path)
    if not path.exists():
        return []
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM clips WHERE project_id=? ORDER BY required_start_sec, clip_id",
            (project_slug,),
        ).fetchall()]
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def inventory(project_dir, clips_db_path, content_db_path):
    project_dir = Path(project_dir).resolve()
    state = _read_json(project_dir / "state.json", {}) or {}
    gates = _read_json(project_dir / "gates.json", {}) or {}
    documents = [name for name in DOCUMENT_FILES if (project_dir / name).is_file()]
    artifacts = []
    for pattern, kind in ARTIFACT_PATTERNS.items():
        artifacts.extend((str(path), kind) for path in sorted(project_dir.glob(pattern)) if path.is_file())
    clips = _legacy_clips(project_dir.name, clips_db_path)
    content = _legacy_content_row(project_dir.name, content_db_path)
    return {
        "project_dir": str(project_dir),
        "project_slug": project_dir.name,
        "state_steps": len(state.get("step_status", {})),
        "gates": len(gates.get("gates", {})),
        "documents": documents,
        "artifacts": [path for path, _kind in artifacts],
        "clips": len(clips),
        "content_unit_found": content is not None,
        "_state": state,
        "_gates": gates,
        "_artifacts": artifacts,
        "_clips": clips,
        "_content": content,
    }


def import_project(project_dir, clips_db_path, content_db_path, db_path=None, dry_run=False):
    report = inventory(project_dir, clips_db_path, content_db_path)
    if dry_run:
        return {key: value for key, value in report.items() if not key.startswith("_")}

    project_dir = Path(report["project_dir"])
    state = report["_state"]
    content = report["_content"] or {}
    seed = state.get("seed") or content.get("title") or project_dir.name
    video_type = state.get("format") or content.get("format_archetype")
    production = production_db.ensure_production(
        project_dir.name,
        seed=seed,
        video_type=video_type,
        created_at=state.get("created") or content.get("created_at"),
        db_path=db_path,
    )
    production_db.mirror_state(project_dir, state, db_path=db_path)

    for gate_name, entry in report["_gates"].get("gates", {}).items():
        production_db.mirror_approval(
            project_dir.name,
            gate_name,
            entry.get("status", "pending"),
            artifact_path=entry.get("artifact_path"),
            artifact_sha256=entry.get("artifact_sha256"),
            forced=entry.get("forced", False),
            actor=entry.get("approved_by"),
            decision_note=(entry.get("extra") or {}).get("note"),
            legacy_payload=entry,
            db_path=db_path,
        )

    imported_documents = 0
    for filename, kind in DOCUMENT_FILES.items():
        path = project_dir / filename
        if path.is_file():
            production_db.import_document(project_dir.name, kind, path, db_path=db_path)
            imported_documents += 1

    imported_artifacts = 0
    for path, kind in report["_artifacts"]:
        production_db.import_artifact(project_dir.name, kind, path, db_path=db_path)
        imported_artifacts += 1

    imported_clips = 0
    for clip in report["_clips"]:
        production_db.import_legacy_clip(project_dir.name, clip, db_path=db_path)
        imported_clips += 1

    if content:
        production_db.append_event(
            production["id"],
            "legacy_content_unit_imported",
            actor="legacy_importer",
            payload=content,
            event_key=f"legacy-content:{project_dir.name}",
            db_path=db_path,
        )

    result = {key: value for key, value in report.items() if not key.startswith("_")}
    result.update({
        "production_id": production["id"],
        "imported_documents": imported_documents,
        "imported_artifacts": imported_artifacts,
        "imported_clips": imported_clips,
        "blockers": production_db.blockers(project_dir.name, db_path=db_path),
    })
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Import one legacy video project.")
    parser.add_argument("project_dir")
    parser.add_argument("--db", help="Unified production DB path")
    parser.add_argument("--clips-db", default=str(ROOT / "db" / "clips.db"))
    parser.add_argument("--content-db", default=str(ROOT / "db" / "leverage_mind.db"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    report = import_project(
        args.project_dir,
        args.clips_db,
        args.content_db,
        db_path=args.db,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

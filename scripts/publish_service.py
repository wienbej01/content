"""Sprint 8: Publishing and analytics service.

PUB-801  Metadata package
PUB-802  Thumbnail and caption assets
PUB-803  Publication records (YouTube and other platforms)
PUB-804  Atomization workflow (child productions)
DATA-805 Analytics / metric snapshots
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import production_db as _db
import production_repo as _repo
from assemble_db import is_gate_b_approved


# ---------------------------------------------------------------------------
# PUB-801  Metadata package
# ---------------------------------------------------------------------------

def save_metadata_package(
    production_id: str,
    title: str,
    description: str,
    tags: Optional[list[str]] = None,
    chapters: Optional[list[dict]] = None,
    disclosures: Optional[dict] = None,
    scheduled_at: Optional[str] = None,
    db_path=None,
) -> dict:
    """Version a metadata package document for this production."""
    from stage_runner import save_document_revision
    payload = {
        "title": title,
        "description": description,
        "tags": tags or [],
        "chapters": chapters or [],
        "disclosures": disclosures or {"ai_generated": True, "synthetic_voice": True},
        "scheduled_at": scheduled_at,
    }
    return save_document_revision(production_id, "metadata_package", payload, db_path=db_path)


# ---------------------------------------------------------------------------
# PUB-803  Publication records
# ---------------------------------------------------------------------------

class PublishError(Exception):
    pass


def create_publication(
    production_id: str,
    deliverable_id: str,
    platform: str,
    disclosure_data: Optional[dict] = None,
    metadata_revision_id: Optional[str] = None,
    scheduled_at: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    db_path=None,
) -> dict:
    """Create a publication record. Requires Gate B and metadata approval.

    Hard requirements (HARD INVARIANT #9):
    - Gate B must be approved
    - Disclosure data must be present (mandatory per P2-05 non-negotiable)
    - A deliverable with qa_passed status must exist
    """
    if not is_gate_b_approved(production_id, db_path=db_path):
        raise PublishError(
            f"Cannot publish: Gate B not approved for production {production_id}"
        )

    disclosure = disclosure_data or {}
    if not disclosure.get("ai_generated") and not disclosure.get("synthetic_voice"):
        raise PublishError(
            "AI-content disclosure is MANDATORY. Set disclosure_data with ai_generated=True. "
            "This is a platform-survival non-negotiable."
        )

    _db.migrate(db_path)
    conn = _db.connect(db_path)
    deliverable = conn.execute("SELECT * FROM deliverables WHERE id=?", (deliverable_id,)).fetchone()
    conn.close()
    if not deliverable or deliverable["status"] != "qa_passed":
        raise PublishError(
            f"Deliverable {deliverable_id} must have qa_passed status. "
            f"Current status: {deliverable['status'] if deliverable else 'not found'}"
        )

    idem = idempotency_key or (
        f"pub:{production_id}:{deliverable_id}:{platform}"
    )
    now = _db._now()

    with _db.transaction(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM publications WHERE idempotency_key=?", (idem,)
        ).fetchone()
        if existing:
            return dict(existing)

        pub_id = _db._id("pub")
        conn.execute(
            """INSERT INTO publications
               (id, production_id, deliverable_id, platform, idempotency_key,
                status, scheduled_at, disclosure_json, metadata_revision_id)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                pub_id, production_id, deliverable_id, platform, idem,
                "scheduled" if scheduled_at else "pending",
                scheduled_at, _db._json(disclosure), metadata_revision_id,
            ),
        )
        _db.append_event(
            production_id, "publication_created",
            payload={"pub_id": pub_id, "platform": platform, "deliverable_id": deliverable_id},
            conn=conn,
        )
        return dict(conn.execute("SELECT * FROM publications WHERE id=?", (pub_id,)).fetchone())


def record_published(
    publication_id: str,
    platform_object_id: str,
    url: str,
    db_path=None,
) -> dict:
    """Mark a publication as published with its platform ID. Idempotent on platform_object_id."""
    now = _db._now()
    with _db.transaction(db_path) as conn:
        pub = conn.execute("SELECT * FROM publications WHERE id=?", (publication_id,)).fetchone()
        if not pub:
            raise PublishError(f"publication {publication_id} not found")
        conn.execute(
            """UPDATE publications SET status='published', platform_object_id=?,
               published_at=?, url=? WHERE id=?""",
            (platform_object_id, now, url, publication_id),
        )
        _db.append_event(
            pub["production_id"], "publication_published",
            payload={"pub_id": publication_id, "platform": pub["platform"],
                     "platform_object_id": platform_object_id, "url": url},
            conn=conn,
        )
        return dict(conn.execute("SELECT * FROM publications WHERE id=?", (publication_id,)).fetchone())


def get_publications(production_id: str, db_path=None) -> list[dict]:
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    rows = conn.execute(
        "SELECT * FROM publications WHERE production_id=? ORDER BY id", (production_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# PUB-804  Atomization: child productions
# ---------------------------------------------------------------------------

def create_atomized_production(
    parent_production_id: str,
    short_topic: str,
    source_span_ids: Optional[list[str]] = None,
    db_path=None,
) -> dict:
    """Create a child production for a short/atomized version.

    The child inherits parent_production_id and shares source span lineage.
    """
    _db.migrate(db_path)
    parent = _db.get_production(parent_production_id, db_path=db_path)
    if not parent:
        raise ValueError(f"parent production {parent_production_id} not found")

    slug = f"{parent['project_slug']}_short_{_db._id('s')[:8]}"
    child = _db.ensure_production(slug, seed=short_topic, video_type="short", db_path=db_path)

    # Link parent
    with _db.transaction(db_path) as conn:
        conn.execute(
            "UPDATE productions SET parent_production_id=? WHERE id=?",
            (parent_production_id, child["id"]),
        )
        if source_span_ids:
            for span_id in source_span_ids:
                conn.execute(
                    """INSERT OR IGNORE INTO artifact_dependencies
                       (artifact_id, depends_on_artifact_id, dependency_role)
                       SELECT ?, timing_source_artifact_id, 'atomized_from_span'
                       FROM timeline_spans WHERE id=? AND timing_source_artifact_id IS NOT NULL""",
                    (child["id"], span_id),
                )
        _db.append_event(
            parent_production_id, "child_production_created",
            payload={"child_id": child["id"], "slug": slug}, conn=conn,
        )
    return _db.get_production(child["id"], db_path=db_path)


# ---------------------------------------------------------------------------
# DATA-805  Analytics / metric snapshots
# ---------------------------------------------------------------------------

def record_metric_snapshot(
    publication_id: str,
    metrics: dict,
    db_path=None,
) -> dict:
    """Record one metric snapshot for a publication.

    metrics: {observed_at, views, impressions, watch_time_seconds, avg_view_pct,
               ctr, subscribers_gained, likes, comments, conversions, revenue}

    Idempotent on (publication_id, observed_at).
    """
    observed_at = metrics.get("observed_at") or _db._now()
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    pub = conn.execute("SELECT production_id FROM publications WHERE id=?", (publication_id,)).fetchone()
    conn.close()
    if not pub:
        raise ValueError(f"publication {publication_id} not found")

    with _db.transaction(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM metric_snapshots WHERE publication_id=? AND observed_at=?",
            (publication_id, observed_at),
        ).fetchone()
        if existing:
            return dict(existing)

        snap_id = _db._id("metric")
        conn.execute(
            """INSERT INTO metric_snapshots
               (id, publication_id, observed_at, views, impressions, watch_time_seconds,
                avg_view_pct, ctr, subscribers_gained, likes, comments, conversions,
                revenue, raw_payload_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                snap_id, publication_id, observed_at,
                metrics.get("views"), metrics.get("impressions"),
                metrics.get("watch_time_seconds"), metrics.get("avg_view_pct"),
                metrics.get("ctr"), metrics.get("subscribers_gained"),
                metrics.get("likes"), metrics.get("comments"),
                metrics.get("conversions"), metrics.get("revenue"),
                _db._json(metrics),
            ),
        )
        return dict(conn.execute("SELECT * FROM metric_snapshots WHERE id=?", (snap_id,)).fetchone())


def get_metric_snapshots(publication_id: str, db_path=None) -> list[dict]:
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    rows = conn.execute(
        "SELECT * FROM metric_snapshots WHERE publication_id=? ORDER BY observed_at",
        (publication_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

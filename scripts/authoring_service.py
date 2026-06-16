"""Sprint 4: DB-native authoring service.

CREA-401  Research brief + source citations
CREA-402  Script revision service
CREA-403  Storyboard revision service
CREA-404  Durable human approvals via outbox
CREA-405  Remove pre-TTS JSON file authority (all reads go through this module)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import production_db as _db
from stage_runner import save_document_revision, get_active_document, invalidate_document_descendants


# ---------------------------------------------------------------------------
# CREA-401  Research brief + source citations
# ---------------------------------------------------------------------------

def save_research_brief(
    production_id: str,
    brief_payload: dict,
    citations: Optional[list[dict]] = None,
    stage_run_id: Optional[str] = None,
    db_path=None,
) -> dict:
    """Save a research brief document and record source citations.

    Enforces:
    - At least 3 primary sources (NON-NEGOTIABLE #1 sourcing discipline)

    Each citation dict:
        url, title, source_type, published_at, accessed_at,
        excerpt_sha256, how_used, is_primary (bool)
    """
    primary_count = sum(1 for c in (citations or []) if c.get("is_primary"))
    if primary_count < 3:
        raise ValueError(
            f"Sourcing discipline violation: need >= 3 primary sources, got {primary_count}. "
            "TED talks and similar are research-input only and must NOT be primary sources."
        )

    doc = save_document_revision(production_id, "research_brief", brief_payload,
                                 stage_run_id=stage_run_id, db_path=db_path)
    doc_id = doc["id"]

    if citations:
        now = _db._now()
        with _db.transaction(db_path) as conn:
            for cit in citations:
                cit_id = _db._id("cit")
                conn.execute(
                    """INSERT OR IGNORE INTO source_citations
                       (id, document_revision_id, url, title, source_type, published_at,
                        accessed_at, excerpt_sha256, how_used, is_primary, metadata_json)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        cit_id, doc_id,
                        cit.get("url", ""), cit.get("title"),
                        cit.get("source_type"), cit.get("published_at"),
                        cit.get("accessed_at"), cit.get("excerpt_sha256"),
                        cit.get("how_used"),
                        int(bool(cit.get("is_primary"))),
                        _db._json(cit.get("metadata") or {}),
                    ),
                )
    return doc


def get_research_brief(production_id: str, db_path=None) -> Optional[dict]:
    return get_active_document(production_id, "research_brief", db_path=db_path)


def get_citations(document_revision_id: str, db_path=None) -> list[dict]:
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    rows = conn.execute(
        "SELECT * FROM source_citations WHERE document_revision_id=?", (document_revision_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# CREA-402  Script revision service
# ---------------------------------------------------------------------------

def save_script(
    production_id: str,
    script_payload: dict,
    stage_run_id: Optional[str] = None,
    db_path=None,
) -> dict:
    """Save an immutable script revision and extract script_segments.

    script_payload must contain a 'segments' list; each segment:
        label, text, [word_count]
    """
    segments = script_payload.get("segments", [])
    if not segments:
        raise ValueError("script_payload must contain a non-empty 'segments' list")

    # Supersede prior active script → descendants become stale
    prior = get_active_script_revision_id(production_id, db_path=db_path)

    doc = save_document_revision(production_id, "script", script_payload,
                                 stage_run_id=stage_run_id, db_path=db_path)
    doc_id = doc["id"]

    # Write script_segments (immutable within this revision)
    with _db.transaction(db_path) as conn:
        for i, seg in enumerate(segments):
            text = seg.get("text", "")
            seg_id = _db._id("seg")
            conn.execute(
                """INSERT OR IGNORE INTO script_segments
                   (id, script_revision_id, ordinal, label, text, word_count)
                   VALUES (?,?,?,?,?,?)""",
                (
                    seg_id, doc_id, i, seg.get("label", f"S{i:03d}"),
                    text, seg.get("word_count") or len(text.split()),
                ),
            )

    # If there was a prior revision, propagate invalidation
    if prior:
        invalidate_document_descendants(production_id, prior, db_path=db_path)

    return doc


def get_active_script_revision_id(production_id: str, db_path=None) -> Optional[str]:
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    row = conn.execute(
        """SELECT id FROM document_revisions WHERE production_id=? AND kind='script' AND status='active'
           ORDER BY revision DESC LIMIT 1""",
        (production_id,),
    ).fetchone()
    conn.close()
    return row["id"] if row else None


def get_script(production_id: str, db_path=None) -> Optional[dict]:
    return get_active_document(production_id, "script", db_path=db_path)


def get_script_segments(production_id: str, db_path=None) -> list[dict]:
    rev_id = get_active_script_revision_id(production_id, db_path=db_path)
    if not rev_id:
        return []
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    rows = conn.execute(
        "SELECT * FROM script_segments WHERE script_revision_id=? ORDER BY ordinal", (rev_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# CREA-403  Storyboard revision service
# ---------------------------------------------------------------------------

def save_storyboard(
    production_id: str,
    storyboard_payload: dict,
    stage_run_id: Optional[str] = None,
    db_path=None,
) -> dict:
    """Save an immutable storyboard revision and extract creative_beats.

    storyboard_payload must contain a 'beats' list; each beat:
        label, shot_type, [visual_intent], [graphics], [narration_text], [script_segment_label]
    """
    beats = storyboard_payload.get("beats", [])
    if not beats:
        raise ValueError("storyboard_payload must contain a non-empty 'beats' list")

    prior = _get_active_storyboard_revision_id(production_id, db_path=db_path)
    doc = save_document_revision(production_id, "storyboard", storyboard_payload,
                                 stage_run_id=stage_run_id, db_path=db_path)
    doc_id = doc["id"]

    with _db.transaction(db_path) as conn:
        for i, beat in enumerate(beats):
            beat_id = _db._id("beat")
            narr = beat.get("narration_text", "")
            sha = _db._sha256_bytes(narr.encode()) if narr else None
            conn.execute(
                """INSERT OR IGNORE INTO creative_beats
                   (id, storyboard_revision_id, ordinal, label, shot_type,
                    visual_intent_json, graphics_json, narration_text_sha256)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    beat_id, doc_id, i,
                    beat.get("label", f"B{i:03d}"),
                    beat.get("shot_type"),
                    _db._json(beat.get("visual_intent") or {}),
                    _db._json(beat.get("graphics") or {}),
                    sha,
                ),
            )

    if prior:
        invalidate_document_descendants(production_id, prior, db_path=db_path)

    return doc


def _get_active_storyboard_revision_id(production_id: str, db_path=None) -> Optional[str]:
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    row = conn.execute(
        """SELECT id FROM document_revisions
           WHERE production_id=? AND kind='storyboard' AND status='active'
           ORDER BY revision DESC LIMIT 1""",
        (production_id,),
    ).fetchone()
    conn.close()
    return row["id"] if row else None


def get_storyboard(production_id: str, db_path=None) -> Optional[dict]:
    return get_active_document(production_id, "storyboard", db_path=db_path)


def get_creative_beats(production_id: str, db_path=None) -> list[dict]:
    rev_id = _get_active_storyboard_revision_id(production_id, db_path=db_path)
    if not rev_id:
        return []
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    rows = conn.execute(
        "SELECT * FROM creative_beats WHERE storyboard_revision_id=? ORDER BY ordinal", (rev_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# CREA-404  Durable human approvals via outbox
# ---------------------------------------------------------------------------

def request_approval(
    production_id: str,
    gate_name: str,
    subject_type: Optional[str] = None,
    subject_id: Optional[str] = None,
    subject_sha256: Optional[str] = None,
    artifact_uri: Optional[str] = None,
    db_path=None,
) -> dict:
    """Create or update an approval_request row and enqueue an outbox notification.

    If an approval already exists for this gate:
    - If subject_sha256 changed, mark it 'stale' and create fresh 'pending' record.
    - If unchanged and pending/pass, return existing.
    """
    now = _db._now()
    idem_key = f"approval_request:{production_id}:{gate_name}:{subject_sha256 or ''}"

    with _db.transaction(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM approval_requests WHERE production_id=? AND gate_name=?",
            (production_id, gate_name),
        ).fetchone()

        if existing:
            if existing["subject_sha256"] == subject_sha256 and existing["status"] in ("pending", "pass"):
                return dict(existing)
            # Subject changed or needs reset → update in place to 'pending' with new sha
            conn.execute(
                """UPDATE approval_requests
                   SET subject_type=?, subject_id=?, subject_sha256=?, artifact_uri=?,
                       status='pending', requested_at=?, decided_at=NULL, actor=NULL,
                       decision_note=NULL, forced=0
                   WHERE id=?""",
                (subject_type, subject_id, subject_sha256, artifact_uri, now, existing["id"]),
            )
            # Outbox notification for the updated approval
            conn.execute(
                """INSERT OR IGNORE INTO outbox_messages
                   (id, production_id, topic, idempotency_key, payload_json, status,
                    available_at, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    _db._id("out"), production_id, "telegram_approval", idem_key,
                    _db._json({"message": f"⏳ Re-approval needed\nGate: {gate_name}",
                               "gate_name": gate_name, "approval_id": existing["id"]}),
                    "pending", now, now,
                ),
            )
            return dict(conn.execute(
                "SELECT * FROM approval_requests WHERE id=?", (existing["id"],)
            ).fetchone())

        ar_id = _db._id("approval")
        conn.execute(
            """INSERT INTO approval_requests
               (id, production_id, gate_name, subject_type, subject_id, subject_sha256,
                artifact_uri, status, requested_at, forced)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (ar_id, production_id, gate_name, subject_type, subject_id, subject_sha256,
             artifact_uri, "pending", now, 0),
        )

        # Outbox: Telegram notification
        msg = (
            f"⏳ Approval needed\n"
            f"Production: {production_id[:12]}\n"
            f"Gate: {gate_name}\n"
            f"Subject: {subject_type or 'n/a'}"
        )
        conn.execute(
            """INSERT OR IGNORE INTO outbox_messages
               (id, production_id, topic, idempotency_key, payload_json, status,
                available_at, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                _db._id("out"), production_id, "telegram_approval", idem_key,
                _db._json({"message": msg, "gate_name": gate_name, "approval_id": ar_id}),
                "pending", now, now,
            ),
        )
        return dict(conn.execute("SELECT * FROM approval_requests WHERE id=?", (ar_id,)).fetchone())


def record_approval_decision(
    production_id: str,
    gate_name: str,
    decision: str,  # 'pass' or 'fail'
    actor: str = "human",
    note: Optional[str] = None,
    forced: bool = False,
    db_path=None,
) -> dict:
    """Record a human approval decision. Forced overrides create an audit event."""
    if decision not in ("pass", "fail"):
        raise ValueError(f"decision must be 'pass' or 'fail', got {decision!r}")
    now = _db._now()
    with _db.transaction(db_path) as conn:
        conn.execute(
            """UPDATE approval_requests
               SET status=?, decided_at=?, actor=?, decision_note=?, forced=?
               WHERE production_id=? AND gate_name=? AND status='pending'""",
            (decision, now, actor, note, int(forced), production_id, gate_name),
        )
        if forced:
            conn.execute(
                """INSERT INTO production_events
                   (id, production_id, event_type, actor, payload_json, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (
                    _db._id("evt"), production_id, "approval_forced",
                    actor, _db._json({"gate": gate_name, "decision": decision, "note": note}), now,
                ),
            )
        row = conn.execute(
            "SELECT * FROM approval_requests WHERE production_id=? AND gate_name=?",
            (production_id, gate_name),
        ).fetchone()
        return dict(row)


def get_approval(production_id: str, gate_name: str, db_path=None) -> Optional[dict]:
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    row = conn.execute(
        "SELECT * FROM approval_requests WHERE production_id=? AND gate_name=?",
        (production_id, gate_name),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def is_approved(production_id: str, gate_name: str, db_path=None) -> bool:
    approval = get_approval(production_id, gate_name, db_path=db_path)
    return bool(approval and approval["status"] == "pass")


# ---------------------------------------------------------------------------
# CREA-405  JSON export helpers (projection only — not execution authority)
# ---------------------------------------------------------------------------

def export_script_json(production_id: str, out_path: Path, db_path=None) -> Path:
    """Export the active script as a JSON file for inspection/debug only."""
    script = get_script(production_id, db_path=db_path)
    if not script:
        raise RuntimeError(f"no active script for production {production_id}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(script, indent=2))
    return out_path


def export_storyboard_json(production_id: str, out_path: Path, db_path=None) -> Path:
    """Export the active storyboard as a JSON file for inspection/debug only."""
    board = get_storyboard(production_id, db_path=db_path)
    if not board:
        raise RuntimeError(f"no active storyboard for production {production_id}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(board, indent=2))
    return out_path

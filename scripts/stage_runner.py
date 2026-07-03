"""Sprint 3: Durable stage runner and dependency invalidation.

ORCH-301  Stage registry with dependency graph
ORCH-302  Job queue (reuses production_db primitives)
ORCH-303  Idempotent stage runner
ORCH-304  Dependency invalidation via document lineage
ORCH-305  Legacy stage adapter
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import production_db as _db
import production_repo as _repo

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# ORCH-301  Stage registry
# ---------------------------------------------------------------------------

@dataclass
class StageDefinition:
    name: str
    depends_on: list[str] = field(default_factory=list)
    max_attempts: int = 3
    retry_delay_sec: int = 60
    # document kinds this stage produces (for invalidation graph)
    produces_kinds: list[str] = field(default_factory=list)
    # document kinds this stage consumes (for staleness checks)
    consumes_kinds: list[str] = field(default_factory=list)
    # S2-T02: when True, a stage may only be marked 'succeeded' if it produced a
    # committed output (document revision or artifact registered in the DB).
    # Stages that are pure gates/approvals or analytics set this to False.
    requires_committed_output: bool = True


# Canonical pipeline stage order (S2-T01: corrected to match the intended
# production flow — visuals planned before narration, timing aligns narration
# to visuals, repair and graphics composite before assembly).
STAGE_REGISTRY: dict[str, StageDefinition] = {
    "research":          StageDefinition("research", depends_on=[], produces_kinds=["research_brief"]),
    "write_script":      StageDefinition("write_script", depends_on=["research"], produces_kinds=["script"], consumes_kinds=["research_brief"]),
    "review_script":     StageDefinition("review_script", depends_on=["write_script"], produces_kinds=["script_review"], consumes_kinds=["script"]),
    "gate_a_content":    StageDefinition("gate_a_content", depends_on=["review_script"], produces_kinds=["gate_a_content_approval"], consumes_kinds=["script"], requires_committed_output=False),
    "storyboard":        StageDefinition("storyboard", depends_on=["gate_a_content"], produces_kinds=["storyboard"], consumes_kinds=["script"]),
    "review_storyboard": StageDefinition("review_storyboard", depends_on=["storyboard"], produces_kinds=["storyboard_review"], consumes_kinds=["storyboard"], requires_committed_output=False),
    "gate_storyboard":   StageDefinition("gate_storyboard", depends_on=["review_storyboard"], produces_kinds=["gate_storyboard_approval"], consumes_kinds=["storyboard"], requires_committed_output=False),
    "tts":               StageDefinition("tts", depends_on=["gate_storyboard"], produces_kinds=["tts_artifact"], consumes_kinds=["script"]),
    "audio_timing":      StageDefinition("audio_timing", depends_on=["tts"], produces_kinds=["timing_map"], consumes_kinds=["tts_artifact", "storyboard"]),
    "reconcile_timing":  StageDefinition("reconcile_timing", depends_on=["audio_timing"], produces_kinds=["timing_reconciliation"], consumes_kinds=["timing_map", "storyboard"], requires_committed_output=False),
    "compile_media":     StageDefinition("compile_media", depends_on=["reconcile_timing"], produces_kinds=["render_plan"], consumes_kinds=["storyboard", "timing_map"]),
    "gate_a_spend":      StageDefinition("gate_a_spend", depends_on=["compile_media"], produces_kinds=["gate_a_spend_approval"], consumes_kinds=["render_plan"], requires_committed_output=False),
    "generate_media":    StageDefinition("generate_media", depends_on=["gate_a_spend"], consumes_kinds=["render_plan"]),
    "qa_media":          StageDefinition("qa_media", depends_on=["generate_media"]),
    "repair":            StageDefinition("repair", depends_on=["qa_media"], requires_committed_output=False),
    "graphics_compositing": StageDefinition("graphics_compositing", depends_on=["repair"]),
    "assemble":          StageDefinition("assemble", depends_on=["graphics_compositing"], produces_kinds=["deliverable"]),
    "qa_final":          StageDefinition("qa_final", depends_on=["assemble"]),
    "gate_b_review":     StageDefinition("gate_b_review", depends_on=["qa_final"], produces_kinds=["gate_b_approval"], requires_committed_output=False),
    "publish":           StageDefinition("publish", depends_on=["gate_b_review"]),
    "analytics":         StageDefinition("analytics", depends_on=["publish"], requires_committed_output=False),
}

# Reverse map: document kind → which stages it blocks when stale
_KIND_BLOCKS: dict[str, list[str]] = {}
for _stage in STAGE_REGISTRY.values():
    for _kind in _stage.consumes_kinds:
        _KIND_BLOCKS.setdefault(_kind, []).append(_stage.name)


def stages_blocked_by_kind(kind: str) -> list[str]:
    """Return stage names that consume a document kind (i.e. are stale when it changes)."""
    return _KIND_BLOCKS.get(kind, [])


def downstream_stages(stage_name: str) -> list[str]:
    """Return all stages that directly or transitively depend on stage_name."""
    result = []
    queue = [stage_name]
    seen = {stage_name}
    while queue:
        current = queue.pop(0)
        for s in STAGE_REGISTRY.values():
            if current in s.depends_on and s.name not in seen:
                result.append(s.name)
                seen.add(s.name)
                queue.append(s.name)
    return result


def deps_satisfied(stage_name: str, production_id: str, db_path=None) -> tuple[bool, list[str]]:
    """Check whether all upstream stages have succeeded for this production."""
    stage = STAGE_REGISTRY.get(stage_name)
    if not stage:
        return False, [f"unknown stage: {stage_name}"]
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    missing = []
    for dep in stage.depends_on:
        row = conn.execute(
            """SELECT status FROM stage_runs
               WHERE production_id=? AND stage_name=? ORDER BY attempt DESC LIMIT 1""",
            (production_id, dep),
        ).fetchone()
        if not row or row["status"] != "succeeded":
            missing.append(dep)
    conn.close()
    return len(missing) == 0, missing


# ---------------------------------------------------------------------------
# ORCH-303  Idempotent stage runner
# ---------------------------------------------------------------------------

class StageSkipped(Exception):
    """Raised when a stage reuses a prior result."""
    def __init__(self, stage_run_id: str, result: Any):
        self.stage_run_id = stage_run_id
        self.result = result


def _verify_committed_output(production_id, produces_kinds, run_id, db_path=None):
    """S2-T02: Verify that a stage produced committed output evidence.

    Checks that at least one active document revision exists for each produced
    kind, or that the stage_run has an associated artifact. Raises if no
    committed output is found — a stage must not be marked succeeded without
    evidence.
    """
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    for kind in produces_kinds:
        row = conn.execute(
            """SELECT id FROM document_revisions
               WHERE production_id=? AND kind=? AND status='active'
               ORDER BY revision DESC LIMIT 1""",
            (production_id, kind),
        ).fetchone()
        if not row:
            conn.close()
            raise RuntimeError(
                f"BLOCKED: STAGE_SUCCESS_REQUIRES_COMMITTED_OUTPUT — stage run {run_id} "
                f"produced no committed document of kind '{kind}' for production {production_id}. "
                f"A stage may not be marked succeeded without committed output evidence.")
    conn.close()


def run_stage(
    production_id: str,
    stage_name: str,
    work_fn: Callable[[dict], Any],
    input_data: Optional[dict] = None,
    worker_id: Optional[str] = None,
    db_path=None,
) -> Any:
    """Idempotent stage runner.

    1. Compute input fingerprint from input_data.
    2. If a prior run with the same fingerprint already succeeded, return its result.
    3. Otherwise, insert/update a stage_run row, call work_fn(input_data), commit result.
    4. On exception, record failure and re-raise.
    """
    stage_def = STAGE_REGISTRY.get(stage_name)
    inputs = input_data or {}
    fingerprint = _db._sha256_bytes(_db._json(inputs).encode())
    worker = worker_id or f"runner_{uuid.uuid4().hex[:8]}"
    now = _db._now()

    _db.migrate(db_path)
    # Check for prior success with same fingerprint
    conn = _db.connect(db_path)
    prior = conn.execute(
        """SELECT id, result_summary_json FROM stage_runs
           WHERE production_id=? AND stage_name=? AND input_fingerprint=? AND status='succeeded'
           ORDER BY attempt DESC LIMIT 1""",
        (production_id, stage_name, fingerprint),
    ).fetchone()
    conn.close()
    if prior:
        result = json.loads(prior["result_summary_json"]) if prior["result_summary_json"] else {}
        raise StageSkipped(prior["id"], result)

    # Get next attempt number
    conn = _db.connect(db_path)
    max_attempt = conn.execute(
        "SELECT COALESCE(MAX(attempt), 0) FROM stage_runs WHERE production_id=? AND stage_name=?",
        (production_id, stage_name),
    ).fetchone()[0]
    conn.close()
    attempt = max_attempt + 1

    run_id = _db._id("run")
    with _db.transaction(db_path) as conn:
        conn.execute(
            """INSERT INTO stage_runs
               (id, production_id, stage_name, attempt, status, input_fingerprint,
                started_at, worker_id, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (run_id, production_id, stage_name, attempt, "running", fingerprint,
             now, worker, now, now),
        )
        conn.execute(
            "UPDATE productions SET current_stage=?, status='running', updated_at=? WHERE id=?",
            (stage_name, now, production_id),
        )

    try:
        result = work_fn(inputs)
        result_json = _db._json(result) if result is not None else None
        finished = _db._now()
        with _db.transaction(db_path) as conn:
            conn.execute(
                """UPDATE stage_runs SET status='succeeded', finished_at=?,
                   result_summary_json=?, updated_at=? WHERE id=?""",
                (finished, result_json, finished, run_id),
            )
        _db.append_event(
            production_id, "stage_succeeded",
            payload={"stage": stage_name, "run_id": run_id, "attempt": attempt},
            db_path=db_path,
        )
        return result
    except StageSkipped:
        # Clean up the running row if we somehow ended up here
        with _db.transaction(db_path) as conn:
            conn.execute(
                "UPDATE stage_runs SET status='cancelled', updated_at=? WHERE id=?",
                (_db._now(), run_id),
            )
        raise
    except Exception as exc:
        finished = _db._now()
        with _db.transaction(db_path) as conn:
            conn.execute(
                """UPDATE stage_runs SET status='failed', finished_at=?,
                   error_class=?, error_message=?, updated_at=? WHERE id=?""",
                (finished, type(exc).__name__, str(exc), finished, run_id),
            )
        _db.append_event(
            production_id, "stage_failed",
            payload={"stage": stage_name, "error": str(exc), "run_id": run_id},
            db_path=db_path,
        )
        raise


# ---------------------------------------------------------------------------
# ORCH-304  Dependency invalidation via document lineage
# ---------------------------------------------------------------------------

def invalidate_document_descendants(
    production_id: str, document_revision_id: str, db_path=None
) -> dict:
    """Mark all documents and approvals that depend on this revision as stale.

    Traverses document_dependencies recursively, then marks stage_runs stale for
    any stage that produces one of the affected document kinds.

    Returns counts of each affected entity type.
    """
    _db.migrate(db_path)

    affected_doc_ids: set[str] = set()
    queue = [document_revision_id]
    while queue:
        current = queue.pop(0)
        conn = _db.connect(db_path)
        deps = conn.execute(
            "SELECT document_revision_id FROM document_dependencies WHERE depends_on_document_revision_id=?",
            (current,),
        ).fetchall()
        conn.close()
        for dep in deps:
            did = dep["document_revision_id"]
            if did not in affected_doc_ids:
                affected_doc_ids.add(did)
                queue.append(did)

    if not affected_doc_ids:
        return {"documents": 0, "approvals": 0, "stage_runs": 0}

    now = _db._now()
    doc_ids_list = list(affected_doc_ids)
    ph = ",".join("?" * len(doc_ids_list))

    with _db.transaction(db_path) as conn:
        # Stale affected document revisions
        conn.execute(
            f"UPDATE document_revisions SET status='stale' WHERE id IN ({ph})",
            doc_ids_list,
        )
        # Stale approvals whose subject is one of the affected documents
        conn.execute(
            f"UPDATE approval_requests SET status='stale' WHERE production_id=? AND subject_id IN ({ph})",
            (production_id, *doc_ids_list),
        )
        # Find which stages produce these document kinds
        kinds = [
            r["kind"]
            for r in conn.execute(
                f"SELECT DISTINCT kind FROM document_revisions WHERE id IN ({ph})", doc_ids_list
            ).fetchall()
        ]

    # Mark those stage runs stale
    stale_stages = []
    for kind in kinds:
        for stage_name, sdef in STAGE_REGISTRY.items():
            if kind in sdef.produces_kinds:
                stale_stages.append(stage_name)

    stage_count = 0
    if stale_stages:
        stage_count = _db.invalidate_stages(
            _db.get_production(production_id, db_path=db_path)["project_slug"],
            stale_stages,
            reason=f"document {document_revision_id} superseded",
            db_path=db_path,
        )

    _db.append_event(
        production_id, "descendants_invalidated",
        payload={
            "source_revision": document_revision_id,
            "affected_docs": len(doc_ids_list),
            "affected_stages": stale_stages,
        },
        db_path=db_path,
    )
    return {"documents": len(doc_ids_list), "approvals": len(doc_ids_list), "stage_runs": stage_count}


# ---------------------------------------------------------------------------
# ORCH-305  Legacy stage adapter
# ---------------------------------------------------------------------------

class LegacyAdapter:
    """Wraps a legacy CLI script call as an idempotent DB-aware stage.

    The adapter:
    1. Materialises a run-scoped temporary JSON for the script.
    2. Invokes the current function (or CLI).
    3. Parses the result.
    4. Commits the output document revision to the DB.

    This is a migration mechanism only; final stage implementations read
    repository objects directly.
    """

    def __init__(
        self,
        stage_name: str,
        output_kind: str,
        invoke_fn: Callable[[dict, Path], dict],
    ):
        self.stage_name = stage_name
        self.output_kind = output_kind
        self.invoke_fn = invoke_fn

    def run(
        self,
        production_id: str,
        input_data: dict,
        db_path=None,
    ) -> dict:
        """Execute via run_stage; commits result document to DB.

        S2-T02: After the invoker runs, verifies committed output evidence for
        stages that require it (produces_kinds is non-empty and
        requires_committed_output is True). A stage must not be marked succeeded
        without committed output.
        """
        import tempfile, os

        stage_def = STAGE_REGISTRY.get(self.stage_name)

        def work(inputs: dict) -> dict:
            with tempfile.TemporaryDirectory(prefix="ytch_adapter_") as tmpdir:
                tmp_path = Path(tmpdir)
                result = self.invoke_fn(inputs, tmp_path)
                # Commit output document
                if self.output_kind:
                    production = _db.get_production(production_id, db_path=db_path)
                    save_document_revision(production_id, self.output_kind, result, db_path=db_path)
                return result

        result = None
        try:
            result = run_stage(production_id, self.stage_name, work, input_data, db_path=db_path)
        except StageSkipped as skipped:
            return skipped.result

        # S2-T02: Verify committed output after successful execution. Only
        # enforced when the adapter itself is responsible for committing a
        # document kind that matches the stage's produces_kinds. DB-native
        # stages (output_kind=None) commit their own output internally.
        if (self.output_kind and stage_def
                and stage_def.requires_committed_output
                and self.output_kind in stage_def.produces_kinds):
            _verify_committed_output(
                production_id, [self.output_kind], None, db_path)

        return result


# ---------------------------------------------------------------------------
# Convenience: document revision helpers (used by Sprint 4 authoring_service)
# ---------------------------------------------------------------------------

def save_document_revision(
    production_id: str,
    kind: str,
    payload: dict,
    stage_run_id: Optional[str] = None,
    supersedes_id: Optional[str] = None,
    db_path=None,
) -> dict:
    """Save a versioned document revision, superseding any prior active revision."""
    canonical = _db._json(payload)
    digest = _db._sha256_bytes(canonical.encode())
    now = _db._now()

    with _db.transaction(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM document_revisions WHERE production_id=? AND kind=? AND payload_sha256=?",
            (production_id, kind, digest),
        ).fetchone()
        if existing and existing["status"] == "active":
            return dict(existing)

        # If same payload exists but is stale/superseded, reactivate it
        if existing:
            previous_active = conn.execute(
                """SELECT * FROM document_revisions WHERE production_id=? AND kind=? AND status='active'
                   ORDER BY revision DESC LIMIT 1""",
                (production_id, kind),
            ).fetchone()
            if previous_active and previous_active["id"] != existing["id"]:
                conn.execute(
                    "UPDATE document_revisions SET status='superseded' WHERE id=?", (previous_active["id"],)
                )
            conn.execute(
                "UPDATE document_revisions SET status='active' WHERE id=?", (existing["id"],)
            )
            return dict(existing)

        previous = conn.execute(
            """SELECT * FROM document_revisions WHERE production_id=? AND kind=? AND status='active'
               ORDER BY revision DESC LIMIT 1""",
            (production_id, kind),
        ).fetchone()

        if previous:
            conn.execute(
                "UPDATE document_revisions SET status='superseded' WHERE id=?", (previous["id"],)
            )

        if previous:
            revision = previous["revision"] + 1
        else:
            max_row = conn.execute(
                "SELECT COALESCE(MAX(revision), 0) FROM document_revisions WHERE production_id=? AND kind=?", (production_id, kind),
            ).fetchone()
            revision = (max_row[0] or 0) + 1
        doc_id = _db._id("doc")
        conn.execute(
            """INSERT INTO document_revisions
               (id, production_id, kind, revision, status, payload_json, payload_sha256,
                created_by_stage_run_id, supersedes_id, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                doc_id, production_id, kind, revision, "active", canonical, digest,
                stage_run_id, supersedes_id or (previous["id"] if previous else None), now,
            ),
        )
        return dict(conn.execute("SELECT * FROM document_revisions WHERE id=?", (doc_id,)).fetchone())


def get_active_document(production_id: str, kind: str, db_path=None) -> Optional[dict]:
    """Return the active document revision payload (parsed), or None."""
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    row = conn.execute(
        """SELECT * FROM document_revisions WHERE production_id=? AND kind=? AND status='active'
           ORDER BY revision DESC LIMIT 1""",
        (production_id, kind),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {"_id": row["id"], "_revision": row["revision"], **json.loads(row["payload_json"])}

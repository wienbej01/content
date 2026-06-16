"""Tests for Sprint 3: stage_runner.py
(Stage registry, idempotent runner, dependency invalidation, legacy adapter)
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import production_db as _db
from stage_runner import (
    STAGE_REGISTRY, downstream_stages, deps_satisfied,
    run_stage, StageSkipped, save_document_revision, get_active_document,
    invalidate_document_descendants,
)


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db.migrate(str(p))
    yield str(p)
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    return _db.ensure_production("sprint3_test", db_path=db)


# ---------------------------------------------------------------------------
# Stage registry
# ---------------------------------------------------------------------------

class TestStageRegistry:
    def test_all_critical_stages_present(self):
        required = [
            "research", "write_script", "review_script", "gate_a_content",
            "tts", "audio_timing", "storyboard", "compile_media", "gate_a_spend",
            "generate_media", "qa_media", "assemble", "qa_final", "gate_b_review", "publish",
        ]
        for stage in required:
            assert stage in STAGE_REGISTRY, f"missing stage: {stage}"

    def test_dependency_graph_acyclic(self):
        # Simple cycle detection via DFS
        def has_cycle(name, visiting, visited):
            if name in visiting:
                return True
            if name in visited:
                return False
            visiting.add(name)
            for dep in STAGE_REGISTRY.get(name, type("", (), {"depends_on": []})()).depends_on:
                if has_cycle(dep, visiting, visited):
                    return True
            visiting.discard(name)
            visited.add(name)
            return False

        visiting, visited = set(), set()
        for stage_name in STAGE_REGISTRY:
            assert not has_cycle(stage_name, visiting, visited), f"cycle detected at {stage_name}"

    def test_downstream_stages(self):
        downstream = downstream_stages("write_script")
        assert "review_script" in downstream
        assert "gate_a_content" in downstream
        assert "tts" in downstream
        assert "publish" in downstream
        assert "write_script" not in downstream  # not itself

    def test_deps_satisfied_no_prior_runs(self, db, prod):
        ok, missing = deps_satisfied("write_script", prod["id"], db_path=db)
        assert not ok
        assert "research" in missing

    def test_deps_satisfied_after_completion(self, db, prod):
        _db.mirror_stage_state("sprint3_test", "research", "succeeded", db_path=db)
        ok, missing = deps_satisfied("write_script", prod["id"], db_path=db)
        assert ok
        assert missing == []


# ---------------------------------------------------------------------------
# Idempotent stage runner
# ---------------------------------------------------------------------------

class TestStageRunner:
    def test_successful_run(self, db, prod):
        call_count = [0]

        def work(inputs):
            call_count[0] += 1
            return {"result": "done", "count": call_count[0]}

        result = run_stage(prod["id"], "research", work, {"topic": "AI"}, db_path=db)
        assert result["result"] == "done"
        assert call_count[0] == 1

    def test_idempotent_same_inputs(self, db, prod):
        call_count = [0]

        def work(inputs):
            call_count[0] += 1
            return {"result": "done"}

        run_stage(prod["id"], "research", work, {"topic": "AI"}, db_path=db)
        with pytest.raises(StageSkipped) as exc_info:
            run_stage(prod["id"], "research", work, {"topic": "AI"}, db_path=db)
        assert call_count[0] == 1  # second call skipped
        assert exc_info.value.result["result"] == "done"

    def test_different_inputs_reruns(self, db, prod):
        call_count = [0]

        def work(inputs):
            call_count[0] += 1
            return {"result": call_count[0]}

        run_stage(prod["id"], "research", work, {"topic": "AI"}, db_path=db)
        run_stage(prod["id"], "research", work, {"topic": "ML"}, db_path=db)
        assert call_count[0] == 2

    def test_failure_recorded(self, db, prod):
        def work(inputs):
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            run_stage(prod["id"], "research", work, db_path=db)

        conn = _db.connect(db)
        row = conn.execute(
            "SELECT * FROM stage_runs WHERE production_id=? AND stage_name='research'",
            (prod["id"],),
        ).fetchone()
        conn.close()
        assert row["status"] == "failed"
        assert "test error" in row["error_message"]

    def test_stage_run_event_appended(self, db, prod):
        run_stage(prod["id"], "research", lambda i: {"ok": True}, db_path=db)
        events = _db.events(prod["id"], db_path=db)
        types = [e["event_type"] for e in events]
        assert "stage_succeeded" in types


# ---------------------------------------------------------------------------
# Document revision service
# ---------------------------------------------------------------------------

class TestDocumentRevision:
    def test_save_and_retrieve(self, db, prod):
        doc = save_document_revision(prod["id"], "script", {"text": "hello"}, db_path=db)
        assert doc["kind"] == "script"
        assert doc["revision"] == 1
        assert doc["status"] == "active"

        retrieved = get_active_document(prod["id"], "script", db_path=db)
        assert retrieved["text"] == "hello"
        assert retrieved["_revision"] == 1

    def test_revision_increments(self, db, prod):
        save_document_revision(prod["id"], "script", {"v": 1}, db_path=db)
        doc2 = save_document_revision(prod["id"], "script", {"v": 2}, db_path=db)
        assert doc2["revision"] == 2

        active = get_active_document(prod["id"], "script", db_path=db)
        assert active["v"] == 2

    def test_prior_revision_superseded(self, db, prod):
        doc1 = save_document_revision(prod["id"], "script", {"v": 1}, db_path=db)
        save_document_revision(prod["id"], "script", {"v": 2}, db_path=db)

        conn = _db.connect(db)
        row = conn.execute("SELECT status FROM document_revisions WHERE id=?", (doc1["id"],)).fetchone()
        conn.close()
        assert row["status"] == "superseded"

    def test_idempotent_same_payload(self, db, prod):
        doc1 = save_document_revision(prod["id"], "script", {"v": 1}, db_path=db)
        doc2 = save_document_revision(prod["id"], "script", {"v": 1}, db_path=db)
        assert doc1["id"] == doc2["id"]

    def test_no_active_returns_none(self, db, prod):
        result = get_active_document(prod["id"], "nonexistent_kind", db_path=db)
        assert result is None


# ---------------------------------------------------------------------------
# Dependency invalidation
# ---------------------------------------------------------------------------

class TestInvalidation:
    def test_descendant_becomes_stale(self, db, prod):
        parent = save_document_revision(prod["id"], "script", {"text": "hello"}, db_path=db)
        child = save_document_revision(prod["id"], "tts_artifact", {"audio": "x.mp3"}, db_path=db)

        # Link child → parent
        with _db.transaction(db) as conn:
            conn.execute(
                """INSERT INTO document_dependencies
                   (document_revision_id, depends_on_document_revision_id, dependency_role)
                   VALUES (?,?,?)""",
                (child["id"], parent["id"], "test_dep"),
            )

        counts = invalidate_document_descendants(prod["id"], parent["id"], db_path=db)
        assert counts["documents"] >= 1

        conn = _db.connect(db)
        child_row = conn.execute("SELECT status FROM document_revisions WHERE id=?", (child["id"],)).fetchone()
        conn.close()
        assert child_row["status"] == "stale"

    def test_no_descendants_returns_zeros(self, db, prod):
        doc = save_document_revision(prod["id"], "research_brief", {"topic": "AI"}, db_path=db)
        counts = invalidate_document_descendants(prod["id"], doc["id"], db_path=db)
        assert counts["documents"] == 0

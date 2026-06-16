"""Tests for Sprint 8: publish_service.py
(Metadata package, publications, atomization, analytics)
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import production_db as _db
from production_repo import register_artifact
from authoring_service import request_approval, record_approval_decision
from assemble_db import register_deliverable, run_final_qa
from publish_service import (
    save_metadata_package,
    create_publication, record_published, get_publications, PublishError,
    create_atomized_production,
    record_metric_snapshot, get_metric_snapshots,
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
    return _db.ensure_production("sprint8_test", db_path=db)


def _make_publishable_deliverable(prod_id, db, tmp_path):
    """Make a qa_passed deliverable with Gate B approved."""
    f = tmp_path / "output.mp4"
    f.write_bytes(b"assembled video " * 300)
    del_row = register_deliverable(prod_id, "16x9", f, db_path=db)
    run_final_qa(prod_id, del_row["id"], {
        "dimensions_ok": True, "duration_ok": True,
        "loudnorm_ok": True, "no_black_frames": True,
    }, db_path=db)
    from assemble_db import request_gate_b
    request_gate_b(prod_id, del_row["id"], db_path=db)
    record_approval_decision(prod_id, "gate_b_review", "pass", db_path=db)
    return del_row


class TestMetadataPackage:
    def test_save_metadata(self, db, prod):
        doc = save_metadata_package(
            prod["id"], "Test Video", "Description here",
            tags=["AI", "productivity"],
            disclosures={"ai_generated": True},
            db_path=db,
        )
        assert doc["kind"] == "metadata_package"


class TestPublication:
    def test_gate_b_required(self, db, prod, tmp_path):
        f = tmp_path / "output.mp4"
        f.write_bytes(b"video")
        del_row = register_deliverable(prod["id"], "16x9", f, db_path=db)
        with pytest.raises(PublishError, match="Gate B not approved"):
            create_publication(
                prod["id"], del_row["id"], "youtube",
                disclosure_data={"ai_generated": True},
                db_path=db,
            )

    def test_disclosure_required(self, db, prod, tmp_path):
        del_row = _make_publishable_deliverable(prod["id"], db, tmp_path)
        with pytest.raises(PublishError, match="disclosure"):
            create_publication(
                prod["id"], del_row["id"], "youtube",
                disclosure_data={},  # missing ai_generated
                db_path=db,
            )

    def test_qa_passed_required(self, db, prod, tmp_path):
        # Gate B approved but deliverable not qa_passed
        f = tmp_path / "output.mp4"
        f.write_bytes(b"video")
        del_row = register_deliverable(prod["id"], "16x9", f, db_path=db)
        # Manually approve gate_b without qa
        request_approval(prod["id"], "gate_b_review", subject_sha256="x", db_path=db)
        record_approval_decision(prod["id"], "gate_b_review", "pass", db_path=db)
        with pytest.raises(PublishError, match="qa_passed"):
            create_publication(
                prod["id"], del_row["id"], "youtube",
                disclosure_data={"ai_generated": True},
                db_path=db,
            )

    def test_create_publication(self, db, prod, tmp_path):
        del_row = _make_publishable_deliverable(prod["id"], db, tmp_path)
        pub = create_publication(
            prod["id"], del_row["id"], "youtube",
            disclosure_data={"ai_generated": True, "synthetic_voice": True},
            db_path=db,
        )
        assert pub["platform"] == "youtube"
        assert pub["status"] in ("pending", "scheduled")

    def test_idempotent_publication(self, db, prod, tmp_path):
        del_row = _make_publishable_deliverable(prod["id"], db, tmp_path)
        idem = "test_idem_123"
        p1 = create_publication(
            prod["id"], del_row["id"], "youtube",
            disclosure_data={"ai_generated": True, "synthetic_voice": True},
            idempotency_key=idem, db_path=db,
        )
        p2 = create_publication(
            prod["id"], del_row["id"], "youtube",
            disclosure_data={"ai_generated": True, "synthetic_voice": True},
            idempotency_key=idem, db_path=db,
        )
        assert p1["id"] == p2["id"]

    def test_record_published(self, db, prod, tmp_path):
        del_row = _make_publishable_deliverable(prod["id"], db, tmp_path)
        pub = create_publication(
            prod["id"], del_row["id"], "youtube",
            disclosure_data={"ai_generated": True, "synthetic_voice": True},
            db_path=db,
        )
        updated = record_published(pub["id"], "YT_VIDEO_ID_123", "https://youtu.be/abc", db_path=db)
        assert updated["status"] == "published"
        assert updated["platform_object_id"] == "YT_VIDEO_ID_123"

    def test_get_publications(self, db, prod, tmp_path):
        del_row = _make_publishable_deliverable(prod["id"], db, tmp_path)
        create_publication(
            prod["id"], del_row["id"], "youtube",
            disclosure_data={"ai_generated": True, "synthetic_voice": True},
            db_path=db,
        )
        pubs = get_publications(prod["id"], db_path=db)
        assert len(pubs) == 1


class TestAtomization:
    def test_create_child_production(self, db, prod):
        child = create_atomized_production(prod["id"], "short topic", db_path=db)
        assert child["parent_production_id"] == prod["id"]
        assert child["video_type"] == "short"
        assert "sprint8_test" in child["project_slug"]

    def test_parent_not_found_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            create_atomized_production("nonexistent_prod_id", "topic", db_path=db)


class TestMetrics:
    def _make_publication(self, prod_id, del_row, db):
        return create_publication(
            prod_id, del_row["id"], "youtube",
            disclosure_data={"ai_generated": True, "synthetic_voice": True},
            db_path=db,
        )

    def test_record_metric_snapshot(self, db, prod, tmp_path):
        del_row = _make_publishable_deliverable(prod["id"], db, tmp_path)
        pub = self._make_publication(prod["id"], del_row, db)
        snap = record_metric_snapshot(pub["id"], {
            "views": 1000, "impressions": 5000, "ctr": 0.2,
            "watch_time_seconds": 3600, "avg_view_pct": 0.6,
        }, db_path=db)
        assert snap["views"] == 1000
        assert snap["ctr"] == pytest.approx(0.2)

    def test_idempotent_on_same_observed_at(self, db, prod, tmp_path):
        del_row = _make_publishable_deliverable(prod["id"], db, tmp_path)
        pub = self._make_publication(prod["id"], del_row, db)
        s1 = record_metric_snapshot(pub["id"], {"views": 100, "observed_at": "2026-06-15T12:00:00"}, db_path=db)
        s2 = record_metric_snapshot(pub["id"], {"views": 200, "observed_at": "2026-06-15T12:00:00"}, db_path=db)
        assert s1["id"] == s2["id"]
        assert s1["views"] == 100  # first write wins

    def test_multiple_snapshots(self, db, prod, tmp_path):
        del_row = _make_publishable_deliverable(prod["id"], db, tmp_path)
        pub = self._make_publication(prod["id"], del_row, db)
        record_metric_snapshot(pub["id"], {"views": 100, "observed_at": "2026-06-15T12:00:00"}, db_path=db)
        record_metric_snapshot(pub["id"], {"views": 500, "observed_at": "2026-06-16T12:00:00"}, db_path=db)
        snaps = get_metric_snapshots(pub["id"], db_path=db)
        assert len(snaps) == 2

    def test_missing_publication_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            record_metric_snapshot("nonexistent_pub_id", {"views": 100}, db_path=db)

"""S22_T019 - Tests for compliance feedback ingestion."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import production_db as _db
from feedback_ingest import (
    ingest_compliance_finding,
    ingest_compliance_findings,
    FeedbackIngestionError,
    ALLOWED_ENTITY_TYPES,
    ALLOWED_SEVERITIES,
    ALLOWED_REPAIR_ACTIONS,
)


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "test.db"
        os.environ["PRODUCTION_DB_PATH"] = str(p)
        _db.migrate(str(p))
        yield str(p)
        del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    return _db.ensure_production("feedback_test", db_path=db)


def _make_render_unit(prod_id, db_path):
    from production_repo import commit_timeline_spans, plan_render_units

    spans = commit_timeline_spans(
        prod_id,
        [{"label": "S001", "start_ms": 0, "end_ms": 5000}],
        db_path=db_path,
    )
    return plan_render_units(
        prod_id,
        [
            {
                "span_id": spans[0]["id"],
                "asset_type": "lipsync_video",
                "audio_policy": "HERO_SYNC_LOCKED",
                "final_audio_source": "master_narration",
                "provider_audio_usage": "diagnostic_only",
            }
        ],
        db_path=db_path,
    )[0]


class TestFeedbackIngestion:
    def test_generic_broll_creates_shot_change_request(self, db, prod):
        shot_id = "shot_broll_001"
        result = ingest_compliance_finding(
            production_id=prod["id"],
            entity_type="shot",
            entity_id=shot_id,
            severity="BLOCKER",
            rule_id="BLOCKED_GENERIC_BROLL",
            source_stage="qa_media",
            finding_message="Generic B-roll: 'business people walking'",
            recommended_action="regenerate_same_prompt",
            repair_owner="media_generation",
            downstream_stages_impacted=["qa_media", "assemble"],
            db_path=db,
        )

        assert result["validation"]["subject_type"] == "render_unit"
        assert result["validation"]["subject_id"] == shot_id
        assert result["validation"]["status"] == "fail"

        cr = result["change_request"]
        assert cr is not None
        assert cr["subject_type"] == "render_unit"
        assert cr["subject_id"] == shot_id
        assert cr["status"] == "open"
        assert cr["requested_by_stage"] == "qa_media"
        assert cr["target_stage"] == "generate_media"
        assert result["change_request_action"] == "created"

        conn = _db.connect(db)
        crs = conn.execute(
            "SELECT * FROM change_requests WHERE production_id=? AND status='open'",
            (prod["id"],),
        ).fetchall()
        conn.close()
        assert len(crs) == 1

    def test_unsupported_claim_creates_claim_storyboard_request(self, db, prod):
        claim_id = "claim_alpha_001"
        result = ingest_compliance_finding(
            production_id=prod["id"],
            entity_type="claim",
            entity_id=claim_id,
            severity="BLOCKER",
            rule_id="BLOCKED_UNSUPPORTED_CLAIM",
            source_stage="storyboard_validation",
            finding_message="Unsupported claim: no source ref for 'AI will take over'",
            recommended_action="sonnet_repair_storyboard",
            repair_owner="storyboard_architect",
            downstream_stages_impacted=["storyboard_review", "gate_storyboard"],
            db_path=db,
        )

        assert result["validation"]["subject_type"] == "storyboard"
        assert result["validation"]["subject_id"] == claim_id

        cr = result["change_request"]
        assert cr is not None
        assert cr["subject_type"] == "storyboard"
        assert cr["subject_id"] == claim_id
        assert cr["target_stage"] == "storyboard_repair"
        assert cr["status"] == "open"
        assert result["change_request_action"] == "created"

    def test_overlay_safe_zone_creates_rerender_request(self, db, prod):
        overlay_id = "overlay_015"
        result = ingest_compliance_finding(
            production_id=prod["id"],
            entity_type="overlay",
            entity_id=overlay_id,
            severity="MAJOR",
            rule_id="BAD_SAFE_ZONE",
            source_stage="qa_final",
            finding_message="Overlay text clipped in 9x16 safe zone",
            recommended_action="rerender_overlay",
            repair_owner="overlay_timeline_engineer",
            downstream_stages_impacted=["render_overlays", "assemble"],
            db_path=db,
        )

        assert result["validation"]["subject_type"] == "render_unit"
        assert result["validation"]["subject_id"] == overlay_id

        cr = result["change_request"]
        assert cr is not None
        assert cr["target_stage"] == "render_overlays"
        assert cr["status"] == "open"
        assert result["change_request_action"] == "created"

    def test_duration_drift_creates_render_unit_request(self, db, prod):
        ru = _make_render_unit(prod["id"], db)
        result = ingest_compliance_finding(
            production_id=prod["id"],
            entity_type="render_unit",
            entity_id=ru["id"],
            severity="MAJOR",
            rule_id="BLOCKED_DURATION_DRIFT_UNRESOLVED",
            source_stage="reconcile_timing",
            finding_message="Planned 4.2s, actual 2.1s, exceeds min usable duration",
            recommended_action="regenerate_same_prompt",
            repair_owner="media_generation",
            downstream_stages_impacted=["qa_media", "assemble", "qa_final"],
            db_path=db,
        )

        assert result["validation"]["subject_type"] == "render_unit"
        assert result["validation"]["subject_id"] == ru["id"]

        cr = result["change_request"]
        assert cr is not None
        assert cr["subject_type"] == "render_unit"
        assert cr["subject_id"] == ru["id"]
        assert cr["target_stage"] == "generate_media"
        assert cr["status"] == "open"
        assert result["change_request_action"] == "created"

    def test_duplicate_open_finding_is_idempotent(self, db, prod):
        ru = _make_render_unit(prod["id"], db)
        finding = dict(
            production_id=prod["id"],
            entity_type="render_unit",
            entity_id=ru["id"],
            severity="BLOCKER",
            rule_id="BLOCKED_DURATION_DRIFT_UNRESOLVED",
            source_stage="reconcile_timing",
            finding_message="Duration drift: actual 1.5s < min 3.0s",
            recommended_action="regenerate_same_prompt",
            repair_owner="media_generation",
            db_path=db,
        )

        first = ingest_compliance_finding(**finding)
        assert first["change_request_action"] == "created"
        assert first["change_request"] is not None

        second = ingest_compliance_finding(**finding)
        assert second["change_request_action"] == "existing"
        assert second["change_request"] is not None
        assert second["change_request"]["id"] == first["change_request"]["id"]

        conn = _db.connect(db)
        open_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM change_requests WHERE production_id=? AND status='open'",
            (prod["id"],),
        ).fetchone()["cnt"]
        conn.close()
        assert open_count == 1

    def test_missing_entity_id_fails_unrouted(self, db, prod):
        with pytest.raises(FeedbackIngestionError, match="BLOCKED_FEEDBACK_UNROUTED"):
            ingest_compliance_finding(
                production_id=prod["id"],
                entity_type="shot",
                entity_id="",
                severity="BLOCKER",
                rule_id="SOME_RULE",
                source_stage="qa_media",
                finding_message="Missing entity id",
                recommended_action="regenerate_same_prompt",
                db_path=db,
            )

    def test_missing_repair_action_fails(self, db, prod):
        ru = _make_render_unit(prod["id"], db)
        with pytest.raises(FeedbackIngestionError, match="BLOCKED_FEEDBACK_UNROUTED"):
            ingest_compliance_finding(
                production_id=prod["id"],
                entity_type="render_unit",
                entity_id=ru["id"],
                severity="MAJOR",
                rule_id="SOME_RULE",
                source_stage="qa_media",
                finding_message="No repair action provided",
                recommended_action="",
                db_path=db,
            )

    def test_minor_warning_records_validation_only(self, db, prod):
        ru = _make_render_unit(prod["id"], db)
        result = ingest_compliance_finding(
            production_id=prod["id"],
            entity_type="render_unit",
            entity_id=ru["id"],
            severity="MINOR",
            rule_id="WARN_SLIGHLY_OVERDURATION",
            source_stage="qa_media",
            finding_message="Slightly over planned duration but within tolerance",
            recommended_action="trim_in_assembly",
            repair_owner="assembly",
            db_path=db,
        )

        assert result["validation"] is not None
        assert result["validation"]["status"] == "pass"

        assert result["change_request"] is None
        assert result["change_request_action"] == "skipped"

        conn = _db.connect(db)
        open_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM change_requests WHERE production_id=? AND status='open'",
            (prod["id"],),
        ).fetchone()["cnt"]
        assert open_count == 0

        vals = conn.execute(
            "SELECT * FROM validations WHERE production_id=?",
            (prod["id"],),
        ).fetchall()
        conn.close()
        assert len(vals) == 1

    def test_batch_ingestion_with_mixed_severities(self, db, prod):
        ru = _make_render_unit(prod["id"], db)
        findings = [
            {
                "entity_type": "render_unit",
                "entity_id": ru["id"],
                "severity": "BLOCKER",
                "rule_id": "BLOCKER_001",
                "source_stage": "qa_media",
                "finding_message": "Blocker finding",
                "recommended_action": "regenerate_same_prompt",
            },
            {
                "entity_type": "shot",
                "entity_id": "shot_minor_001",
                "severity": "MINOR",
                "rule_id": "WARN_001",
                "source_stage": "qa_media",
                "finding_message": "Minor cosmetic",
                "recommended_action": "trim_in_assembly",
            },
            {
                "entity_type": "overlay",
                "entity_id": "overlay_major_001",
                "severity": "MAJOR",
                "rule_id": "MAJOR_001",
                "source_stage": "qa_final",
                "finding_message": "Major overlay issue",
                "recommended_action": "rerender_overlay",
            },
        ]
        results = ingest_compliance_findings(prod["id"], findings, db_path=db)

        assert len(results) == 3

        assert results[0]["change_request_action"] == "created"
        assert results[0]["change_request"]["status"] == "open"

        assert results[1]["change_request_action"] == "skipped"
        assert results[1]["change_request"] is None

        assert results[2]["change_request_action"] == "created"
        assert results[2]["change_request"]["status"] == "open"

        conn = _db.connect(db)
        cr_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM change_requests WHERE production_id=?",
            (prod["id"],),
        ).fetchone()["cnt"]
        val_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM validations WHERE production_id=?",
            (prod["id"],),
        ).fetchone()["cnt"]
        conn.close()
        assert cr_count == 2
        assert val_count == 3

    def test_note_severity_creates_validation_only(self, db, prod):
        ru = _make_render_unit(prod["id"], db)
        result = ingest_compliance_finding(
            production_id=prod["id"],
            entity_type="render_unit",
            entity_id=ru["id"],
            severity="NOTE",
            rule_id="INFO_SOMETHING",
            source_stage="qa_final",
            finding_message="Informational note about render",
            recommended_action="trim_in_assembly",
            db_path=db,
        )

        assert result["validation"] is not None
        assert result["validation"]["status"] == "pass"
        assert result["change_request"] is None
        assert result["change_request_action"] == "skipped"

    def test_can_wire_to_human_review_action(self, db, prod):
        result = ingest_compliance_finding(
            production_id=prod["id"],
            entity_type="claim",
            entity_id="claim_human_review",
            severity="BLOCKER",
            rule_id="BLOCKED_NEEDS_HUMAN",
            source_stage="storyboard_creative_review",
            finding_message="Creative reviewer flagged this claim for human input",
            recommended_action="human_review_required",
            db_path=db,
        )

        cr = result["change_request"]
        assert cr is not None
        assert cr["target_stage"] == "gate_storyboard"
        assert cr["status"] == "open"

    def test_reject_unfixable_maps_to_gate_b_review(self, db, prod):
        ru = _make_render_unit(prod["id"], db)
        result = ingest_compliance_finding(
            production_id=prod["id"],
            entity_type="render_unit",
            entity_id=ru["id"],
            severity="BLOCKER",
            rule_id="BLOCKED_UNFIXABLE",
            source_stage="qa_final",
            finding_message="Cannot fix — content is fundamentally broken",
            recommended_action="reject_unfixable",
            db_path=db,
        )

        cr = result["change_request"]
        assert cr is not None
        assert cr["target_stage"] == "gate_b_review"

    def test_pad_or_extend_maps_to_assemble(self, db, prod):
        ru = _make_render_unit(prod["id"], db)
        result = ingest_compliance_finding(
            production_id=prod["id"],
            entity_type="render_unit",
            entity_id=ru["id"],
            severity="MAJOR",
            rule_id="DRIFT_SLIGHTLY_SHORT",
            source_stage="reconcile_timing",
            finding_message="Duration 3.8s vs planned 4.0s",
            recommended_action="pad_or_extend",
            db_path=db,
        )

        cr = result["change_request"]
        assert cr is not None
        assert cr["target_stage"] == "assemble"

    def test_evidence_full_roundtrip(self, db, prod):
        ru = _make_render_unit(prod["id"], db)
        result = ingest_compliance_finding(
            production_id=prod["id"],
            entity_type="render_unit",
            entity_id=ru["id"],
            severity="BLOCKER",
            rule_id="BLOCKED_FROZEN_VIDEO",
            source_stage="qa_media",
            finding_message="Clip is frozen for 3.5s",
            recommended_action="regenerate_same_prompt",
            repair_owner="media_generation",
            downstream_stages_impacted=["qa_media", "assemble", "qa_final"],
            evidence={"ffprobe_duration": 5.0, "freeze_pct": 70.0},
            db_path=db,
        )

        import json

        cr_evidence = json.loads(result["change_request"]["failure_evidence_json"])
        assert cr_evidence["entity_type"] == "render_unit"
        assert cr_evidence["entity_id"] == ru["id"]
        assert cr_evidence["severity"] == "BLOCKER"
        assert cr_evidence["rule_id"] == "BLOCKED_FROZEN_VIDEO"
        assert cr_evidence["source_stage"] == "qa_media"
        assert cr_evidence["recommended_action"] == "regenerate_same_prompt"
        assert cr_evidence["repair_owner"] == "media_generation"
        assert "assemble" in cr_evidence["downstream_stages_impacted"]
        assert cr_evidence["extra"]["ffprobe_duration"] == 5.0

    def test_events_are_recorded(self, db, prod):
        ru = _make_render_unit(prod["id"], db)
        ingest_compliance_finding(
            production_id=prod["id"],
            entity_type="render_unit",
            entity_id=ru["id"],
            severity="BLOCKER",
            rule_id="BLOCKER_X",
            source_stage="qa_media",
            finding_message="Test event recording",
            recommended_action="regenerate_same_prompt",
            db_path=db,
        )

        conn = _db.connect(db)
        events = conn.execute(
            "SELECT * FROM production_events WHERE production_id=? AND event_type='feedback_change_requested'",
            (prod["id"],),
        ).fetchall()
        conn.close()
        assert len(events) == 1

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import production_db as _db
import assemble_db
from assemble_db import validate_assembly_inputs, AssemblyError


def _setup_minimal_db(db_path: Path, production_id: str,
                       span_duration_ms: int = 10000,
                       ru_duration_ms: int = 10000) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS productions "
        "(id TEXT PRIMARY KEY, project_slug TEXT, video_type TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS timeline_spans "
        "(id TEXT PRIMARY KEY, production_id TEXT, ordinal INTEGER, label TEXT, "
        "start_ms INTEGER, end_ms INTEGER, duration_ms INTEGER, "
        "creative_beat_id TEXT, status TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS render_units "
        "(id TEXT PRIMARY KEY, production_id TEXT, timeline_span_id TEXT, "
        "ordinal INTEGER, label TEXT, asset_type TEXT, status TEXT, "
        "required_duration_ms INTEGER, active_artifact_id TEXT, "
        "audio_policy TEXT, lipsync_required INTEGER, "
        "required_start_ms INTEGER, required_end_ms INTEGER, "
        "metadata_json TEXT, artifact_sha256 TEXT, "
        "artifact_has_audio INTEGER, artifact_uri TEXT, "
        "hero_framing TEXT, model TEXT, source_slice_sha256 TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS artifacts "
        "(id TEXT PRIMARY KEY, production_id TEXT, uri TEXT, sha256 TEXT, "
        "has_audio INTEGER, kind TEXT, duration_ms INTEGER, created_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS validation_evidence "
        "(id TEXT PRIMARY KEY, production_id TEXT, subject_type TEXT, "
        "subject_id TEXT, validator_name TEXT, status TEXT, "
        "evidence TEXT, created_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS validations "
        "(id TEXT PRIMARY KEY, production_id TEXT, subject_type TEXT, "
        "subject_id TEXT, validator_name TEXT, status TEXT, "
        "evidence_json TEXT, created_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS change_requests "
        "(id TEXT PRIMARY KEY, production_id TEXT, subject_type TEXT, "
        "subject_id TEXT, change_type TEXT, status TEXT, target_stage TEXT, "
        "reason TEXT, created_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS provider_jobs "
        "(id TEXT PRIMARY KEY, production_id TEXT, render_unit_id TEXT, "
        "provider TEXT, operation TEXT, status TEXT, "
        "compensated_artifact_path TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS creative_beats "
        "(id TEXT PRIMARY KEY, production_id TEXT, label TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS deliverables "
        "(id TEXT PRIMARY KEY, production_id TEXT, variant TEXT, "
        "artifact_id TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS approval_requests "
        "(id TEXT PRIMARY KEY, production_id TEXT, gate_name TEXT, status TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS concept_memory "
        "(id TEXT PRIMARY KEY, concept TEXT, render_unit_id TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version TEXT PRIMARY KEY, filename TEXT NOT NULL, "
        "sha256 TEXT NOT NULL, applied_at TEXT NOT NULL)"
    )

    conn.execute("INSERT INTO productions (id, project_slug) VALUES (?, 'test')",
                 (production_id,))
    conn.execute(
        "INSERT INTO timeline_spans (id, production_id, ordinal, label, "
        "start_ms, end_ms, duration_ms, status) VALUES (?,?,?,?,?,?,?,?)",
        ("ts1", production_id, 0, "Span1", 0, span_duration_ms,
         span_duration_ms, "active"),
    )
    conn.execute(
        "INSERT INTO render_units (id, production_id, timeline_span_id, "
        "ordinal, label, asset_type, status, required_duration_ms, "
        "active_artifact_id, audio_policy, required_start_ms, "
        "required_end_ms, metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("ru1", production_id, "ts1", 0, "Beat1", "generated_video",
         "generated", ru_duration_ms, "art1", "BROLL_FLEX", 0,
         ru_duration_ms, "{}"),
    )
    conn.execute(
        "INSERT INTO artifacts (id, production_id, uri, sha256, has_audio, "
        "kind, duration_ms, created_at) VALUES (?,?,?,?,?,?,?,?)",
        ("art1", production_id, "/tmp/a.mp4", "abc123", 0,
         "generated_video", ru_duration_ms, "2026-01-01"),
    )
    conn.execute(
        "INSERT INTO validation_evidence (id, production_id, subject_type, "
        "subject_id, validator_name, status, evidence, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        ("ve1", production_id, "render_unit", "ru1", "qa_media_contract",
         "pass", "{}", "2026-01-01"),
    )
    conn.commit()
    conn.close()


class TestDurationDivergenceGuard:
    PRODUCTION_ID = "prod_divergence_test"

    @pytest.fixture(autouse=True)
    def _mock_db_ops(self, monkeypatch):
        monkeypatch.setattr(_db, "migrate", lambda *a, **kw: None)
        monkeypatch.setattr(_db, "_backup_db", lambda *a, **kw: None)
        mock_verdict = type("V", (), {
            "passes": True, "contract_name": "test",
            "violations": [], "expected": {}, "actual": {},
            "to_dict": lambda self: {},
        })()
        monkeypatch.setattr(
            assemble_db, "validate_shot_mix",
            lambda units: mock_verdict,
        )

    def test_matching_durations_passes(self, tmp_path):
        db = tmp_path / "test.db"
        _setup_minimal_db(db, self.PRODUCTION_ID, span_duration_ms=10000, ru_duration_ms=10000)
        evidence = validate_assembly_inputs(
            self.PRODUCTION_ID, variant="16x9", db_path=str(db), review_only=True,
        )
        assert evidence["duration_divergence_ms"] == 0

    def test_divergence_within_frame_precision_passes(self, tmp_path):
        db = tmp_path / "test.db"
        _setup_minimal_db(db, self.PRODUCTION_ID, span_duration_ms=10000, ru_duration_ms=10033)
        evidence = validate_assembly_inputs(
            self.PRODUCTION_ID, variant="16x9", db_path=str(db), review_only=True,
        )
        assert "duration_divergence_ms" in evidence

    def test_divergence_exceeds_frame_precision_fails(self, tmp_path):
        db = tmp_path / "test.db"
        _setup_minimal_db(db, self.PRODUCTION_ID, span_duration_ms=10000, ru_duration_ms=10100)
        with pytest.raises(AssemblyError,
                           match="BLOCKED_STORYBOARD_DURATION_DIVERGENCE"):
            validate_assembly_inputs(
                self.PRODUCTION_ID, variant="16x9", db_path=str(db),
            )

    def test_large_divergence_fails_clearly(self, tmp_path):
        db = tmp_path / "test.db"
        _setup_minimal_db(db, self.PRODUCTION_ID, span_duration_ms=10000, ru_duration_ms=8500)
        with pytest.raises(AssemblyError,
                           match="BLOCKED_STORYBOARD_DURATION_DIVERGENCE"):
            validate_assembly_inputs(
                self.PRODUCTION_ID, variant="16x9", db_path=str(db),
            )

    def test_error_message_includes_sums_and_delta(self, tmp_path):
        db = tmp_path / "test.db"
        _setup_minimal_db(db, self.PRODUCTION_ID, span_duration_ms=10000, ru_duration_ms=11000)
        with pytest.raises(AssemblyError) as excinfo:
            validate_assembly_inputs(
                self.PRODUCTION_ID, variant="16x9", db_path=str(db),
            )
        msg = str(excinfo.value)
        assert "11000" in msg
        assert "10000" in msg

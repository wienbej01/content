"""Tests for Sprint 4: authoring_service.py
(Research briefs, script/storyboard revisions, durable approvals)
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import production_db as _db
from authoring_service import (
    save_research_brief, get_research_brief, get_citations,
    save_script, get_script, get_script_segments,
    save_storyboard, get_storyboard, get_creative_beats,
    request_approval, record_approval_decision, get_approval, is_approved,
    export_script_json, export_storyboard_json,
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
    return _db.ensure_production("sprint4_test", db_path=db)


GOOD_CITATIONS = [
    {"url": "https://source1.com", "title": "Source 1", "is_primary": True, "how_used": "framework"},
    {"url": "https://source2.com", "title": "Source 2", "is_primary": True, "how_used": "data"},
    {"url": "https://source3.com", "title": "Source 3", "is_primary": True, "how_used": "concept"},
]


class TestResearchBrief:
    def test_save_and_retrieve(self, db, prod):
        doc = save_research_brief(prod["id"], {"topic": "AI memory"}, GOOD_CITATIONS, db_path=db)
        assert doc["kind"] == "research_brief"

        retrieved = get_research_brief(prod["id"], db_path=db)
        assert retrieved["topic"] == "AI memory"

    def test_citations_stored(self, db, prod):
        doc = save_research_brief(prod["id"], {"topic": "AI"}, GOOD_CITATIONS, db_path=db)
        cits = get_citations(doc["id"], db_path=db)
        assert len(cits) == 3
        assert all(c["is_primary"] == 1 for c in cits)

    def test_fewer_than_3_primary_sources_blocked(self, db, prod):
        bad_citations = [
            {"url": "https://ted.com/talk1", "title": "TED talk", "is_primary": False},
            {"url": "https://source.com", "title": "Source", "is_primary": True},
        ]
        with pytest.raises(ValueError, match="primary sources"):
            save_research_brief(prod["id"], {"topic": "AI"}, bad_citations, db_path=db)

    def test_no_citations_blocked(self, db, prod):
        with pytest.raises(ValueError, match="primary sources"):
            save_research_brief(prod["id"], {"topic": "AI"}, [], db_path=db)

    def test_none_citations_blocked(self, db, prod):
        with pytest.raises(ValueError, match="primary sources"):
            save_research_brief(prod["id"], {"topic": "AI"}, None, db_path=db)


class TestScriptRevision:
    SEGMENTS = [
        {"label": "S001", "text": "Hook: AI memory"},
        {"label": "S002", "text": "The framework"},
        {"label": "S003", "text": "CTA"},
    ]

    def test_save_and_retrieve(self, db, prod):
        doc = save_script(prod["id"], {"segments": self.SEGMENTS}, db_path=db)
        assert doc["kind"] == "script"
        script = get_script(prod["id"], db_path=db)
        assert "segments" in script

    def test_segments_extracted(self, db, prod):
        save_script(prod["id"], {"segments": self.SEGMENTS}, db_path=db)
        segs = get_script_segments(prod["id"], db_path=db)
        assert len(segs) == 3
        assert segs[0]["label"] == "S001"
        assert segs[1]["text"] == "The framework"

    def test_word_count_computed(self, db, prod):
        save_script(prod["id"], {"segments": [{"label": "S001", "text": "one two three four"}]}, db_path=db)
        segs = get_script_segments(prod["id"], db_path=db)
        assert segs[0]["word_count"] == 4

    def test_empty_segments_rejected(self, db, prod):
        with pytest.raises(ValueError, match="segments"):
            save_script(prod["id"], {"segments": []}, db_path=db)

    def test_no_segments_key_rejected(self, db, prod):
        with pytest.raises(ValueError):
            save_script(prod["id"], {"text": "no segments key"}, db_path=db)

    def test_revision_increment(self, db, prod):
        save_script(prod["id"], {"segments": self.SEGMENTS}, db_path=db)
        doc2 = save_script(prod["id"], {"segments": self.SEGMENTS[:2]}, db_path=db)
        assert doc2["revision"] == 2


class TestStoryboardRevision:
    BEATS = [
        {"label": "B001", "shot_type": "lipsync", "narration_text": "Hook"},
        {"label": "B002", "shot_type": "b_roll", "narration_text": "Proof"},
    ]

    def test_save_and_retrieve(self, db, prod):
        doc = save_storyboard(prod["id"], {"beats": self.BEATS}, db_path=db)
        assert doc["kind"] == "storyboard"

    def test_beats_extracted(self, db, prod):
        save_storyboard(prod["id"], {"beats": self.BEATS}, db_path=db)
        beats = get_creative_beats(prod["id"], db_path=db)
        assert len(beats) == 2
        assert beats[0]["label"] == "B001"

    def test_narration_sha_stored(self, db, prod):
        import hashlib
        save_storyboard(prod["id"], {"beats": self.BEATS}, db_path=db)
        beats = get_creative_beats(prod["id"], db_path=db)
        expected = hashlib.sha256("Hook".encode()).hexdigest()
        assert beats[0]["narration_text_sha256"] == expected

    def test_empty_beats_rejected(self, db, prod):
        with pytest.raises(ValueError, match="beats"):
            save_storyboard(prod["id"], {"beats": []}, db_path=db)


class TestApprovals:
    def test_request_creates_pending(self, db, prod):
        ar = request_approval(
            prod["id"], "gate_a_content",
            subject_type="script", subject_id="rev1", subject_sha256="abc123",
            db_path=db,
        )
        assert ar["status"] == "pending"
        assert ar["gate_name"] == "gate_a_content"

    def test_idempotent_same_sha(self, db, prod):
        ar1 = request_approval(prod["id"], "gate_a_content", subject_sha256="abc", db_path=db)
        ar2 = request_approval(prod["id"], "gate_a_content", subject_sha256="abc", db_path=db)
        assert ar1["id"] == ar2["id"]

    def test_changed_sha_creates_new(self, db, prod):
        request_approval(prod["id"], "gate_a_content", subject_sha256="abc", db_path=db)
        ar2 = request_approval(prod["id"], "gate_a_content", subject_sha256="def", db_path=db)
        # Should be reset to pending with new sha
        assert ar2["status"] == "pending"
        assert ar2["subject_sha256"] == "def"
        # Only one row per gate (UNIQUE constraint)
        conn = _db.connect(db)
        rows = conn.execute(
            "SELECT COUNT(*) FROM approval_requests WHERE production_id=? AND gate_name='gate_a_content'",
            (prod["id"],),
        ).fetchone()
        conn.close()
        assert rows[0] == 1

    def test_record_pass(self, db, prod):
        request_approval(prod["id"], "gate_a_content", subject_sha256="abc", db_path=db)
        ar = record_approval_decision(prod["id"], "gate_a_content", "pass", actor="human", db_path=db)
        assert ar["status"] == "pass"
        assert is_approved(prod["id"], "gate_a_content", db_path=db)

    def test_record_fail(self, db, prod):
        request_approval(prod["id"], "gate_a_content", subject_sha256="abc", db_path=db)
        ar = record_approval_decision(prod["id"], "gate_a_content", "fail", db_path=db)
        assert ar["status"] == "fail"
        assert not is_approved(prod["id"], "gate_a_content", db_path=db)

    def test_invalid_decision_rejected(self, db, prod):
        request_approval(prod["id"], "gate_a_content", subject_sha256="abc", db_path=db)
        with pytest.raises(ValueError, match="pass.*fail"):
            record_approval_decision(prod["id"], "gate_a_content", "maybe", db_path=db)

    def test_forced_decision_logged(self, db, prod):
        request_approval(prod["id"], "gate_a_content", subject_sha256="abc", db_path=db)
        record_approval_decision(prod["id"], "gate_a_content", "pass", forced=True, db_path=db)
        events = _db.events(prod["id"], db_path=db)
        assert any(e["event_type"] == "approval_forced" for e in events)

    def test_outbox_message_created(self, db, prod):
        request_approval(prod["id"], "gate_a_content", subject_sha256="abc", db_path=db)
        conn = _db.connect(db)
        msgs = conn.execute(
            "SELECT * FROM outbox_messages WHERE production_id=? AND topic='telegram_approval'",
            (prod["id"],),
        ).fetchall()
        conn.close()
        assert len(msgs) >= 1


class TestJsonExport:
    def test_export_script(self, db, prod, tmp_path):
        save_script(prod["id"], {"segments": [{"label": "S001", "text": "Hello"}]}, db_path=db)
        out = tmp_path / "script_export.json"
        export_script_json(prod["id"], out, db_path=db)
        assert out.exists()
        import json
        data = json.loads(out.read_text())
        assert "segments" in data

    def test_export_storyboard(self, db, prod, tmp_path):
        save_storyboard(prod["id"], {"beats": [{"label": "B001", "shot_type": "lipsync"}]}, db_path=db)
        out = tmp_path / "storyboard_export.json"
        export_storyboard_json(prod["id"], out, db_path=db)
        assert out.exists()

    def test_export_missing_raises(self, db, prod, tmp_path):
        with pytest.raises(RuntimeError, match="no active script"):
            export_script_json(prod["id"], tmp_path / "x.json", db_path=db)

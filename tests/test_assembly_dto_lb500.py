"""Tests for policy-complete assembly DTOs (Ticket LB-500)."""
import pytest
from unittest.mock import patch, MagicMock

from assembly_dto import build_hero_assembly_dto, validate_dto_staleness, AssemblyDTOValidationError


def _make_mock_conn():
    """Helper to create a mock DB connection that handles both fetchone and fetchall."""
    mock_conn = MagicMock()
    
    # Default side effect for execute().fetchone()
    mock_conn.execute.return_value.fetchone.return_value = None
    # Default side effect for execute().fetchall()
    mock_conn.execute.return_value.fetchall.return_value = []
    
    return mock_conn


class TestAssemblyDTOValidation:
    @patch('assembly_dto._db.connect')
    @patch('assembly_dto._db.migrate')
    def test_missing_policy_rejected(self, mock_migrate, mock_connect):
        """Verify that a render unit missing audio_policy is rejected."""
        mock_conn = _make_mock_conn()
        mock_connect.return_value = mock_conn
        mock_conn.execute.return_value.fetchone.return_value = {
            "id": "ru_1",
            "active_artifact_id": "art_1",
            "audio_policy": "",  # Empty policy
            "text_policy": "NO_VISIBLE_TEXT",
            "required_start_ms": 0,
            "required_end_ms": 5000
        }
        
        with pytest.raises(AssemblyDTOValidationError, match="missing audio_policy"):
            build_hero_assembly_dto("prod_1", "ru_1", db_path="test.db")

    @patch('assembly_dto._db.connect')
    @patch('assembly_dto._db.migrate')
    def test_missing_qa_evidence_rejected(self, mock_migrate, mock_connect):
        """Verify that a hero unit without passing lipsync QA evidence is rejected."""
        mock_conn = _make_mock_conn()
        mock_connect.return_value = mock_conn
        
        def mock_execute_side_effect(sql, params=None):
            mock_cursor = MagicMock()
            if "render_units" in sql:
                mock_cursor.fetchone.return_value = {
                    "id": "ru_1",
                    "active_artifact_id": "art_1",
                    "audio_policy": "HERO_SYNC_LOCKED",
                    "text_policy": "NO_VISIBLE_TEXT",
                    "required_start_ms": 0,
                    "required_end_ms": 5000
                }
            elif "validations" in sql:
                # Only boundary passes, no lipsync
                mock_cursor.fetchall.return_value = [
                    {"id": "val_bound_1", "subject_type": "boundary_check", "status": "pass"}
                ]
            elif "tts_master" in sql:
                mock_cursor.fetchone.return_value = {"id": "art_audio_1"}
            return mock_cursor
            
        mock_conn.execute.side_effect = mock_execute_side_effect
        
        with pytest.raises(AssemblyDTOValidationError, match="Missing or failing lipsync QA evidence"):
            build_hero_assembly_dto("prod_1", "ru_1", db_path="test.db")

    @patch('assembly_dto._db.connect')
    @patch('assembly_dto._db.migrate')
    def test_stale_artifact_rejected(self, mock_migrate, mock_connect):
        """Verify that a deleted artifact is rejected during staleness validation."""
        mock_conn = _make_mock_conn()
        mock_connect.return_value = mock_conn
        
        # Artifact is deleted (returns None)
        mock_conn.execute.return_value.fetchone.return_value = None
        
        dto = MagicMock()
        dto.approved_video_artifact_id = "art_1"
        dto.render_unit_id = "ru_1"
        
        with pytest.raises(AssemblyDTOValidationError, match="is stale or deleted"):
            validate_dto_staleness(dto, "prod_1", db_path="test.db")

    @patch('assembly_dto._db.connect')
    @patch('assembly_dto._db.migrate')
    def test_stale_validation_rejected(self, mock_migrate, mock_connect):
        """Verify that a failing validation is rejected during staleness validation."""
        mock_conn = _make_mock_conn()
        mock_connect.return_value = mock_conn
        
        def mock_execute_side_effect(sql, params=None):
            mock_cursor = MagicMock()
            if "artifacts" in sql and "deleted_at" in sql:
                mock_cursor.fetchone.return_value = {"id": "art_1"}
            elif "render_units" in sql and "active_artifact_id" in sql:
                mock_cursor.fetchone.return_value = {"active_artifact_id": "art_1"}
            elif "validations" in sql:
                mock_cursor.fetchone.return_value = {"status": "fail"}
            return mock_cursor
            
        mock_conn.execute.side_effect = mock_execute_side_effect
        
        dto = MagicMock()
        dto.approved_video_artifact_id = "art_1"
        dto.render_unit_id = "ru_1"
        dto.boundary_evidence_ids = ["val_1"]
        dto.lipsync_evidence_ids = []
        
        with pytest.raises(AssemblyDTOValidationError, match="is stale or failing"):
            validate_dto_staleness(dto, "prod_1", db_path="test.db")

    @patch('assembly_dto._db.connect')
    @patch('assembly_dto._db.migrate')
    def test_valid_hero_unit_builds_successfully(self, mock_migrate, mock_connect):
        """Verify that a fully valid hero unit builds a complete DTO."""
        mock_conn = _make_mock_conn()
        mock_connect.return_value = mock_conn
        
        call_count = 0
        def mock_execute_side_effect(sql, params=None):
            nonlocal call_count
            call_count += 1
            mock_cursor = MagicMock()
            if call_count == 1: # render_units query
                mock_cursor.fetchone.return_value = {
                    "id": "ru_1",
                    "active_artifact_id": "art_video_1",
                    "audio_policy": "HERO_SYNC_LOCKED",
                    "text_policy": "NO_VISIBLE_TEXT",
                    "required_start_ms": 0,
                    "required_end_ms": 5000
                }
            elif call_count == 2: # validations query (fetchall)
                mock_cursor.fetchall.return_value = [
                    {"id": "val_bound_1", "subject_type": "boundary_check", "status": "pass"},
                    {"id": "val_lip_1", "subject_type": "lipsync_check", "status": "pass"}
                ]
            elif call_count == 3: # tts_master query
                mock_cursor.fetchone.return_value = {"id": "art_audio_1"}
            elif call_count == 4: # staleness: artifacts deleted_at check
                mock_cursor.fetchone.return_value = {"id": "art_video_1"}
            elif call_count == 5: # staleness: render_units active_artifact_id check
                mock_cursor.fetchone.return_value = {"active_artifact_id": "art_video_1"}
            elif call_count in (6, 7): # staleness: validations status check
                mock_cursor.fetchone.return_value = {"status": "pass"}
            return mock_cursor
            
        mock_conn.execute.side_effect = mock_execute_side_effect
        
        dto = build_hero_assembly_dto("prod_1", "ru_1", db_path="test.db")
        
        assert dto.render_unit_id == "ru_1"
        assert dto.approved_video_artifact_id == "art_video_1"
        assert dto.audio_policy == "HERO_SYNC_LOCKED"
        assert "setpts" in dto.forbidden_temporal_transforms
        assert "crop" in dto.permitted_spatial_transforms
        
        # Staleness check should pass
        validate_dto_staleness(dto, "prod_1", db_path="test.db")

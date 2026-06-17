"""Tests for FFmpeg policy validator (Ticket LB-501)."""
import pytest
from unittest.mock import MagicMock

from assembly_dto import HeroAssemblyDTO, AssemblyDTOValidationError
from ffmpeg_validator import validate_hero_ffmpeg_command, FORBIDDEN_TEMPORAL_FILTERS


def _make_hero_dto():
    """Helper to create a valid HERO_SYNC_LOCKED DTO."""
    return HeroAssemblyDTO(
        render_unit_id="ru_1",
        hero_render_group_id=None,
        approved_video_artifact_id="art_1",
        exact_timeline_placement={"start_ms": 0, "end_ms": 5000},
        visible_intervals=[{"start_ms": 0, "end_ms": 5000}],
        broll_cover_intervals=[],
        master_narration_reference="art_audio_1",
        audio_policy="HERO_SYNC_LOCKED",
        text_policy="NO_VISIBLE_TEXT",
        permitted_spatial_transforms=["crop", "scale"],
        forbidden_temporal_transforms=["setpts", "atempo", "loop", "reverse", "tpad", "trim"],
        boundary_evidence_ids=["val_1"],
        lipsync_evidence_ids=["val_2"],
    )


def _make_broll_dto():
    """Helper to create a BROLL_FLEX DTO (should bypass strict checks)."""
    dto = _make_hero_dto()
    dto.audio_policy = "BROLL_FLEX"
    return dto


class TestFFmpegPolicyValidator:
    def test_forbidden_setpts_rejected(self):
        """Verify that setpts filter is rejected for hero clips."""
        dto = _make_hero_dto()
        cmd = ["ffmpeg", "-i", "input.mp4", "-vf", "scale=1920:1080,setpts=0.5*PTS", "output.mp4"]
        with pytest.raises(AssemblyDTOValidationError, match="Forbidden temporal filter 'setpts'"):
            validate_hero_ffmpeg_command(cmd, dto)

    def test_forbidden_atempo_rejected(self):
        """Verify that atempo filter is rejected for hero clips."""
        dto = _make_hero_dto()
        cmd = ["ffmpeg", "-i", "input.mp4", "-af", "atempo=1.5", "output.mp4"]
        with pytest.raises(AssemblyDTOValidationError, match="Forbidden temporal filter 'atempo'"):
            validate_hero_ffmpeg_command(cmd, dto)

    def test_forbidden_loop_rejected(self):
        """Verify that loop filter is rejected for hero clips."""
        dto = _make_hero_dto()
        cmd = ["ffmpeg", "-i", "input.mp4", "-vf", "loop=2", "output.mp4"]
        with pytest.raises(AssemblyDTOValidationError, match="Forbidden temporal filter 'loop'"):
            validate_hero_ffmpeg_command(cmd, dto)

    def test_forbidden_reverse_rejected(self):
        """Verify that reverse filter is rejected for hero clips."""
        dto = _make_hero_dto()
        cmd = ["ffmpeg", "-i", "input.mp4", "-vf", "reverse", "output.mp4"]
        with pytest.raises(AssemblyDTOValidationError, match="Forbidden temporal filter 'reverse'"):
            validate_hero_ffmpeg_command(cmd, dto)

    def test_forbidden_tpad_rejected(self):
        """Verify that tpad (freeze extension) filter is rejected for hero clips."""
        dto = _make_hero_dto()
        cmd = ["ffmpeg", "-i", "input.mp4", "-vf", "tpad=stop_mode=clone:stop_duration=1", "output.mp4"]
        with pytest.raises(AssemblyDTOValidationError, match="Forbidden temporal filter 'tpad'"):
            validate_hero_ffmpeg_command(cmd, dto)

    def test_forbidden_trim_rejected(self):
        """Verify that trim filter is rejected for hero clips."""
        dto = _make_hero_dto()
        cmd = ["ffmpeg", "-i", "input.mp4", "-vf", "trim=start=1:end=2", "output.mp4"]
        with pytest.raises(AssemblyDTOValidationError, match="Forbidden temporal filter 'trim'"):
            validate_hero_ffmpeg_command(cmd, dto)

    def test_allowed_spatial_operations_pass(self):
        """Verify that allowed spatial operations (crop, scale, grade) pass for hero clips."""
        dto = _make_hero_dto()
        cmd = [
            "ffmpeg", "-i", "input.mp4",
            "-vf", "scale=1920:1080,crop=1920:1080:0:0,format=yuv420p",
            "output.mp4"
        ]
        # Should not raise
        validate_hero_ffmpeg_command(cmd, dto)

    def test_allowed_hard_cut_passes(self):
        """Verify that controlled -ss and -t (hard cuts) pass for hero clips."""
        dto = _make_hero_dto()
        cmd = ["ffmpeg", "-ss", "0.0", "-i", "input.mp4", "-t", "5.0", "-c", "copy", "output.mp4"]
        # Should not raise
        validate_hero_ffmpeg_command(cmd, dto)

    def test_broll_bypasses_strict_temporal_checks(self):
        """Verify that B-roll clips are not subjected to strict hero temporal checks."""
        dto = _make_broll_dto()
        # Even with a forbidden filter, it should pass because it's not HERO_SYNC_LOCKED
        cmd = ["ffmpeg", "-i", "input.mp4", "-vf", "setpts=0.5*PTS", "output.mp4"]
        # Should not raise
        validate_hero_ffmpeg_command(cmd, dto)

    def test_future_unknown_temporal_filter_fails_closed(self):
        """Verify that adding a new forbidden filter to the list causes failure."""
        dto = _make_hero_dto()
        # Simulate a new forbidden filter being added
        import ffmpeg_validator
        original_forbidden = ffmpeg_validator.FORBIDDEN_TEMPORAL_FILTERS.copy()
        ffmpeg_validator.FORBIDDEN_TEMPORAL_FILTERS.append("new_temporal_filter")
        
        cmd = ["ffmpeg", "-i", "input.mp4", "-vf", "new_temporal_filter=1", "output.mp4"]
        
        try:
            with pytest.raises(AssemblyDTOValidationError, match="Forbidden temporal filter 'new_temporal_filter'"):
                validate_hero_ffmpeg_command(cmd, dto)
        finally:
            # Restore original list
            ffmpeg_validator.FORBIDDEN_TEMPORAL_FILTERS = original_forbidden

    def test_command_inspection_catches_flag(self):
        """Verify that forbidden command flags are caught."""
        dto = _make_hero_dto()
        cmd = ["ffmpeg", "-i", "input.mp4", "-itsoffset", "1.5", "output.mp4"]
        with pytest.raises(AssemblyDTOValidationError, match="Forbidden command flag '-itsoffset'"):
            validate_hero_ffmpeg_command(cmd, dto)

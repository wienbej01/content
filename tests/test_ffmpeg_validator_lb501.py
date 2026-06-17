"""Tests for FFmpeg policy validator (R5-003)."""
import pytest

import ffmpeg_validator
from ffmpeg_validator import validate_ffmpeg_command, FFmpegPolicyError


class TestFFmpegPolicyValidator:
    def test_forbidden_setpts_rejected(self):
        cmd = ["ffmpeg", "-i", "input.mp4", "-vf", "scale=1920:1080,setpts=0.5*PTS", "output.mp4"]
        with pytest.raises(FFmpegPolicyError, match="setpts"):
            validate_ffmpeg_command(cmd, "HERO_SYNC_LOCKED", "test")

    def test_forbidden_atempo_rejected(self):
        cmd = ["ffmpeg", "-i", "input.mp4", "-af", "atempo=1.5", "output.mp4"]
        with pytest.raises(FFmpegPolicyError, match="atempo"):
            validate_ffmpeg_command(cmd, "HERO_SYNC_LOCKED", "test")

    def test_forbidden_loop_rejected(self):
        cmd = ["ffmpeg", "-i", "input.mp4", "-vf", "loop=2", "output.mp4"]
        with pytest.raises(FFmpegPolicyError, match="loop"):
            validate_ffmpeg_command(cmd, "HERO_SYNC_LOCKED", "test")

    def test_forbidden_reverse_rejected(self):
        cmd = ["ffmpeg", "-i", "input.mp4", "-vf", "reverse", "output.mp4"]
        with pytest.raises(FFmpegPolicyError, match="reverse"):
            validate_ffmpeg_command(cmd, "HERO_SYNC_LOCKED", "test")

    def test_forbidden_tpad_rejected(self):
        cmd = ["ffmpeg", "-i", "input.mp4", "-vf", "tpad=stop_mode=clone:stop_duration=1", "output.mp4"]
        with pytest.raises(FFmpegPolicyError, match="tpad"):
            validate_ffmpeg_command(cmd, "HERO_SYNC_LOCKED", "test")

    def test_forbidden_trim_rejected(self):
        cmd = ["ffmpeg", "-i", "input.mp4", "-vf", "trim=start=1:end=2", "output.mp4"]
        with pytest.raises(FFmpegPolicyError, match="trim"):
            validate_ffmpeg_command(cmd, "HERO_SYNC_LOCKED", "test")

    def test_allowed_spatial_operations_pass(self):
        cmd = ["ffmpeg", "-i", "input.mp4",
               "-vf", "scale=1920:1080,crop=1920:1080:0:0,format=yuv420p",
               "output.mp4"]
        validate_ffmpeg_command(cmd, "HERO_SYNC_LOCKED", "test")

    def test_allowed_hard_cut_passes(self):
        cmd = ["ffmpeg", "-ss", "0.0", "-i", "input.mp4", "-t", "5.0", "-c", "copy", "output.mp4"]
        validate_ffmpeg_command(cmd, "HERO_SYNC_LOCKED", "test")

    def test_broll_bypasses_strict_temporal_checks(self):
        cmd = ["ffmpeg", "-i", "input.mp4", "-vf", "setpts=0.5*PTS", "output.mp4"]
        validate_ffmpeg_command(cmd, "BROLL_FLEX", "test")

    def test_unknown_temporal_filter_fails_closed(self):
        cmd = ["ffmpeg", "-i", "input.mp4", "-vf", "tpad=stop_mode=clone", "output.mp4"]
        with pytest.raises(FFmpegPolicyError, match="tpad"):
            validate_ffmpeg_command(cmd, "HERO_SYNC_LOCKED", "test")

    def test_itsoffset_flag_rejected(self):
        cmd = ["ffmpeg", "-i", "input.mp4", "-itsoffset", "1.5", "output.mp4"]
        with pytest.raises(FFmpegPolicyError, match="itsoffset"):
            validate_ffmpeg_command(cmd, "HERO_SYNC_LOCKED", "test")

    def test_frame_count_validation(self):
        assert ffmpeg_validator.validate_frame_count(24.0, 5.0, 120, 1.0) is True
        assert ffmpeg_validator.validate_frame_count(24.0, 5.0, 100, 1.0) is False

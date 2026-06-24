"""Tests for hero no-temporal-edit enforcement (S02-T003).

Verifies that HERO_SYNC_LOCKED visuals cannot be retimed, looped, frozen,
or trimmed through speech in any assembly path.
"""
import pytest
from pathlib import Path


@pytest.fixture
def tmp_base(tmp_path):
    """Create a temporary base directory with a minimal valid media file."""
    d = tmp_path / "media"
    d.mkdir()
    # Create a tiny valid MP4 for media reference (required for non-guard code paths).
    # The guard tests should trigger BEFORE ffmpeg is called, so this is a safety net.
    import subprocess
    media = d / "dummy_video.mp4"
    # Use ffmpeg to create a minimal 1-frame video
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=160x90:d=1",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        str(media),
    ], capture_output=True, check=True)
    return d


class TestHeroSpeedChangeGuard:
    """speed_change on hero raises BLOCKED."""

    def _call_process_segment(self, seg, speed=1.0, allow_looping=False,
                               tmp_base=None):
        """Call process_segment with minimal params."""
        from scripts.assemble import process_segment
        return process_segment(
            seg, speed,
            w=160, h=90, fps=24, grade="", crf=23,
            tmp=str(tmp_base.parent) if tmp_base else "/tmp",
            base=str(tmp_base) if tmp_base else "/tmp",
            idx=0, allow_looping=allow_looping,
        )

    def test_hero_speed_change_raises(self, tmp_base):
        """S02-T003-R1: Speed != 1.0 on hero raises BLOCKED."""
        seg = {"audio_policy": "HERO_SYNC_LOCKED"}
        with pytest.raises(ValueError, match="HERO_TEMPORAL_EDIT_FORBIDDEN"):
            self._call_process_segment(seg, speed=0.8, tmp_base=tmp_base)
        with pytest.raises(ValueError, match="operation=speed_change"):
            self._call_process_segment(seg, speed=1.5, tmp_base=tmp_base)

    def test_hero_speed_change_blocks_0_5x(self, tmp_base):
        """Speed=0.5 is still forbidden."""
        seg = {"audio_policy": "HERO_SYNC_LOCKED"}
        with pytest.raises(ValueError, match="HERO_TEMPORAL_EDIT_FORBIDDEN"):
            self._call_process_segment(seg, speed=0.5, tmp_base=tmp_base)

    def test_hero_speed_1_0_passes_guard(self, tmp_base):
        """Speed=1.0 on hero passes the speed guard (may fail elsewhere on ffmpeg)."""
        # This should pass the guard but may fail on missing media.
        # We just check no ValueError with BLOCKED is raised.
        seg = {"audio_policy": "HERO_SYNC_LOCKED", "media": "dummy_video.mp4"}
        try:
            self._call_process_segment(seg, speed=1.0, tmp_base=tmp_base)
        except ValueError as e:
            assert "BLOCKED" not in str(e), f"Guard should not trigger: {e}"
        except Exception:
            pass  # Non-guard failures are expected (no real media)


class TestHeroLoopGuard:
    """Loop on hero raises BLOCKED."""

    def test_hero_loop_raises(self, tmp_base):
        """S02-T003-R2: allow_looping=True on hero raises BLOCKED."""
        seg = {"audio_policy": "HERO_SYNC_LOCKED"}
        with pytest.raises(ValueError, match="HERO_TEMPORAL_EDIT_FORBIDDEN"):
            from scripts.assemble import process_segment
            process_segment(
                seg, 1.0, 160, 90, 24, "", 23,
                str(tmp_base.parent), str(tmp_base), 0,
                allow_looping=True,
            )


class TestHeroTrimGuard:
    """trim_through_speech on hero raises BLOCKED."""

    def test_hero_trim_through_speech_raises(self, tmp_base):
        """S02-T003-R3: trim_end < speech_len_sec raises BLOCKED."""
        seg = {
            "audio_policy": "HERO_SYNC_LOCKED",
            "trim_end": 2.0,
            "speech_len_sec": 3.0,
        }
        with pytest.raises(ValueError, match="trim_through_speech"):
            from scripts.assemble import process_segment
            process_segment(
                seg, 1.0, 160, 90, 24, "", 23,
                str(tmp_base.parent), str(tmp_base), 0,
            )

    def test_hero_trim_at_speech_end_passes(self, tmp_base):
        """trim_end == speech_len_sec should not trigger the trim guard."""
        seg = {
            "audio_policy": "HERO_SYNC_LOCKED",
            "trim_end": 3.0,
            "speech_len_sec": 3.0,
            "media": "dummy_video.mp4",
        }
        try:
            from scripts.assemble import process_segment
            process_segment(
                seg, 1.0, 160, 90, 24, "", 23,
                str(tmp_base.parent), str(tmp_base), 0,
            )
        except ValueError as e:
            assert "trim_through_speech" not in str(e), (
                f"Trim guard should not trigger: {e}"
            )
        except Exception:
            pass  # Non-guard failures expected


class TestNonHeroBroll:
    """Non-hero b-roll still allows safe trim/pad where policy permits."""

    def test_non_hero_broll_speed_not_blocked(self, tmp_base):
        """S02-T003-R4: Non-hero with speed != 1.0 does NOT trigger BLOCKED."""
        seg = {
            "audio_policy": "BROLL_FLEX",
            "media": "dummy_video.mp4",
        }
        try:
            from scripts.assemble import process_segment
            process_segment(
                seg, 1.2, 160, 90, 24, "", 23,
                str(tmp_base.parent), str(tmp_base), 0,
            )
        except ValueError as e:
            assert "BLOCKED" not in str(e), (
                f"Non-hero should not trigger guard: {e}"
            )
        except Exception:
            pass  # Non-guard failures expected (media/ffmpeg)

    def test_non_hero_broll_allowed_loop(self, tmp_base):
        """Non-hero with allow_looping=True does NOT trigger BLOCKED."""
        seg = {
            "audio_policy": "BROLL_FLEX",
            "media": "dummy_video.mp4",
        }
        try:
            from scripts.assemble import process_segment
            process_segment(
                seg, 1.0, 160, 90, 24, "", 23,
                str(tmp_base.parent), str(tmp_base), 0,
                allow_looping=True,
            )
        except ValueError as e:
            assert "BLOCKED" not in str(e), (
                f"Non-hero loop should not trigger guard: {e}"
            )
        except Exception:
            pass


class TestIsHeroLipsync:
    """_is_hero_lipsync classification."""

    def test_hero_policy_classification(self):
        from scripts.assemble import _is_hero_lipsync
        assert _is_hero_lipsync({"audio_policy": "HERO_SYNC_LOCKED"}) is True
        assert _is_hero_lipsync({"audio_policy": "keep_lipsync"}) is True
        assert _is_hero_lipsync({"audio_policy": "hero_lipsync"}) is True
        assert _is_hero_lipsync({"audio_policy": "BROLL_FLEX"}) is False
        assert _is_hero_lipsync({"lipsync_required": True}) is True
        assert _is_hero_lipsync({}) is False

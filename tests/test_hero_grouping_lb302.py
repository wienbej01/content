"""Tests for hero render-group planner (Ticket LB-302)."""
import pytest
from scripts.hero_grouping import (
    plan_hero_render_groups,
    validate_hero_group,
    HeroRenderGroup,
    MAX_PROVIDER_DURATION_SEC,
)


class TestHeroRenderGroupPlanner:
    def test_short_cutaway_forms_one_group(self):
        """Verify that a short B-roll cutaway allows hero-before and hero-after to form one group."""
        beats = [
            {
                "beat_id": "B001", "lipsync_required": True,
                "speech_start_sample": 0, "speech_end_sample": 48000,  # 1.0s
                "leading_silence_samples": 0, "trailing_silence_samples": 0,
                "scene_id": "scene_A", "camera_id": "cam_1", "continuity_value": "high",
                "positive_prompt": "hero speaking", "model": "seedance_2_0"
            },
            # Short cutaway (simulated by being part of the same scene/camera with high continuity)
            {
                "beat_id": "B002", "lipsync_required": True,
                "speech_start_sample": 96000, "speech_end_sample": 144000,  # 2.0s to 3.0s
                "leading_silence_samples": 0, "trailing_silence_samples": 0,
                "scene_id": "scene_A", "camera_id": "cam_1", "continuity_value": "high",
                "positive_prompt": "hero speaking continued", "model": "seedance_2_0"
            }
        ]
        groups = plan_hero_render_groups(beats, master_duration_samples=200000)
        
        assert len(groups) == 1
        assert len(groups[0].member_visible_intervals) == 2
        assert groups[0].requested_duration_sec == 3.0  # 0 to 144000 samples = 3.0s

    def test_long_cutaway_creates_separate_groups(self):
        """Verify that a long cutaway (or low continuity) forces separate groups."""
        beats = [
            {
                "beat_id": "B001", "lipsync_required": True,
                "speech_start_sample": 0, "speech_end_sample": 48000,
                "leading_silence_samples": 0, "trailing_silence_samples": 0,
                "scene_id": "scene_A", "camera_id": "cam_1", "continuity_value": "low",  # Low continuity
                "positive_prompt": "hero speaking", "model": "seedance_2_0"
            },
            {
                "beat_id": "B002", "lipsync_required": True,
                "speech_start_sample": 96000, "speech_end_sample": 144000,
                "leading_silence_samples": 0, "trailing_silence_samples": 0,
                "scene_id": "scene_A", "camera_id": "cam_1", "continuity_value": "low",
                "positive_prompt": "hero speaking continued", "model": "seedance_2_0"
            }
        ]
        groups = plan_hero_render_groups(beats, master_duration_samples=200000)
        
        # Low continuity should prevent merging
        assert len(groups) == 2

    def test_provider_maximum_forces_split(self):
        """Verify that exceeding the provider maximum duration forces a split."""
        beats = [
            {
                "beat_id": "B001", "lipsync_required": True,
                "speech_start_sample": 0, "speech_end_sample": 480000,  # 10.0s
                "leading_silence_samples": 0, "trailing_silence_samples": 0,
                "scene_id": "scene_A", "camera_id": "cam_1", "continuity_value": "high",
                "positive_prompt": "hero speaking", "model": "seedance_2_0"
            },
            {
                "beat_id": "B002", "lipsync_required": True,
                "speech_start_sample": 528000, "speech_end_sample": 1008000,  # 11.0s to 21.0s (total 21s > 15s max)
                "leading_silence_samples": 0, "trailing_silence_samples": 0,
                "scene_id": "scene_A", "camera_id": "cam_1", "continuity_value": "high",
                "positive_prompt": "hero speaking continued", "model": "seedance_2_0"
            }
        ]
        groups = plan_hero_render_groups(beats, master_duration_samples=1100000)
        
        # Should split because 21.0s > 15.0s max
        assert len(groups) == 2
        assert groups[0].requested_duration_sec == 10.0
        assert groups[1].requested_duration_sec == 10.0

    def test_scene_change_forces_split(self):
        """Verify that a scene or camera change forces a split."""
        beats = [
            {
                "beat_id": "B001", "lipsync_required": True,
                "speech_start_sample": 0, "speech_end_sample": 48000,
                "leading_silence_samples": 0, "trailing_silence_samples": 0,
                "scene_id": "scene_A", "camera_id": "cam_1", "continuity_value": "high",
                "positive_prompt": "hero speaking", "model": "seedance_2_0"
            },
            {
                "beat_id": "B002", "lipsync_required": True,
                "speech_start_sample": 96000, "speech_end_sample": 144000,
                "leading_silence_samples": 0, "trailing_silence_samples": 0,
                "scene_id": "scene_B",  # Scene change
                "camera_id": "cam_1", "continuity_value": "high",
                "positive_prompt": "hero speaking in new scene", "model": "seedance_2_0"
            }
        ]
        groups = plan_hero_render_groups(beats, master_duration_samples=200000)
        
        assert len(groups) == 2

    def test_group_cannot_include_unrelated_next_beat(self):
        """Verify that unrelated beats (e.g., non-lipsync) are not included in the hero group."""
        beats = [
            {
                "beat_id": "B001", "lipsync_required": True,
                "speech_start_sample": 0, "speech_end_sample": 48000,
                "leading_silence_samples": 0, "trailing_silence_samples": 0,
                "scene_id": "scene_A", "camera_id": "cam_1", "continuity_value": "high",
                "positive_prompt": "hero speaking", "model": "seedance_2_0"
            },
            {
                "beat_id": "B002", "lipsync_required": False,  # B-roll, not lipsync
                "scene_id": "scene_A", "camera_id": "cam_1", "continuity_value": "high",
            },
            {
                "beat_id": "B003", "lipsync_required": True,
                "speech_start_sample": 96000, "speech_end_sample": 144000,
                "leading_silence_samples": 0, "trailing_silence_samples": 0,
                "scene_id": "scene_A", "camera_id": "cam_1", "continuity_value": "high",
                "positive_prompt": "hero speaking continued", "model": "seedance_2_0"
            }
        ]
        groups = plan_hero_render_groups(beats, master_duration_samples=200000)
        
        # B001 and B003 should be grouped together, B002 is ignored by the planner
        assert len(groups) == 1
        assert len(groups[0].member_visible_intervals) == 2
        assert groups[0].member_visible_intervals[0].beat_id == "B001"
        assert groups[0].member_visible_intervals[1].beat_id == "B003"

    def test_broll_covered_interval_remains_within_group(self):
        """Verify that B-roll covered intervals are correctly attached to the group."""
        beats = [
            {
                "beat_id": "B001", "lipsync_required": True,
                "speech_start_sample": 0, "speech_end_sample": 96000,  # 2.0s
                "leading_silence_samples": 0, "trailing_silence_samples": 0,
                "scene_id": "scene_A", "camera_id": "cam_1", "continuity_value": "high",
                "positive_prompt": "hero speaking", "model": "seedance_2_0",
                "broll_covered": [
                    {"start_sample": 24000, "end_sample": 48000, "beat_id": "B001_BROLL"}
                ]
            }
        ]
        groups = plan_hero_render_groups(beats, master_duration_samples=200000)
        
        assert len(groups) == 1
        assert len(groups[0].broll_covered_intervals) == 1
        assert groups[0].broll_covered_intervals[0].beat_id == "B001_BROLL"
        assert groups[0].broll_covered_intervals[0].start_sample == 24000


class TestHeroGroupValidation:
    def test_valid_group_passes_validation(self):
        """Verify that a valid group passes validation."""
        group = HeroRenderGroup(
            hero_render_group_id="test_grp",
            generation_start_sample=0,
            generation_end_sample=144000,  # 3.0s
            requested_duration_sec=3.0,
            member_visible_intervals=[{"start_sample": 0, "end_sample": 144000, "beat_id": "B001"}]  # type: ignore
        )
        # Note: The dataclass expects VisibleInterval objects, but for this test we just check duration
        # Let's create it properly
        from scripts.hero_grouping import VisibleInterval
        group = HeroRenderGroup(
            hero_render_group_id="test_grp",
            generation_start_sample=0,
            generation_end_sample=144000,
            requested_duration_sec=3.0,
            member_visible_intervals=[VisibleInterval(start_sample=0, end_sample=144000, beat_id="B001")]
        )
        assert validate_hero_group(group) is True

    def test_exceeds_max_duration_fails_validation(self):
        """Verify that a group exceeding max duration fails validation."""
        from scripts.hero_grouping import VisibleInterval
        group = HeroRenderGroup(
            hero_render_group_id="test_grp",
            generation_start_sample=0,
            generation_end_sample=960000,  # 20.0s
            requested_duration_sec=20.0,
            member_visible_intervals=[VisibleInterval(start_sample=0, end_sample=960000, beat_id="B001")]
        )
        with pytest.raises(ValueError, match="exceeds max duration"):
            validate_hero_group(group)

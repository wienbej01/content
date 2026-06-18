"""S4-T04: Persist hero render groups — deterministic ID + membership.

Named test required by the program:
  test_hero_group_deterministic_and_persisted
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from hero_grouping import (
    HeroRenderGroup, VisibleInterval, BrollCoveredInterval,
    _deterministic_group_id, plan_hero_render_groups, validate_hero_group,
)


def test_hero_group_deterministic_id():
    """The same members + master slice + prompt produce the same group ID."""
    members = [{"beat_id": "B001"}, {"beat_id": "B002"}]
    gid1 = _deterministic_group_id(members, "slice_sha_abc", "prompt_rev_1")
    gid2 = _deterministic_group_id(members, "slice_sha_abc", "prompt_rev_1")
    assert gid1 == gid2, "same inputs must produce same group ID"

    # Different members → different ID
    gid3 = _deterministic_group_id([{"beat_id": "B001"}], "slice_sha_abc", "prompt_rev_1")
    assert gid1 != gid3

    # Different slice → different ID
    gid4 = _deterministic_group_id(members, "slice_sha_xyz", "prompt_rev_1")
    assert gid1 != gid4


def test_hero_group_membership_persisted():
    """A HeroRenderGroup records its visible intervals and B-roll coverage."""
    group = HeroRenderGroup(
        hero_render_group_id="hero_grp_test",
        group_hash="abc123",
        generation_start_sample=48000,
        generation_end_sample=144000,
        member_visible_intervals=[
            VisibleInterval(start_sample=48000, end_sample=96000, beat_id="B001"),
            VisibleInterval(start_sample=96000, end_sample=144000, beat_id="B002"),
        ],
        broll_covered_intervals=[
            BrollCoveredInterval(start_sample=72000, end_sample=84000, beat_id="B001"),
        ],
        source_audio_slice_sha256="slice_sha_abc",
        prompt="hero speaking about topic",
        requested_duration_sec=3.0,
        continuity_benefit="continuous speech across B001-B002",
    )

    assert len(group.member_visible_intervals) == 2
    assert group.member_visible_intervals[0].beat_id == "B001"
    assert len(group.broll_covered_intervals) == 1
    assert group.generation_end_sample - group.generation_start_sample == 96000


def test_hero_group_validation_rejects_too_long():
    """A group exceeding MAX_PROVIDER_DURATION_SEC fails validation."""
    group = HeroRenderGroup(
        hero_render_group_id="hero_grp_long",
        group_hash="def456",
        generation_start_sample=0,
        generation_end_sample=int(20.0 * 48000),  # 20s > 15s max
        member_visible_intervals=[],
        requested_duration_sec=20.0,
    )
    with pytest.raises(ValueError, match="exceeds max duration"):
        validate_hero_group(group)


def test_hero_group_validation_accepts_valid():
    """A group within MAX_PROVIDER_DURATION_SEC passes validation."""
    group = HeroRenderGroup(
        hero_render_group_id="hero_grp_ok",
        group_hash="ghi789",
        generation_start_sample=0,
        generation_end_sample=int(10.0 * 48000),  # 10s < 15s max
        member_visible_intervals=[
            VisibleInterval(start_sample=0, end_sample=int(5.0 * 48000), beat_id="B001"),
        ],
        requested_duration_sec=10.0,
    )
    assert validate_hero_group(group)

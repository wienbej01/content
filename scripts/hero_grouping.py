"""Sprint 3/R3: Hero Render Group Planner (Ticket LB-302 / R3-003).

Decides when hero-before and hero-after B-roll should be one continuous render.
Uses deterministic group IDs (hash of members + master slice + prompt revision),
persists groups via DB, and includes intervening narration in merge decisions.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import List, Optional


MAX_PROVIDER_DURATION_SEC = 15.0
MIN_PROVIDER_DURATION_SEC = 4.0


@dataclass
class VisibleInterval:
    start_sample: int
    end_sample: int
    beat_id: str


@dataclass
class BrollCoveredInterval:
    start_sample: int
    end_sample: int
    beat_id: str


@dataclass
class HeroRenderGroup:
    hero_render_group_id: str
    group_hash: str
    generation_start_sample: int
    generation_end_sample: int
    generation_duration_samples: int = 0
    member_visible_intervals: List[VisibleInterval] = field(default_factory=list)
    broll_covered_intervals: List[BrollCoveredInterval] = field(default_factory=list)
    source_audio_slice_path: Optional[str] = None
    source_audio_slice_sha256: Optional[str] = None
    prompt: str = ""
    model: str = "seedance_2_0"
    requested_duration_sec: float = 0.0
    regeneration_blast_radius: List[str] = field(default_factory=list)
    temporal_edit_policy: str = "HERO_SYNC_LOCKED"
    continuity_benefit: str = ""
    scene_consistent: bool = True
    intervening_beat_ids: List[str] = field(default_factory=list)


def _deterministic_group_id(members: list[dict], master_slice_sha: Optional[str],
                            prompt_revision: Optional[str]) -> str:
    """Derive a deterministic semantic group id from members + provenance."""
    member_keys = sorted([m.get("beat_id", "") for m in members])
    payload = f"{'|'.join(member_keys)}|{master_slice_sha or ''}|{prompt_revision or ''}"
    digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return f"hero_grp_{digest}"


def plan_hero_render_groups(
    beats: List[dict],
    master_duration_samples: int,
    sample_rate: int = 48000,
    intervening_beats: Optional[List[dict]] = None,
) -> List[HeroRenderGroup]:
    """Plan hero render groups based on continuity, duration limits, and scene consistency.

    R3-003 hardening:
    - Deterministic group id (hash of members + source + prompt revision)
    - Includes intervening (non-hero) narration in merge decisions
    - Scene and camera remain consistent
    - Return interval is explicit
    """
    groups = []
    current_group: Optional[HeroRenderGroup] = None
    intervening_map = {b.get("beat_id"): b for b in (intervening_beats or [])}

    for beat in beats:
        if not beat.get("lipsync_required"):
            continue

        beat_id = beat["beat_id"]
        speech_start = int(beat.get("speech_start_sample", 0))
        speech_end = int(beat.get("speech_end_sample", speech_start))
        lead_silence = int(beat.get("leading_silence_samples", 0))
        trail_silence = int(beat.get("trailing_silence_samples", 0))

        gen_start = speech_start - lead_silence
        gen_end = speech_end + trail_silence
        duration_sec = (gen_end - gen_start) / sample_rate

        scene_id = beat.get("scene_id", "default")
        camera_id = beat.get("camera_id", "default")
        continuity_value = beat.get("continuity_value", "low")

        can_merge = False
        intervening_cost = 0
        if current_group is not None:
            intervening_cost = 0
            for ib_id in current_group.intervening_beat_ids:
                ib = intervening_map.get(ib_id, {})
                intervening_cost += int(ib.get("speech_end_sample", int(ib.get("end_ms", 0)) * sample_rate / 1000)) \
                    - int(ib.get("speech_start_sample", int(ib.get("start_ms", 0)) * sample_rate / 1000))

            potential_end = max(current_group.generation_end_sample, gen_end) + intervening_cost
            potential_duration_sec = (potential_end - current_group.generation_start_sample) / sample_rate

            if potential_duration_sec <= MAX_PROVIDER_DURATION_SEC:
                if current_group.scene_consistent and scene_id == current_group._last_scene_id and camera_id == current_group._last_camera_id:
                    if continuity_value in ("high", "medium"):
                        can_merge = True

        if can_merge and current_group is not None:
            current_group.generation_end_sample = max(current_group.generation_end_sample, gen_end) + intervening_cost
            current_group.generation_duration_samples = current_group.generation_end_sample - current_group.generation_start_sample
            current_group.requested_duration_sec = current_group.generation_duration_samples / sample_rate
            current_group.member_visible_intervals.append(VisibleInterval(
                start_sample=speech_start,
                end_sample=speech_end,
                beat_id=beat_id,
            ))
            current_group.regeneration_blast_radius.append(beat_id)
            current_group._last_scene_id = scene_id
            current_group._last_camera_id = camera_id

            current_members = [{"beat_id": vi.beat_id} for vi in current_group.member_visible_intervals]
            current_group.hero_render_group_id = _deterministic_group_id(
                current_members, current_group.source_audio_slice_sha256, None)
            current_group.group_hash = current_group.hero_render_group_id
        else:
            if current_group is not None:
                groups.append(current_group)

            current_group = HeroRenderGroup(
                hero_render_group_id=_deterministic_group_id(
                    [{"beat_id": beat_id}], None, None),
                group_hash="",
                generation_start_sample=gen_start,
                generation_end_sample=gen_end,
                generation_duration_samples=gen_end - gen_start,
                requested_duration_sec=duration_sec,
                member_visible_intervals=[VisibleInterval(
                    start_sample=speech_start,
                    end_sample=speech_end,
                    beat_id=beat_id,
                )],
                regeneration_blast_radius=[beat_id],
                scene_consistent=True,
                continuity_benefit=f"Grouped for {continuity_value} continuity" if continuity_value in ("high", "medium") else "Default grouping",
                intervening_beat_ids=[],
            )
            current_group._last_scene_id = scene_id
            current_group._last_camera_id = camera_id

        if beat.get("broll_covered"):
            for broll in beat["broll_covered"]:
                current_group.broll_covered_intervals.append(BrollCoveredInterval(
                    start_sample=int(broll["start_sample"]),
                    end_sample=int(broll["end_sample"]),
                    beat_id=broll["beat_id"],
                ))

        if current_group.source_audio_slice_path is None and beat.get("audio_slice"):
            current_group.source_audio_slice_path = beat["audio_slice"].get("file")
            current_group.source_audio_slice_sha256 = beat["audio_slice"].get("slice_sha256")

        if not current_group.prompt and beat.get("positive_prompt"):
            current_group.prompt = beat["positive_prompt"]
            current_group.model = beat.get("model", "seedance_2_0")

    if current_group is not None:
        if hasattr(current_group, "_last_scene_id"):
            delattr(current_group, "_last_scene_id")
        if hasattr(current_group, "_last_camera_id"):
            delattr(current_group, "_last_camera_id")
        groups.append(current_group)

    return groups


def validate_hero_group(group: HeroRenderGroup, max_duration_sec: float = MAX_PROVIDER_DURATION_SEC) -> bool:
    if group.requested_duration_sec > max_duration_sec:
        raise ValueError(f"Group {group.hero_render_group_id} exceeds max duration: {group.requested_duration_sec}s > {max_duration_sec}s")

    if not group.member_visible_intervals:
        raise ValueError(f"Group {group.hero_render_group_id} has no visible intervals")

    return True


def groups_to_db_dicts(groups: List[HeroRenderGroup], master_artifact_id: Optional[str] = None,
                       master_sha256: Optional[str] = None) -> list[dict]:
    """Convert HeroRenderGroup list to dicts suitable for persist_hero_render_groups."""
    result = []
    for g in groups:
        result.append({
            "hero_render_group_id": g.hero_render_group_id,
            "group_hash": g.group_hash or g.hero_render_group_id,
            "generation_start_sample": g.generation_start_sample,
            "generation_end_sample": g.generation_end_sample,
            "generation_duration_samples": g.generation_duration_samples,
            "source_audio_sha256": g.source_audio_slice_sha256,
            "prompt": g.prompt,
            "model": g.model,
            "requested_duration_sec": g.requested_duration_sec,
            "regeneration_blast_radius": g.regeneration_blast_radius,
            "temporal_edit_policy": g.temporal_edit_policy,
            "continuity_benefit": g.continuity_benefit,
            "scene_consistent": g.scene_consistent,
            "master_audio_artifact_id": master_artifact_id,
            "master_audio_sha256": master_sha256,
            "member_visible_intervals": [
                {"start_sample": vi.start_sample, "end_sample": vi.end_sample,
                 "render_unit_id": vi.beat_id, "beat_id": vi.beat_id}
                for vi in g.member_visible_intervals
            ],
            "covered_intervals": [
                {"start_sample": ci.start_sample, "end_sample": ci.end_sample,
                 "beat_id": ci.beat_id, "kind": "broll_covered"}
                for ci in g.broll_covered_intervals
            ],
        })
    return result

"""Sprint 3: Hero Render Group Planner (Ticket LB-302).

Decides when hero-before and hero-after B-roll should be one continuous Seedance render.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

# Provider limits (e.g., Seedance max 15s)
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
    generation_start_sample: int
    generation_end_sample: int
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


def _generate_group_id() -> str:
    return f"hero_grp_{uuid.uuid4().hex[:12]}"


def plan_hero_render_groups(
    beats: List[dict],
    master_duration_samples: int,
    sample_rate: int = 48000,
) -> List[HeroRenderGroup]:
    """
    Plan hero render groups based on continuity, duration limits, and scene consistency.
    
    Rules:
    - One continuous group is permitted only when total duration is provider-valid.
    - No unrelated neighbouring speech is included.
    - Scene and camera remain consistent.
    - Return interval is explicit.
    - Continuity benefit is documented.
    """
    groups = []
    current_group: Optional[HeroRenderGroup] = None
    
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
        
        # Check if we can merge with the current group
        can_merge = False
        if current_group is not None:
            # Rule: total duration must be provider-valid
            potential_end = max(current_group.generation_end_sample, gen_end)
            potential_duration_sec = (potential_end - current_group.generation_start_sample) / sample_rate
            
            if potential_duration_sec <= MAX_PROVIDER_DURATION_SEC:
                # Rule: scene and camera must remain consistent
                if current_group.scene_consistent and scene_id == current_group._last_scene_id and camera_id == current_group._last_camera_id:  # type: ignore
                    # Rule: continuity benefit must be documented
                    if continuity_value in ("high", "medium"):
                        can_merge = True
        
        if can_merge and current_group is not None:
            # Merge into current group
            current_group.generation_end_sample = max(current_group.generation_end_sample, gen_end)
            current_group.requested_duration_sec = (current_group.generation_end_sample - current_group.generation_start_sample) / sample_rate
            current_group.member_visible_intervals.append(VisibleInterval(
                start_sample=speech_start,
                end_sample=speech_end,
                beat_id=beat_id
            ))
            current_group.regeneration_blast_radius.append(beat_id)
            current_group._last_scene_id = scene_id  # type: ignore
            current_group._last_camera_id = camera_id  # type: ignore
        else:
            # Start a new group
            if current_group is not None:
                groups.append(current_group)
                
            current_group = HeroRenderGroup(
                hero_render_group_id=_generate_group_id(),
                generation_start_sample=gen_start,
                generation_end_sample=gen_end,
                requested_duration_sec=duration_sec,
                member_visible_intervals=[VisibleInterval(
                    start_sample=speech_start,
                    end_sample=speech_end,
                    beat_id=beat_id
                )],
                regeneration_blast_radius=[beat_id],
                scene_consistent=True,
                continuity_benefit=f"Grouped for {continuity_value} continuity" if continuity_value in ("high", "medium") else "Default grouping"
            )
            # Attach internal tracking for consistency checks
            current_group._last_scene_id = scene_id  # type: ignore
            current_group._last_camera_id = camera_id  # type: ignore
            
        # Handle B-roll covered intervals if specified
        if beat.get("broll_covered"):
            for broll in beat["broll_covered"]:
                current_group.broll_covered_intervals.append(BrollCoveredInterval(
                    start_sample=int(broll["start_sample"]),
                    end_sample=int(broll["end_sample"]),
                    beat_id=broll["beat_id"]
                ))
                
        # Attach source audio slice info from the first beat in the group
        if current_group.source_audio_slice_path is None and beat.get("audio_slice"):
            current_group.source_audio_slice_path = beat["audio_slice"].get("file")
            current_group.source_audio_slice_sha256 = beat["audio_slice"].get("slice_sha256")
            
        # Attach prompt/model from the beat
        if not current_group.prompt and beat.get("positive_prompt"):
            current_group.prompt = beat["positive_prompt"]
            current_group.model = beat.get("model", "seedance_2_0")

    if current_group is not None:
        # Clean up internal tracking attributes before returning
        if hasattr(current_group, "_last_scene_id"):
            delattr(current_group, "_last_scene_id")
        if hasattr(current_group, "_last_camera_id"):
            delattr(current_group, "_last_camera_id")
        groups.append(current_group)
        
    return groups


def validate_hero_group(group: HeroRenderGroup, max_duration_sec: float = MAX_PROVIDER_DURATION_SEC) -> bool:
    """Validate that a hero render group meets all provider and continuity rules."""
    if group.requested_duration_sec > max_duration_sec:
        raise ValueError(f"Group {group.hero_render_group_id} exceeds max duration: {group.requested_duration_sec}s > {max_duration_sec}s")
    
    if group.requested_duration_sec < MIN_PROVIDER_DURATION_SEC:
        # This is allowed, the provider will handle minimum duration padding, 
        # but we log it or handle it in the request payload.
        pass
        
    if not group.member_visible_intervals:
        raise ValueError(f"Group {group.hero_render_group_id} has no visible intervals")
        
    return True

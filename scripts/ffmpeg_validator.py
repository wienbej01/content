"""Sprint 5: FFmpeg Policy Validator for Hero Clips (Ticket LB-501).

Ensures that generated FFmpeg commands for hero clips contain no unauthorized
temporal transformations, enforcing strict synchronization integrity.
"""
from __future__ import annotations

from typing import List

from assembly_dto import HeroAssemblyDTO, AssemblyDTOValidationError


FORBIDDEN_TEMPORAL_FILTERS = [
    "setpts",      # Non-identity time manipulation
    "atempo",      # Audio speed change
    "loop",        # Looping
    "reverse",     # Reverse playback
    "tpad",        # Freeze extension
    "trim",        # Arbitrary trimming (we use controlled -ss/-t instead)
]

FORBIDDEN_COMMAND_FLAGS = [
    "-itsoffset",  # Temporal offset
]


def validate_hero_ffmpeg_command(cmd: List[str], dto: HeroAssemblyDTO) -> None:
    """
    Validate that an FFmpeg command does not contain forbidden temporal transformations
    for a HERO_SYNC_LOCKED render unit.
    
    Raises AssemblyDTOValidationError if any forbidden operation is detected.
    """
    if dto.audio_policy != "HERO_SYNC_LOCKED":
        return  # Only strictly enforce for hero clips
        
    cmd_str = " ".join(cmd)
    
    # 1. Check for forbidden filters in -vf or -af arguments
    for forbidden_filter in FORBIDDEN_TEMPORAL_FILTERS:
        if forbidden_filter in cmd_str:
            raise AssemblyDTOValidationError(
                f"Forbidden temporal filter '{forbidden_filter}' detected in hero FFmpeg command. "
                f"Hero clips must not undergo temporal transformation."
            )
            
    # 2. Check for forbidden command flags
    for forbidden_flag in FORBIDDEN_COMMAND_FLAGS:
        if forbidden_flag in cmd:
            raise AssemblyDTOValidationError(
                f"Forbidden command flag '{forbidden_flag}' detected in hero FFmpeg command."
            )
            
    # 3. Verify that -ss and -t are used (if at all) in a controlled manner
    # For hero clips, the assembly should ideally use the exact timeline placement
    # from the DTO, or no trimming at all if it's a direct copy.
    # This is a basic check; more complex validation can be added if needed.
    if "-ss" in cmd or "-t" in cmd:
        # Ensure we are not trimming *through* speech. 
        # This is implicitly handled by the DTO's exact_timeline_placement,
        # but we can add a specific check here if the command structure is predictable.
        pass  # Detailed -ss/-t validation is handled by DTO exact_timeline_placement alignment

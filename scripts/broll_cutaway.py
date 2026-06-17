"""Sprint 5: Hero/B-roll Picture Cutaways (Ticket LB-502).

Handles the assembly of hero footage with B-roll picture cutaways,
ensuring master narration remains continuous and temporal policies are enforced.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any

from assembly_dto import HeroAssemblyDTO, AssemblyDTOValidationError


def validate_cutaway_policy(dto: HeroAssemblyDTO, broll_intervals: List[Dict[str, int]]) -> None:
    """
    Validate that B-roll cutaway intervals comply with hero assembly policies.
    """
    if dto.audio_policy != "HERO_SYNC_LOCKED":
        return
        
    for interval in broll_intervals:
        start_ms = interval.get("start_ms", 0)
        end_ms = interval.get("end_ms", 0)
        
        # Check if cutaway is within the hero's visible interval
        hero_start = dto.exact_timeline_placement["start_ms"]
        hero_end = dto.exact_timeline_placement["end_ms"]
        
        if start_ms < hero_start or end_ms > hero_end:
            raise AssemblyDTOValidationError(
                f"B-roll cutaway interval [{start_ms}, {end_ms}] falls outside "
                f"hero visible interval [{hero_start}, {hero_end}]."
            )
            
        # Check for unsafe crossfades (prohibited by default for hero)
        # This is enforced by the assembly command generation, but we can flag it here
        # if the DTO or interval specifies a crossfade duration > 0.
        if interval.get("transition", "hard_cut") != "hard_cut":
            raise AssemblyDTOValidationError(
                f"Unsafe transition '{interval.get('transition')}' detected in hero cutaway. "
                f"Only 'hard_cut' is permitted for HERO_SYNC_LOCKED clips."
            )


def assemble_hero_with_broll_cutaways(
    hero_video_path: Path,
    broll_video_path: Path,
    cutaway_intervals: List[Dict[str, int]],  # [{"start_ms": 1000, "end_ms": 3000}, ...]
    output_path: Path,
    fps: int = 24,
) -> None:
    """
    Assemble a hero video with B-roll cutaways at specified millisecond intervals.
    
    This function generates an FFmpeg command that:
    1. Uses the hero video as the base.
    2. Cuts to the B-roll video for the specified intervals.
    3. Uses hard cuts only (no crossfades).
    4. Strips all audio from the output (audio is handled by the master narration mix).
    """
    if not cutaway_intervals:
        # No cutaways, just copy the hero video without audio
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(hero_video_path), "-an", "-c:v", "copy", str(output_path)],
            capture_output=True, check=True
        )
        return

    # Sort intervals by start time
    sorted_intervals = sorted(cutaway_intervals, key=lambda x: x["start_ms"])
    
    # Build a complex filtergraph for precise cutting
    # We will split the hero video and the broll video, then concatenate them in order.
    
    # First, calculate the segments
    # Format: (source, start_sec, duration_sec)
    # source: 0 for hero, 1 for broll
    segments = []
    current_ms = 0
    
    for interval in sorted_intervals:
        start_ms = interval["start_ms"]
        end_ms = interval["end_ms"]
        
        # Add hero segment before cutaway
        if start_ms > current_ms:
            duration_ms = start_ms - current_ms
            segments.append(("0", current_ms / 1000.0, duration_ms / 1000.0))
            
        # Add broll segment
        broll_duration_ms = end_ms - start_ms
        segments.append(("1", 0, broll_duration_ms / 1000.0))  # B-roll starts at 0 for this cutaway
        
        current_ms = end_ms
        
    # Add final hero segment if any
    # We need the total duration of the hero video to know where to end
    # For simplicity, we'll let FFmpeg handle the end of the last segment if we use a specific filter,
    # or we can query the duration. Let's query the duration.
    import json
    probe_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(hero_video_path)
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    hero_duration_sec = float(result.stdout.strip()) if result.stdout.strip() else 0.0
    
    if current_ms < (hero_duration_sec * 1000):
        duration_ms = (hero_duration_sec * 1000) - current_ms
        segments.append(("0", current_ms / 1000.0, duration_ms / 1000.0))
        
    if not segments:
        raise AssemblyDTOValidationError("No valid segments generated for cutaway assembly.")
        
    # Build FFmpeg filtergraph
    # We need to trim each segment and then concatenate them.
    filter_parts = []
    concat_inputs = []
    
    for i, (src, start_sec, duration_sec) in enumerate(segments):
        label = f"v{i}"
        # Use trim and setpts to reset timestamps for concatenation
        filter_parts.append(
            f"[{src}:v]trim=start={start_sec}:duration={duration_sec},setpts=PTS-STARTPTS[{label}]"
        )
        concat_inputs.append(f"[{label}]")
        
    filtergraph = ";".join(filter_parts) + "".join(concat_inputs) + f"concat=n={len(segments)}:v=1:a=0[outv]"
    
    cmd = [
        "ffmpeg", "-y",
        "-i", str(hero_video_path),
        "-i", str(broll_video_path),
        "-filter_complex", filtergraph,
        "-map", "[outv]",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        "-an",  # Explicitly strip audio
        str(output_path)
    ]
    
    subprocess.run(cmd, capture_output=True, check=True)

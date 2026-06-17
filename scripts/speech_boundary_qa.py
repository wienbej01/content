"""Sprint 6: Speech-Boundary and Overlap Validation (Ticket LB-600).

Validates that source audio slices do not overlap, silence pads contain no speech,
and visible trims do not cut through active speech.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Dict, Any, Tuple


def _detect_speech_regions(path: Path, threshold_db: float = -40.0, min_duration: float = 0.1) -> List[Tuple[float, float]]:
    """
    Detect regions of active speech in an audio file.
    Returns a list of (start_sec, end_sec) tuples.
    """
    cmd = [
        "ffmpeg", "-y", "-i", str(path),
        "-af", f"silencedetect=noise={threshold_db}dB:d={min_duration}",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    stderr = result.stderr
    
    import re
    silence_starts = [float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", stderr)]
    silence_ends = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", stderr)]
    
    # Speech regions are the gaps between silence regions
    speech_regions = []
    
    # Get total duration to handle speech at the very end
    probe_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ]
    dur_result = subprocess.run(probe_cmd, capture_output=True, text=True)
    try:
        total_dur = float(dur_result.stdout.strip())
    except ValueError:
        total_dur = 0.0
        
    # If file starts with speech (no silence_start at 0)
    if not silence_starts or silence_starts[0] > 0.05:
        first_speech_end = silence_starts[0] if silence_starts else total_dur
        speech_regions.append((0.0, first_speech_end))
        
    # Speech between silence regions
    for i in range(len(silence_ends)):
        if i < len(silence_starts):
            start = silence_ends[i]
            end = silence_starts[i]
            if end - start > 0.05:  # Minimum speech duration
                speech_regions.append((start, end))
                
    # If file ends with speech
    if silence_ends and (not silence_starts or silence_ends[-1] > silence_starts[-1]):
        last_speech_start = silence_ends[-1]
        if total_dur - last_speech_start > 0.05:
            speech_regions.append((last_speech_start, total_dur))
            
    return speech_regions


def validate_speech_boundaries(
    slice_path: Path,
    assigned_start_sec: float,
    assigned_end_sec: float,
    visible_trim_end_sec: float,
) -> Dict[str, Any]:
    """
    Validate speech boundaries for a single hero slice.
    
    Returns a dict with pass/fail status and specific issues.
    """
    issues = []
    
    if not slice_path.exists():
        return {"status": "fail", "issues": ["Slice file does not exist"]}
        
    speech_regions = _detect_speech_regions(slice_path)
    
    # Check 1: Source speech begins and ends within assigned interval
    for start, end in speech_regions:
        # Allow small tolerance (0.05s) for detection inaccuracies
        if start < assigned_start_sec - 0.05:
            issues.append(f"Speech starts at {start:.2f}s, before assigned interval start {assigned_start_sec:.2f}s")
        if end > assigned_end_sec + 0.05:
            issues.append(f"Speech ends at {end:.2f}s, after assigned interval end {assigned_end_sec:.2f}s")
            
    # Check 2: No active speech truncated by visible trim
    # The visible trim should not cut through a speech region
    for start, end in speech_regions:
        if start < visible_trim_end_sec < end:
            issues.append(f"Visible trim at {visible_trim_end_sec:.2f}s cuts through active speech region ({start:.2f}s - {end:.2f}s)")
            
    # Check 3: No neighbouring words in silence pad
    # The silence pad is the area outside the assigned_start_sec to assigned_end_sec
    # We already check if speech is outside the assigned interval above, which covers this.
    
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "speech_regions": speech_regions
    }


def validate_no_slice_overlap(slices: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate that a list of source slices do not have overlapping speech regions.
    
    Each slice dict should contain:
    - "path": Path to the slice
    - "assigned_start_sec": float
    - "assigned_end_sec": float
    """
    issues = []
    
    # Collect all speech regions with their slice identifiers
    all_speech_regions = []
    for i, sl in enumerate(slices):
        path = sl.get("path")
        if not path or not Path(path).exists():
            continue
            
        regions = _detect_speech_regions(Path(path))
        for start, end in regions:
            all_speech_regions.append({
                "slice_idx": i,
                "start": start,
                "end": end,
                "assigned_start": sl.get("assigned_start_sec", 0),
                "assigned_end": sl.get("assigned_end_sec", 0)
            })
            
    # Check for overlaps
    for i in range(len(all_speech_regions)):
        for j in range(i + 1, len(all_speech_regions)):
            r1 = all_speech_regions[i]
            r2 = all_speech_regions[j]
            
            # Check if regions overlap
            if r1["start"] < r2["end"] and r2["start"] < r1["end"]:
                # They overlap. Check if they are from different slices
                if r1["slice_idx"] != r2["slice_idx"]:
                    issues.append(
                        f"Speech overlap detected between slice {r1['slice_idx']} "
                        f"({r1['start']:.2f}s-{r1['end']:.2f}s) and slice {r2['slice_idx']} "
                        f"({r2['start']:.2f}s-{r2['end']:.2f}s)"
                    )
                    
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues
    }

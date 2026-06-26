"""Audio test fixtures for S13-T004 audio continuity tests.

Generates synthetic audio/video files with specific characteristics:

- Clean continuous audio (no gaps, overlaps, or seam clicks)
- Audio with a silent gap between speech regions
- Audio with an overlapping segment timeline
- Audio with a transient click at a segment seam

Each ``create_*`` generator returns a ``(video_path, segments)`` tuple where
``segments`` is the timeline metadata (list of ``{"start": sec, "end": sec}``)
that ``evaluate_audio_continuity`` consumes for overlap + click checks. Fixtures
that exercise overlap/click checks carry the timeline that produces the defect;
fixtures that only exercise gap detection carry a single whole-audio segment.
"""
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Tuple

import numpy as np


SR = 16000  # Sample rate


def generate_silence(duration_sec: float, sr: int = SR) -> np.ndarray:
    """Generate silence (zeros)."""
    return np.zeros(int(duration_sec * sr), dtype=np.int16)


def generate_tone(frequency: float, duration_sec: float,
                  amplitude: float = 0.3, sr: int = SR) -> np.ndarray:
    """Generate a pure tone."""
    t = np.linspace(0, duration_sec, int(duration_sec * sr), endpoint=False)
    samples = amplitude * np.sin(2 * np.pi * frequency * t)
    return (samples * 32767).astype(np.int16)


def generate_speech_like(duration_sec: float, sr: int = SR) -> np.ndarray:
    """Generate speech-like audio (bandpass noise) with smooth end fades."""
    samples = np.random.randn(int(duration_sec * sr))

    from scipy import signal
    sos = signal.butter(4, [300, 3400], btype='band', fs=sr, output='sos')
    filtered = signal.sosfiltfilt(sos, samples)
    filtered = filtered / np.max(np.abs(filtered)) * 0.3

    # Fade only the very start/end so internal seams keep a real signal level.
    fade_duration = int(0.1 * sr)
    if len(filtered) > 2 * fade_duration:
        fade_in = np.linspace(0, 1, fade_duration)
        fade_out = np.linspace(1, 0, fade_duration)
        filtered[:fade_duration] *= fade_in
        filtered[-fade_duration:] *= fade_out

    return (filtered * 32767).astype(np.int16)


def create_wav_file(samples: np.ndarray, output_path: Path, sr: int = SR):
    """Create a 16-bit mono WAV file from int16 samples."""
    import wave
    wav = wave.open(str(output_path), 'w')
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(sr)
    wav.writeframes(samples.astype(np.int16).tobytes())
    wav.close()


def create_video_with_audio(audio_path: Path, output_path: Path, duration_sec: float):
    """Create a minimal MP4 (H.264 + AAC 128k) video with the given audio.

    AAC 128k matches the real assembly codec path — important because click
    detection must work against perceptually-coded audio, not just raw PCM.
    """
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s=320x240:d={duration_sec}",
        "-i", str(audio_path),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)


def _render(samples: np.ndarray, output_path: Path) -> Path:
    """Render samples to an MP4 file whose duration matches the samples."""
    duration = len(samples) / SR + 0.1
    wav_path = output_path.with_suffix(".wav")
    create_wav_file(samples, wav_path)
    create_video_with_audio(wav_path, output_path, duration)
    wav_path.unlink(missing_ok=True)
    return output_path


# ---------------------------------------------------------------------------
# Fixture generators: each returns (video_path, segments)
# ---------------------------------------------------------------------------
def create_clean_audio_video(output_path: Path,
                             duration_sec: float = 5.0
                             ) -> Tuple[Path, List[Dict[str, Any]]]:
    """Clean continuous audio. Single segment -> no seam, no overlap, no gap."""
    speech = generate_speech_like(duration_sec)
    video = _render(speech, output_path)
    segments = [{"start": 0.0, "end": duration_sec}]
    return video, segments


def create_audio_with_gap(output_path: Path,
                          gap_duration_ms: float = 500.0
                          ) -> Tuple[Path, List[Dict[str, Any]]]:
    """Two speech segments separated by an absolute-silence gap.

    Carried as a single timeline segment so only gap detection (raw audio)
    runs; the gap is detected from the waveform silence between speech regions.
    """
    segment_duration = 2.0
    gap_sec = gap_duration_ms / 1000.0

    speech1 = generate_speech_like(segment_duration)
    gap = generate_silence(gap_sec)
    speech2 = generate_speech_like(segment_duration)
    combined = np.concatenate([speech1, gap, speech2])

    video = _render(combined, output_path)
    total = len(combined) / SR
    segments = [{"start": 0.0, "end": total}]
    return video, segments


def create_timeline_with_overlap(output_path: Path,
                                 overlap_ms: float = 200.0
                                 ) -> Tuple[Path, List[Dict[str, Any]]]:
    """A timeline whose second segment overlaps the first by ``overlap_ms``.

    The audio is continuous speech-like content (any valid audio); the DEFECT
    is in the segment timeline metadata, which is the honest source of overlap
    truth (two mixed voices cannot be separated by energy detection).
    """
    speech = generate_speech_like(4.0)
    video = _render(speech, output_path)
    overlap_sec = overlap_ms / 1000.0
    # Segment 1: 0.0–2.0s; Segment 2 starts at 2.0-overlap (overlaps segment 1).
    segments = [
        {"start": 0.0, "end": 2.0},
        {"start": 2.0 - overlap_sec, "end": 4.0},
    ]
    return video, segments


def create_audio_with_seam_click(output_path: Path,
                                 impulse_amplitude: float = 32000.0
                                 ) -> Tuple[Path, List[Dict[str, Any]]]:
    """Two speech segments joined at a seam with a full-scale impulse click.

    The audio has a deliberate transient at the seam (2.0s); the timeline has
    one internal seam so the click detector measures it there.
    """
    seg_a = generate_speech_like(2.0)
    seg_b = generate_speech_like(2.0)
    seam = len(seg_a)
    combined = np.concatenate([seg_a, seg_b]).astype(np.float64)
    # Full-scale impulse exactly at the seam (survives AAC; see evidence notes).
    combined[seam] += impulse_amplitude
    combined = np.clip(combined, -32768, 32767).astype(np.int16)

    video = _render(combined, output_path)
    segments = [
        {"start": 0.0, "end": 2.0},
        {"start": 2.0, "end": 4.0},
    ]
    return video, segments


def create_silent_video(output_path: Path,
                        duration_sec: float = 3.0
                        ) -> Tuple[Path, List[Dict[str, Any]]]:
    """Completely silent video (zeros)."""
    silence = generate_silence(duration_sec)
    video = _render(silence, output_path)
    segments = [{"start": 0.0, "end": duration_sec}]
    return video, segments

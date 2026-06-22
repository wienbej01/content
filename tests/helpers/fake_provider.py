"""ENG-0901: Fake provider adapter for tests.

Generates tiny synthetic video/audio files via FFmpeg.
Never calls external APIs. Supports duration control, dimensions,
lipsync placeholder, and an optional visible-text failure mode.

Usage:
    provider = FakeProvider()
    path = provider.generate_video(duration_sec=4)
    path = provider.generate_lipsync(duration_sec=5, fps=24)
    path = provider.generate_graphic(width=1920, height=1080)
    path = provider.generate_with_text("Hello World", duration_sec=3)
"""
import hashlib
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


class FakeProvider:
    """Test-only fake media provider that produces real synthetic media files.

    All generated files are deterministic (same arguments → same SHA-256).
    No external API calls are made. All files are valid FFmpeg containers.

    Attributes:
        output_root: directory where generated files are stored.
        created_files: list of Path objects created by this instance.
    """

    def __init__(self, output_root: Optional[Path] = None):
        self.output_root = Path(output_root or tempfile.mkdtemp())
        self.created_files: list[Path] = []
        self.output_root.mkdir(parents=True, exist_ok=True)

    def generate_video(
        self,
        duration_sec: float = 5.0,
        width: int = 1920,
        height: int = 1080,
        fps: int = 24,
        with_audio: bool = True,
        label: str = "fake_video",
    ) -> Path:
        """Generate a synthetic video file with optional audio.

        The video contains a moving test pattern (testsrc2) and optional
        sine-wave audio. Returns path to the generated .mp4 file.
        """
        cache_key = hashlib.sha256(
            f"{label}_{duration_sec}_{width}_{height}_{fps}_{with_audio}".encode()
        ).hexdigest()[:16]
        out_path = self.output_root / f"{label}_{cache_key}.mp4"

        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i",
            f"testsrc2=size={width}x{height}:duration={duration_sec}:rate={fps}",
        ]
        if with_audio:
            cmd += [
                "-f", "lavfi", "-i",
                f"sine=frequency=440:duration={duration_sec}",
                "-shortest",
            ]
        else:
            cmd += ["-an"]
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "30", str(out_path)]

        subprocess.run(cmd, capture_output=True, check=True)
        self.created_files.append(out_path)
        return out_path

    def generate_lipsync(
        self,
        duration_sec: float = 5.0,
        width: int = 1920,
        height: int = 1080,
        fps: int = 24,
        label: str = "fake_lipsync",
    ) -> Path:
        """Generate a synthetic lipsync placeholder with audio track.

        Returns path to the generated .mp4 file.
        """
        return self.generate_video(
            duration_sec=duration_sec,
            width=width,
            height=height,
            fps=fps,
            with_audio=True,
            label=label,
        )

    def generate_graphic(
        self,
        width: int = 1920,
        height: int = 1080,
        label: str = "fake_graphic",
    ) -> Path:
        """Generate a static graphic (PNG) for local_graphic testing."""
        cache_key = hashlib.sha256(f"{label}_{width}_{height}".encode()).hexdigest()[:16]
        out_path = self.output_root / f"{label}_{cache_key}.png"

        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i",
            f"color=c=blue:size={width}x{height}:duration=0.1",
            "-vframes", "1",
            str(out_path),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        self.created_files.append(out_path)
        return out_path

    def generate_with_visible_text(
        self,
        text: str = "VISIBLE TEXT FAILURE",
        duration_sec: float = 5.0,
        width: int = 1920,
        height: int = 1080,
        fps: int = 24,
        label: str = "fake_with_text",
    ) -> Path:
        """Generate a video with visible text rendered into frames.

        This simulates the 'generated text becomes garbled' failure mode
        where exact text leaks into provider-generated output.
        """
        cache_key = hashlib.sha256(
            f"{label}_{text}_{duration_sec}_{width}_{height}_{fps}".encode()
        ).hexdigest()[:16]
        out_path = self.output_root / f"{label}_{cache_key}.mp4"

        escaped_text = text.replace(":", "\\:").replace("'", "\\\\'")
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i",
            f"color=c=black:size={width}x{height}:duration={duration_sec}:rate={fps}",
            "-vf", f"drawtext=text='{escaped_text}':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_path),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        self.created_files.append(out_path)
        return out_path

    def sha256(self, path: Path) -> str:
        """Return the SHA-256 hex digest of a generated file."""
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def cleanup(self):
        """Remove all generated files."""
        for p in self.created_files:
            if p.exists():
                p.unlink()

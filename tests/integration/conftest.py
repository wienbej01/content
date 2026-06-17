"""Integration-test fixtures — deterministic tone-marked master audio builder."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
HAS_FFMPEG = FFMPEG is not None and FFPROBE is not None


def _probe_duration(path):
    result = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


@pytest.fixture
def tone_marked_master(tmp_path):
    """Deterministic audio fixture: adjacent tone regions for contamination detection.

    Structure:
      0.0 – 2.0s  sine 440 Hz  (beat 1 — "speech" region)
      2.0 – 4.0s  sine 880 Hz  (beat 2 — adjacent "speech", no gap)
      4.0 – 5.0s  silence      (trailing gap)

    Beat 1 and beat 2 are deliberately adjacent (no silence gap) so that
    the slicer's master-range padding bug reaches into the 440 Hz region
    when extracting beat 2's slice.  With a 2s speech span needing 2s padding
    (leading=1s), the extraction window widens to [1.0, 5.0], copying 440 Hz
    audio from 1.0–2.0s instead of generating true silence.

    Returns the Path to the generated master file.
    """
    if not HAS_FFMPEG:
        pytest.skip("ffmpeg not available")

    master = tmp_path / "tone_marked_master.mp3"

    subprocess.run([
        FFMPEG, "-y",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2:sample_rate=44100",
        "-f", "lavfi", "-i", "sine=frequency=880:duration=2:sample_rate=44100",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo:duration=1",
        "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1",
        "-q:a", "9", str(master),
    ], capture_output=True, check=True)

    return master

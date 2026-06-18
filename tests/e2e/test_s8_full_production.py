"""Sprint 8 — Full local 45-second E2E production (S8-T01 / S8-T02).

Drives a real production through the entire DB-native stage graph via
run_production() in YT_TEST_MODE=1 and asserts a valid 16:9 deliverable.

No paid calls: research/script/storyboard are authored deterministically (the LLM
stages are marked done and skipped), the master narration is a deterministic
ffmpeg fixture (TTS refuses paid calls in test mode — see test_s8_tts_paid_guard),
and YT_TEST_MODE substitutes FakeProviderAdapter (real moving ffmpeg media) for
media generation.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "scripts"))

from s8_helpers import build_production, run_to_completion, PROJECTS  # noqa: E402


@pytest.mark.slow
def test_full_45s_production_e2e(monkeypatch):
    monkeypatch.setenv("YT_TEST_MODE", "1")
    pid, slug, _ = build_production("s8_e2e")
    assert run_to_completion(pid), "production did not reach 'completed'"

    outputs = sorted(PROJECTS.glob(f"{slug}/*_16x9.mp4"))
    assert outputs, f"no 16x9 deliverable produced in {PROJECTS / slug}"
    out = outputs[0]

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=width,height,codec_type",
         "-of", "json", str(out)], capture_output=True, text=True, check=True)
    info = json.loads(probe.stdout)
    vs = [s for s in info["streams"] if s.get("codec_type") == "video"][0]
    assert (vs["width"], vs["height"]) == (1920, 1080), \
        f"expected 1920x1080, got {vs['width']}x{vs['height']}"
    dur = float(info["format"]["duration"])
    assert 30.0 <= dur <= 60.0, f"deliverable duration {dur:.1f}s outside 30-60s"
    assert any(s.get("codec_type") == "audio" for s in info["streams"]), "no audio stream"

    # S8-T05 criterion: no frozen span > 1.5s.
    fd = subprocess.run(
        ["ffmpeg", "-i", str(out), "-vf",
         "freezedetect=noise=0.001:duration=1.5", "-f", "null", "-"],
        capture_output=True, text=True)
    assert "lavfi.freezedetect.freeze_start" not in fd.stderr, \
        "deliverable contains a frozen span > 1.5s"

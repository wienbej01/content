"""tests/test_pipeline_local_e2e.py — End-to-end local smoke test (TKT-14).

Exercises the full pipeline path from reconciliation through final QA
using tiny FFmpeg-generated fixtures. No paid API calls or internet needed.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _run(script, *args):
    """Run a pipeline script, return CompletedProcess."""
    cmd = [sys.executable, str(SCRIPTS / script)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))


def _ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y"] + list(args), capture_output=True, check=True)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture()
def pipeline_project(tmp_path):
    """Build a minimal valid project with tiny FFmpeg fixtures."""
    proj = tmp_path / "proj"
    proj.mkdir()

    # 1. Hero lipsync clip: 3s video + baked audio (testsrc avoids blank/frozen detection)
    hero = proj / "hero.mp4"
    _ffmpeg("-f", "lavfi", "-i", "testsrc=duration=3:size=1280x720:rate=24",
            "-f", "lavfi", "-i", "sine=440:d=3",
            "-c:v", "libx264", "-c:a", "aac", str(hero))

    # 2. B-roll clip: 3s (testsrc to avoid frozen/blank detection)
    broll = proj / "broll.mp4"
    _ffmpeg("-f", "lavfi", "-i", "testsrc=duration=3:size=1280x720:rate=24",
            "-an", "-c:v", "libx264", str(broll))

    # 3. Narration (continuous): 6s
    narr_dir = proj / "narration"
    narr_dir.mkdir()
    narration = narr_dir / "continuous.mp3"
    _ffmpeg("-f", "lavfi", "-i", "sine=440:d=6", "-c:a", "mp3", str(narration))

    # 4. Music bed: 6s
    music = proj / "music.mp3"
    _ffmpeg("-f", "lavfi", "-i", "sine=220:d=6", "-c:a", "mp3", str(music))

    # 5. Beat timing map: hero 0-3s, broll 3-6s = 6s total
    timing = {
        "total_duration": 6.0,
        "beat_count": 2,
        "beats": [
            {"beat_id": "B001", "start": 0.0, "end": 3.0},
            {"beat_id": "B002", "start": 3.0, "end": 6.0},
        ],
    }
    (narr_dir / "beat_timing_map.json").write_text(json.dumps(timing))

    # 6. Media plan
    plan = {
        "project_id": "e2e_test",
        "beats": [
            {
                "beat_id": "B001",
                "segment_id": "001_hook",
                "output_path": str(hero),
                "asset_type": "generated_video",
                "audio_policy": "keep_lipsync",
                "lipsync_required": True,
                "audio_slice": {
                    "speech_len_sec": 3.0,
                    "padded_len_sec": 3.0,
                    "slice_sha256": _sha256(narration),
                    "parent_mp3_sha256": _sha256(narration),
                    "file": str(narration),
                },
                "narration_text": "test hook words here",
            },
            {
                "beat_id": "B002",
                "segment_id": "002_body",
                "output_path": str(broll),
                "asset_type": "generated_video",
                "audio_policy": "strip",
                "narration_text": "three seconds of body content here today",
            },
        ],
    }
    (proj / "media_plan.json").write_text(json.dumps(plan))

    # 7. Fingerprint for hero and broll
    sys.path.insert(0, str(SCRIPTS))
    from artifact_fingerprint import write_fingerprint
    write_fingerprint(str(hero), "test", "1.0", project_id="e2e_test")
    write_fingerprint(str(broll), "test", "1.0", project_id="e2e_test")

    # 8. State file: use format that doesn't require music (avoids needing brand/music/)
    (proj / "state.json").write_text(json.dumps({"format": "teaser"}))

    return proj

def test_valid_pipeline_passes(pipeline_project):
    """Valid fixtures pass all gates: reconcile → qa_media → build_manifest → assemble → qa_final."""
    proj = pipeline_project

    # Reconcile
    r = _run("reconcile_duration.py", str(proj))
    assert r.returncode == 0, f"reconcile failed:\n{r.stdout}\n{r.stderr}"

    # QA media — needs a script-like JSON with beats
    plan_path = proj / "media_plan.json"
    r = _run("qa_media.py", str(plan_path), "--project-id", "e2e_test")
    assert r.returncode == 0, f"qa_media failed:\n{r.stdout}\n{r.stderr}"

    # Build manifest
    r = _run("build_manifest.py", str(proj))
    assert r.returncode == 0, f"build_manifest failed:\n{r.stdout}\n{r.stderr}"

    manifest_path = proj / "manifest.json"
    assert manifest_path.exists()

    # Assemble (16x9 only for speed; no gates required)
    r = _run("assemble.py", str(manifest_path), "--formats", "16x9", "--no-music")
    assert r.returncode == 0, f"assemble failed:\n{r.stdout}\n{r.stderr}"

    # Find the output MP4
    outputs = list(proj.glob("*_16x9.mp4"))
    assert outputs, "No 16x9 output MP4 found"
    final = outputs[0]

    # Final QA
    r = _run("qa_final.py", str(final))
    assert r.returncode == 0, f"qa_final failed:\n{r.stdout}\n{r.stderr}"


# ---------- Test 2: Stream mismatch fails final QA ----------

def test_stream_mismatch_fails_final_qa(tmp_path):
    """MP4 with 3s video + 8s audio fails qa_final with LENGTH_MISMATCH or TERMINAL_FREEZE."""
    mp4 = tmp_path / "mismatch.mp4"
    v = tmp_path / "v.mp4"
    a = tmp_path / "a.mp3"
    _ffmpeg("-f", "lavfi", "-i", "color=c=black:s=320x240:r=24:d=3",
            "-c:v", "libx264", "-t", "3", str(v))
    _ffmpeg("-f", "lavfi", "-i", "sine=440:d=8", "-c:a", "mp3", "-t", "8", str(a))
    _ffmpeg("-i", str(v), "-i", str(a), "-c:v", "copy", "-c:a", "copy", str(mp4))

    r = _run("qa_final.py", str(mp4))
    assert r.returncode == 1
    assert "TERMINAL_FREEZE" in r.stdout or "LENGTH_MISMATCH" in r.stdout


# ---------- Test 3: Missing segment fails reconciliation ----------

def test_missing_segment_fails_reconciliation(tmp_path):
    """Timing map requires 10s for beat but clip is only 2s → reconcile exits 1."""
    proj = tmp_path / "proj"
    proj.mkdir()
    narr = proj / "narration"
    narr.mkdir()

    clip = proj / "short.mp4"
    _ffmpeg("-f", "lavfi", "-i", "color=c=red:s=320x240:r=24:d=2",
            "-c:v", "libx264", str(clip))

    timing = {
        "total_duration": 10.0, "beat_count": 1,
        "beats": [{"beat_id": "B001", "start": 0.0, "end": 10.0}],
    }
    (narr / "beat_timing_map.json").write_text(json.dumps(timing))
    plan = {"beats": [{"beat_id": "B001", "output_path": str(clip), "asset_type": "generated_video"}]}
    (proj / "media_plan.json").write_text(json.dumps(plan))

    r = _run("reconcile_duration.py", str(proj))
    assert r.returncode == 1
    assert "B001" in r.stdout
    assert "deficit" in r.stdout.lower() or "INSUFFICIENT" in r.stdout


# ---------- Test 4: Frozen clip detected ----------

def test_frozen_clip_detected(tmp_path):
    """A static-color (frozen) clip triggers FREEZE detection in qa_final."""
    frozen = tmp_path / "frozen.mp4"
    # 5s single-color video + audio so qa_final can compare durations
    _ffmpeg("-f", "lavfi", "-i", "color=c=red:s=320x240:r=24:d=5",
            "-f", "lavfi", "-i", "sine=440:d=5",
            "-c:v", "libx264", "-c:a", "aac", str(frozen))

    r = _run("qa_final.py", str(frozen))
    # Frozen detection uses freezedetect; a solid-color clip is frozen
    assert r.returncode == 1, f"Expected frozen detection to fail, got:\n{r.stdout}"
    assert "FREEZE" in r.stdout


# ---------- Test 5: Stale hash fails QA ----------

def test_stale_hash_fails_qa(tmp_path):
    """Overwriting a clip after fingerprinting triggers STALE_ARTIFACT in qa_media."""
    proj = tmp_path / "proj"
    proj.mkdir()
    narr = proj / "narration"
    narr.mkdir()

    clip = proj / "clip.mp4"
    _ffmpeg("-f", "lavfi", "-i", "color=c=blue:s=320x240:r=24:d=3",
            "-an", "-c:v", "libx264", str(clip))

    # Fingerprint it
    sys.path.insert(0, str(SCRIPTS))
    from artifact_fingerprint import write_fingerprint
    write_fingerprint(str(clip), "test", "1.0", project_id="stale_test")

    # Overwrite the clip (different content)
    _ffmpeg("-f", "lavfi", "-i", "color=c=yellow:s=320x240:r=24:d=3",
            "-an", "-c:v", "libx264", str(clip))

    # Create a minimal script JSON for qa_media
    script = {
        "project_id": "stale_test",
        "beats": [{
            "beat_id": "B001",
            "segment_id": "001",
            "output_path": str(clip),
            "audio_mode": "generated_tts",
            "asset_type": "generated_video",
        }],
    }
    script_path = proj / "script.json"
    script_path.write_text(json.dumps(script))

    # Timing map so qa_media doesn't complain
    timing = {"total_duration": 3.0, "beat_count": 1,
              "beats": [{"beat_id": "B001", "start": 0.0, "end": 3.0}]}
    (narr / "beat_timing_map.json").write_text(json.dumps(timing))

    r = _run("qa_media.py", str(script_path), "--project-id", "stale_test")
    assert r.returncode == 1, f"Expected stale artifact fail:\n{r.stdout}\n{r.stderr}"
    assert "STALE_ARTIFACT" in r.stdout


# ---------- Test 6: Missing music fails assembly ----------

def test_missing_required_music_fails_assembly(tmp_path):
    """Manifest with music.enabled=true but wrong path → assembly exits nonzero."""
    proj = tmp_path / "proj"
    proj.mkdir()

    clip = proj / "clip.mp4"
    _ffmpeg("-f", "lavfi", "-i", "color=c=blue:s=320x240:r=24:d=3",
            "-f", "lavfi", "-i", "sine=440:d=3",
            "-c:v", "libx264", "-c:a", "aac", str(clip))

    manifest = {
        "id": "music_test",
        "segments": [{"id": "seg1", "media": "clip.mp4", "words": 10}],
        "music": {"enabled": True, "path": "nonexistent/music.mp3"},
        "pacing": {"reference": 0, "baseline_speed": 1.0},
        "render": {"fps": 24, "crf": 23},
        "brand": {},
        "output": {"directory": "."},
        "format": "short",
    }
    manifest_path = proj / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    r = _run("assemble.py", str(manifest_path), "--formats", "16x9")
    assert r.returncode != 0, f"Expected failure for missing music:\n{r.stdout}\n{r.stderr}"
    assert "not found" in r.stderr.lower() or "music" in r.stderr.lower()


# ---------- Test 7: Missing required overlay fails assembly ----------

def test_missing_required_overlay_fails_assembly(tmp_path):
    """Segment with overlay.required=true but no PNG → assembly exits nonzero."""
    proj = tmp_path / "proj"
    proj.mkdir()

    clip = proj / "clip.mp4"
    _ffmpeg("-f", "lavfi", "-i", "color=c=blue:s=320x240:r=24:d=3",
            "-f", "lavfi", "-i", "sine=440:d=3",
            "-c:v", "libx264", "-c:a", "aac", str(clip))

    manifest = {
        "id": "overlay_test",
        "segments": [{
            "id": "seg1",
            "media": "clip.mp4",
            "words": 10,
            "overlay": {"required": True},
        }],
        "music": {"enabled": False},
        "pacing": {"reference": 0, "baseline_speed": 1.0},
        "render": {"fps": 24, "crf": 23},
        "brand": {},
        "output": {"directory": "."},
    }
    manifest_path = proj / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    r = _run("assemble.py", str(manifest_path), "--formats", "16x9")
    assert r.returncode != 0, f"Expected failure for missing overlay:\n{r.stdout}\n{r.stderr}"
    assert "overlay" in r.stderr.lower() or "not found" in r.stderr.lower()

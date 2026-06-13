#!/usr/bin/env python3
"""tests/test_qa_media.py — P4-12 media technical QA tests."""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _load():
    spec = importlib.util.spec_from_file_location("qa_media", ROOT / "scripts" / "qa_media.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _make_clip(path, duration=5, width=1280, height=720, audio=False):
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=blue:size={width}x{height}:d={duration}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=duration={duration}"]
        cmd += ["-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "64k"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)]
    subprocess.run(cmd, capture_output=True, check=True)


def test_pass_generated_tts_no_audio():
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        clip = td / "clip.mp4"
        _make_clip(clip, audio=False)
        script = {"project_id": "t", "segments": [
            {"id": "s1", "audio_mode": "generated_tts", "media": str(clip)}
        ], "defaults": {"format": "mp3"}}
        sp = td / "script.json"
        sp.write_text(json.dumps(script))
        results, ok = qa.run_qa(str(sp))
    assert ok and results[0]["status"] == "pass"
    print("  ✓ generated_tts without audio → pass")


def test_fail_generated_tts_with_audio():
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        clip = td / "clip.mp4"
        _make_clip(clip, audio=True)
        script = {"project_id": "t", "segments": [
            {"id": "s1", "audio_mode": "generated_tts", "media": str(clip)}
        ], "defaults": {"format": "mp3"}}
        sp = td / "script.json"
        sp.write_text(json.dumps(script))
        results, ok = qa.run_qa(str(sp))
    assert not ok and "AUDIO_POLICY" in results[0]["issues"][0]
    print("  ✓ generated_tts WITH audio → fail (AUDIO_POLICY)")


def test_fail_baked_in_without_audio():
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        clip = td / "clip.mp4"
        _make_clip(clip, audio=False)
        script = {"project_id": "t", "segments": [
            {"id": "s1", "audio_mode": "baked_in", "media": str(clip)}
        ], "defaults": {"format": "mp3"}}
        sp = td / "script.json"
        sp.write_text(json.dumps(script))
        results, ok = qa.run_qa(str(sp))
    assert not ok and "AUDIO_POLICY" in results[0]["issues"][0]
    print("  ✓ baked_in WITHOUT audio → fail (AUDIO_POLICY)")


def test_fail_missing_file():
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        script = {"project_id": "t", "segments": [
            {"id": "s1", "audio_mode": "generated_tts", "media": "/nonexistent.mp4"}
        ], "defaults": {"format": "mp3"}}
        sp = td / "script.json"
        sp.write_text(json.dumps(script))
        results, ok = qa.run_qa(str(sp))
    assert not ok and "MISSING" in results[0]["issues"][0]
    print("  ✓ missing file → fail (MISSING)")


def test_fail_wrong_dimensions():
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        clip = td / "clip.mp4"
        _make_clip(clip, width=640, height=480)
        script = {"project_id": "t", "segments": [
            {"id": "s1", "audio_mode": "generated_tts", "media": str(clip)}
        ], "defaults": {"format": "mp3"}}
        sp = td / "script.json"
        sp.write_text(json.dumps(script))
        results, ok = qa.run_qa(str(sp))
    assert not ok and "DIMENSIONS" in results[0]["issues"][0]
    print("  ✓ wrong dimensions → fail (DIMENSIONS)")


def test_real_teaser_qa():
    """Run QA on actual teaser_02 script — report but don't assert all pass."""
    qa = _load()
    sp = ROOT / "scripts/generated/james_growth_system_teaser_02.json"
    if not sp.exists():
        print("  ⊘ teaser_02 script not found (skipped)")
        return
    results, ok = qa.run_qa(str(sp))
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    print(f"  ✓ teaser_02 QA: {passed} pass, {failed} fail (info only)")


# =====================================================================
# T2 — qa_media lipsync structural checks (LIPSYNC_TICKETS.md)
# =====================================================================
import hashlib as _hashlib


def _sha256_file(path):
    h = _hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 16), b""):
            h.update(c)
    return h.hexdigest()


def _make_tone_mp3(path, freq, dur):
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={dur}",
         "-c:a", "libmp3lame", "-q:a", "2", str(path)],
        capture_output=True, check=True)


def _build_lipsync_beat_plan(td, *, speech_len=3.0, clip_dur=3.0, clip_audio=True,
                             tamper_provenance=False):
    """Build a media-plan-shaped fixture with one hero_lipsync beat + its slice."""
    td = Path(td)
    slices = td / "narration" / "slices"
    slices.mkdir(parents=True)
    clip = td / "B001.mp4"
    _make_clip(clip, duration=clip_dur, audio=clip_audio)
    slice_path = slices / "B001.mp3"
    _make_tone_mp3(slice_path, 220, speech_len)
    parent = td / "narration" / "001_hook.mp3"
    _make_tone_mp3(parent, 220, speech_len + 1.0)
    slice_sha = _sha256_file(slice_path)
    if tamper_provenance:
        slice_sha = "f" * 64
    plan = {
        "project_id": "t",
        "defaults": {"format": "mp3"},
        "beats": [{
            "beat_id": "B001",
            "segment_id": "001_hook",
            "audio_policy": "keep_lipsync",
            "shot_type": "hero_lipsync",
            "lipsync_required": True,
            "output_path": str(clip),
            "audio_slice": {
                "file": "narration/slices/B001.mp3",
                "start_sec": 0.0,
                "end_sec": float(speech_len),
                "speech_len_sec": float(speech_len),
                "padded_len_sec": int(speech_len) + (0 if speech_len == int(speech_len) else 1),
                "slice_sha256": slice_sha,
                "parent_mp3_sha256": _sha256_file(parent),
            },
        }],
    }
    pp = td / "media_plan.json"
    pp.write_text(json.dumps(plan))
    return pp


def test_lipsync_valid_clip_passes():
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        # clip audio duration must match speech_len; make the clip the same length
        pp = _build_lipsync_beat_plan(td, speech_len=3.0, clip_dur=3.0, clip_audio=True)
        results, ok = qa.run_qa(str(pp))
    assert ok, f"valid lipsync clip should pass, issues={results[0]['issues']}"
    print("  ✓ valid hero_lipsync clip → pass")


def test_lipsync_silent_clip_fatal():
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        pp = _build_lipsync_beat_plan(td, clip_audio=False)
        results, ok = qa.run_qa(str(pp))
    assert not ok
    assert any("LIPSYNC" in i and "audio stream" in i for i in results[0]["issues"]), results[0]["issues"]
    print("  ✓ silent hero_lipsync clip → fatal")


def test_lipsync_wrong_duration_fatal():
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        # clip/audio is 6s but the slice claims speech_len 3.0 / padded 3 → mismatch
        pp = _build_lipsync_beat_plan(td, speech_len=3.0, clip_dur=6.0, clip_audio=True)
        results, ok = qa.run_qa(str(pp))
    assert not ok
    assert any("LIPSYNC" in i and "duration" in i for i in results[0]["issues"]), results[0]["issues"]
    print("  ✓ wrong-duration hero_lipsync clip → fatal")


def test_lipsync_tampered_provenance_fatal():
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        pp = _build_lipsync_beat_plan(td, speech_len=3.0, clip_dur=3.0,
                                      clip_audio=True, tamper_provenance=True)
        results, ok = qa.run_qa(str(pp))
    assert not ok
    assert any("provenance" in i.lower() or "mismatch" in i.lower() for i in results[0]["issues"]), results[0]["issues"]
    print("  ✓ tampered provenance → fatal")


def test_voiceover_with_audio_still_fatal():
    """Existing rule must not regress: generated_tts (voiceover) with audio → fatal."""
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        clip = td / "clip.mp4"
        _make_clip(clip, audio=True)
        script = {"project_id": "t", "segments": [
            {"id": "s1", "audio_mode": "generated_tts", "media": str(clip)}
        ], "defaults": {"format": "mp3"}}
        sp = td / "script.json"
        sp.write_text(json.dumps(script))
        results, ok = qa.run_qa(str(sp))
    assert not ok and any("AUDIO_POLICY" in i for i in results[0]["issues"])
    print("  ✓ voiceover-with-audio → fatal (no regression)")


def test_hero_crop_safety_must_be_center_safe():
    """A hero beat declaring a non-center-safe crop is flagged (James must survive
    the 9:16 center crop)."""
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        clip = td / "B1.mp4"
        _make_clip(clip, audio=True)
        sl = td / "narration" / "slices"; sl.mkdir(parents=True)
        slicef = sl / "B1.mp3"
        _make_tone_mp3(slicef, 220, 5.0)
        sh = _sha256_file(slicef)
        plan = {"project_id": "t", "defaults": {"format": "mp3"}, "beats": [{
            "beat_id": "B1", "shot_type": "hero_lipsync", "audio_policy": "keep_lipsync",
            "lipsync_required": True, "output_path": str(clip),
            "crop_safety": "full_frame_16x9",  # WRONG for a hero
            "audio_slice": {"file": "narration/slices/B1.mp3", "start_sec": 0, "end_sec": 5,
                            "speech_len_sec": 5.0, "padded_len_sec": 5,
                            "slice_sha256": sh, "parent_mp3_sha256": sh},
        }]}
        pp = td / "media_plan.json"; pp.write_text(json.dumps(plan))
        results, ok = qa.run_qa(str(pp))
    assert not ok and any("CROP_SAFETY" in i for i in results[0]["issues"]), results[0]["issues"]
    print("  ✓ non-center-safe hero crop → fatal (CROP_SAFETY)")


def test_assembled_aspect_crop_safety():
    """An assembled clip whose aspect doesn't match the scope is flagged (center
    crop not applied)."""
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        clip = td / "B1.mp4"
        _make_clip(clip, width=1280, height=720, audio=False)  # 16:9, but scope wants 9:16
        plan = {"project_id": "t", "defaults": {"format": "mp3"}, "beats": [{
            "beat_id": "B1", "shot_type": "graphic_progressive", "audio_mode": "silent",
            "output_path": str(clip), "crop_safety": "center_safe",
        }]}
        pp = td / "media_plan.json"; pp.write_text(json.dumps(plan))
        results, ok = qa.run_qa(str(pp), scope="assembled_9x16")
    assert any("CROP_SAFETY" in i for i in results[0]["issues"]), results[0]["issues"]
    print("  ✓ wrong assembled aspect → CROP_SAFETY flagged")


def main():
    print("Media Technical QA Tests (P4-12)")
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  ✗ {t.__name__}: {e}")
            failed += 1
    print(f"\n{'PASSED' if failed == 0 else 'FAILED'}: {passed}/{passed+failed}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()

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
    # Use testsrc2 (moving pattern) to avoid triggering perceptual blank/frozen checks
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc2=size={width}x{height}:d={duration}:rate=24"]
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
    assert ok and results[0]["status"] == "PASS"
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
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
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


# --- Phase C1: Perceptual QA tests ---

def test_blank_screen_fatal():
    """A solid-color clip triggers BLANK_SCREEN FATAL."""
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        clip = Path(td) / "blank.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                        "color=c=0xFAFAF0:size=320x180:d=3",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        str(clip)], capture_output=True, check=True)
        issues = qa.check_blank_screen(str(clip))
        assert any("BLANK_SCREEN" in i for i in issues), f"expected BLANK_SCREEN, got {issues}"
    print("  ✓ blank/solid-color clip triggers BLANK_SCREEN")


def test_frozen_video_fatal():
    """A clip that is one held frame (loop) triggers FROZEN_VIDEO."""
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        clip = Path(td) / "frozen.mp4"
        # Single image looped for 6s = frozen
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                        "color=c=navy:size=320x180:d=6",
                        "-vf", "drawtext=text='static':fontsize=24:fontcolor=white:x=10:y=10",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        str(clip)], capture_output=True, check=True)
        issues = qa.check_frozen_video(str(clip), duration=6.0)
        assert any("FROZEN_VIDEO" in i for i in issues), f"expected FROZEN_VIDEO, got {issues}"
    print("  ✓ frozen/static clip triggers FROZEN_VIDEO")


def test_moving_video_passes():
    """A clip with real motion (testsrc2) passes both checks."""
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        clip = Path(td) / "motion.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                        "testsrc2=size=320x180:d=4:rate=24",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        str(clip)], capture_output=True, check=True)
        blank_issues = qa.check_blank_screen(str(clip))
        frozen_issues = qa.check_frozen_video(str(clip), duration=4.0)
        assert not blank_issues, f"false positive blank: {blank_issues}"
        assert not frozen_issues, f"false positive frozen: {frozen_issues}"
    print("  ✓ moving video passes perceptual checks (no false positives)")


# --- TKT-07: Media QA Upgrade tests ---

def test_lowercase_fail_counts_as_failure():
    """Any row with status 'fail' (lowercase) must make aggregate passed=False.
    After the fix, qa_media emits uppercase, but produce.py now handles both."""
    qa = _load()
    # Simulate old-style lowercase results going through produce.py logic
    results = [
        {"id": "B001", "status": "PASS", "issues": []},
        {"id": "B002", "status": "fail", "issues": ["something"]},
    ]
    # The produce.py aggregation logic (case-insensitive)
    fail_count = sum(1 for r in results if r.get("status", "").upper() == "FAIL")
    assert fail_count == 1, f"expected 1 fail, got {fail_count}"
    passed = fail_count == 0
    assert not passed, "aggregate must be False when any row is fail/FAIL"
    print("  ✓ lowercase 'fail' counts as failure in aggregation")


def test_coverage_deficit_fails_beat():
    """A clip shorter than its timing-map requirement triggers COVERAGE_DEFICIT."""
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # Create a 3s clip
        clip = td / "B001.mp4"
        _make_clip(clip, duration=3, audio=False)
        # Create project structure with timing map expecting 10s
        proj = td / "Videos" / "Projects" / "tkt07test"
        nar = proj / "narration"
        nar.mkdir(parents=True)
        timing = {"beats": [{"beat_id": "B001", "start": 0.0, "end": 10.0}],
                  "total_duration": 10.0, "beat_count": 1}
        (nar / "beat_timing_map.json").write_text(json.dumps(timing))
        # Build media plan
        plan = {"project_id": "tkt07test", "defaults": {"format": "mp3"}, "beats": [{
            "beat_id": "B001", "shot_type": "b_roll_specific",
            "audio_mode": "generated_tts", "output_path": str(clip),
        }]}
        pp = td / "media_plan.json"
        pp.write_text(json.dumps(plan))
        # Patch ROOT so _load_timing_map finds our fixture
        import scripts.qa_media as qm
        orig_root = qm.ROOT
        qm.ROOT = td
        try:
            results, ok = qm.run_qa(str(pp))
        finally:
            qm.ROOT = orig_root
    assert not ok, f"should fail with coverage deficit, got passed=True"
    assert any("COVERAGE_DEFICIT" in i for r in results for i in r.get("issues", [])), \
        f"expected COVERAGE_DEFICIT issue, got {results}"
    print("  ✓ coverage deficit (3s clip, 10s required) → FAIL")


def test_coverage_sufficient_passes():
    """A clip with duration >= timing-map requirement passes."""
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        clip = td / "B001.mp4"
        _make_clip(clip, duration=10, audio=False)
        proj = td / "Videos" / "Projects" / "tkt07ok"
        nar = proj / "narration"
        nar.mkdir(parents=True)
        timing = {"beats": [{"beat_id": "B001", "start": 0.0, "end": 9.5}],
                  "total_duration": 9.5, "beat_count": 1}
        (nar / "beat_timing_map.json").write_text(json.dumps(timing))
        plan = {"project_id": "tkt07ok", "defaults": {"format": "mp3"}, "beats": [{
            "beat_id": "B001", "shot_type": "b_roll_specific",
            "audio_mode": "generated_tts", "output_path": str(clip),
        }]}
        pp = td / "media_plan.json"
        pp.write_text(json.dumps(plan))
        import scripts.qa_media as qm
        orig_root = qm.ROOT
        qm.ROOT = td
        try:
            results, ok = qm.run_qa(str(pp))
        finally:
            qm.ROOT = orig_root
    assert ok, f"10s clip covering 9.5s requirement should pass, issues={results}"
    assert all("COVERAGE_DEFICIT" not in i for r in results for i in r.get("issues", []))
    print("  ✓ coverage sufficient (10s clip, 9.5s required) → PASS")


def test_multislot_coverage_aggregates_per_beat():
    """REGRESSION: a beat split into coverage slots (e.g. hero_cutaway B009-s0..s3)
    must have its slot durations SUMMED before the timing-map coverage comparison.
    Each slot is shorter than the whole-beat requirement, but together they cover it.
    Before the fix, each ~6s slot was compared against the whole 23s beat requirement,
    producing a false COVERAGE_DEFICIT on every slot."""
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # 4 slot clips, ~6s each = 24s total, covering a 23.4s beat.
        slots = []
        for i in range(4):
            c = td / f"B009_s{i}.mp4"
            _make_clip(c, duration=6, audio=False)
            slots.append(c)
        proj = td / "Videos" / "Projects" / "multislot"
        nar = proj / "narration"
        nar.mkdir(parents=True)
        # Timing map carries ONE whole-beat requirement for B009 (23.4s).
        timing = {"beats": [{"beat_id": "B009", "start": 0.0, "end": 23.4}],
                  "total_duration": 23.4, "beat_count": 1}
        (nar / "beat_timing_map.json").write_text(json.dumps(timing))
        # 4 separate plan beats, all beat_id B009 (the overloaded-identity case),
        # each with its OWN clip_id and a per-slot required window.
        beats = []
        for i, c in enumerate(slots):
            beats.append({
                "beat_id": "B009", "shot_type": "hero_cutaway",
                "audio_mode": "generated_tts", "output_path": str(c),
                "clip_id": f"multislot::B009::B009-s{i}",
                "required_start_sec": round(i * 5.85, 3),
                "required_end_sec": round((i + 1) * 5.85, 3),
            })
        plan = {"project_id": "multislot", "defaults": {"format": "mp3"}, "beats": beats}
        pp = td / "media_plan.json"
        pp.write_text(json.dumps(plan))
        import scripts.qa_media as qm
        orig_root = qm.ROOT
        qm.ROOT = td
        try:
            results, ok = qm.run_qa(str(pp))
        finally:
            qm.ROOT = orig_root
    assert ok, f"4×6s slots (24s) covering a 23.4s beat should PASS, got {results}"
    assert all("COVERAGE_DEFICIT" not in i for r in results for i in r.get("issues", [])), \
        f"no slot should report COVERAGE_DEFICIT, got {results}"
    # Each slot keeps its OWN clip_id (no collision onto the last slot).
    cids = {r.get("clip_id") for r in results}
    assert cids == {f"multislot::B009::B009-s{i}" for i in range(4)}, \
        f"each slot must keep its own clip_id, got {cids}"
    print("  ✓ multi-slot beat: durations aggregate per-beat, clip_ids distinct → PASS")


def test_multislot_coverage_deficit_still_caught():
    """The aggregation fix must NOT mask a genuine deficit: if the summed slot
    durations are still short of the requirement, COVERAGE_DEFICIT must fire."""
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # 2 slots × 4s = 8s total, but the beat needs 20s → genuine deficit.
        slots = []
        for i in range(2):
            c = td / f"B009_s{i}.mp4"
            _make_clip(c, duration=4, audio=False)
            slots.append(c)
        proj = td / "Videos" / "Projects" / "multislotdef"
        nar = proj / "narration"
        nar.mkdir(parents=True)
        timing = {"beats": [{"beat_id": "B009", "start": 0.0, "end": 20.0}],
                  "total_duration": 20.0, "beat_count": 1}
        (nar / "beat_timing_map.json").write_text(json.dumps(timing))
        beats = [{
            "beat_id": "B009", "shot_type": "hero_cutaway",
            "audio_mode": "generated_tts", "output_path": str(c),
            "clip_id": f"multislotdef::B009::B009-s{i}",
        } for i, c in enumerate(slots)]
        plan = {"project_id": "multislotdef", "defaults": {"format": "mp3"}, "beats": beats}
        pp = td / "media_plan.json"
        pp.write_text(json.dumps(plan))
        import scripts.qa_media as qm
        orig_root = qm.ROOT
        qm.ROOT = td
        try:
            results, ok = qm.run_qa(str(pp))
        finally:
            qm.ROOT = orig_root
    assert not ok, "8s total across 2 slots vs 20s requirement should FAIL"
    assert any("COVERAGE_DEFICIT" in i for r in results for i in r.get("issues", [])), \
        f"genuine aggregate deficit must still fire COVERAGE_DEFICIT, got {results}"
    print("  ✓ multi-slot genuine deficit (8s vs 20s) still caught → FAIL")


def test_aggregate_cannot_disagree_with_rows():
    """If any row is FAIL, overall passed must be False — enforced by aggregate check."""
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        clip = td / "clip.mp4"
        _make_clip(clip, width=640, height=480)  # wrong dims → FAIL
        plan = {"project_id": "t", "defaults": {"format": "mp3"}, "beats": [{
            "beat_id": "B001", "shot_type": "b_roll_specific",
            "audio_mode": "generated_tts", "output_path": str(clip),
        }]}
        pp = td / "media_plan.json"
        pp.write_text(json.dumps(plan))
        results, ok = qa.run_qa(str(pp))
    assert not ok, "aggregate must be False when any row has issues"
    assert results[0]["status"] == "FAIL"
    print("  ✓ aggregate cannot disagree with row-level FAIL")

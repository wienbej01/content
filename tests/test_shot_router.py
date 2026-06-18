#!/usr/bin/env python3
"""tests/test_shot_router.py — Shot-type routing tests."""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _load():
    spec = importlib.util.spec_from_file_location("shot_router", ROOT / "scripts" / "shot_router.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_config_loads():
    sr = _load()
    r = sr.ShotRouter(skip_availability_check=True)
    assert len(r.routes) >= 4
    assert "talking_head_hero" in r.routes
    assert "broll_environment" in r.routes
    print(f"  ✓ config loads: {len(r.routes)} shot_types")


def test_talking_head_hero_routes_to_veo3():
    sr = _load()
    r = sr.ShotRouter(skip_availability_check=True)
    model_id, prompt, policy = r.resolve("talking_head_hero")
    assert model_id == "seedance_2_0"
    assert policy["requires_audio"] is True
    assert policy["preserve_baked_audio"] is True
    print(f"  ✓ talking_head_hero → seedance_2_0, requires_audio=True")


def test_broll_environment_routes_to_hailuo():
    sr = _load()
    r = sr.ShotRouter(skip_availability_check=True)
    model_id, prompt, policy = r.resolve("broll_environment")
    assert model_id == "kling3_0"
    assert policy["requires_audio"] is False
    print(f"  ✓ broll_environment → kling3_0, no audio required")


def test_talking_head_standard_routes_to_kling():
    sr = _load()
    r = sr.ShotRouter(skip_availability_check=True)
    model_id, prompt, policy = r.resolve("talking_head_standard")
    # talking_head_standard uses lipsync_primary (seedance_2_0)
    assert model_id == "seedance_2_0"
    assert policy["requires_audio"] is True
    assert policy["preserve_baked_audio"] is True
    print(f"  ✓ talking_head_standard → seedance_2_0, preserve_baked_audio")


def test_unknown_shot_type_fails():
    sr = _load()
    r = sr.ShotRouter(skip_availability_check=True)
    try:
        r.resolve("nonexistent_type")
        assert False, "should fail"
    except ValueError as e:
        assert "Unknown shot_type" in str(e)
    print("  ✓ unknown shot_type → ValueError")


def test_unavailable_model_fails_loudly():
    sr = _load()
    r = sr.ShotRouter(skip_availability_check=True)
    r._available = {"kling3_0"}  # simulate limited catalog
    try:
        r.resolve("talking_head_hero", allow_alternate=False)
        assert False, "should fail"
    except RuntimeError as e:
        assert "BLOCKED" in str(e) and "not available" in str(e)
    print("  ✓ unavailable primary model → BLOCKED RuntimeError")


def test_alternate_used_when_primary_unavailable():
    sr = _load()
    r = sr.ShotRouter(skip_availability_check=True)
    # Add an alternate to talking_head_hero dynamically for this test.
    r.routes["talking_head_hero"]["alternates"] = ["hero_face_insert"]
    r._available = {"kling3_0"}  # seedance_2_0 not available; kling3_0 (hero_face_insert) is
    model_id, prompt, policy = r.resolve("talking_head_hero", allow_alternate=True)
    assert model_id == "kling3_0"
    assert "alternate" in policy["reason"]
    print(f"  ✓ alternate used when primary unavailable: {model_id}")


def test_no_silent_fallback():
    """If primary unavailable and allow_alternate=False, must fail, not silently substitute."""
    sr = _load()
    r = sr.ShotRouter(skip_availability_check=True)
    r._available = {"kling3_0"}  # seedance not available
    try:
        r.resolve("talking_head_hero", allow_alternate=False)
        assert False
    except RuntimeError:
        pass
    print("  ✓ no silent fallback: fails when allow_alternate=False")


def test_segment_without_shot_type_fails():
    sr = _load()
    r = sr.ShotRouter(skip_availability_check=True)
    try:
        r.plan_segment({"id": "x"})
        assert False
    except ValueError as e:
        assert "shot_type" in str(e)
    print("  ✓ segment without shot_type → ValueError")


def test_baked_audio_preserved_flag():
    sr = _load()
    r = sr.ShotRouter(skip_availability_check=True)
    for st in ["talking_head_hero", "talking_head_standard"]:
        _, _, policy = r.resolve(st)
        assert policy["preserve_baked_audio"] is True, f"{st} must preserve baked audio"
    for st in ["broll_environment", "broll_human"]:
        _, _, policy = r.resolve(st)
        assert policy.get("preserve_baked_audio", False) is False
    print("  ✓ baked_audio preserved for talking_head, not for b-roll")


def test_james_segment_mapping_valid():
    sr = _load()
    r = sr.ShotRouter(skip_availability_check=True)
    james_map = r.config.get("james_segments", {})
    assert "001_hook" in james_map
    assert james_map["001_hook"]["shot_type"] == "talking_head_hero"
    assert james_map["002_background"]["shot_type"] == "broll_environment"
    print(f"  ✓ james_segments mapping: {len(james_map)} segments configured")


def test_eleven_v3_is_default_tts():
    import importlib.util
    spec = importlib.util.spec_from_file_location("tts", ROOT / "scripts" / "tts.py")
    tts = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tts)
    assert tts.DEFAULT_MODEL == "eleven_v3"
    print("  ✓ ElevenLabs Eleven v3 is default TTS model")


def main():
    print("Shot Router Tests")
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

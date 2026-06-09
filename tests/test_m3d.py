#!/usr/bin/env python3
"""tests/test_m3d.py — M3-D production acceptance tests."""
import importlib.util
import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# --- Narration ---
def test_speed_always_in_voice_settings():
    src = (ROOT / "scripts" / "tts.py").read_text()
    assert 'vs["speed"] = speed' in src, "speed must be set in voice_settings"
    assert "if speed is not None and speed != 1.0" not in src, "speed must NOT be gated on !=1.0"
    print("  ✓ speed always sent in voice_settings (incl. 1.0)")


def test_show_segment_audio_exists():
    src = (ROOT / "scripts" / "tts.py").read_text()
    assert "--show-segment-audio" in src and "--segment-text-contains" in src
    assert "--compare-pack" in src
    print("  ✓ tts.py has --show-segment-audio / --segment-text-contains / --compare-pack")


# --- Lipsync ---
def test_lipsync_provenance_functions():
    gm = _load("generate_media")
    assert hasattr(gm, "validate_lipsync_provenance")
    assert hasattr(gm, "record_lipsync_provenance")
    assert hasattr(gm, "file_sha256")
    print("  ✓ lipsync provenance + validation functions present")


def test_lipsync_validation_flags_missing_hash():
    gm = _load("generate_media")
    s = json.load(open(ROOT / "scripts/generated/james_growth_system_teaser_02.json"))
    base = (ROOT / "scripts/generated").resolve()
    issues = gm.validate_lipsync_provenance(s, base)
    # Existing logs lack audio_source_sha256 → must be flagged
    assert any("005_give_back" in i for i in issues), "005 lipsync must be flagged"
    assert all("BLOCKED" in i or "NO PROVENANCE" in i for i in issues)
    print(f"  ✓ lipsync validation flags {len(issues)} unverifiable segments incl. 005")


# --- Text policy ---
def test_risk_classifier_blocks_text_surfaces():
    gm = _load("generate_media")
    r = gm.classify_prompt_risk("executive reviewing a report on a laptop screen with a whiteboard")
    assert r["text_surface_risk"] is True
    assert "document_risk" in r["text_flags"] or "screen_risk" in r["text_flags"]
    print("  ✓ classifier flags screen/document/whiteboard prompts")


def test_risk_classifier_negation_aware():
    gm = _load("generate_media")
    r = gm.classify_prompt_risk("modern office corridor, no screens, no documents, no whiteboards")
    assert r["text_surface_risk"] is False, "negated text surfaces must not flag"
    print("  ✓ classifier is negation-aware ('no screens' not flagged)")


def test_anti_text_prompt_present():
    gm = _load("generate_media")
    assert "without any text-bearing surfaces" in gm.BROLL_REALISM_PREFIX.lower()
    assert "deformed hands" in gm.BROLL_NEGATIVE.lower()
    print("  ✓ anti-text + anti-deformed-hands prompt present")


# --- Human model routing ---
def test_human_closeup_routes_to_seedance():
    gm = _load("generate_media")
    seg = {"id": "x", "audio_mode": "generated_tts",
           "visual_brief": "overhead close-up of hands typing on a keyboard"}
    assert gm.route_model(seg, "generated_tts") == gm.HUMAN_CLOSEUP_MODEL
    print("  ✓ close-up hands route to seedance_2_0")


def test_environment_broll_routes_to_wan():
    gm = _load("generate_media")
    seg = {"id": "x", "audio_mode": "generated_tts",
           "visual_brief": "wide aerial shot of a city skyline at dusk"}
    assert gm.route_model(seg, "generated_tts") == gm.DEFAULT_BROLL_MODEL
    print("  ✓ environment b-roll routes to wan2_7")


# --- Duration / storyboard ---
def test_plan_shots_multiple_for_long_narration():
    gm = _load("generate_media")
    seg = {"id": "s", "audio_mode": "generated_tts", "media": "x.mp4", "visual_brief": "city"}
    shots, needed = gm.plan_shots(seg, 13.0, ROOT)
    assert len(shots) >= 3, f"13s narration should need 3+ shots, got {len(shots)}"
    print(f"  ✓ 13s narration plans {len(shots)} shots")


def test_plan_shots_single_for_short():
    gm = _load("generate_media")
    seg = {"id": "s", "audio_mode": "generated_tts", "media": "x.mp4", "visual_brief": "city"}
    shots, needed = gm.plan_shots(seg, 4.0, ROOT)
    assert len(shots) == 1
    print("  ✓ short narration stays single shot")


def test_assemble_rejects_long_freeze():
    asm = _load("assemble")
    assert asm.MAX_FREEZE == 0.5
    src = (ROOT / "scripts" / "assemble.py").read_text()
    assert "exceeds the" in src and "MAX_FREEZE" in src
    print(f"  ✓ assemble rejects freeze > {asm.MAX_FREEZE}s")


def test_assemble_shots_bed_support():
    src = (ROOT / "scripts" / "assemble.py").read_text()
    assert 'shots = seg.get("shots")' in src
    assert "concat" in src.lower()
    print("  ✓ assemble supports shots[] visual bed via concat")


# --- Reports ---
def test_reports_generate():
    gm = _load("generate_media")
    s = json.load(open(ROOT / "scripts/generated/james_growth_system_teaser_02.json"))
    base = (ROOT / "scripts/generated").resolve()
    dr = gm.duration_report(s, base)
    rr = gm.risk_report(s, base)
    assert len(dr) == len(s["segments"]) == len(rr)
    proj = ROOT / "Videos/Projects/james_growth_system_teaser_02"
    assert (proj / "duration_mismatch_report.json").exists()
    assert (proj / "media_risk_report.json").exists()
    print("  ✓ duration_mismatch_report.json + media_risk_report.json generated")


def main():
    print("M3-D Production Acceptance Tests")
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

#!/usr/bin/env python3
"""tests/test_m3e.py — M3-E per-shot generation tests (no API/credits)."""
import importlib.util
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


def _script():
    return json.load(open(ROOT / "scripts/generated/james_growth_system_teaser_02.json"))


def test_generate_segment_accepts_shot_spec():
    gm = _load("generate_media")
    import inspect
    sig = inspect.signature(gm.generate_segment)
    for p in ("audio_mode", "spec", "duration"):
        assert p in sig.parameters, f"generate_segment missing {p}"
    print("  ✓ generate_segment accepts spec/audio_mode/duration")


def test_dry_run_prints_shot_ids_and_paths(capsys=None):
    gm = _load("generate_media")
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        gm.run(str(ROOT / "scripts/generated/james_growth_system_teaser_02.json"),
               dry_run=True, force=True, selected_segments={"004_system"})
    out = buf.getvalue()
    assert "004_system_shot01" in out and "004_system_shot02" in out and "004_system_shot03" in out
    assert "004_system_shot01.mp4" in out
    assert "wan2_7" in out and "seedance_2_0" in out
    print("  ✓ dry-run prints shot IDs, target paths, per-shot models")


def test_dry_run_no_credits_no_files():
    gm = _load("generate_media")
    import io, contextlib
    before = set((ROOT / "assets/media/james_teaser_02").glob("004_system_shot*.mp4"))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        gm.run(str(ROOT / "scripts/generated/james_growth_system_teaser_02.json"),
               dry_run=True, force=True, selected_segments={"004_system"})
    after = set((ROOT / "assets/media/james_teaser_02").glob("004_system_shot*.mp4"))
    assert before == after, "dry-run must not create shot files"
    print("  ✓ dry-run spends no credits / creates no files")


def test_shots_route_models_per_shot():
    gm = _load("generate_media")
    s = _script()
    seg = next(x for x in s["segments"] if x["id"] == "004_system")
    models = [gm.route_model(sh, "generated_tts") for sh in seg["shots"]]
    # shot03 = walking executive -> close-human -> seedance
    assert models[2] == gm.HUMAN_CLOSEUP_MODEL, "walking-person shot must route to seedance"
    assert models[0] == gm.DEFAULT_BROLL_MODEL, "abstract shot routes to wan2_7"
    print(f"  ✓ per-shot routing: {models}")


def test_coverage_uses_sum_of_shots():
    gm = _load("generate_media")
    s = _script()
    base = (ROOT / "scripts/generated").resolve()
    dr = gm.duration_report(s, base)
    for sid in ("002_background", "004_system", "006_audience"):
        e = next(x for x in dr if x["segment_id"] == sid)
        assert e["has_shots"] is True
        assert e["coverage_pass"] is True, f"{sid} coverage must pass"
        assert e["total_planned_shot_duration"] >= e["required_visual_duration"] - 0.05
    print("  ✓ coverage uses sum(shots[].duration) and passes for 002/004/006")


def test_insufficient_coverage_blocks():
    gm = _load("generate_media")
    import tempfile, os
    s = _script()
    seg = next(x for x in s["segments"] if x["id"] == "004_system")
    seg["shots"] = [{"id": "004_system_shot01", "duration": 2.0, "media": seg["media"],
                     "visual_brief": "abstract light"}]
    # write temp script in same dir for narration resolution
    tmp = ROOT / "scripts/generated/_tmp_cov.json"
    tmp.write_text(json.dumps(s))
    try:
        try:
            gm.run(str(tmp), dry_run=False, force=True, selected_segments={"004_system"})
            assert False, "should have raised on insufficient coverage"
        except RuntimeError as e:
            assert "BLOCKED" in str(e) and "cover" in str(e)
        print("  ✓ insufficient coverage blocks before generation")
    finally:
        tmp.unlink()


def test_text_shot_blocks_by_default():
    gm = _load("generate_media")
    s = _script()
    seg = next(x for x in s["segments"] if x["id"] == "004_system")
    seg["shots"] = [{"id": "004_system_shot01", "duration": 14.0, "media": seg["media"],
                     "visual_brief": "close-up of a laptop screen showing a financial report"}]
    tmp = ROOT / "scripts/generated/_tmp_text.json"
    tmp.write_text(json.dumps(s))
    try:
        try:
            gm.run(str(tmp), dry_run=False, force=True, selected_segments={"004_system"})
            assert False, "should block text-surface shot"
        except RuntimeError as e:
            assert "text-bearing" in str(e) or "BLOCKED" in str(e)
        print("  ✓ text-surface shot blocks by default")
    finally:
        tmp.unlink()


def test_wan_blocked_for_closeup_human():
    gm = _load("generate_media")
    s = _script()
    seg = next(x for x in s["segments"] if x["id"] == "004_system")
    seg["shots"] = [{"id": "004_system_shot01", "duration": 14.0, "media": seg["media"],
                     "visual_brief": "extreme close-up of hands typing", "model": "wan2_7"}]
    tmp = ROOT / "scripts/generated/_tmp_wan.json"
    tmp.write_text(json.dumps(s))
    try:
        try:
            gm.run(str(tmp), dry_run=False, force=True, selected_segments={"004_system"})
            assert False, "should block wan2_7 close-human"
        except RuntimeError as e:
            assert "seedance" in str(e).lower() and "BLOCKED" in str(e)
        print("  ✓ wan2_7 blocked for close-up hands")
    finally:
        tmp.unlink()


def test_review_handles_shots():
    gm = _load("generate_media")
    import io, contextlib
    s = _script()
    base = (ROOT / "scripts/generated").resolve()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        entries = gm.media_review(s, base, selected={"004_system"})
    # 004 has 3 shots → 3 units (likely missing media, but still listed)
    sids = [e for e in entries if e["segment_id"] == "004_system"]
    assert len(sids) == 3, f"expected 3 shot units, got {len(sids)}"
    assert all(e.get("shot_id") for e in sids)
    print("  ✓ review expands per-shot units")


def test_backward_compat_single_media():
    gm = _load("generate_media")
    seg = {"id": "x", "audio_mode": "generated_tts", "media": "y.mp4", "visual_brief": "city skyline"}
    shots, needed = gm.plan_shots(seg, 4.0, ROOT)
    assert len(shots) == 1 and shots[0]["id"] == "x"
    print("  ✓ backward compat: no shots[] → single segment-level media")


def main():
    print("M3-E Per-Shot Generation Tests")
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

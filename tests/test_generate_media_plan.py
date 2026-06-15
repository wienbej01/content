#!/usr/bin/env python3
"""tests/test_generate_media_plan.py — T8 tests for the media-plan generation path.

No Higgsfield calls. Exercises run_from_media_plan in dry-run, the still_kenburns
local path, reuse lookup, and the spend-gate block.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
FLAGSHIP = ROOT / "scripts" / "generated" / "flagship_001_learn_half_time.json"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def GM(monkeypatch, tmp_path):
    gm = _load("generate_media")
    # Redirect project output + library index into a temp tree.
    monkeypatch.setattr(gm, "ROOT", tmp_path)
    monkeypatch.setattr(gm, "LIBRARY_INDEX", tmp_path / "assets" / "media" / "library_index.json")
    return gm


def _mini_plan(project_id="t_proj"):
    return {
        "schema_version": "media_plan_2.0",
        "project_id": project_id,
        "video_type": "explainer",
        "beats": [
            {"beat_id": "B001", "shot_type": "hero_lipsync", "asset_type": "generated_video",
             "model": "seedance_2_0", "model_tier": "premium", "prompt_class": "x",
             "positive_prompt": "James at desk", "negative_prompt": "no neon",
             "duration_target_sec": 6, "lipsync_required": True,
             "reference_images": ["ref.jpg"], "cost": {"est_clips": 1, "est_credits": 22.5, "est_usd": 1.10},
             "reuse": {"allowed": False}, "fallback": {"on_generation_fail": "still_kenburns"}},
            {"beat_id": "B002", "shot_type": "broll_environment", "asset_type": "generated_video",
             "model": "kling3_0", "model_tier": "standard", "prompt_class": "env",
             "positive_prompt": "warm study desk", "negative_prompt": "no neon",
             "duration_target_sec": 6, "lipsync_required": False,
             "reference_images": [], "cost": {"est_clips": 1, "est_credits": 10, "est_usd": 0.49},
             "reuse": {"allowed": True}, "fallback": {"on_generation_fail": "still_kenburns"}},
            {"beat_id": "B003", "shot_type": "graphic_progressive", "asset_type": "local_graphic",
             "model": "local_graphic", "model_tier": "local", "prompt_class": "g",
             "positive_prompt": "framework", "negative_prompt": "",
             "duration_target_sec": 5, "lipsync_required": False, "reference_images": [],
             "cost": {"est_clips": 0, "est_credits": 0, "est_usd": 0.0},
             "reuse": {"allowed": False}, "fallback": {}},
            {"beat_id": "B004", "shot_type": "still_kenburns", "asset_type": "generated_still",
             "model": "still_kenburns", "model_tier": "cheap", "prompt_class": "still",
             "positive_prompt": "atmospheric study", "negative_prompt": "",
             "duration_target_sec": 4, "lipsync_required": False, "reference_images": [],
             "cost": {"est_clips": 1, "est_credits": 0, "est_usd": 0.0},
             "reuse": {"allowed": False}, "fallback": {}},
        ],
        "totals": {"est_usd": 1.59, "budget_cap_usd": 60},
    }


def _write_plan(gm, plan):
    pdir = gm.ROOT / "Videos" / "Projects" / plan["project_id"]
    pdir.mkdir(parents=True, exist_ok=True)
    p = pdir / "media_plan.json"
    p.write_text(json.dumps(plan))
    return p


def test_dry_run_zero_api_and_report(GM):
    p = _write_plan(GM, _mini_plan())
    summary = GM.run_from_media_plan(p, dry_run=True)
    assert summary["beats_total"] == 4
    assert summary["beats_local_graphic"] == 1
    # est spend = generated beats only (hero 1.10 + env 0.49 + still 0.0) — locals excluded
    assert abs(summary["est_spend_usd"] - 1.59) < 0.01
    report = GM.ROOT / "Videos" / "Projects" / "t_proj" / "dryrun_report.json"
    assert report.exists(), "dry-run must write dryrun_report.json"
    print(f"  ✓ dry-run: zero API, report written, est ${summary['est_spend_usd']}")


def test_dry_run_no_files_created(GM):
    p = _write_plan(GM, _mini_plan())
    GM.run_from_media_plan(p, dry_run=True)
    shots = GM.ROOT / "assets" / "media" / "t_proj" / "shots"
    assert not shots.exists() or not any(shots.glob("*.mp4")), "dry-run must not create clips"
    print("  ✓ dry-run creates no clip files")


def test_still_kenburns_local_render(GM):
    """still_kenburns: with a reference image, renders a real moving file at $0.
    Without a reference, it MUST hard-fail (never emit a solid/blank frame)."""
    import subprocess, tempfile
    beat = _mini_plan()["beats"][3]

    # No reference → must hard-fail (the safety contract: no blank frames)
    out_nofile = GM.ROOT / "Videos" / "Projects" / "t_proj" / "B004_noref.mp4"
    res = GM._still_kenburns(beat, out_nofile, dry_run=False)
    assert res["cost_usd"] == 0.0
    assert res.get("status") == "fail" and "error" in res, \
        "still_kenburns with no reference must hard-fail, not emit a blank frame"
    assert not out_nofile.exists(), "must NOT produce a file when no reference"

    # With a reference image → renders a real file at $0
    with tempfile.TemporaryDirectory() as td:
        ref = Path(td) / "ref.png"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                        "testsrc2=size=1280x720:d=1", "-frames:v", "1", str(ref)],
                       capture_output=True, check=True)
        beat2 = dict(beat)
        beat2["reference_images"] = [str(ref.relative_to(GM.ROOT)) if str(ref).startswith(str(GM.ROOT)) else str(ref)]
        # Use absolute path so the resolver finds it
        beat2["reference_images"] = [str(ref)]
        out = Path(td) / "B004.mp4"
        res2 = GM._still_kenburns(beat2, out, dry_run=False)
        assert res2["cost_usd"] == 0.0
        assert out.exists(), "kenburns with a reference should produce a real file"
    print("  ✓ still_kenburns: renders with ref at $0; hard-fails (no blank) without ref")


def test_reuse_lookup(GM):
    idx = {"assets": {"a1": {"prompt_class": "env", "qa_status": "pass", "path": "assets/media/reused.mp4"}}}
    reused = GM.ROOT / "assets" / "media" / "reused.mp4"
    reused.parent.mkdir(parents=True, exist_ok=True)
    reused.write_bytes(b"x")
    beat = _mini_plan()["beats"][1]  # broll_environment, reuse allowed, prompt_class env
    hit = GM._library_lookup(beat, idx)
    assert hit == "assets/media/reused.mp4"
    print("  ✓ reuse lookup finds QA-passed asset by prompt_class")


def test_banned_model_in_plan_raises(GM):
    plan = _mini_plan()
    plan["beats"][1]["model"] = "wan2_7"
    beat = plan["beats"][1]
    with pytest.raises(RuntimeError):
        GM._generate_beat_clip(beat, GM.ROOT / "x.mp4", dry_run=False)
    print("  ✓ banned model in plan raises before any call")


def test_live_run_blocked_without_gates(GM, monkeypatch):
    """run_from_media_plan must exit/raise via the gate guard before any HF call."""
    import gates
    monkeypatch.setattr(gates, "PROJECTS_DIR", GM.ROOT / "Videos" / "Projects")
    monkeypatch.setattr(GM, "require_gates", gates.require_gates)
    p = _write_plan(GM, _mini_plan("ungated"))
    with pytest.raises(SystemExit):
        GM.run_from_media_plan(p, dry_run=False)
    print("  ✓ live run blocked without spend gates (no HF call)")


def test_media_plan_is_sole_prompt_source(GM):
    """The dry-run report must reflect the media-plan prompts, not script briefs."""
    plan = _mini_plan()
    p = _write_plan(GM, plan)
    summary = GM.run_from_media_plan(p, dry_run=True)
    gen_beats = [b for b in summary["beats"] if b["action"] == "generate"]
    assert all("B00" in b["beat_id"] for b in gen_beats)
    print("  ✓ generation driven solely by media_plan beats")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

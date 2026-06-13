#!/usr/bin/env python3
"""tests/test_review_storyboard.py — T5 tests for the v2 storyboard validator (G2)."""
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


@pytest.fixture(scope="module")
def RS():
    return _load("review_storyboard")


@pytest.fixture(scope="module")
def compliant_sb():
    S = _load("storyboard")
    return S.route(json.loads(FLAGSHIP.read_text()), S.load_constraints())


def _all_hero_sb():
    """A storyboard shaped like flagship 001: every beat a James close-up, no
    archival/graphics. Must be rejected (the failure that motivated V2)."""
    beats = []
    for i in range(9):
        beats.append({
            "beat_id": f"B{i+1:03d}", "segment_id": f"00{i}", "act": min(6, i + 1),
            "order": i, "narration_text": "James talks about learning at the desk.",
            "est_duration_sec": 18.0, "shot_type": "hero_lipsync",
            "asset_type": "generated_video", "model_tier": "premium",
            "model": "seedance_2_0", "prompt_class": "james_studio_lipsync",
            "visual_brief": "James medium close-up, direct to camera, mahogany desk.",
            "narrative_function": "James delivers to camera.",
            "audio_mode": "lipsync", "lipsync_required": True, "crop_safety": "center_safe",
            "cost": {"est_clips": 1, "est_credits": 22.5, "est_usd": 1.10},
            "fallback": {}, "approval": {}, "qa": {},
        })
    return {
        "schema_version": "2.0", "project_id": "flagship_001_allhero", "video_type": "explainer",
        "acts": [], "beats": beats,
        "shot_mix_summary": {
            "hero_lipsync_pct": 100.0, "hero_cutaway_pct": 0.0, "broll_specific_pct": 0.0,
            "broll_metaphorical_pct": 0.0, "graphics_ui_pct": 0.0, "kinetic_text_pct": 0.0,
            "max_hero_block_sec": 162.0, "distinct_visual_setups": 1,
        },
        "totals": {"est_higgsfield_credits": 200, "est_usd": 9.9, "budget_cap_usd": 60},
        "approval": {"status": "draft"},
    }


def test_compliant_storyboard_passes(RS, compliant_sb):
    blocking, warnings, fixes = RS.review(compliant_sb, RS.load_constraints())
    assert blocking == [], f"compliant storyboard should pass; got: {blocking}"
    print(f"  ✓ compliant flagship-001 route passes G2 ({len(warnings)} warnings)")


def test_all_hero_storyboard_fails(RS):
    blocking, warnings, fixes = RS.review(_all_hero_sb(), RS.load_constraints())
    assert blocking, "all-hero storyboard must fail"
    blob = " ".join(blocking).lower()
    assert "all-hero" in blob or "flagship-001" in blob, blocking
    assert any("hero" in b.lower() for b in blocking)
    assert any("archival" in b.lower() for b in blocking)
    print(f"  ✓ all-hero (flagship-001 shape) fails with {len(blocking)} named violations")


def test_max_hero_block_violation_named(RS):
    sb = _all_hero_sb()
    blocking, _, _ = RS.review(sb, RS.load_constraints())
    assert any("hero" in b.lower() and ("15s" in b or "exceeds" in b.lower()) for b in blocking)
    print("  ✓ max-hero-block violation is named")


def _mixed_chain_sb(chain_specs, summary_max=12.0):
    """Build a minimal storyboard whose hero chains are given by chain_specs:
    list of (shot_type, act, dur). Non-hero spacer beats separate explicit chains
    when a None appears. shot_mix_summary.max_hero_block_sec is set to summary_max
    (deliberately a LIE to prove the reviewer recomputes from raw beats)."""
    beats, order = [], 0
    for i, spec in enumerate(chain_specs):
        if spec is None:
            beats.append({"beat_id": f"S{order}", "segment_id": "s", "act": 4, "order": order,
                          "narration_text": "spacer", "est_duration_sec": 4.0,
                          "shot_type": "broll_archival", "asset_type": "generated_video",
                          "model": "kling3_0", "visual_brief": "archival library scene, period detail",
                          "narrative_function": "x", "lipsync_required": False,
                          "crop_safety": "center_safe", "cost": {"est_clips": 1, "est_credits": 10, "est_usd": 0.49},
                          "fallback": {}, "approval": {}, "qa": {}})
            order += 1
            continue
        st, act, dur = spec
        beats.append({"beat_id": f"H{order}", "segment_id": "s", "act": act, "order": order,
                      "narration_text": "James speaks.", "est_duration_sec": dur,
                      "shot_type": st, "asset_type": "generated_video", "model": "seedance_2_0",
                      "visual_brief": "James medium close-up at the mahogany desk, direct address",
                      "narrative_function": "x", "lipsync_required": st == "hero_lipsync",
                      "crop_safety": "center_safe", "cost": {"est_clips": 1, "est_credits": 22.5, "est_usd": 1.10},
                      "fallback": {}, "approval": {}, "qa": {}})
        order += 1
    return {
        "schema_version": "2.0", "project_id": "chaintest", "video_type": "explainer",
        "acts": [], "beats": beats,
        "shot_mix_summary": {
            "hero_lipsync_pct": 18.0, "hero_cutaway_pct": 11.0, "broll_specific_pct": 36.0,
            "broll_metaphorical_pct": 10.0, "graphics_ui_pct": 15.0, "kinetic_text_pct": 5.0,
            "max_hero_block_sec": summary_max, "distinct_visual_setups": 20,
        },
        "totals": {"est_usd": 30, "budget_cap_usd": 60}, "approval": {"status": "draft"},
    }


def test_recomputed_hero_chain_blocks_despite_summary_lie(RS):
    """A mixed lipsync+cutaway chain of 19.58s in a non-Act-6 act must BLOCK even
    though shot_mix_summary.max_hero_block_sec lies (12.0). Reviewer recomputes."""
    sb = _mixed_chain_sb(
        [("hero_cutaway", 4, 5.42), ("hero_lipsync", 4, 10.83), ("hero_cutaway", 4, 3.33),
         None, ("broll_archival", 4, 4.0)],
        summary_max=12.0)
    blocking, warnings, _ = RS.review(sb, RS.load_constraints())
    assert any("hero chain" in b.lower() and "exceeds 15s" in b.lower() for b in blocking), blocking
    assert any("understates" in w.lower() for w in warnings), warnings
    print("  ✓ recomputed 19.58s non-Act-6 hero chain blocks despite lying summary")


def test_act6_closing_chain_exception_allowed(RS):
    """A SINGLE hero chain entirely in Act 6, <=25s, is allowed (closing exception)."""
    sb = _mixed_chain_sb(
        [None, ("hero_cutaway", 6, 5.42), ("hero_lipsync", 6, 10.83), ("hero_cutaway", 6, 3.33)],
        summary_max=19.58)
    blocking, _, _ = RS.review(sb, RS.load_constraints())
    assert not any("hero chain" in b.lower() for b in blocking), blocking
    print("  ✓ single Act-6 closing hero chain <=25s allowed")


def test_act6_chain_over_25s_still_blocks(RS):
    """Even an Act-6 chain may not exceed 25s."""
    sb = _mixed_chain_sb(
        [None, ("hero_lipsync", 6, 14.0), ("hero_cutaway", 6, 13.0)], summary_max=10.0)
    blocking, _, _ = RS.review(sb, RS.load_constraints())
    assert any("hero chain" in b.lower() for b in blocking), blocking
    print("  ✓ Act-6 hero chain >25s still blocks")


def test_banned_model_blocks(RS, compliant_sb):
    sb = json.loads(json.dumps(compliant_sb))
    sb["beats"][3]["model"] = "wan2_7"
    blocking, _, _ = RS.review(sb, RS.load_constraints())
    assert any("banned model" in b.lower() for b in blocking)
    print("  ✓ banned model is blocked")


def test_empty_brief_blocks(RS, compliant_sb):
    sb = json.loads(json.dumps(compliant_sb))
    sb["beats"][5]["visual_brief"] = ""
    blocking, _, _ = RS.review(sb, RS.load_constraints())
    assert any("empty visual_brief" in b.lower() for b in blocking)
    print("  ✓ empty visual_brief is blocked")


def test_front_facing_cutaway_blocks(RS, compliant_sb):
    sb = json.loads(json.dumps(compliant_sb))
    # Find a hero_cutaway beat or convert one.
    target = next((b for b in sb["beats"] if b["shot_type"] == "hero_cutaway"), sb["beats"][1])
    target["shot_type"] = "hero_cutaway"
    target["visual_brief"] = "James medium close-up, front-facing, direct to camera."
    blocking, _, _ = RS.review(sb, RS.load_constraints())
    assert any("front-facing" in b.lower() or "flagship-001 failure" in b.lower() for b in blocking)
    print("  ✓ front-facing hero_cutaway under voiceover is blocked")


def test_records_gate(RS, compliant_sb, tmp_path, monkeypatch):
    import gates
    monkeypatch.setattr(gates, "PROJECTS_DIR", tmp_path / "Projects")
    sb_path = tmp_path / "storyboard.json"
    sb_path.write_text(json.dumps(compliant_sb))
    gates.record_gate("gatetest", "storyboard_review", "pass", artifact_path=str(sb_path))
    entry = gates.gate_status("gatetest", "storyboard_review")
    assert entry["status"] == "pass"
    print("  ✓ storyboard_review gate records to ledger")


def test_schema_version_enforced(RS):
    sb = _all_hero_sb()
    sb["schema_version"] = "1.0"
    blocking, _, _ = RS.review(sb, RS.load_constraints())
    assert any("schema_version" in b for b in blocking)
    print("  ✓ schema_version must be 2.0")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

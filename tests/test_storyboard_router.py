#!/usr/bin/env python3
"""tests/test_storyboard_router.py — T4 tests for the v2 directorial router.

Primary fixture: the flagship 001 script (the failure that motivated V2). The
router must produce archival beats for Ebbinghaus/1885 and Roediger/2006,
graphic beats for the principles, ui_insert for the AI section, no hero block
>15s, and shot-mix within the §7 bands.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
FLAGSHIP = ROOT / "scripts" / "generated" / "flagship_001_learn_half_time.json"
SCHEMA = ROOT / "schemas" / "storyboard_v2.schema.json"


def _load():
    spec = importlib.util.spec_from_file_location("storyboard", ROOT / "scripts" / "storyboard.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def S():
    return _load()


@pytest.fixture(scope="module")
def flagship_sb(S):
    script = json.loads(FLAGSHIP.read_text())
    return S.route(script, S.load_constraints())


# ---- chunking ----

def test_chunks_within_duration_band(S):
    text = " ".join([f"This is sentence number {i} about learning and memory systems." for i in range(12)])
    beats = S.chunk_segment(text, S.DEFAULT_WPS)
    for b in beats:
        dur = S.est_duration(" ".join(b), S.DEFAULT_WPS)
        assert dur <= S.BEAT_MAX_SEC + 6, f"beat too long pre-split: {dur}"
    print("  ✓ chunker groups sentences into beats")


def test_trigger_sentence_starts_new_beat(S):
    text = "Reading feels productive and easy. In 1885 a psychologist demonstrated the forgetting curve."
    beats = S.chunk_segment(text, S.DEFAULT_WPS)
    # The 1885 sentence carries a year trigger → must not be merged with the prior.
    joined = [" ".join(b) for b in beats]
    assert any("1885" in j and "Reading feels" not in j for j in joined), joined
    print("  ✓ trigger sentence (year) starts a new beat")


# ---- triggers ----

def test_year_triggers_archival(S):
    t = S.detect_triggers("In 1885, a German psychologist named Hermann Ebbinghaus discovered the forgetting curve.")
    assert t.get("archival") is True
    print("  ✓ year → archival trigger")


def test_study_verb_triggers_archival(S):
    t = S.detect_triggers("Roediger and Karpicke demonstrated this in 2006.")
    assert t.get("archival") is True
    print("  ✓ name+study-verb → archival trigger")


def test_ordinal_principle_triggers_titlecard(S):
    t = S.detect_triggers("The first principle is Layered Encoding.")
    assert t.get("principle_titlecard") is True
    print("  ✓ ordinal principle → title card trigger")


def test_ai_tactical_triggers_ui_insert(S):
    t = S.detect_triggers("Ask the language model to generate three Socratic questions.")
    assert t.get("ui_insert") is True
    print("  ✓ AI + tactical → ui_insert trigger")


def test_percent_triggers_kinetic(S):
    t = S.detect_triggers("Within twenty-four hours, sixty-seven percent of what you learned is gone.")
    assert t.get("kinetic_text") is True
    print("  ✓ spelled-out percent → kinetic_text trigger")


# ---- hero cap ----

def test_no_hero_block_over_15s(flagship_sb):
    for b in flagship_sb["beats"]:
        if b["shot_type"] == "hero_lipsync":
            assert b["est_duration_sec"] <= 15.05, f"{b['beat_id']} hero {b['est_duration_sec']}s > 15"
    print("  ✓ no hero_lipsync beat exceeds 15s")


def test_max_hero_block_metric_within_cap(flagship_sb):
    assert flagship_sb["shot_mix_summary"]["max_hero_block_sec"] <= 15.05
    print("  ✓ max consecutive hero run ≤ 15s (Act-6 close excluded)")


# ---- flagship 001 specific assertions (blueprint T4) ----

def test_ebbinghaus_and_roediger_archival(flagship_sb):
    cites = [b["overlay"].get("text", "") for b in flagship_sb["beats"]
             if b["shot_type"] == "broll_archival"]
    blob = " ".join(c for c in cites if c)
    assert "1885" in blob or any("1885" in b["narration_text"] and b["shot_type"] == "broll_archival"
                                 for b in flagship_sb["beats"])
    assert "Roediger" in blob
    print(f"  ✓ archival beats produced for Ebbinghaus/1885 and Roediger/2006 ({cites})")


def test_principles_get_graphic_beats(flagship_sb):
    titlecards = [b for b in flagship_sb["beats"] if b["shot_type"] == "graphic_title_card"]
    assert len(titlecards) >= 2, "expected title cards for the principles"
    print(f"  ✓ {len(titlecards)} graphic title cards for principles")


def test_ai_section_has_ui_insert(flagship_sb):
    ui = [b for b in flagship_sb["beats"] if b["shot_type"] == "ui_insert"]
    assert len(ui) >= 1, "AI-prompt section should yield ≥1 ui_insert beat"
    print(f"  ✓ {len(ui)} ui_insert beats for the AI section")


def test_not_all_hero(flagship_sb):
    """The flagship-001 failure mode: every beat a James close-up. Must not recur."""
    hero = [b for b in flagship_sb["beats"] if b["shot_type"] in ("hero_lipsync", "hero_cutaway")]
    assert len(hero) < len(flagship_sb["beats"]) * 0.5, "too many hero beats — flagship-001 shape"
    print("  ✓ not an all-hero storyboard")


# ---- shot-mix bands (§7) ----

def test_shot_mix_bands(flagship_sb):
    m = flagship_sb["shot_mix_summary"]
    hero_total = m["hero_lipsync_pct"] + m["hero_cutaway_pct"]
    assert 25 <= hero_total <= 40, f"hero_total {hero_total}"
    assert m["hero_lipsync_pct"] <= 25
    assert m["broll_specific_pct"] >= 25
    assert m["graphics_ui_pct"] >= 10
    assert 5 <= m["broll_metaphorical_pct"] <= 15
    assert 2 <= m["kinetic_text_pct"] <= 8
    assert m["distinct_visual_setups"] >= 12
    print("  ✓ all §7 shot-mix bands satisfied")


def test_first_beat_is_hero(flagship_sb):
    assert flagship_sb["beats"][0]["shot_type"] in ("hero_lipsync", "hero_cutaway")
    print("  ✓ first beat is the host (hook)")


# ---- schema / structure ----

def test_schema_version_and_required_top_level(flagship_sb):
    for key in ("schema_version", "project_id", "video_type", "acts", "beats",
                "shot_mix_summary", "totals", "approval"):
        assert key in flagship_sb, f"missing top-level key {key}"
    assert flagship_sb["schema_version"] == "2.0"
    print("  ✓ schema-v2 top-level structure present")


def test_every_beat_has_required_fields(flagship_sb):
    req = ["beat_id", "segment_id", "act", "order", "narration_text", "est_duration_sec",
           "visual_function", "narrative_function", "shot_type", "asset_type",
           "model_tier", "model", "prompt_class", "visual_brief", "audio_mode",
           "lipsync_required", "crop_safety", "cost", "fallback", "approval", "qa"]
    for b in flagship_sb["beats"]:
        for k in req:
            assert k in b, f"beat {b.get('beat_id')} missing {k}"
    print("  ✓ every beat carries all required fields")


def test_broll_beats_have_specific_narrative_function(flagship_sb):
    for b in flagship_sb["beats"]:
        if b["shot_type"].startswith("broll"):
            nf = b["narrative_function"]
            assert nf and nf.lower() not in ("", "supporting visual"), b["beat_id"]
    print("  ✓ b-roll beats carry a specific narrative_function")


def test_no_banned_models(flagship_sb):
    for b in flagship_sb["beats"]:
        assert b["model"] not in S_BANNED, f"{b['beat_id']} routed to banned {b['model']}"
    print("  ✓ no beat routed to a banned model")


def test_local_graphics_cost_zero(flagship_sb):
    for b in flagship_sb["beats"]:
        if b["shot_type"] in ("graphic_progressive", "graphic_title_card", "kinetic_text", "ui_insert"):
            assert b["cost"]["est_usd"] == 0.0, f"{b['beat_id']} graphic should be $0"
    print("  ✓ local graphics/text beats cost $0")


def test_no_segment_visual_brief_copied(flagship_sb):
    """§3.14 #6: no beat's brief is a copy of the segment-level visual_brief."""
    script = json.loads(FLAGSHIP.read_text())
    seg_briefs = {s.get("visual_brief", "")[:60] for s in script["segments"]}
    for b in flagship_sb["beats"]:
        assert b["visual_brief"][:60] not in seg_briefs, f"{b['beat_id']} copies segment brief"
    print("  ✓ no beat copies the segment-level visual_brief")


S_BANNED = {"minimax_hailuo", "seedance_2_0_fast", "seedance1_5", "wan2_7", "wan2_6"}


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

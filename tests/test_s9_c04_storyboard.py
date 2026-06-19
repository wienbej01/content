"""S9-C04 — Canonical, band-compliant DB-native storyboard shot mix.

Defect (D-016): the DB path's `invoke_storyboard` was a simplified stub that
(a) discarded segment structure/role, (b) derived shot types in the WRONG
vocabulary (`talking_head_*` — not in `review_storyboard.VALID_SHOT_TYPES`),
(c) fell back uniformly to `talking_head_standard`, and (d) emitted no
schema-v2 structure, no shot_mix_summary, and no usable visual intent. The real
`ai_notes_teaser` storyboard was 4 beats of `talking_head_standard`; the
rule-based G2 gate (`review_storyboard`) would block on every beat.

Root cause: `invoke_storyboard` + `_derive_shot_type` in scripts/produce_db.py
produced a non-canonical, non-band-compliant stub. This suite pins the fix:
the DB storyboard must emit the canonical vocabulary in a `review_storyboard`
band-compliant mix, every beat carrying usable visual intent, with the
schema-v2 fields the G2 gate requires.

These tests exercise `invoke_storyboard` for real (no LLM — storyboarding is
deterministic structural assignment, Option B) and assert the produced
storyboard passes the rule-based `review_storyboard.review()` gate. No paid
calls; no mocks of the logic under test.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as _db
import produce_db
import review_storyboard as rs
from authoring_service import (
    save_research_brief,
    save_script,
    get_storyboard,
    get_creative_beats,
)


# --- fixtures -------------------------------------------------------------

def _seed(slug: str, video_type: str, segments: list[dict]) -> str:
    """Seed an isolated production with a research brief + structured script."""
    prod = _db.ensure_production(slug, seed=slug, video_type=video_type)
    assert prod is not None, f"ensure_production returned None for {slug}"
    pid = prod["id"]
    citations = [
        {"url": f"https://src.example/{i}", "title": f"src{i}",
         "source_type": "web", "is_primary": True}
        for i in range(3)
    ]
    save_research_brief(pid, {"title": slug, "summary": "context",
                              "sources": [], "key_claims": []}, citations=citations)
    save_script(pid, {"title": slug, "video_type": video_type,
                      "segments": segments})
    return pid


def _inputs(pid: str, slug: str, video_type: str) -> dict:
    return {"production_id": pid, "project_slug": slug,
            "seed": slug, "video_type": video_type}


def _storyboard(pid: str) -> dict:
    """Fetch the active storyboard, asserting it exists (fail loud, not None)."""
    sb = get_storyboard(pid)
    assert sb is not None, f"no storyboard persisted for {pid}"
    return sb


def _seg(label: str, text: str) -> dict:
    return {"label": label, "text": text, "visual_intent": {}}


# Equal-length (~12-word) narration so the duration-weighted shot-mix bands
# match the beat-count fractions the assignment targets.
_SHORT_SEGS = [
    _seg("B1", "Compound interest is the single most powerful force in all of personal finance today."),
    _seg("B2", "In 1926 a researcher named it the eighth wonder repeated over many long decades."),
    _seg("B3", "Your early earnings begin to generate their own fresh earnings each and every year."),
    _seg("B4", "A modest monthly deposit becomes a truly substantial final balance over thirty years."),
    _seg("B5", "Start investing early, stay fully consistent, and let long time frames compound relentlessly."),
]

# 13 segments so the explainer-scale distinct_visual_setups >= 12 band is met.
_EXPLAINER_SEGS = [
    _seg(f"S{i+1:02d}",
         f"Segment number {i+1} explains one concrete facet of the core idea quite clearly indeed.")
    for i in range(13)
]


@pytest.fixture
def _clean_dirs():
    yield
    import shutil
    for slug in ("c04_short", "c04_explainer", "c04_degenerate", "c04_persist"):
        p = ROOT / "Videos" / "Projects" / slug
        if p.exists():
            shutil.rmtree(p)


# --- band compliance ------------------------------------------------------

def test_db_storyboard_passes_bands_short(tmp_path, _clean_dirs):
    """A DB-produced short-form storyboard passes review_storyboard with NO
    blocking violations (the rule-based G2 gate). This is the core D-016 fix."""
    pid = _seed("c04_short", "short", _SHORT_SEGS)
    produce_db.invoke_storyboard(_inputs(pid, "c04_short", "short"), tmp_path)
    sb = _storyboard(pid)
    blocking, warnings, _ = rs.review(sb, rs.load_constraints())
    assert blocking == [], f"short storyboard should pass G2; blocking: {blocking}"


def test_db_storyboard_passes_bands_explainer(tmp_path, _clean_dirs):
    """The same assignment satisfies the strict explainer bands
    (distinct_visual_setups >= 12, broll >= 25%) — proving it is not tuned only
    for the relaxed short path."""
    pid = _seed("c04_explainer", "explainer", _EXPLAINER_SEGS)
    produce_db.invoke_storyboard(_inputs(pid, "c04_explainer", "explainer"), tmp_path)
    sb = _storyboard(pid)
    blocking, _, _ = rs.review(sb, rs.load_constraints())
    assert blocking == [], f"explainer storyboard should pass G2; blocking: {blocking}"


# --- canonical mix + visual intent ---------------------------------------

def test_canonical_mix_and_visual_intent(tmp_path, _clean_dirs):
    """>=1 hero_lipsync + >=1 broll_* + >=1 graphic_*, each with non-empty
    visual intent."""
    pid = _seed("c04_short", "short", _SHORT_SEGS)
    produce_db.invoke_storyboard(_inputs(pid, "c04_short", "short"), tmp_path)
    beats = _storyboard(pid)["beats"]

    def types(prefix):
        return [b for b in beats if b["shot_type"].startswith(prefix)]

    assert types("hero_lipsync"), "no hero_lipsync beat"
    assert any(b["shot_type"].startswith("broll") for b in beats), "no broll beat"
    assert any(b["shot_type"].startswith("graphic") or b["shot_type"] == "kinetic_text"
               for b in beats), "no graphic beat"
    # Every beat carries non-empty visual intent (the S9-C06 generation input).
    for b in beats:
        assert b.get("visual_intent"), f"{b.get('label')} has empty visual_intent"
        assert isinstance(b["visual_intent"], dict)
    # Every beat also carries a non-empty visual_brief (G2 anti-pattern #6).
    for b in beats:
        assert b.get("visual_brief", "").strip(), f"{b.get('label')} has empty visual_brief"


def test_no_legacy_vocabulary(tmp_path, _clean_dirs):
    """No talking_head_* (the legacy stub vocabulary) is emitted; all shot
    types are canonical."""
    pid = _seed("c04_short", "short", _SHORT_SEGS)
    produce_db.invoke_storyboard(_inputs(pid, "c04_short", "short"), tmp_path)
    beats = _storyboard(pid)["beats"]
    for b in beats:
        assert not b["shot_type"].startswith("talking_head"), \
            f"legacy vocab leaked: {b['shot_type']}"
        assert b["shot_type"] in rs.VALID_SHOT_TYPES, \
            f"non-canonical shot_type: {b['shot_type']}"


# --- persistence contract -------------------------------------------------

def test_fields_persisted_in_revision(tmp_path, _clean_dirs):
    """shot_type / visual_intent / graphics are retrievable both from the
    storyboard document revision and from the creative_beats projection that
    compile_media reads."""
    pid = _seed("c04_persist", "short", _SHORT_SEGS)
    produce_db.invoke_storyboard(_inputs(pid, "c04_persist", "short"), tmp_path)

    # Full payload (document_revisions) carries every field.
    beats = _storyboard(pid)["beats"]
    for b in beats:
        assert b["shot_type"] in rs.VALID_SHOT_TYPES
        assert b.get("visual_intent")
    graphic_beats = [b for b in beats
                     if b["shot_type"].startswith("graphic") or b["shot_type"] == "kinetic_text"]
    assert graphic_beats, "no graphic beat to exercise the graphics contract"
    for b in graphic_beats:
        assert b.get("graphics"), f"graphic beat {b.get('label')} has no graphics contract"
        assert b["graphics"].get("text"), "graphics contract missing exact text"

    # creative_beats projection (consumed by compile_media) carries shot_type,
    # visual_intent_json, graphics_json.
    rows = get_creative_beats(pid)
    assert rows
    for r in rows:
        assert r["shot_type"] in rs.VALID_SHOT_TYPES
        assert r["visual_intent_json"] not in (None, "", "{}"), \
            f"creative_beat {r['label']} visual_intent_json empty"
    assert any(r["graphics_json"] not in (None, "", "{}") for r in rows), \
        "no creative_beat carries a graphics contract"


# --- negative / degenerate ------------------------------------------------

def test_degenerate_single_segment_handled(tmp_path, _clean_dirs):
    """A single-segment script must not crash; it produces a defensible
    on-camera hero beat (canonical vocab)."""
    pid = _seed("c04_degenerate", "short", [_seg("B1", "One short sentence about a single idea.")])
    res = produce_db.invoke_storyboard(_inputs(pid, "c04_degenerate", "short"), tmp_path)
    assert res["status"] == "saved"
    beats = _storyboard(pid)["beats"]
    assert len(beats) == 1
    assert beats[0]["shot_type"] == "hero_lipsync"  # James present (not absent)
    assert beats[0]["shot_type"] in rs.VALID_SHOT_TYPES
    assert beats[0]["visual_intent"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

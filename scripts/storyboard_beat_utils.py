"""storyboard_beat_utils.py — shared beat-enrichment helpers.

Used by BOTH the production path (storyboard_projection.project_canonical) and
the test-mode path (produce_db.invoke_storyboard) so they never diverge — the
divergence was the root cause of REPAIR-TKT-601A, where the test path populated
narrative_function/order/act/est_duration_sec/narration_text/shot_mix_summary
but the production path did not, causing every real LLM storyboard to fail
review_storyboard structural validation.

All functions are deterministic (no LLM, no network, no IO).
"""
from __future__ import annotations


# Canonical shot-type properties (mirrors direct_storyboard.SHOT_ROUTING and
# produce_db._CANONICAL_SHOTS). Kept here so the helpers are self-contained.
_CANONICAL_SHOTS = {
    "hero_lipsync":        {"asset_type": "generated_video", "hero": True,  "graphic": False},
    "hero_cutaway":        {"asset_type": "generated_video", "hero": True,  "graphic": False},
    "broll_archival":      {"asset_type": "generated_video", "hero": False, "graphic": False},
    "broll_environment":   {"asset_type": "generated_video", "hero": False, "graphic": False},
    "broll_tactical":      {"asset_type": "generated_video", "hero": False, "graphic": False},
    "broll_metaphorical":  {"asset_type": "generated_video", "hero": False, "graphic": False},
    "graphic_progressive": {"asset_type": "local_graphic",   "hero": False, "graphic": True},
    "graphic_title_card":  {"asset_type": "local_graphic",   "hero": False, "graphic": True},
    "kinetic_text":        {"asset_type": "local_graphic",   "hero": False, "graphic": True},
    "still_kenburns":      {"asset_type": "generated_still", "hero": False, "graphic": False},
}

# Narration words -> seconds. Matches direct_storyboard._load_calibrated_wps
# (configs/voice_pacing.yaml calibrated_wps). Used only to size beats so the
# shot-mix DURATION bands are computable; generation-stage clamping is the
# generation stage's concern, not the storyboard schema's.
_NARRATION_WPS = 1.8077


def act_for(order: int, n: int) -> int:
    """Deterministic act assignment for a beat at position `order` of `n` beats.

    Act 1 = opening, Act 6 = closing. Matches produce_db._act_for exactly.
    """
    if n <= 1:
        return 6
    if order == n - 1:
        return 6  # closing beat
    return min(5, max(1, (order * 5) // max(1, n - 1) + 1))


def beat_duration_sec(narration_text: str) -> float:
    """Estimate beat duration from narration word count.

    Falls back to a 3s minimum for beats with no narration (b-roll, graphic).
    Matches produce_db._beat_duration_sec exactly.
    """
    words = len((narration_text or "").split())
    if not words:
        return 3.0
    return round(words / _NARRATION_WPS, 2)


def narrative_function_for(shot_type: str) -> str:
    """Specific (non-generic) narrative function per shot type.

    Satisfies review_storyboard._anti_patterns which rejects b-roll beats whose
    narrative_function is empty or one of ('supporting visual', 'b-roll',
    'supporting'). Matches produce_db._narrative_function_for exactly.
    """
    return {
        "hero_lipsync": "James addresses the viewer directly on camera.",
        "hero_cutaway": "Reinforce James's presence with a non-speaking reaction under voiceover.",
        "broll_archival": "Anchor the named evidence or date with a concrete archival visual.",
        "broll_environment": "Establish the real-world setting behind the spoken claim.",
        "broll_tactical": "Insert a concrete object that embodies the mechanism described.",
        "broll_metaphorical": "Externalize the abstract idea as an observational metaphor.",
        "graphic_progressive": "Render the framework or list as an on-screen progressive graphic.",
        "graphic_title_card": "Mark the section with a branded title card.",
        "kinetic_text": "Emphasize the key phrase as kinetic on-screen text.",
        "still_kenburns": "Hold a representative still with gentle motion.",
    }[shot_type]


def is_hero(shot_type: str) -> bool:
    return bool(_CANONICAL_SHOTS.get(shot_type, {}).get("hero", False))


def is_graphic(shot_type: str) -> bool:
    return bool(_CANONICAL_SHOTS.get(shot_type, {}).get("graphic", False))


def max_hero_chain_sec(beats: list[dict]) -> float:
    """Longest continuous hero (hero_lipsync/hero_cutaway) run in seconds.

    Mirrors review_storyboard._max_hero_chain for the non-Act-6 case.
    """
    ordered = sorted(beats, key=lambda b: b.get("order", 0))
    best = cur = 0.0
    for b in ordered:
        if is_hero(b.get("shot_type") or ""):
            cur += b.get("est_duration_sec", 0) or 0
            best = max(best, cur)
        else:
            cur = 0.0
    return round(best, 2)


def compute_mix_summary(beats: list[dict]) -> dict:
    """shot_mix_summary consumed by review_storyboard._bands_check.

    Percentages are duration-weighted (matching direct_storyboard.hydrate_beats).
    Matches produce_db._compute_mix_summary exactly.
    """
    total = sum((b.get("est_duration_sec", 0) or 0) for b in beats) or 1.0

    def pct(pred) -> float:
        s = sum((b.get("est_duration_sec", 0) or 0) for b in beats if pred(b))
        return round(100.0 * s / total, 1)

    return {
        "hero_lipsync_pct": pct(lambda b: b.get("shot_type") == "hero_lipsync"),
        "hero_cutaway_pct": pct(lambda b: b.get("shot_type") == "hero_cutaway"),
        "broll_specific_pct": pct(lambda b: (b.get("shot_type") or "").startswith("broll")),
        "broll_metaphorical_pct": pct(lambda b: b.get("shot_type") == "broll_metaphorical"),
        "graphics_ui_pct": pct(lambda b: is_graphic(b.get("shot_type") or "")),
        "kinetic_text_pct": pct(lambda b: b.get("shot_type") == "kinetic_text"),
        "max_hero_block_sec": max_hero_chain_sec(beats),
        "distinct_visual_setups": len(beats),
        "total_cuts_estimate": len(beats),
    }

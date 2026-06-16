#!/usr/bin/env python3
"""tests/test_uci05_text_policy.py — UCI-05: text_policy=out_of_focus broll must NOT be rerouted."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import compile_media_prompts as C


def _make_beat(bid, shot_type, visual_brief, text_policy=None,
               asset_type="generated_video", model="kling3_0"):
    beat = {
        "beat_id": bid,
        "shot_type": shot_type,
        "asset_type": asset_type,
        "model": model,
        "visual_brief": visual_brief,
        "est_duration_sec": 5,
        "narration_text": "test narration",
        "cost": {"est_clips": 1},
    }
    if text_policy is not None:
        beat["text_policy"] = text_policy
    return beat


def _constraints():
    return C.load_constraints()


def _routing():
    return C.load_routing()


class TestOutOfFocusBrollNotRerouted:
    """Broll with text_policy indicating no readable text must stay generated_video."""

    @pytest.mark.parametrize("policy", ["soft_focus_only", "out_of_focus", "none", "no_readable_text", "background"])
    def test_out_of_focus_broll_not_rerouted(self, policy):
        """B003-style: broll_environment with 'writing'/'document' + text_policy=out_of_focus stays generated_video."""
        beat = _make_beat(
            "B003", "broll_environment",
            "A clinician reviewing a printed document and writing a note with a pen, all text out of focus",
            text_policy=policy,
        )
        entry, errors, warnings = C.compile_beat(beat, _constraints(), _routing())
        assert entry["asset_type"] == "generated_video", (
            f"text_policy={policy} broll was wrongly rerouted: asset_type={entry['asset_type']}")
        assert entry["model"] != "local_graphic"
        # Should have a neutralization warning, not a reroute warning
        neutralized = [w for w in warnings if "neutralized" in w]
        assert neutralized, f"expected neutralization warning, got: {warnings}"
        rerouted = [w for w in warnings if "rerouted to local_graphic" in w]
        assert not rerouted, f"should NOT be rerouted: {rerouted}"


class TestReadableTextStillRerouted:
    """Beats WITHOUT a non-readable text_policy must still be rerouted."""

    def test_readable_text_still_rerouted(self):
        """A broll beat with no text_policy and 'laptop screen showing dashboard' -> rerouted."""
        beat = _make_beat(
            "B010", "broll_tactical",
            "laptop screen showing a financial dashboard with readable text",
        )
        entry, errors, warnings = C.compile_beat(beat, _constraints(), _routing())
        assert entry["asset_type"] == "local_graphic"
        rerouted = [w for w in warnings if "rerouted to local_graphic" in w]
        assert rerouted

    def test_empty_text_policy_still_rerouted(self):
        """A broll beat with text_policy='' (empty) and banned terms -> rerouted."""
        beat = _make_beat(
            "B011", "broll_environment",
            "close-up of handwriting in a notebook",
            text_policy="",
        )
        entry, errors, warnings = C.compile_beat(beat, _constraints(), _routing())
        assert entry["asset_type"] == "local_graphic"

    def test_post_overlay_text_policy_still_rerouted(self):
        """text_policy=post_overlay means text IS needed (added in post) — still reroute."""
        beat = _make_beat(
            "B012", "broll_tactical",
            "laptop screen showing a spreadsheet with data",
            text_policy="post_overlay",
        )
        entry, errors, warnings = C.compile_beat(beat, _constraints(), _routing())
        assert entry["asset_type"] == "local_graphic"


class TestUnreadableBriefInfersPolicy:
    """REGRESSION (2026-06-16): a broll beat with NO text_policy whose brief
    EXPLICITLY states the text is unreadable/out-of-focus/illegible must infer
    a no-readable-text policy and NEUTRALIZE (stay footage) — not reroute to a
    blank local_graphic (which renders a near-black frozen frame failing final QA).
    This is the using_ai_to_help_memory_retention_short B003/B005/B007 failure."""

    @pytest.mark.parametrize("brief", [
        "University library, a chat interface glows on the laptop screen — text deliberately out of focus and unreadable.",
        "A hand writes in a dark-cover notebook. Notebook text is intentionally illegible. No faces in frame.",
        "Professional writing in a notebook, lips moving as they recall. Notebook text unreadable, no readable screens.",
    ])
    def test_explicit_unreadable_brief_neutralizes(self, brief):
        beat = _make_beat("B003", "broll_environment", brief, text_policy=None)
        entry, errors, warnings = C.compile_beat(beat, _constraints(), _routing())
        assert entry["asset_type"] == "generated_video", \
            f"explicit-unreadable broll must stay footage, got {entry['asset_type']}"
        assert entry["model"] != "local_graphic"
        rerouted = [w for w in warnings if "rerouted to local_graphic" in w]
        assert not rerouted, f"must NOT reroute to local_graphic: {warnings}"

    def test_genuinely_readable_brief_still_reroutes(self):
        """Guard: the inference must NOT fire for briefs that genuinely need legible
        text — those must still reroute per UCI-05."""
        beat = _make_beat(
            "B010", "broll_tactical",
            "laptop screen showing a financial dashboard with readable text",
            text_policy=None,
        )
        entry, errors, warnings = C.compile_beat(beat, _constraints(), _routing())
        assert entry["asset_type"] == "local_graphic", \
            "a brief needing legible text must still reroute (UCI-05 intent preserved)"


class TestHeroUnaffected:
    """Hero beats with out_of_focus text_policy still use existing neutralization (no change)."""

    def test_hero_with_out_of_focus_unaffected(self):
        """Hero beats already neutralize — adding text_policy doesn't break them."""
        beat = _make_beat(
            "B020", "hero_lipsync",
            "James at desk with notebook visible in background",
            text_policy="soft_focus_only",
            asset_type="generated_video",
            model="seedance_2_0",
        )
        beat["reference_images"] = ["assets/reference/studio_library/canonical/STUDIO_CANONICAL_003_PATTERN_FRAME.jpg"]
        beat["lipsync_required"] = True
        entry, errors, warnings = C.compile_beat(beat, _constraints(), _routing())
        assert entry["asset_type"] == "generated_video"
        assert entry["model"] != "local_graphic"
        # Hero neutralization still works
        neutralized = [w for w in warnings if "hero neutralized" in w]
        assert neutralized


class TestNegativePromptGetsBannedTerms:
    """Out-of-focus broll must have the matched banned term negated."""

    def test_negative_prompt_gets_banned_terms(self):
        """The neutralized broll has banned terms added to its negative_prompt."""
        beat = _make_beat(
            "B003", "broll_environment",
            "A clinician reviewing a document and writing notes, all text out of focus",
            text_policy="soft_focus_only",
        )
        entry, errors, warnings = C.compile_beat(beat, _constraints(), _routing())
        neg = entry["negative_prompt"]
        # The matched term should be negated
        assert "no writing" in neg or "no document" in neg, f"banned term not in negative: {neg[:200]}"
        assert "no readable text" in neg, f"'no readable text' not in negative: {neg[:200]}"

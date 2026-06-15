"""PTC-FIX regression tests: 4 blocking defects in compile_media_prompts.py."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import compile_media_prompts as C


def _constraints():
    return C.load_constraints()


def _routing():
    return C.load_routing()


def _make_beat(bid, shot_type, visual_brief, asset_type="generated_video", model="kling_3_0"):
    return {
        "beat_id": bid,
        "shot_type": shot_type,
        "visual_brief": visual_brief,
        "asset_type": asset_type,
        "model": model,
        "est_duration_sec": 5.0,
    }


class TestDefect1_RerouteIsWarning:
    """Successful reroute to local_graphic must be a WARNING, not an error."""

    def test_successful_reroute_is_warning_not_error(self):
        beat = _make_beat("B003", "broll_tactical", "laptop screen showing stock charts")
        entry, errors, warnings = C.compile_beat(beat, _constraints(), _routing())
        # Must NOT be in errors
        policy_errs = [e for e in errors if "TEXT_SURFACE_POLICY" in e]
        assert not policy_errs, f"reroute should not produce errors: {policy_errs}"
        # Must be in warnings
        policy_warns = [w for w in warnings if "TEXT_SURFACE_POLICY" in w]
        assert policy_warns, f"reroute should produce a warning"
        assert "rerouted to local_graphic" in policy_warns[0]
        assert entry["asset_type"] == "local_graphic"


class TestDefect2_HeroCutawayNeutralized:
    """hero_cutaway with banned term → neutralize in negative_prompt, not hard error."""

    def test_hero_cutaway_text_term_neutralized(self):
        beat = _make_beat("B001", "hero_cutaway", "James writing in notebook at desk",
                          asset_type="generated_video", model="kling_3_0")
        beat["reference_images"] = ["assets/reference/studio_library/canonical/STUDIO_CANONICAL_003_PATTERN_FRAME.jpg"]
        entry, errors, warnings = C.compile_beat(beat, _constraints(), _routing())
        # No hard error for hero_cutaway
        policy_errs = [e for e in errors if "TEXT_SURFACE_POLICY" in e]
        assert not policy_errs, f"hero_cutaway should not hard-error: {policy_errs}"
        # Warning present
        policy_warns = [w for w in warnings if "TEXT_SURFACE_POLICY" in w]
        assert policy_warns, f"hero_cutaway neutralization should produce a warning"
        assert "neutralized" in policy_warns[0]
        # Banned term added to negative_prompt
        assert "no notebook" in entry["negative_prompt"]

    def test_hero_lipsync_text_term_neutralized(self):
        """hero_lipsync with text-surface term → neutralized in negative_prompt, NOT hard error.
        Hero shots are talking-head (James to camera); any 'notebook' is set decoration,
        not instructional readable text. The model renders a person, not a text surface."""
        beat = _make_beat("B020", "hero_lipsync",
                          "James pointing at notebook with visible handwriting",
                          asset_type="generated_video", model="seedance_2_0")
        beat["reference_images"] = ["assets/reference/studio_library/canonical/STUDIO_CANONICAL_003_PATTERN_FRAME.jpg"]
        beat["lipsync_required"] = True
        entry, errors, warnings = C.compile_beat(beat, _constraints(), _routing())
        policy_errs = [e for e in errors if "TEXT_SURFACE_POLICY" in e]
        policy_warns = [w for w in warnings if "TEXT_SURFACE_POLICY" in w]
        assert not policy_errs, f"hero_lipsync should NOT hard-error on set decoration: {policy_errs}"
        assert policy_warns, f"should neutralize with warning: {warnings}"


class TestDefect3_GraphicsPlural:
    """Canonical 'graphics' (plural list) must be carried through compile."""

    def test_graphics_plural_read_by_compile(self):
        beat = _make_beat("B010", "graphic_progressive", "framework diagram",
                          asset_type="local_graphic", model="local_graphic")
        beat["graphics"] = [
            {"type": "framework_diagram", "required": True, "layout": "thirds"},
            {"type": "data_chart", "required": True, "layout": "full"},
        ]
        entry, errors, warnings = C.compile_beat(beat, _constraints(), _routing())
        assert entry["graphics"] == beat["graphics"]

    def test_singular_graphic_fallback(self):
        """Old-style singular 'graphic' dict is wrapped into a list."""
        beat = _make_beat("B011", "graphic_progressive", "title card",
                          asset_type="local_graphic", model="local_graphic")
        beat["graphic"] = {"type": "title_card", "required": True, "layout": "center"}
        entry, errors, warnings = C.compile_beat(beat, _constraints(), _routing())
        assert entry["graphics"] == [beat["graphic"]]


class TestDefect4_MissingAudioSlice:
    """Missing audio_slice is NOT an error when slice_lipsync is downstream."""

    def test_missing_audio_slice_not_error_when_slice_downstream(self):
        beats = [
            {
                "beat_id": "B001",
                "shot_type": "hero_lipsync",
                "visual_brief": "James at desk",
                "asset_type": "generated_video",
                "model": "seedance_2_0",
                "est_duration_sec": 6.0,
                "lipsync_required": True,
                "reference_images": ["assets/reference/studio_library/canonical/STUDIO_CANONICAL_003_PATTERN_FRAME.jpg"],
                "source_beat_id": "SB001",
                # NO audio_slice — this is expected pre-slice_lipsync
            },
        ]
        storyboard = {
            "beats": beats,
            "project_id": "test",
            "reconciled_from": "test_sb",
        }
        plan, errors = C.compile_plan(storyboard, _constraints(), _routing())
        # Must NOT have an audio_slice error
        slice_errs = [e for e in errors if "audio_slice" in e]
        assert not slice_errs, f"missing audio_slice should not be an error: {slice_errs}"
        # Should be in warnings
        slice_warns = [w for w in plan.get("warnings", []) if "audio_slice" in w]
        assert slice_warns, "missing audio_slice should produce a warning"


class TestAuditedPreview:
    """The real audited production storyboard must compile with 0 errors."""

    def test_audited_preview_compiles_clean(self):
        preview_path = Path(__file__).resolve().parent.parent / \
            "reports/remediation/post_tts_corrective/audited_project_preview/production_storyboard.preview.json"
        if not preview_path.exists():
            pytest.skip("audited preview not available")
        prod = json.loads(preview_path.read_text())
        plan, errors = C.compile_plan(prod, _constraints(), _routing())
        assert errors == [], f"compile_plan should produce 0 errors on audited preview: {errors[:5]}"
        # Verify graphics carried
        graphics_beats = [b for b in plan.get("beats", []) if b.get("graphics")]
        assert graphics_beats, "graphics should be carried through compile"
        # Verify warnings present (not suppressed)
        assert plan.get("warnings"), "warnings should be present for reroutes/sliceless"

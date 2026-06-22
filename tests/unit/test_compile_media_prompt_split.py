"""ENG-0301/0302/0303: Render metadata split + prompt sanitizer + deterministic text routing.

Tests:
  - Metadata split helpers (get_provider_visual_prompt, get_deterministic_text_spec)
  - Prompt sanitizer (sanitize_provider_visual_prompt)
  - Deterministic text spec routing (_compose_generation_prompt)
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from production_repo import get_deterministic_text_spec, get_provider_visual_prompt
from media_contract import (
    PROMPT_TEXT_RISK_KEYWORDS,
    sanitize_provider_visual_prompt,
    assert_provider_prompt_text_free,
    MediaContractError,
)


# =========================================================================
# ENG-0301: Render metadata split helpers
# =========================================================================

class TestGetProviderVisualPrompt:
    def test_returns_provider_visual_prompt_when_present(self):
        md = {"provider_visual_prompt": "Cinematic shot of an office", "prompt": "old prompt"}
        assert get_provider_visual_prompt(md) == "Cinematic shot of an office"

    def test_falls_back_to_prompt(self):
        md = {"prompt": "Cinematic shot of an office"}
        assert get_provider_visual_prompt(md) == "Cinematic shot of an office"

    def test_returns_none_when_no_prompt(self):
        assert get_provider_visual_prompt({}) is None

    def test_deterministic_text_spec_not_confused_with_prompt(self):
        md = {
            "provider_visual_prompt": "Cinematic establishing shot",
            "deterministic_text_spec": {"type": "source_card", "text": "HBR 2026"},
        }
        assert get_provider_visual_prompt(md) == "Cinematic establishing shot"
        assert get_deterministic_text_spec(md) == {"type": "source_card", "text": "HBR 2026"}


class TestGetDeterministicTextSpec:
    def test_returns_spec_when_present(self):
        md = {"deterministic_text_spec": {"type": "title_card", "headline": "James"}}
        assert get_deterministic_text_spec(md) == {"type": "title_card", "headline": "James"}

    def test_returns_none_when_not_present(self):
        assert get_deterministic_text_spec({"prompt": "hello"}) is None

    def test_returns_none_for_empty_dict(self):
        assert get_deterministic_text_spec({}) is None


# =========================================================================
# ENG-0302: Prompt sanitizer
# =========================================================================

class TestSanitizeProviderVisualPrompt:
    def test_title_card_returns_none(self):
        """Title card prompt routes to deterministic text spec."""
        result = sanitize_provider_visual_prompt("Title card: I'M JAMES HARRINGTON. MCKINSEY'S")
        assert result is None

    def test_lower_third_returns_none(self):
        result = sanitize_provider_visual_prompt("Lower third: James Harrington")
        assert result is None

    def test_source_card_returns_none(self):
        result = sanitize_provider_visual_prompt("Source card: Harvard Business Review 2026")
        assert result is None

    def test_hbr_narrative_is_sanitized(self):
        """HBR embedded in narrative is removed, text-free safeguard added."""
        result = sanitize_provider_visual_prompt(
            "As Harvard Business Review put it in 2026, productivity is up."
        )
        assert result is not None
        assert "harvard business review" not in result.lower()
        assert "Harvard Business Review" not in result
        assert "No screens, documents" in result
        # Result passes the prompt-risk guard
        assert_provider_prompt_text_free(result)

    def test_mckinsey_in_prompt_is_sanitized(self):
        result = sanitize_provider_visual_prompt(
            "McKinsey's latest research shows productivity gains."
        )
        assert result is not None
        assert "mckinsey" not in result.lower()
        assert "No screens, documents" in result
        assert_provider_prompt_text_free(result)

    def test_clean_prompt_returns_as_is(self):
        result = sanitize_provider_visual_prompt(
            "Cinematic establishing shot of a modern office with warm lighting"
        )
        assert result is not None
        assert "No screens" not in result
        assert_provider_prompt_text_free(result)

    def test_empty_prompt_returns_empty(self):
        assert sanitize_provider_visual_prompt("") == ""
        assert sanitize_provider_visual_prompt(None) is None

    def test_sanitized_prompt_passes_guard(self):
        """Sanitized result must pass assert_provider_prompt_text_free."""
        cases = [
            "Cinematic establishing shot",
            "Text-free visual metaphor for productivity",
            "Warm office scene with bookshelves in background",
        ]
        for c in cases:
            result = sanitize_provider_visual_prompt(c)
            assert result is not None
            assert_provider_prompt_text_free(result)


# =========================================================================
# ENG-0303: Deterministic text spec routing (_compose_generation_prompt)
# =========================================================================

class TestComposeGenerationPrompt:
    """Tests the _compose_generation_prompt function from produce_db.py."""

    @pytest.fixture(autouse=True)
    def _import(self):
        # Import inside fixture to handle sys.path correctly
        from produce_db import _compose_generation_prompt
        self._compose = _compose_generation_prompt

    def test_graphic_text_content_returns_deterministic_spec(self):
        """Graphic text content produces a deterministic_text_spec, no visual prompt."""
        visual_intent = {}
        result = self._compose(visual_intent, "broll", "I'M JAMES HARRINGTON")
        pvp, dts, asset_override = result
        assert pvp is None
        assert dts is not None
        assert dts["type"] == "title_card"
        assert "JAMES HARRINGTON" in dts["text"]
        assert asset_override == "local_graphic"

    def test_hbr_content_becomes_source_card(self):
        visual_intent = {}
        result = self._compose(visual_intent, "broll", "Harvard Business Review 2026 study")
        pvp, dts, asset_override = result
        assert pvp is None
        assert dts is not None
        assert dts["type"] == "source_card"
        assert asset_override == "local_graphic"

    def test_mckinsey_content_becomes_source_card(self):
        visual_intent = {}
        result = self._compose(visual_intent, "broll", "McKinsey latest research")
        pvp, dts, asset_override = result
        assert dts is not None
        assert dts["type"] == "source_card"

    def test_hero_lipsync_returns_visual_prompt(self):
        """Hero lipsync without graphic text returns a visual prompt."""
        visual_intent = {
            "visual_function": "illustrate",
            "narrative_claim": "Productivity is rising",
            "information_to_show": "a chart going up",
            "viewer_takeaway": "people work smarter now",
        }
        result = self._compose(visual_intent, "hero_lipsync", None)
        pvp, dts, asset_override = result
        assert pvp is not None
        assert "Photorealistic cinematic" in pvp
        assert dts is None
        assert asset_override is None

    def test_broll_returns_visual_prompt(self):
        """B-roll without graphic text returns a visual prompt."""
        visual_intent = {
            "visual_function": "illustrate",
            "narrative_claim": "Modern offices are changing",
            "viewer_takeaway": "workspace design matters",
        }
        result = self._compose(visual_intent, "broll", None)
        pvp, dts, asset_override = result
        assert pvp is not None
        assert "Cinematic" in pvp
        assert dts is None
        assert asset_override is None

    def test_provider_visual_prompt_is_text_free(self):
        """Composed visual prompt passes the text-free guard."""
        visual_intent = {
            "visual_function": "illustrate",
            "narrative_claim": "Productivity is rising in modern workplaces",
            "viewer_takeaway": "people work smarter",
        }
        result = self._compose(visual_intent, "broll", None)
        pvp, dts, asset_override = result
        assert pvp is not None
        assert_provider_prompt_text_free(pvp)

    def test_hbr_in_narrative_claim_is_sanitized(self):
        """HBR reference in narrative_claim is sanitized away."""
        visual_intent = {
            "visual_function": "illustrate",
            "narrative_claim": "As Harvard Business Review put it in 2026",
            "viewer_takeaway": "productivity is rising",
        }
        result = self._compose(visual_intent, "broll", None)
        pvp, dts, asset_override = result
        assert pvp is not None
        assert "Harvard Business Review" not in pvp
        assert_provider_prompt_text_free(pvp)

    def test_no_prompt_for_pure_text_shot(self):
        """A beat whose sole purpose is text display returns None visual prompt."""
        visual_intent = {
            "visual_function": "display_text",
            "narrative_claim": "Title card: Welcome",
        }
        result = self._compose(visual_intent, "broll", None)
        pvp, dts, asset_override = result
        # The sanitizer catches "Title card:" → returns None
        assert pvp is None
        assert asset_override == "local_graphic"


# =========================================================================
# Forward-integration: metadata_json stores split fields
# =========================================================================

class TestMetadataSplitInPlanRenderUnits:
    """Verifies that plan_render_units stores the split metadata fields."""

    def test_provider_visual_prompt_stored_in_metadata(self):
        import production_db as _db
        from production_repo import plan_render_units, commit_timeline_spans

        prod = _db.ensure_production("test_meta_split_pvp")
        spans = commit_timeline_spans(
            prod["id"],
            [{"label": "T001", "start_ms": 0, "end_ms": 5000}],
        )
        units = plan_render_units(
            prod["id"],
            [{
                "span_id": spans[0]["id"],
                "asset_type": "generated_video",
                "model": "kling3_0",
                "audio_policy": "BROLL_FLEX",
                "final_audio_source": "none",
                "provider_audio_usage": "discarded",
                "text_policy": "NO_VISIBLE_TEXT",
                "visual_function": "illustrate",
                "narrative_claim": "Productivity is rising",
                "information_to_show": "office workers at desks",
                "viewer_takeaway": "people work smarter",
                "required_action": "slow pan across office",
                "distinctness_requirement": "bright modern office with natural light",
                "semantic_acceptance_criteria": "matches productivity theme",
                "concept_key": "prod_office",
                "concept_hash": "prod_office",
                "provider_visual_prompt": "Cinematic office scene",
                "prompt": "Cinematic office scene",
            }],
        )
        meta = json.loads(units[0]["metadata_json"])
        assert meta.get("provider_visual_prompt") == "Cinematic office scene"
        assert meta.get("prompt") == "Cinematic office scene"

    def test_deterministic_text_spec_stored_in_metadata(self):
        import production_db as _db
        from production_repo import plan_render_units, commit_timeline_spans

        prod = _db.ensure_production("test_meta_split_dts")
        spans = commit_timeline_spans(
            prod["id"],
            [{"label": "T001", "start_ms": 0, "end_ms": 5000}],
        )
        dts = {"type": "source_card", "headline": "Harvard Business Review", "text": "Harvard Business Review 2026"}
        units = plan_render_units(
            prod["id"],
            [{
                "span_id": spans[0]["id"],
                "asset_type": "local_graphic",
                "model": None,
                "audio_policy": "SILENT_GRAPHIC",
                "final_audio_source": "none",
                "provider_audio_usage": "discarded",
                "text_policy": "DETERMINISTIC_GRAPHIC",
                "visual_function": "display_text",
                "deterministic_text_spec": dts,
            }],
        )
        meta = json.loads(units[0]["metadata_json"])
        assert meta.get("deterministic_text_spec") == dts
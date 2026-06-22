"""Unit tests for scripts/media_contract.py.

Covers provider eligibility, local-renderer requirements,
render-method classification, and the provider-eligibility guard.
"""

import pytest

from scripts.media_contract import (
    PROVIDER_ELIGIBLE_ASSET_TYPES,
    PROVIDER_FORBIDDEN_ASSET_TYPES,
    MediaContractError,
    assert_provider_eligible,
    assert_provider_prompt_text_free,
    classify_render_method,
    detect_provider_prompt_text_risks,
    is_provider_eligible_asset_type,
    is_provider_forbidden_asset_type,
    normalize_asset_type,
    requires_local_renderer,
)


class TestNormalizeAssetType:
    def test_none_returns_empty(self):
        assert normalize_asset_type(None) == ""

    def test_empty_returns_empty(self):
        assert normalize_asset_type("") == ""

    def test_lowercases(self):
        assert normalize_asset_type("LOCAL_GRAPHIC") == "local_graphic"

    def test_strips_whitespace(self):
        assert normalize_asset_type("  lipsync_video  ") == "lipsync_video"

    def test_hyphens_to_underscores(self):
        assert normalize_asset_type("lipsync-video") == "lipsync_video"

    def test_spaces_to_underscores(self):
        assert normalize_asset_type("local graphic") == "local_graphic"


class TestIsProviderEligibleAssetType:
    def test_lipsync_video_eligible(self):
        assert is_provider_eligible_asset_type("lipsync_video") is True

    def test_generated_video_eligible(self):
        assert is_provider_eligible_asset_type("generated_video") is True

    def test_broll_video_eligible(self):
        assert is_provider_eligible_asset_type("broll_video") is True

    def test_atmospheric_video_eligible(self):
        assert is_provider_eligible_asset_type("atmospheric_video") is True

    def test_local_graphic_not_eligible(self):
        assert is_provider_eligible_asset_type("local_graphic") is False

    def test_title_card_not_eligible(self):
        assert is_provider_eligible_asset_type("title_card") is False

    def test_lower_third_not_eligible(self):
        assert is_provider_eligible_asset_type("lower_third") is False

    def test_none_not_eligible(self):
        assert is_provider_eligible_asset_type(None) is False

    def test_empty_not_eligible(self):
        assert is_provider_eligible_asset_type("") is False

    def test_unknown_type_not_eligible(self):
        assert is_provider_eligible_asset_type("unknown_type") is False


class TestIsProviderForbiddenAssetType:
    def test_local_graphic_forbidden(self):
        assert is_provider_forbidden_asset_type("local_graphic") is True

    def test_title_card_forbidden(self):
        assert is_provider_forbidden_asset_type("title_card") is True

    def test_lower_third_forbidden(self):
        assert is_provider_forbidden_asset_type("lower_third") is True

    def test_source_card_forbidden(self):
        assert is_provider_forbidden_asset_type("source_card") is True

    def test_quote_card_forbidden(self):
        assert is_provider_forbidden_asset_type("quote_card") is True

    def test_researcher_card_forbidden(self):
        assert is_provider_forbidden_asset_type("researcher_card") is True

    def test_framework_card_forbidden(self):
        assert is_provider_forbidden_asset_type("framework_card") is True

    def test_chart_forbidden(self):
        assert is_provider_forbidden_asset_type("chart") is True

    def test_diagram_forbidden(self):
        assert is_provider_forbidden_asset_type("diagram") is True

    def test_caption_forbidden(self):
        assert is_provider_forbidden_asset_type("caption") is True

    def test_subtitle_forbidden(self):
        assert is_provider_forbidden_asset_type("subtitle") is True

    def test_lipsync_video_not_forbidden(self):
        assert is_provider_forbidden_asset_type("lipsync_video") is False

    def test_generated_video_not_forbidden(self):
        assert is_provider_forbidden_asset_type("generated_video") is False

    def test_none_is_forbidden(self):
        assert is_provider_forbidden_asset_type(None) is True

    def test_empty_is_forbidden(self):
        assert is_provider_forbidden_asset_type("") is True


class TestRequiresLocalRenderer:
    def test_local_graphic_requires_local(self):
        assert requires_local_renderer("local_graphic") is True

    def test_title_card_requires_local(self):
        assert requires_local_renderer("title_card") is True

    def test_lower_third_requires_local(self):
        assert requires_local_renderer("lower_third") is True

    def test_lipsync_video_does_not_require_local(self):
        assert requires_local_renderer("lipsync_video") is False

    def test_generated_video_does_not_require_local(self):
        assert requires_local_renderer("generated_video") is False

    def test_deterministic_graphic_policy_forces_local(self):
        assert requires_local_renderer("generated_video", text_policy="DETERMINISTIC_GRAPHIC") is True

    def test_none_type_requires_local(self):
        assert requires_local_renderer(None) is True

    def test_empty_type_requires_local(self):
        assert requires_local_renderer("") is True

    def test_unknown_type_does_not_require_local_without_policy(self):
        assert requires_local_renderer("unknown_type") is False


class TestClassifyRenderMethod:
    def test_lipsync_video_is_hero_lipsync(self):
        assert classify_render_method("lipsync_video") == "hero_lipsync"

    def test_generated_video_is_generated_video(self):
        assert classify_render_method("generated_video") == "generated_video"

    def test_broll_video_is_generated_video(self):
        assert classify_render_method("broll_video") == "generated_video"

    def test_local_graphic_is_deterministic_graphic(self):
        assert classify_render_method("local_graphic") == "deterministic_graphic"

    def test_title_card_is_deterministic_graphic(self):
        assert classify_render_method("title_card") == "deterministic_graphic"

    def test_still_kenburns_is_still_kenburns(self):
        assert classify_render_method("still_kenburns") == "still_kenburns"

    def test_deterministic_policy_overrides_provider_eligible(self):
        assert classify_render_method("generated_video", text_policy="DETERMINISTIC_GRAPHIC") == "deterministic_graphic"


class TestAssertProviderEligible:
    def test_lipsync_video_passes(self):
        assert_provider_eligible({"asset_type": "lipsync_video"})

    def test_generated_video_passes(self):
        assert_provider_eligible({"asset_type": "generated_video"})

    def test_local_graphic_raises(self):
        with pytest.raises(MediaContractError) as exc:
            assert_provider_eligible({"asset_type": "local_graphic"})
        assert "BLOCKED" in str(exc.value)
        assert "local_graphic" in str(exc.value)

    def test_title_card_raises(self):
        with pytest.raises(MediaContractError) as exc:
            assert_provider_eligible({"asset_type": "title_card"})
        assert "BLOCKED" in str(exc.value)

    def test_lower_third_raises(self):
        with pytest.raises(MediaContractError):
            assert_provider_eligible({"asset_type": "lower_third"})

    def test_none_asset_type_raises(self):
        with pytest.raises(MediaContractError) as exc:
            assert_provider_eligible({})
        assert "BLOCKED" in str(exc.value)

    def test_message_includes_asset_type(self):
        with pytest.raises(MediaContractError) as exc:
            assert_provider_eligible({"asset_type": "local_graphic"})
        msg = str(exc.value)
        assert "asset_type=local_graphic" in msg


class TestDetectProviderPromptTextRisks:
    def test_title_card_fails(self):
        reasons = detect_provider_prompt_text_risks(
            "Title card: I'M JAMES HARRINGTON. MCKINSEY'S"
        )
        assert len(reasons) >= 1
        assert any("title card" in r for r in reasons)

    def test_hbr_fails(self):
        reasons = detect_provider_prompt_text_risks(
            "As Harvard Business Review put it in 2026"
        )
        assert len(reasons) >= 1
        assert any("harvard business review" in r for r in reasons)

    def test_mckinsey_fails(self):
        reasons = detect_provider_prompt_text_risks(
            "McKinsey's latest research"
        )
        assert len(reasons) >= 1
        assert any("mckinsey" in r for r in reasons)

    def test_text_free_passes(self):
        reasons = detect_provider_prompt_text_risks(
            "Text-free cinematic office metaphor"
        )
        assert reasons == []

    def test_none_returns_empty(self):
        assert detect_provider_prompt_text_risks(None) == []

    def test_empty_returns_empty(self):
        assert detect_provider_prompt_text_risks("") == []

    def test_returns_useful_reason_strings(self):
        reasons = detect_provider_prompt_text_risks("Show title card and caption")
        assert len(reasons) >= 2
        for r in reasons:
            assert "exact-text risk" in r
            assert "found keyword" in r

    def test_stanford_detected(self):
        reasons = detect_provider_prompt_text_risks(
            "A Stanford researcher presents the study title"
        )
        assert len(reasons) >= 1


class TestAssertProviderPromptTextFree:
    def test_forensic_title_card_raises(self):
        with pytest.raises(MediaContractError) as exc:
            assert_provider_prompt_text_free(
                "Title card: I'M JAMES HARRINGTON. MCKINSEY'S"
            )
        msg = str(exc.value)
        assert "BLOCKED" in msg
        assert "provider prompt contains exact-text risk" in msg

    def test_forensic_hbr_raises(self):
        with pytest.raises(MediaContractError):
            assert_provider_prompt_text_free(
                "As Harvard Business Review put it in 2026"
            )

    def test_clean_prompt_passes(self):
        assert_provider_prompt_text_free(
            "Cinematic wide shot of a modern office"
        )

    def test_none_prompt_passes(self):
        assert_provider_prompt_text_free(None)

    def test_empty_prompt_passes(self):
        assert_provider_prompt_text_free("")
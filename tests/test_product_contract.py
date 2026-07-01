import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from product_contract import (
    HERO_PROVIDER_AUDIO_ISLAND,
    VIDEO_ONLY_OVER_CANONICAL_NARRATION,
    ProductContractError,
    resolve_product_audio_policy,
    validate_corporate_broll_contract,
    validate_hero_provider_audio_island,
    validate_no_narration_tail_cut,
    validate_text_graphic_provenance,
    validate_video_only_over_narration,
)


def test_hero_provider_audio_island_requires_provider_synced_artifact(tmp_path):
    artifact = tmp_path / "hero_provider.mp4"
    artifact.write_bytes(b"placeholder")
    ru = {
        "id": "S000",
        "audio_policy": "HERO_SYNC_LOCKED",
        "product_audio_policy": HERO_PROVIDER_AUDIO_ISLAND,
        "provider_audio_usage": "diagnostic_only",
        "final_audio_source": "master_narration",
    }

    assert resolve_product_audio_policy(ru) == HERO_PROVIDER_AUDIO_ISLAND
    validate_hero_provider_audio_island(ru, str(artifact))

    with pytest.raises(ProductContractError, match="ARTIFACT_MISSING"):
        validate_hero_provider_audio_island(ru, None)


def test_video_only_over_canonical_narration_rejects_provider_audio_final_mix():
    ru = {
        "id": "S001",
        "audio_policy": "BROLL_FLEX",
        "product_audio_policy": VIDEO_ONLY_OVER_CANONICAL_NARRATION,
        "asset_type": "generated_video",
        "provider_audio_usage": "final_mix",
    }

    with pytest.raises(ProductContractError, match="VIDEO_ONLY_SEGMENT_USES_PROVIDER_AUDIO"):
        validate_video_only_over_narration(ru)


def test_transition_cannot_cut_narration_tail():
    validate_no_narration_tail_cut(audio_duration_ms=6060, video_duration_ms=6060)
    with pytest.raises(ProductContractError, match="NARRATION_TAIL_CUT"):
        validate_no_narration_tail_cut(audio_duration_ms=8080, video_duration_ms=7471)


def test_text_graphic_requires_deterministic_renderer_provenance():
    ru = {
        "id": "S003",
        "asset_type": "local_graphic",
        "metadata_json": json.dumps({
            "deterministic_text_spec": {"text": "More output or better outcomes?"}
        }),
    }
    good_meta = {
        "render_method": "local_graphic",
        "renderer": "render_graphics.py",
        "expected_text": ["More output or better outcomes?"],
        "text_spec_sha256": "abc123",
    }
    validate_text_graphic_provenance(ru, good_meta)

    with pytest.raises(ProductContractError, match="MISSING_DETERMINISTIC_PROVENANCE"):
        validate_text_graphic_provenance(ru, {"render_method": "ai_video"})


def test_sci_fi_broll_rejected_for_corporate_education():
    ru = {
        "id": "S001",
        "asset_type": "generated_video",
        "audio_policy": "BROLL_FLEX",
        "product_audio_policy": VIDEO_ONLY_OVER_CANONICAL_NARRATION,
        "metadata_json": json.dumps({
            "prompt": "A cyberpunk hologram robot in a glowing AI brain data tunnel",
            "broll_contract": {
                "beat_text": "UC Berkeley Haas found speed crowded out reflection",
                "narrative_text": "UC Berkeley Haas found speed crowded out reflection",
                "literal_visual_brief": "A senior manager pauses over a notebook before a meeting",
                "allowed_subjects": ["manager", "notebook", "meeting room"],
                "forbidden_subjects": ["sci-fi", "robots", "holograms"],
                "style_constraints": ["real corporate office", "natural light"],
                "semantic_relevance_evidence": "Shows deliberate pause before work",
                "reviewer_verdict": "pass",
            },
        }),
    }

    with pytest.raises(ProductContractError, match="BROLL_FORBIDDEN_SUBJECTS"):
        validate_corporate_broll_contract(ru)


def test_grounded_broll_contract_passes():
    ru = {
        "id": "S001",
        "asset_type": "generated_video",
        "audio_policy": "BROLL_FLEX",
        "product_audio_policy": VIDEO_ONLY_OVER_CANONICAL_NARRATION,
        "metadata_json": json.dumps({
            "prompt": "A senior manager pauses over a notebook in a quiet meeting room",
            "broll_contract": {
                "beat_text": "UC Berkeley Haas found speed crowded out reflection",
                "narrative_text": "UC Berkeley Haas found speed crowded out reflection",
                "literal_visual_brief": "A senior manager pauses over a notebook before answering",
                "allowed_subjects": ["manager", "notebook", "meeting room"],
                "forbidden_subjects": ["sci-fi", "robots", "holograms"],
                "style_constraints": ["real corporate office", "natural light"],
                "semantic_relevance_evidence": "The pause visualizes reflection being protected",
                "reviewer_verdict": "pass",
            },
        }),
    }

    assert validate_corporate_broll_contract(ru)["status"] == "pass"

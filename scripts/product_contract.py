"""Product contract checks for DB-native video assembly.

These checks encode the policy exposed by the Seedance truth test without
changing provider behavior or adding a parallel manifest authority.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


HERO_PROVIDER_AUDIO_ISLAND = "HERO_PROVIDER_AUDIO_ISLAND"
VIDEO_ONLY_OVER_CANONICAL_NARRATION = "VIDEO_ONLY_OVER_CANONICAL_NARRATION"
SILENT_VISUAL = "SILENT_VISUAL"

PRODUCT_AUDIO_POLICIES = frozenset({
    HERO_PROVIDER_AUDIO_ISLAND,
    VIDEO_ONLY_OVER_CANONICAL_NARRATION,
    SILENT_VISUAL,
})

LEGACY_AUDIO_POLICY_MAP = {
    "HERO_SYNC_LOCKED": HERO_PROVIDER_AUDIO_ISLAND,
    "keep_lipsync": HERO_PROVIDER_AUDIO_ISLAND,
    "hero_lipsync": HERO_PROVIDER_AUDIO_ISLAND,
    "baked_in": HERO_PROVIDER_AUDIO_ISLAND,
    "generated_tts": HERO_PROVIDER_AUDIO_ISLAND,
    "BROLL_FLEX": VIDEO_ONLY_OVER_CANONICAL_NARRATION,
    "BROLL_SYNCED_ACTION": VIDEO_ONLY_OVER_CANONICAL_NARRATION,
    "AMBIENCE_OR_SFX": VIDEO_ONLY_OVER_CANONICAL_NARRATION,
    "narration_overlay": VIDEO_ONLY_OVER_CANONICAL_NARRATION,
    "strip": VIDEO_ONLY_OVER_CANONICAL_NARRATION,
    "SILENT_GRAPHIC": VIDEO_ONLY_OVER_CANONICAL_NARRATION,
    "MUSIC_BED": SILENT_VISUAL,
    "silent": SILENT_VISUAL,
    "ambient": SILENT_VISUAL,
}

CORPORATE_FORBIDDEN_BROLL_TERMS = frozenset({
    "sci-fi",
    "scifi",
    "science fiction",
    "cyberpunk",
    "robot",
    "robots",
    "hologram",
    "holograms",
    "glowing ai brain",
    "glowing brain",
    "ai brain",
    "fantasy data tunnel",
    "data tunnel",
    "futuristic tunnel",
    "neon",
})


class ProductContractError(ValueError):
    """Raised when media state violates the product contract."""


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("metadata_json") or row.get("metadata") or {}
    if isinstance(meta, dict):
        return meta
    try:
        return json.loads(meta or "{}")
    except (TypeError, ValueError):
        return {}


def resolve_product_audio_policy(render_unit: dict[str, Any]) -> str:
    """Resolve the explicit product policy, falling back to legacy aliases."""
    explicit = render_unit.get("product_audio_policy")
    if explicit:
        if explicit not in PRODUCT_AUDIO_POLICIES:
            raise ProductContractError(f"invalid product_audio_policy: {explicit}")
        return explicit

    meta = _metadata(render_unit)
    meta_policy = meta.get("product_audio_policy")
    if meta_policy:
        if meta_policy not in PRODUCT_AUDIO_POLICIES:
            raise ProductContractError(f"invalid metadata product_audio_policy: {meta_policy}")
        return meta_policy

    legacy = render_unit.get("audio_policy")
    try:
        return LEGACY_AUDIO_POLICY_MAP[legacy]
    except KeyError as exc:
        raise ProductContractError(f"unknown audio policy: {legacy}") from exc


def assembly_mode_for_product_policy(product_audio_policy: str) -> str:
    if product_audio_policy == HERO_PROVIDER_AUDIO_ISLAND:
        return "hero_island"
    if product_audio_policy == VIDEO_ONLY_OVER_CANONICAL_NARRATION:
        return "canonical_narration_video_only"
    if product_audio_policy == SILENT_VISUAL:
        return "silent_visual"
    raise ProductContractError(f"unknown product audio policy: {product_audio_policy}")


def validate_hero_provider_audio_island(render_unit: dict[str, Any], compensated_artifact_path: str | None) -> None:
    """Hero islands must have a provider-synced artifact and cannot use raw master audio."""
    policy = resolve_product_audio_policy(render_unit)
    if policy != HERO_PROVIDER_AUDIO_ISLAND:
        return
    if not compensated_artifact_path:
        raise ProductContractError("BLOCKED_HERO_PROVIDER_AUDIO_ARTIFACT_MISSING")
    if not Path(compensated_artifact_path).exists():
        raise ProductContractError(f"BLOCKED_HERO_PROVIDER_AUDIO_ARTIFACT_FILE_MISSING: {compensated_artifact_path}")

    final_audio = render_unit.get("final_audio_source")
    provider_usage = render_unit.get("provider_audio_usage")
    # Legacy rows may still say master_narration/diagnostic_only. The resolved
    # product policy is stricter for assembly: use the provider-synced artifact.
    if final_audio == "master_narration" and provider_usage == "discarded":
        raise ProductContractError("BLOCKED_HERO_PROVIDER_AUDIO_DISCARDED")


def validate_video_only_over_narration(render_unit: dict[str, Any]) -> None:
    policy = resolve_product_audio_policy(render_unit)
    if policy != VIDEO_ONLY_OVER_CANONICAL_NARRATION:
        return
    if render_unit.get("provider_audio_usage") == "final_mix":
        raise ProductContractError("BLOCKED_VIDEO_ONLY_SEGMENT_USES_PROVIDER_AUDIO")


def validate_no_narration_tail_cut(audio_duration_ms: int, video_duration_ms: int, *, tolerance_ms: int = 80) -> None:
    """Block segment operations that end before the required audio tail."""
    if video_duration_ms + tolerance_ms < audio_duration_ms:
        raise ProductContractError(
            f"BLOCKED_NARRATION_TAIL_CUT: video={video_duration_ms}ms audio={audio_duration_ms}ms"
        )


def _flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_flatten_text(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten_text(v) for v in value)
    return str(value)


def validate_corporate_broll_contract(render_unit: dict[str, Any]) -> dict[str, Any]:
    """Require grounded corporate b-roll and reject sci-fi/futuristic concepts."""
    policy = resolve_product_audio_policy(render_unit)
    if policy != VIDEO_ONLY_OVER_CANONICAL_NARRATION:
        return {"applicable": False}
    if render_unit.get("asset_type") not in {"generated_video", "generated_still", "broll", "local_visual"}:
        return {"applicable": False}

    meta = _metadata(render_unit)
    contract = meta.get("broll_contract") or {}
    prompt_text = _flatten_text({
        "prompt": meta.get("prompt"),
        "provider_visual_prompt": meta.get("provider_visual_prompt"),
        "literal_visual_brief": contract.get("literal_visual_brief"),
        "allowed_subjects": contract.get("allowed_subjects"),
        "style_constraints": contract.get("style_constraints"),
    }).lower()

    hits = sorted(term for term in CORPORATE_FORBIDDEN_BROLL_TERMS if re.search(rf"\b{re.escape(term)}\b", prompt_text))
    if hits:
        raise ProductContractError(f"BLOCKED_BROLL_FORBIDDEN_SUBJECTS: {', '.join(hits)}")

    required = [
        "beat_text",
        "narrative_text",
        "literal_visual_brief",
        "allowed_subjects",
        "forbidden_subjects",
        "style_constraints",
        "semantic_relevance_evidence",
        "reviewer_verdict",
    ]
    missing = [key for key in required if not contract.get(key)]
    if missing:
        raise ProductContractError(f"BLOCKED_BROLL_CONTRACT_INCOMPLETE: {', '.join(missing)}")
    if str(contract.get("reviewer_verdict")).lower() not in {"pass", "approved", "grounded"}:
        raise ProductContractError("BLOCKED_BROLL_REVIEWER_VERDICT_NOT_PASS")
    return {"applicable": True, "status": "pass"}


def validate_text_graphic_provenance(render_unit: dict[str, Any], artifact_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Text-bearing graphics must be local deterministic renders with text metadata."""
    meta = _metadata(render_unit)
    dts = meta.get("deterministic_text_spec")
    has_text = bool(render_unit.get("graphic_text_content") or dts)
    if not has_text:
        return {"applicable": False}
    artifact_metadata = artifact_metadata or {}
    render_method = artifact_metadata.get("render_method")
    renderer = artifact_metadata.get("renderer")
    expected_text = artifact_metadata.get("expected_text")
    text_sha = artifact_metadata.get("text_spec_sha256")

    if render_unit.get("asset_type") != "local_graphic":
        raise ProductContractError("BLOCKED_TEXT_GRAPHIC_NOT_LOCAL")
    if render_method not in {"local_graphic", "deterministic_graphic"}:
        raise ProductContractError("BLOCKED_TEXT_GRAPHIC_MISSING_DETERMINISTIC_PROVENANCE")
    if not renderer or not str(renderer).endswith("render_graphics.py"):
        raise ProductContractError("BLOCKED_TEXT_GRAPHIC_UNKNOWN_RENDERER")
    if not expected_text or not text_sha:
        raise ProductContractError("BLOCKED_TEXT_GRAPHIC_MISSING_SOURCE_TEXT_METADATA")
    return {"applicable": True, "status": "pass"}

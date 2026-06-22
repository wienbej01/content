"""Pure-python media-contract rules: provider eligibility, text-risk classification.

No DB imports. All functions are deterministic given their inputs.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

PROVIDER_ELIGIBLE_ASSET_TYPES: frozenset[str] = frozenset({
    "lipsync_video",
    "generated_video",
    "broll_video",
    "atmospheric_video",
})

PROVIDER_FORBIDDEN_ASSET_TYPES: frozenset[str] = frozenset({
    "local_graphic",
    "title_card",
    "lower_third",
    "source_card",
    "quote_card",
    "researcher_card",
    "framework_card",
    "chart",
    "diagram",
    "caption",
    "subtitle",
})

DETERMINISTIC_TEXT_POLICIES: frozenset[str] = frozenset({
    "DETERMINISTIC_GRAPHIC",
})

RENDER_METHOD_GENERATED_VIDEO = "generated_video"
RENDER_METHOD_HERO_LIPSYNC = "hero_lipsync"
RENDER_METHOD_DETERMINISTIC_GRAPHIC = "deterministic_graphic"
RENDER_METHOD_STILL_KENBURNS = "still_kenburns"

PROMPT_TEXT_RISK_KEYWORDS: list[str] = [
    "title card",
    "lower third",
    "source card",
    "quote card",
    "caption",
    "subtitle",
    "show text",
    "display text",
    "text overlay",
    "harvard business review",
    "mckinsey",
    "stanford",
    "mit",
    "researcher",
    "study title",
    "chart label",
]


class MediaContractError(RuntimeError):
    """Raised when a render unit violates the media contract."""


def normalize_asset_type(asset_type: str | None) -> str:
    """Normalize an asset type string to canonical form."""
    if not asset_type:
        return ""
    text = asset_type.strip().lower()
    text = text.replace("-", "_").replace(" ", "_")
    return text


def is_provider_eligible_asset_type(asset_type: str | None) -> bool:
    """True if the given asset type may be sent to a paid provider."""
    norm = normalize_asset_type(asset_type)
    return norm in PROVIDER_ELIGIBLE_ASSET_TYPES


def is_provider_forbidden_asset_type(asset_type: str | None) -> bool:
    """True if the given asset type must never be sent to a paid provider."""
    norm = normalize_asset_type(asset_type)
    if not norm:
        return True
    return norm in PROVIDER_FORBIDDEN_ASSET_TYPES


def requires_local_renderer(
    asset_type: str | None,
    text_policy: str | None = None,
) -> bool:
    """True if the render unit must be rendered locally.

    Local rendering is required when:
    - The asset type is in the provider-forbidden set (exact-text / graphics).
    - The text policy is DETERMINISTIC_GRAPHIC (exact text must be composited locally).
    """
    norm_type = normalize_asset_type(asset_type)
    if not norm_type:
        return True
    if norm_type in PROVIDER_FORBIDDEN_ASSET_TYPES:
        return True
    if text_policy and text_policy.strip().upper() in DETERMINISTIC_TEXT_POLICIES:
        return True
    return False


def classify_render_method(
    asset_type: str,
    audio_policy: str | None = None,
    text_policy: str | None = None,
) -> str:
    """Classify a render unit to its concrete render method.

    Returns one of:
      - "hero_lipsync"        for lipsync-video units (provider-generated)
      - "deterministic_graphic" for exact-text / local-graphic units
      - "still_kenburns"      for still-image ken-burns units
      - "generated_video"     for standard provider-generated video
    """
    norm_type = normalize_asset_type(asset_type)

    if requires_local_renderer(norm_type, text_policy):
        return RENDER_METHOD_DETERMINISTIC_GRAPHIC

    if norm_type == "lipsync_video":
        return RENDER_METHOD_HERO_LIPSYNC

    if norm_type == "still_kenburns":
        return RENDER_METHOD_STILL_KENBURNS

    return RENDER_METHOD_GENERATED_VIDEO


def assert_provider_eligible(render_unit_or_payload: Mapping[str, Any]) -> None:
    """Raise MediaContractError if the render unit is not provider-eligible.

    The error message starts with 'BLOCKED:' for consistency with
    other pipeline guards.
    """
    asset_type = normalize_asset_type(
        render_unit_or_payload.get("asset_type")
    )

    if not asset_type:
        raise MediaContractError(
            f"BLOCKED: render unit is not provider eligible: "
            f"asset_type is empty or None"
        )

    if not is_provider_eligible_asset_type(asset_type):
        raise MediaContractError(
            f"BLOCKED: render unit is not provider eligible: "
            f"asset_type={asset_type}"
        )


def detect_provider_prompt_text_risks(prompt: str | None) -> list[str]:
    """Check a provider prompt for exact-text risks.

    Returns a list of human-readable reason strings for each
    detected risk keyword. Returns an empty list when the prompt
    is clean, None, or empty — the caller decides whether a
    missing prompt is an error.
    """
    if not prompt:
        return []
    prompt_lower = prompt.lower()
    reasons: list[str] = []
    for keyword in PROMPT_TEXT_RISK_KEYWORDS:
        if keyword in prompt_lower:
            reasons.append(
                f"provider prompt contains exact-text risk: found keyword "
                f"{keyword!r} in prompt"
            )
    return reasons


def assert_provider_prompt_text_free(prompt: str | None) -> None:
    """Raise MediaContractError if the prompt contains text risks.

    A None or empty prompt is considered clean and passes
    without raising.
    """
    reasons = detect_provider_prompt_text_risks(prompt)
    if reasons:
        raise MediaContractError(
            "BLOCKED: provider prompt contains exact-text risk. "
            + "; ".join(reasons)
        )


# ---------------------------------------------------------------------------
# S3-C03 (ENG-0302): Prompt sanitizer for provider visuals
# ---------------------------------------------------------------------------

TEXT_FREE_SAFEGUARD = (
    "No screens, documents, visible writing, labels, charts, "
    "or readable text of any kind in the frame."
)

# Patterns that indicate the prompt is purely about displaying exact text
_EXACT_TEXT_TRIGGERS = [
    "title card:",
    "lower third:",
    "source card:",
    "quote card:",
]


def sanitize_provider_visual_prompt(
    raw_text: str, *, text_policy: str = "NO_VISIBLE_TEXT"
) -> str | None:
    """Sanitize a raw prompt for use as a provider visual prompt.

    Returns:
      - ``None`` if the prompt is purely about exact-text display (title cards,
        lower thirds, etc.) and should be routed to ``deterministic_text_spec``.
      - A sanitized text-free prompt string for visual generation.
      - The original prompt if it already passes the prompt-risk guard.

    The sanitizer:
      1. Detects exact-text display instructions → returns None.
      2. Removes embedded exact-text keywords (source names, study labels)
         from prompt fragments.
      3. Appends TEXT_FREE_SAFEGUARD when exact-text fragments were removed.
      4. Runs ``assert_provider_prompt_text_free`` on the result.
    """
    if not raw_text:
        return raw_text

    raw_lower = raw_text.lower().strip()

    # Step 1: Detect text-display instructions anywhere in the prompt.
    # This catches both "Title card: James" standalone and
    # "Cinematic shot. Title card: James" in composed prompts.
    has_text_display = False
    for trigger in _EXACT_TEXT_TRIGGERS:
        if trigger in raw_lower:
            has_text_display = True
            break
    # Also check for generic text-display instructions
    for keyword in ("show text", "display text", "text overlay"):
        if keyword in raw_lower:
            has_text_display = True
            break

    if has_text_display:
        return None

    # Step 2: Check for embedded exact-text risks
    risks = detect_provider_prompt_text_risks(raw_text)

    # Step 3: No risks — return as-is
    if not risks:
        return raw_text

    # Step 4: Remove exact-text fragments from the prompt
    sanitized = raw_text
    for keyword in PROMPT_TEXT_RISK_KEYWORDS:
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        sanitized = pattern.sub("", sanitized)
    # Clean up double spaces and leading/trailing whitespace
    sanitized = " ".join(sanitized.split())

    if not sanitized:
        return None

    sanitized = sanitized + " " + TEXT_FREE_SAFEGUARD

    # Step 5: Verify the result passes the guard
    assert_provider_prompt_text_free(sanitized)
    return sanitized
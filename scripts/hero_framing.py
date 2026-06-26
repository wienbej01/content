"""Hero framing metadata module for S14_T002.

Provides hero framing metadata management for render_units, including:
- Hero framing validation (close, medium, wide)
- Effective framing resolution with fail-closed defaults
- Policy name mapping from hero framing
- Integration with render_units metadata
"""

from typing import Optional, Literal
from dataclasses import dataclass
import production_db as _db


# Valid hero framing values
HeroFraming = Literal["close", "medium", "wide"]

# Default framing for hero units with missing metadata
DEFAULT_HERO_FRAMING: HeroFraming = "close"

# Audio policies that require hero framing
HERO_AUDIO_POLICIES = {"HERO_SYNC_LOCKED", "keep_lipsync", "hero_lipsync"}


@dataclass
class HeroFramingMetadata:
    """Hero framing metadata for a render unit."""

    hero_framing: Optional[HeroFraming]
    effective_framing: HeroFraming
    policy_name: str
    is_hero_unit: bool
    requires_framing: bool
    source: str  # "explicit", "default", "not_required"


def normalize_hero_framing(value: Optional[str]) -> Optional[HeroFraming]:
    """Normalize hero framing value to valid enum.

    Args:
        value: Raw hero framing value (close, medium, wide, or NULL/invalid)

    Returns:
        Normalized value (close, medium, wide) or None if value is None/empty

    Raises:
        ValueError: If value is explicitly invalid (not None/empty and not close/medium/wide)
    """
    if value is None or value == "":
        return None

    normalized = value.strip().lower()
    valid_values = {"close", "medium", "wide"}

    if normalized not in valid_values:
        raise ValueError(
            f"BLOCKED_INVALID_HERO_FRAMING: invalid hero_framing '{value}'. "
            f"Valid values: close, medium, wide, or NULL"
        )

    return normalized  # type: ignore


def get_effective_hero_framing(
    hero_framing: Optional[str],
    audio_policy: Optional[str] = None,
    lipsync_required: Optional[bool] = None,
) -> HeroFramingMetadata:
    """Get effective hero framing with fail-closed defaults.

    Rules:
    1. Hero units (HERO_SYNC_LOCKED/hero_lipsync/lipsync_required=True) require framing.
    2. Missing hero_framing for hero units defaults to 'close' (fail-closed).
    3. Non-hero units (BROLL_FLEX) don't require framing.
    4. Invalid hero_framing raises ValueError.

    Args:
        hero_framing: The hero_framing value from render_units (close, medium, wide, or NULL)
        audio_policy: The audio_policy from render_units
        lipsync_required: The lipsync_required flag from render_units

    Returns:
        HeroFramingMetadata with effective framing and policy mapping

    Raises:
        ValueError: If hero_framing is explicitly invalid
    """
    # Determine if this is a hero unit
    is_hero = (
        (audio_policy in HERO_AUDIO_POLICIES)
        or (lipsync_required is True)
    )

    # Non-hero units don't require framing
    if not is_hero:
        return HeroFramingMetadata(
            hero_framing=None,
            effective_framing="close",  # Unused for non-hero
            policy_name="diagnostic_legacy",  # Should not be used for non-hero
            is_hero_unit=False,
            requires_framing=False,
            source="not_required"
        )

    # Hero units require framing - validate and normalize
    normalized = normalize_hero_framing(hero_framing)

    # Default to 'close' for missing hero framing (fail-closed)
    effective = normalized if normalized is not None else DEFAULT_HERO_FRAMING
    source = "explicit" if normalized is not None else "default"

    # Map hero framing to policy name
    policy_map = {
        "close": "close_hero",
        "medium": "medium_hero",
        "wide": "wide_hero",  # wide_hero maps to medium_hero in policy config
    }
    policy_name = policy_map.get(effective, "close_hero")

    return HeroFramingMetadata(
        hero_framing=normalized,
        effective_framing=effective,
        policy_name=policy_name,
        is_hero_unit=True,
        requires_framing=True,
        source=source
    )


def get_render_unit_hero_framing(
    render_unit_id: str,
    db_path: Optional[str] = None,
) -> HeroFramingMetadata:
    """Get hero framing metadata for a render unit from the database.

    Args:
        render_unit_id: The render unit ID
        db_path: Optional database path (defaults to production_db default)

    Returns:
        HeroFramingMetadata with effective framing and policy mapping

    Raises:
        ValueError: If hero_framing is explicitly invalid
        FileNotFoundError: If render unit not found
    """
    conn = _db.connect(db_path)

    unit = conn.execute(
        """SELECT hero_framing, audio_policy, lipsync_required
           FROM render_units
           WHERE id=?""",
        (render_unit_id,)
    ).fetchone()

    conn.close()

    if not unit:
        raise ValueError(f"Render unit not found: {render_unit_id}")

    return get_effective_hero_framing(
        hero_framing=unit["hero_framing"],
        audio_policy=unit["audio_policy"],
        lipsync_required=bool(unit["lipsync_required"]),
    )


def hero_framing_to_policy_name(hero_framing: HeroFraming) -> str:
    """Map hero framing value to policy name.

    Args:
        hero_framing: The hero framing value (close, medium, wide)

    Returns:
        Policy name (close_hero, medium_hero, wide_hero)
    """
    policy_map = {
        "close": "close_hero",
        "medium": "medium_hero",
        "wide": "wide_hero",
    }
    return policy_map.get(hero_framing, "close_hero")


def policy_name_to_hero_framing(policy_name: str) -> Optional[HeroFraming]:
    """Map policy name back to hero framing value.

    Args:
        policy_name: The policy name (close_hero, medium_hero, wide_hero)

    Returns:
        Hero framing value (close, medium, wide) or None if not a hero policy
    """
    framing_map: dict[str, HeroFraming] = {
        "close_hero": "close",
        "medium_hero": "medium",
        "wide_hero": "wide",
    }
    return framing_map.get(policy_name)


# Constants for code reference
CLOSE_FRAMING: HeroFraming = "close"
MEDIUM_FRAMING: HeroFraming = "medium"
WIDE_FRAMING: HeroFraming = "wide"

"""Shot-mix contract validation for video format enforcement.

S15-T001: Define format-level shot-mix contract to prevent wrong editorial
structure from passing assembly.
"""

from __future__ import annotations

import yaml
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

# Path to shot-mix contract configuration
CONTRACTS_CONFIG_PATH = Path(__file__).parent.parent / "configs" / "video_format_contracts.yaml"

# Default contract for formats without explicit contract
DEFAULT_CONTRACT_NAME = "short_educational"


@dataclass
class ShotMixContract:
    """A shot-mix contract defining minimum requirements for a video format."""

    format_name: str
    description: str
    publish_grade: bool = True
    min_shots: Dict[str, int] = None  # type: ignore[assignment]
    rules: Dict[str, Any] = None  # type: ignore[assignment]
    shot_classification: Dict[str, Dict[str, Any]] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.min_shots is None:
            self.min_shots = {}  # type: ignore[assignment]
        if self.rules is None:
            self.rules = {}  # type: ignore[assignment]
        if self.shot_classification is None:
            self.shot_classification = {}  # type: ignore[assignment]


class ShotMixVerdict:
    """Verdict for shot-mix contract validation."""

    def __init__(
        self,
        passes: bool,
        expected: Dict[str, int],
        actual: Dict[str, int],
        violations: List[str],
        contract_name: str,
    ):
        self.passes = passes
        self.expected = expected
        self.actual = actual
        self.violations = violations
        self.contract_name = contract_name

    def to_dict(self) -> Dict[str, Any]:
        """Convert verdict to dict for evidence/JSON."""
        return {
            "passes": self.passes,
            "contract_name": self.contract_name,
            "expected": self.expected,
            "actual": self.actual,
            "violations": self.violations,
        }


def load_contracts() -> Dict[str, ShotMixContract]:
    """Load all shot-mix contracts from config file.

    Returns:
        Dict mapping contract name to ShotMixContract instance.

    Raises:
        FileNotFoundError: If contracts config file doesn't exist.
        ValueError: If config is malformed.
    """
    if not CONTRACTS_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"BLOCKED_SHOT_MIX_CONTRACT_CONFIG_MISSING: Shot-mix contracts config not found: {CONTRACTS_CONFIG_PATH}"
        )

    with open(CONTRACTS_CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    if not config or "version" not in config:
        raise ValueError(
            f"BLOCKED_SHOT_MIX_CONTRACT_CONFIG_INVALID: Config must have 'version' field"
        )

    contracts = {}
    for key, value in config.items():
        if key == "version":
            continue

        if not isinstance(value, dict):
            continue

        try:
            contracts[key] = ShotMixContract(
                format_name=value.get("format_name", key),
                description=value.get("description", ""),
                publish_grade=value.get("publish_grade", True),
                min_shots=value.get("min_shots", {}),
                rules=value.get("rules", {}),
                shot_classification=value.get("shot_classification", {}),
            )
        except Exception as e:
            raise ValueError(
                f"BLOCKED_SHOT_MIX_CONTRACT_CONFIG_INVALID: Invalid contract '{key}': {e}"
            )

    return contracts


def get_contract(contract_name: Optional[str] = None) -> ShotMixContract:
    """Get a specific shot-mix contract by name.

    Args:
        contract_name: Name of contract to load. Defaults to DEFAULT_CONTRACT_NAME.

    Returns:
        ShotMixContract instance.

    Raises:
        ValueError: If contract name is not found.
    """
    if contract_name is None:
        contract_name = DEFAULT_CONTRACT_NAME

    contracts = load_contracts()

    if contract_name not in contracts:
        available = ", ".join(sorted(contracts.keys()))
        raise ValueError(
            f"BLOCKED_SHOT_MIX_CONTRACT_UNKNOWN: Unknown contract '{contract_name}'. "
            f"Available contracts: {available}"
        )

    return contracts[contract_name]


def classify_render_unit(unit: Dict[str, Any], contract: ShotMixContract) -> Optional[str]:
    """Classify a render unit into shot type (hero_lipsync, broll, graphic, other).

    Args:
        unit: Render unit dict with keys: asset_type, audio_policy, shot_type, etc.
        contract: ShotMixContract instance with classification rules.

    Returns:
        Shot type string ('hero_lipsync', 'broll', 'graphic', 'other') or None if unclassified.
    """
    audio_policy = unit.get("audio_policy", "")
    asset_type = unit.get("asset_type", "")
    shot_type = unit.get("shot_type", "")

    # Check each shot classification in order
    for shot_type_name, classification in contract.shot_classification.items():
        # Check if this unit matches the classification

        # Check asset_type if specified
        if "asset_type" in classification:
            allowed_types = classification["asset_type"]
            if isinstance(allowed_types, str):
                allowed_types = [allowed_types]
            if asset_type not in allowed_types:
                continue

        # Check audio_policy if specified
        if "audio_policy" in classification:
            allowed_policies = classification["audio_policy"]
            if isinstance(allowed_policies, str):
                allowed_policies = [allowed_policies]
            if audio_policy not in allowed_policies:
                continue

        # Check shot_type if specified
        if "shot_type" in classification and shot_type:
            # Only check shot_type if the unit has a non-empty shot_type
            allowed_shot_types = classification["shot_type"]
            if isinstance(allowed_shot_types, str):
                allowed_shot_types = [allowed_shot_types]
            if shot_type not in allowed_shot_types:
                continue

        # Check exclusion rules
        if classification.get("exclude_hero_policies", False):
            hero_policies = ["HERO_SYNC_LOCKED", "keep_lipsync", "hero_lipsync"]
            if audio_policy in hero_policies:
                continue

        # Unit matches this classification
        return shot_type_name

    # No classification matched
    return None


def validate_shot_mix(
    units: List[Dict[str, Any]],
    contract_name: Optional[str] = None,
) -> ShotMixVerdict:
    """Validate shot-mix contract against render units.

    Args:
        units: List of render unit dicts.
        contract_name: Name of contract to apply. Defaults to DEFAULT_CONTRACT_NAME.
        video_type: Optional video type from production (may override contract selection).

    Returns:
        ShotMixVerdict instance with pass/fail and details.

    Raises:
        ValueError: If contract config is invalid or missing.
    """
    contract = get_contract(contract_name)

    # Count shots by type
    shot_counts: Dict[str, int] = {
        "hero_lipsync": 0,
        "broll": 0,
        "graphic": 0,
        "other": 0,
    }

    # Track consecutive hero segments for editorial break validation
    consecutive_hero_count = 0
    max_consecutive_hero_seen = 0  # Track the maximum seen, not just final
    max_consecutive_hero = contract.rules.get("max_consecutive_hero", 999)

    # Track first unit for opening hero validation
    first_unit_is_hero = False

    for i, unit in enumerate(units):
        shot_type = classify_render_unit(unit, contract)

        if shot_type is None:
            shot_type = "other"

        shot_counts[shot_type] = shot_counts.get(shot_type, 0) + 1

        # Track consecutive hero segments
        if shot_type == "hero_lipsync":
            consecutive_hero_count += 1
            if consecutive_hero_count > max_consecutive_hero_seen:
                max_consecutive_hero_seen = consecutive_hero_count
        else:
            consecutive_hero_count = 0

        # Check first unit for opening hero requirement
        if i == 0 and shot_type == "hero_lipsync":
            first_unit_is_hero = True

    # Build expected vs actual
    expected = contract.min_shots.copy()
    actual = {k: shot_counts.get(k, 0) for k in expected.keys()}

    # Check minimum requirements
    violations: List[str] = []

    for shot_type, min_count in expected.items():
        actual_count = actual.get(shot_type, 0)
        if actual_count < min_count:
            violations.append(
                f"{shot_type}: expected >= {min_count}, actual {actual_count}"
            )

    # Check editorial rules
    if contract.rules.get("opening_must_be_hero", False):
        if not first_unit_is_hero:
            violations.append(
                "opening segment must be hero (talking head) unless explicitly waived"
            )

    if max_consecutive_hero_seen > max_consecutive_hero:
        violations.append(
            f"too many consecutive hero segments ({max_consecutive_hero_seen} > {max_consecutive_hero})"
        )

    passes = len(violations) == 0

    return ShotMixVerdict(
        passes=passes,
        expected=expected,
        actual=actual,
        violations=violations,
        contract_name=contract_name or DEFAULT_CONTRACT_NAME,
    )

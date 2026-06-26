"""Tiered lip-sync policy module for S14_T001.

Defines publish-grade thresholds for close_hero, medium_hero, and diagnostic_legacy.
Provides policy evaluation functions that return verdict (pass/warn/fail) with
publish_grade flag.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass


# Default policy for unknown hero framing
DEFAULT_POLICY = "close_hero"


@dataclass
class LipSyncPolicy:
    """Lip-sync policy definition."""

    name: str
    description: str
    publish_grade: bool

    # Offset thresholds in milliseconds
    pass_ms: float
    warn_ms: float
    fail_ms: float

    # Minimum SyncNet confidence (0.0-3.0 scale)
    min_confidence: float

    # Frame-based thresholds (40ms per frame @ 25fps)
    pass_frames: float
    warn_frames: float
    fail_frames: float

    # Non-publish marker
    non_publish_only: bool = False


class LipSyncVerdict:
    """Result of lip-sync policy evaluation."""

    def __init__(
        self,
        policy_name: str,
        offset_ms: float,
        confidence: Optional[float],
        verdict: Literal["pass", "warn", "fail"],
        publish_grade: bool,
        reason: str,
    ):
        self.policy_name = policy_name
        self.offset_ms = offset_ms
        self.confidence = confidence
        self.verdict = verdict
        self.publish_grade = publish_grade
        self.reason = reason

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "policy_name": self.policy_name,
            "offset_ms": self.offset_ms,
            "offset_frames": round(self.offset_ms / 40.0, 2) if self.offset_ms is not None else None,
            "confidence": self.confidence,
            "verdict": self.verdict,
            "publish_grade": self.publish_grade,
            "reason": self.reason,
        }


def load_policy_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load lipsync policy configuration from YAML.

    Args:
        config_path: Path to lipsync_thresholds.yaml. Defaults to configs/lipsync_thresholds.yaml.

    Returns:
        Parsed configuration dict.

    Raises:
        FileNotFoundError: If config file not found.
        yaml.YAMLError: If config is invalid.
    """
    if config_path is None:
        config_path = Path(__file__).resolve().parent.parent / "configs" / "lipsync_thresholds.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Policy config not found: {config_path}")

    with open(config_path) as f:
        config = yaml.safe_load(f)

    return config


def get_policy(policy_name: str, config: Optional[Dict[str, Any]] = None) -> LipSyncPolicy:
    """Get a lip-sync policy by name.

    Args:
        policy_name: Name of policy (close_hero, medium_hero, wide_hero, diagnostic_legacy).
        config: Optional pre-loaded config dict.

    Returns:
        LipSyncPolicy object.

    Raises:
        ValueError: If policy_name not found.
        FileNotFoundError: If config file not found.
    """
    if config is None:
        config = load_policy_config()

    policies = config.get("policies", {})

    # Handle wide_hero reference to medium_hero
    if policy_name == "wide_hero":
        policy_data = policies.get("wide_hero", {})
        uses_policy = policy_data.get("uses_policy")
        if uses_policy:
            policy_name = uses_policy
            policy_data = policies.get(policy_name, {})

    if policy_name not in policies:
        raise ValueError(
            f"Unknown policy: {policy_name}. "
            f"Valid policies: {sorted(policies.keys())}"
        )

    policy_data = policies[policy_name]

    # Extract thresholds
    thresholds = policy_data.get("thresholds", {})
    pass_ms = float(thresholds.get("pass_ms", 30))
    warn_ms = float(thresholds.get("warn_ms", 45))
    fail_ms = float(thresholds.get("fail_ms", 45))

    # Extract confidence requirement
    min_confidence = float(policy_data.get("min_confidence", 2.0))

    # Extract frame-based thresholds
    pass_frames = float(policy_data.get("pass_frames", pass_ms / 40.0))
    warn_frames = float(policy_data.get("warn_frames", warn_ms / 40.0))
    fail_frames = float(policy_data.get("fail_frames", fail_ms / 40.0))

    return LipSyncPolicy(
        name=policy_name,
        description=policy_data.get("description", ""),
        publish_grade=policy_data.get("publish_grade", True),
        pass_ms=pass_ms,
        warn_ms=warn_ms,
        fail_ms=fail_ms,
        min_confidence=min_confidence,
        pass_frames=pass_frames,
        warn_frames=warn_frames,
        fail_frames=fail_frames,
        non_publish_only=policy_data.get("non_publish_only", False),
    )


def evaluate_lipsync(
    offset_ms: float,
    confidence: Optional[float],
    policy_name: str = DEFAULT_POLICY,
    config: Optional[Dict[str, Any]] = None,
) -> LipSyncVerdict:
    """Evaluate lipsync measurement against a policy.

    Args:
        offset_ms: Audio offset in milliseconds.
        confidence: SyncNet confidence score (0.0-3.0), or None if unknown.
        policy_name: Name of policy to apply.
        config: Optional pre-loaded config dict.

    Returns:
        LipSyncVerdict with verdict (pass/warn/fail) and publish_grade flag.
    """
    policy = get_policy(policy_name, config)

    # Check confidence first
    if confidence is None or (confidence < policy.min_confidence):
        return LipSyncVerdict(
            policy_name=policy_name,
            offset_ms=offset_ms,
            confidence=confidence,
            verdict="fail",
            publish_grade=False,  # FAIL is never publish-grade
            reason=f"Confidence {confidence if confidence is not None else 'None'} below minimum {policy.min_confidence}",
        )

    # Evaluate offset against thresholds
    if offset_ms <= policy.pass_ms:
        verdict = "pass"
        reason = f"Offset {offset_ms}ms within PASS threshold (<= {policy.pass_ms}ms)"
    elif offset_ms <= policy.warn_ms:
        verdict = "warn"
        reason = f"Offset {offset_ms}ms in WARN range ({policy.pass_ms}ms - {policy.warn_ms}ms)"
    elif offset_ms <= policy.fail_ms:
        verdict = "fail"
        reason = f"Offset {offset_ms}ms exceeds WARN threshold (> {policy.warn_ms}ms)"
    else:
        verdict = "fail"
        reason = f"Offset {offset_ms}ms far exceeds FAIL threshold (> {policy.fail_ms}ms)"

    # Override verdict for non-publish policies
    if policy.non_publish_only:
        if verdict == "pass":
            verdict = "warn"  # Downgrade to warn for non-publish
            reason = f"{reason} (non-publish policy - not for production use)"

    return LipSyncVerdict(
        policy_name=policy_name,
        offset_ms=offset_ms,
        confidence=confidence,
        verdict=verdict,
        publish_grade=policy.publish_grade and verdict == "pass",  # Only PASS is publish-grade
        reason=reason,
    )


def get_default_policy(config: Optional[Dict[str, Any]] = None) -> str:
    """Get default policy name from config.

    Args:
        config: Optional pre-loaded config dict.

    Returns:
        Default policy name.
    """
    if config is None:
        config = load_policy_config()

    return config.get("default_policy", DEFAULT_POLICY)


def is_policy_publish_grade(policy_name: str, config: Optional[Dict[str, Any]] = None) -> bool:
    """Check if a policy is publish-grade.

    Args:
        policy_name: Name of policy.
        config: Optional pre-loaded config dict.

    Returns:
        True if policy is publish-grade, False otherwise.
    """
    policy = get_policy(policy_name, config)
    return policy.publish_grade


# Pre-defined policy constants for code reference
CLOSE_HERO = "close_hero"
MEDIUM_HERO = "medium_hero"
WIDE_HERO = "wide_hero"
DIAGNOSTIC_LEGACY = "diagnostic_legacy"

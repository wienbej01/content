"""Sprint 4: Provider Request Semantic Fingerprinting (Ticket LB-400).

Generates deterministic fingerprints for hero render requests to ensure
idempotent retries and invalidate stale clips when meaningful inputs change.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional


def _stable_hash(value: Any) -> str:
    """Generate a stable SHA-256 hash for any JSON-serializable value."""
    if value is None:
        return "null"
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def generate_hero_request_fingerprint(
    production_id: str,
    render_unit_id: str,
    hero_render_group_id: Optional[str],
    master_artifact_hash: str,
    slice_artifact_hash: str,
    source_samples: Dict[str, int],  # e.g., {"start": 48000, "end": 96000}
    silence_padding: Dict[str, int],  # e.g., {"leading": 4800, "trailing": 4800}
    prompt: str,
    reference_hashes: List[str],
    model: str,
    requested_duration_sec: float,
    aspect_ratio: str,
    provider_params: Dict[str, Any],
    code_revision: str,
) -> str:
    """
    Generate a semantic fingerprint for a hero render request.
    
    This fingerprint is used as the idempotency key for provider submissions.
    If any meaningful input changes, the fingerprint changes, forcing a new
    provider job and preventing stale clip reuse.
    """
    fingerprint_payload = {
        "production_id": production_id,
        "render_unit_id": render_unit_id,
        "hero_render_group_id": hero_render_group_id,
        "master_artifact_hash": master_artifact_hash,
        "slice_artifact_hash": slice_artifact_hash,
        "source_samples": source_samples,
        "silence_padding": silence_padding,
        "prompt_hash": _stable_hash(prompt),
        "reference_hashes": sorted(reference_hashes),
        "model": model,
        "requested_duration_sec": requested_duration_sec,
        "aspect_ratio": aspect_ratio,
        "provider_params": provider_params,
        "code_revision": code_revision,
    }
    
    return _stable_hash(fingerprint_payload)


def validate_fingerprint_match(
    existing_fingerprint: str,
    new_fingerprint: str,
    changed_field: Optional[str] = None,
) -> bool:
    """
    Validate that an existing fingerprint matches a new one.
    Returns True if they match (safe to reuse), False otherwise.
    """
    if existing_fingerprint != new_fingerprint:
        return False
    return True

"""Sprint 4/R4: Provider Request Semantic Fingerprinting (Ticket LB-400 / R4-001).

Generates deterministic collision-resistant SHA-256 fingerprints for hero render
requests to ensure idempotent retries and invalidate stale clips when meaningful
inputs change. Duration is canonicalized in integer samples (not float seconds)
to eliminate IEEE 754 drift. Payload and algorithm version are persisted for
reproducibility.

FINGERPRINT_ALGORITHM_VERSION is bumped whenever the fingerprint schema changes.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

FINGERPRINT_ALGORITHM_VERSION = 3


def _stable_hash(value: Any) -> str:
    """Generate a stable full SHA-256 hash for any JSON-serializable value."""
    if value is None:
        return "null"
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def generate_hero_request_fingerprint(
    production_id: str,
    render_unit_id: str,
    hero_render_group_id: Optional[str],
    master_artifact_hash: str,
    slice_artifact_hash: str,
    source_samples: Dict[str, int],
    silence_padding: Dict[str, int],
    prompt: str,
    reference_hashes: List[str],
    model: str,
    requested_duration_samples: int,
    aspect_ratio: str,
    provider_params: Dict[str, Any],
    code_revision: str,
    negative_prompt: str = "",
    model_version: str = "",
) -> dict:
    """Generate a semantic fingerprint for a hero render request.

    Returns a dict with 'fingerprint' (full SHA-256), 'algorithm_version',
    and 'payload' (the canonicalized fingerprint payload for persistence).

    Duration is in integer samples (not float seconds) to avoid IEEE 754 drift.

    The fingerprint includes ALL meaningful inputs that must invalidate a cached
    provider job when they change: prompt, negative prompt, references, model AND
    model version, source/slice hashes, sample intervals, silence padding,
    duration, aspect ratio, and provider parameters. Unrelated metadata changes
    (e.g. a display label) must NOT create a new job.
    """
    payload = {
        "_algorithm": FINGERPRINT_ALGORITHM_VERSION,
        "production_id": production_id,
        "render_unit_id": render_unit_id,
        "hero_render_group_id": hero_render_group_id,
        "master_artifact_hash": master_artifact_hash,
        "slice_artifact_hash": slice_artifact_hash,
        "source_samples": source_samples,
        "silence_padding": silence_padding,
        "prompt_hash": _stable_hash(prompt),
        "negative_prompt_hash": _stable_hash(negative_prompt),
        "reference_hashes": sorted(reference_hashes),
        "model": model,
        "model_version": model_version,
        "requested_duration_samples": requested_duration_samples,
        "aspect_ratio": aspect_ratio,
        "provider_params": provider_params,
        "code_revision": code_revision,
    }
    fingerprint = _stable_hash(payload)
    return {
        "fingerprint": fingerprint,
        "algorithm_version": FINGERPRINT_ALGORITHM_VERSION,
        "payload": payload,
    }


def validate_fingerprint_match(
    existing_fingerprint: str,
    new_fingerprint: str,
    changed_field: Optional[str] = None,
) -> bool:
    """Validate that an existing fingerprint matches a new one."""
    return existing_fingerprint == new_fingerprint


def fingerprint_idempotency_key(
    production_id: str,
    render_unit_id: str,
    fingerprint: str,
) -> str:
    """Derive the idempotency key from fingerprint for provider job dedup."""
    return f"fp:{production_id}:{render_unit_id}:{fingerprint}"

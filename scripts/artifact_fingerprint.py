#!/usr/bin/env python3
"""artifact_fingerprint.py — SHA-256 fingerprint for generated media artifacts.

Detects stale/cross-project reuse by writing .fp.json beside each artifact.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def compute_fingerprint(path):
    """Compute SHA-256, size, mtime for a file."""
    p = Path(path)
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    stat = p.stat()
    return {
        "artifact": str(p),
        "sha256": h.hexdigest(),
        "size_bytes": stat.st_size,
        "mtime": stat.st_mtime,
    }


def write_fingerprint(artifact_path, producer, producer_version, upstream_hashes=None, project_id=None):
    """Write .fp.json beside the artifact. Atomic (tmp+rename)."""
    p = Path(artifact_path)
    fp = compute_fingerprint(p)
    fp.update({
        "producer": producer,
        "producer_version": producer_version,
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "upstream_hashes": upstream_hashes or [],
        "project_id": project_id or "",
    })
    out = p.parent / f"{p.name}.fp.json"
    tmp = Path(str(out) + ".tmp")
    tmp.write_text(json.dumps(fp, indent=2, sort_keys=True))
    os.replace(str(tmp), str(out))
    return out


def read_fingerprint(artifact_path):
    """Read .fp.json if it exists, else None. Returns None on read/parse errors."""
    fp_path = Path(artifact_path).parent / f"{Path(artifact_path).name}.fp.json"
    if not fp_path.exists():
        return None
    try:
        return json.loads(fp_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def verify_fingerprint(artifact_path, expected_producer=None, upstream_hashes=None, expected_project_id=None):
    """Verify fingerprint. Returns (valid: bool, reason: str)."""
    fp = read_fingerprint(artifact_path)
    if fp is None:
        return False, "no .fp.json file"
    # SHA-256 check
    current = hashlib.sha256()
    with open(artifact_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            current.update(chunk)
    if current.hexdigest() != fp["sha256"]:
        return False, f"sha256 mismatch (file modified after fingerprint)"
    if expected_producer and fp.get("producer") != expected_producer:
        return False, f"producer mismatch (expected {expected_producer}, got {fp.get('producer')})"
    if expected_project_id and fp.get("project_id") != expected_project_id:
        return False, f"project_id mismatch (expected {expected_project_id}, got {fp.get('project_id')})"
    if upstream_hashes is not None and sorted(upstream_hashes) != sorted(fp.get("upstream_hashes", [])):
        return False, "upstream_hashes mismatch"
    return True, "valid"

#!/usr/bin/env python3
"""canonical_master.py — create a canonical lossless PCM/WAV master from provider audio.

R3-001: Converts the provider master narration (typically MP3) to a fixed-sample-rate
PCM/WAV derivative. All slicing, silence generation, and sample-level interval enforcement
use this canonical master — never the lossy original.

Storage lineage is recorded in the DB artifact store: sample_rate, channels, total_samples,
duration, SHA-256, and source artifact id.

Usage:
  python3 scripts/canonical_master.py <project_dir> [--db-path <path>]
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from production_repo import register_artifact, get_artifact, probe_media, MediaProbe
from timeline_utils import MASTER_SAMPLE_RATE

CANONICAL_SAMPLE_RATE = MASTER_SAMPLE_RATE
CANONICAL_CHANNELS = 1
CANONICAL_FORMAT = "wav"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for c in iter(lambda: f.read(1 << 16), b""):
            h.update(c)
    return h.hexdigest()


def canonicalize_master(
    production_id: str,
    source_path: Path,
    source_artifact_id: Optional[str] = None,
    output_dir: Optional[Path] = None,
    db_path=None,
) -> dict:
    """Convert a provider master audio file to canonical PCM/WAV.

    Returns dict with canonical artifact id, path, sample_rate, channels,
    total_samples, duration_ms, sha256, source_artifact_id.
    """
    src = Path(source_path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Source master audio not found: {src}")

    output_dir = Path(output_dir or src.parent).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    canonical_path = output_dir / f"{src.stem}_canonical.{CANONICAL_FORMAT}"

    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(src),
        "-acodec", "pcm_s16le",
        "-ar", str(CANONICAL_SAMPLE_RATE),
        "-ac", str(CANONICAL_CHANNELS),
        str(canonical_path),
    ], capture_output=True, check=True)

    probe = probe_media(canonical_path)
    if probe is None:
        raise RuntimeError(f"Failed to probe canonical master: {canonical_path}")

    sha = _sha(canonical_path)

    art = register_artifact(
        production_id=production_id,
        path=canonical_path,
        kind="master_audio",
        extra_metadata={
            "sample_rate": probe.sample_rate,
            "channels": probe.channels,
            "total_samples": ms_to_samples(probe.duration_ms),
            "duration_ms": probe.duration_ms,
            "source_artifact_id": source_artifact_id,
            "conversion": "pcm_s16le",
            "canonical_sample_rate": CANONICAL_SAMPLE_RATE,
            "canonical_channels": CANONICAL_CHANNELS,
        },
        db_path=db_path,
    )

    return {
        "artifact_id": art["id"],
        "path": canonical_path,
        "sample_rate": probe.sample_rate,
        "channels": probe.channels,
        "total_samples": ms_to_samples(probe.duration_ms),
        "duration_ms": probe.duration_ms,
        "sha256": sha,
        "source_artifact_id": source_artifact_id,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Create canonical PCM/WAV master from provider audio")
    ap.add_argument("project_dir", help="Project directory (for legacy path resolution)")
    ap.add_argument("--production-id", help="Production DB id", default=None)
    ap.add_argument("--source", help="Source master audio path (default: narration/continuous.mp3)")
    ap.add_argument("--source-artifact-id", help="DB artifact id of the source")
    ap.add_argument("--db-path", help="Override DB path")
    ap.add_argument("--output-dir", help="Output directory for canonical file")
    args = ap.parse_args(argv)

    project_dir = Path(args.project_dir).resolve()
    source = Path(args.source) if args.source else (project_dir / "narration" / "continuous.mp3")

    result = canonicalize_master(
        production_id=args.production_id or project_dir.name,
        source_path=source,
        source_artifact_id=args.source_artifact_id,
        output_dir=args.output_dir,
        db_path=args.db_path,
    )
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

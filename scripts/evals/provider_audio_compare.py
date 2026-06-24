#!/usr/bin/env python3
"""Provider diagnostic audio comparison eval.

Compares provider-returned diagnostic audio against the source slice used
for generation. Uses numpy for cross-correlation when available; falls back
to duration-only comparison.

Outputs JSON with:
  source_duration_sec, provider_duration_sec, duration_delta_ms,
  estimated_offset_ms, correlation_confidence, pass

Usage:
  python3 scripts/evals/provider_audio_compare.py \\
    --source <source_slice.wav> \\
    --provider <provider_diagnostic_audio.wav> \\
    --output <result.json>
"""
import argparse
import json
import struct
import sys
from pathlib import Path

HAS_NUMPY = False
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None


def load_wav(path: Path, expected_sr: int = 48000) -> dict:
    """Load a PCM WAV file into a numpy array (or list if numpy unavailable).

    Returns dict with: samples, sample_rate, duration_sec, channels.
    Assumes standard WAV header (44 bytes for PCM).
    """
    data = path.read_bytes()

    # Parse WAV header manually (no scipy.wavfile dependency)
    riff_id = data[:4]
    if riff_id != b'RIFF':
        raise ValueError(f"Not a valid WAV file: {path} (no RIFF header)")

    # Find fmt chunk
    fmt_start = data.find(b'fmt ')
    if fmt_start < 0:
        raise ValueError(f"No fmt chunk in WAV: {path}")

    audio_format = struct.unpack_from('<H', data, fmt_start + 8)[0]
    channels = struct.unpack_from('<H', data, fmt_start + 10)[0]
    sample_rate = struct.unpack_from('<I', data, fmt_start + 12)[0]
    bits_per_sample = struct.unpack_from('<H', data, fmt_start + 22)[0]

    # Find data chunk
    data_start = data.find(b'data')
    if data_start < 0:
        raise ValueError(f"No data chunk in WAV: {path}")
    data_size = struct.unpack_from('<I', data, data_start + 4)[0]
    raw_audio = data[data_start + 8:data_start + 8 + data_size]

    # Convert to samples based on format
    if audio_format == 1:  # PCM
        if bits_per_sample == 16:
            samples_fmt = f'<{len(raw_audio) // 2}h'
            samples = list(struct.unpack_from(samples_fmt, raw_audio))
        elif bits_per_sample == 32:
            samples_fmt = f'<{len(raw_audio) // 4}i'
            samples = list(struct.unpack_from(samples_fmt, raw_audio))
        else:
            raise ValueError(f"Unsupported bits_per_sample: {bits_per_sample}")
    else:
        raise ValueError(f"Unsupported audio format: {audio_format}")

    # Convert to mono if stereo (average channels)
    if channels > 1:
        frame_count = len(samples) // channels
        mono = []
        for i in range(frame_count):
            mono.append(sum(samples[i * channels:(i + 1) * channels]) // channels)
        samples = mono

    if HAS_NUMPY:
        samples_arr = np.array(samples, dtype=np.float64)
    else:
        samples_arr = samples

    frame_count = len(samples)
    duration_sec = frame_count / float(sample_rate)

    return {
        "samples": samples_arr,
        "sample_rate": sample_rate,
        "duration_sec": round(duration_sec, 4),
        "channels": 1 if channels > 1 else channels,
        "frame_count": frame_count,
    }


def compute_cross_correlation(source: dict, provider: dict) -> dict:
    """Compute cross-correlation between source and provider audio.

    Returns: estimated_offset_ms, correlation_confidence.
    """
    if not HAS_NUMPY:
        return {"estimated_offset_ms": None, "correlation_confidence": 0.0}

    src = source["samples"]
    prv = provider["samples"]
    src_sr = source["sample_rate"]
    prv_sr = provider["sample_rate"]

    # Normalize amplitude to unit energy
    src_norm = (src - np.mean(src)) / (np.std(src) + 1e-10)
    prv_norm = (prv - np.mean(prv)) / (np.std(prv) + 1e-10)

    # Compute cross-correlation (use the shorter signal length)
    # If signals are very different lengths (>2x), skip correlation
    if len(src_norm) == 0 or len(prv_norm) == 0:
        return {"estimated_offset_ms": None, "correlation_confidence": 0.0}

    ratio = max(len(src_norm), len(prv_norm)) / (min(len(src_norm), len(prv_norm)) + 1)
    if ratio > 3.0:
        # Signals too different in length for meaningful correlation
        return {"estimated_offset_ms": None, "correlation_confidence": 0.0}

    # Use the shorter signal length for correlation window
    corr_len = min(len(src_norm), len(prv_norm))
    src_trim = src_norm[:corr_len]
    prv_trim = prv_norm[:corr_len]

    # Normalized cross-correlation
    correlation = np.correlate(src_trim, prv_trim, mode='same')
    max_corr = np.max(np.abs(correlation))
    mean_energy = np.sqrt(np.mean(src_trim ** 2) * np.mean(prv_trim ** 2)) + 1e-10
    confidence = float(max_corr / (corr_len * mean_energy))
    confidence = min(1.0, max(0.0, confidence))  # Clamp to [0, 1]

    # Find peak offset in samples
    peak_idx = int(np.argmax(np.abs(correlation)))
    center = corr_len // 2
    offset_samples = peak_idx - center

    # Convert to ms using the source sample rate
    offset_ms = round(offset_samples / float(src_sr) * 1000, 2)

    return {
        "estimated_offset_ms": offset_ms,
        "correlation_confidence": round(confidence, 4),
    }


def compare(source_path: Path, provider_path: Path) -> dict:
    """Run the full comparison and return metrics dict."""
    source = load_wav(source_path)
    provider = load_wav(provider_path)

    source_dur = source["duration_sec"]
    provider_dur = provider["duration_sec"]
    delta_ms = round(abs(source_dur - provider_dur) * 1000, 2)

    correlation = compute_cross_correlation(source, provider)
    offset_ms = correlation["estimated_offset_ms"]
    confidence = correlation["correlation_confidence"]

    # Determine pass/fail: duration delta < 500ms
    duration_pass = delta_ms < 500.0

    result = {
        "source_duration_sec": source_dur,
        "provider_duration_sec": provider_dur,
        "duration_delta_ms": delta_ms,
        "estimated_offset_ms": offset_ms,
        "correlation_confidence": confidence,
        "pass": duration_pass,
        "dependency_status": "available" if HAS_NUMPY else "blocked_dependency",
        "source_path": str(source_path),
        "provider_path": str(provider_path),
        "source_sample_rate": source["sample_rate"],
        "provider_sample_rate": provider["sample_rate"],
    }
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="Provider diagnostic audio comparison")
    ap.add_argument("--source", required=True, type=Path, help="Source slice WAV path")
    ap.add_argument("--provider", required=True, type=Path, help="Provider diagnostic audio WAV path")
    ap.add_argument("--output", required=True, type=Path, help="Output JSON path")
    args = ap.parse_args(argv)

    if not args.source.exists():
        print(f"ERROR: Source file not found: {args.source}", file=sys.stderr)
        return 1
    if not args.provider.exists():
        print(f"ERROR: Provider file not found: {args.provider}", file=sys.stderr)
        return 1

    result = compare(args.source, args.provider)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2))

    # Print summary
    print(f"Source duration: {result['source_duration_sec']:.3f}s")
    print(f"Provider duration: {result['provider_duration_sec']:.3f}s")
    print(f"Duration delta: {result['duration_delta_ms']:.2f}ms")
    if result['estimated_offset_ms'] is not None:
        print(f"Estimated offset: {result['estimated_offset_ms']:.2f}ms")
    print(f"Correlation confidence: {result['correlation_confidence']:.4f}")
    print(f"Pass: {result['pass']}")
    print(f"Dependency: {result['dependency_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

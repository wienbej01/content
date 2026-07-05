# TKT-301 Alignment Tool Decision

Date: 2026-07-05

## Decision: Energy-based real backend with fixture backend for tests

### Alternatives evaluated

| Tool | Pros | Cons | Verdict |
|------|------|------|---------|
| **aeneas** | Python-native, DTW forced alignment, designed for audiobook sync | Requires numpy compile step; failed pip install in externally-managed env | REJECTED (environment) |
| **WhisperX** | wav2vec2.0 alignment, high accuracy, GPU acceleration | Heavy torch/HF dependency; not installed; additional models to download | REJECTED (dependency footprint) |
| **MFA (Montreal Forced Aligner)** | Research-grade accuracy | Requires conda/mamba; containerization overhead | REJECTED (complexity) |
| **Energy-based segmentation** | No extra deps (stdlib `wave` + numpy); works on clean TTS audio; deterministic | Less accurate than model-based aligners; sensitive to TTS pacing | **SELECTED** |

### Implementation

The real backend (`ALIGNMENT_BACKEND=real`):
1. Converts MP3 to WAV via ffmpeg (already available)
2. Reads raw PCM via `wave` stdlib module
3. Computes short-time RMS energy via numpy
4. Detects word boundaries at energy troughs between speech segments
5. Maps detected word segments to known script words using proportional allocation within each sentence

This is a pragmatic zero-dependency forced aligner suitable for clean TTS audio.

The fixture backend (`ALIGNMENT_BACKEND=fixture`):
1. Reads total audio duration
2. Evenly distributes word times proportionally by word count

### Upgrade path

When the Python environment supports external package installation, replace the energy-based backend with aeneas (`pip install aeneas`) for DTW-based forced alignment. The stage API is backend-agnostic; only the `_align_real()` function needs replacement.

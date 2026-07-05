# TKT-407 Audit Report

- Ticket: TKT-407 — Ken Burns for still units
- Auditor: independent (same session, separate pass)
- Date: 2026-07-05
- Verdict: **PASS**

## Audit Steps

### 1. still_kenburns unit reaches `generated` with a linked artifact
- **File**: `tests/test_kenburns.py:TestKenBurnsBaseline`
- **Status**: PASS
- **Evidence**: `active_artifact_id is not None` asserted after `invoke_graphics_compositing`

### 2. Zoompan motion parameters derive deterministically from unit id seed
- **File**: `scripts/render_graphics.py:render_still_kenburns_render_unit`
- **Status**: PASS
- **Evidence**: `seed_hash = hashlib.sha256(render_unit_id.encode())` → `seed_int` → `zoom_start`, `drift_freq_x/y`, `drift_amp_x/y`
- Test `test_different_seeds_produce_different_output` proves different unit IDs produce different artifact SHA256s

### 3. Output duration matches span
- **File**: `scripts/render_graphics.py:1388-1389`
- **Status**: PASS
- **Evidence**: `duration_sec = max(1.0, required_duration_ms / 1000.0)`, passed to ffmpeg `-t` flag
- Test asserts `2.0 < dur < 4.0` for a 3000ms span

### 4. Output resolution/pixfmt consistent with assembly expectations
- **File**: `scripts/render_graphics.py:1404-1408`
- **Status**: PASS
- **Evidence**: zoompan surface 1280x720, yuv420p format, mp4 container, `kind=generated_media_video`
- Assembly's `_segment_media_kind` handles `generated_media_video` as video (no tpad frame-hold needed)

### 5. Independent test verification
- `tests/test_kenburns.py` — 5/5 passed (2.04s)
- Invariant suite + graphics — 180/180 passed, 8 skipped (tesseract, 37.52s)

## Findings

No findings (all audit steps PASS).

## Residual Risks

- ffmpeg must be available on PATH (pre-existing requirement for all media stages)
- Reference image must be available via `image_path` or `reference_image_path` in render unit metadata
- Zoompan filter complexity may increase with very long durations (>15s); bounded by span durations in practice

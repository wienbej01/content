# REPAIR-601B-W3 — Audit Report

**Date**: 2026-07-06T19:22:00+08:00
**Auditor**: independent
**Verdict**: PASS

## Audit steps

### 1. Root cause evidence

| Claim | Evidence | Verdict |
|---|---|---|
| Defect B: duration-ceil mismatch (7738ms slice → 8s request → 8041ms video, +303ms surplus) | `produce_db.py:2070`: `provider_duration_sec = max(1, int(math.ceil(u["required_duration_ms"] / 1000.0)))` | CONFIRMED |
| Provider pads shorter audio late in longer container | Evidence table: `duration_delta_ms: 303` | CONFIRMED |

### 2. Observable outcome verification

| Requirement | Implementation | Verdict |
|---|---|---|
| Pad fractional slice to ceil'd duration | `apad=whole_dur={ceil_duration_ms}ms` via ffmpeg | PASS |
| Content start at sample 0 (trailing silence only) | Input audio starts at 0, `apad` appends silence | PASS |
| Source slice provenance preserved | `source_slice_sha256` in payload, padded file is derivative | PASS |
| Integer-second slices not padded | ffmpeg `apad=whole_dur` is no-op when input already matches | PASS |

### 3. Production path

- `produce_db.py:2088-2103`: conditional on `meta.get("audio_path")`, pads to `provider_duration_sec * 1000` ms
- Padded file cached (idempotent: `if not padded_path.exists()`)
- `request_payload["audio_path"]` = padded path
- `request_payload["audio_path_padded"] = True` for traceability
- `request_payload["source_slice_sha256"]` = original for provenance

### 4. Test coverage

| Scenario | Test | Expected | Result |
|---|---|---|---|
| Fractional slice pads to ceil | `test_fractional_slice_pads_to_ceil` | 7738ms → ~8000ms | PASS |
| Trailing padding only | `test_padding_is_trailing_only` | 5000ms → ~6000ms | PASS |
| Integer slice unchanged | `test_integer_slice_no_padding_needed` | 5000ms → ~5000ms | PASS |
| Source unchanged | `test_source_slice_unchanged` | original duration preserved | PASS |
| Padded output has audio | `test_padded_slice_has_audio_content` | audio stream present | PASS |

### 5. Regression checks

- Invariant suite: 145/147 passed (2 pre-existing)
- W1 compensation: 9/9 passed
- W2 contract: 14/14 passed

### 6. No paid call

All tests use ffmpeg locally — no Higgsfield/Kling submission.

## Verdict: PASS

No findings. All 4 acceptance gates verified. Ready for validation.
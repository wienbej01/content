# DDL-W2 — Single rounding point, trailing-pad to ceil'd duration

Sprint: `DDL-2026-07-06`. Defect class: **DDL-F3** (double ceil + container surplus). Class: ROUTINE. Risk: low (deterministic change). Deps: none (can run in parallel with W1). Blocks: DDL-W4, DDL-W5.

## Requirement
Provider video requests must carry a video duration that exactly matches the padded audio slice. A fractional audio slice (e.g. 7738ms) is padded to the ceiling integer-second container (8000ms) at submit time; the pad is trailing silence only, preserving content start at sample 0. The provider receives `--audio` of exactly 8000ms and `duration_sec` = 8. There is exactly one rounding operation between the sample timeline and the provider.

## Root cause targeted
DDL-F3. Duration is ceil'd to whole seconds twice: once in `produce_db.py:2071` (request shaping) and again in `paid_adapters.py:182` (CLI invocation). The padded audio slice is not adjusted to match, creating a surplus.

## Observable outcome
1. In `produce_db.py` hero submission path (line ~2070-2088): before building the request payload, pad the conditioning audio to the exact ceil'd duration using ffmpeg with trailing-silence (`-af apad=whole_dur=<ceil_sec>s` or equivalent). The padded slice is written to a temp file.
2. Remove the second `ceil()` in `paid_adapters.py` (line ~182): the CLI argument derives from `duration_sec` already in the request payload, not re-computed.
3. After the fix, for the prod hero slice (7738ms), the payload contains `duration_sec: 8` and the attached audio file is exactly 8.000s.
4. `source_slice_sha256` provenance preserved: the gate still checks against the source (unpadded) slice; the padded slice hash is recorded as `padded_slice_sha256` in the request payload for traceability.

## Scope (files to change)
- `scripts/produce_db.py:2070-2088`: add trailing-silence padding of audio slice to match ceil'd duration. Record padded hash.
- `scripts/paid_adapters.py:182`: remove duplicate `ceil()`; use `duration_sec` from the request payload as-is.
- `scripts/media_service.py:123-134` (hero provenance gate): ensure `source_slice_sha256` still checks the un-padded source. If the gate currently checks the submitted file, update the hash reference to use the padded hash.
- Tests: new file for slice padding, extend paid_adapters tests.

## Test matrix
| Level | Scenario | Expected | Command |
|---|---|---|---|
| unit | 7738ms audio slice, ceil 8s | padded audio is exactly 8.000s (±1ms), content starts at 0, trailing silence fills the rest | `python3 -m pytest tests/test_hero_slice_padding.py -q` (new) |
| unit | integer-second slice (5000ms) | no padding applied (already ceil'd), audio unchanged | same |
| unit | hero submit payload for 7738ms slice | `duration_sec=8`, attached audio 8.000s | extend `tests/test_paid_adapters.py` or create |
| contract | source_slice_sha256 provenance | gate checks un-padded source SHA; padded SHA recorded separately in payload | same |
| contract | submit path has exactly one ceil() | grep confirm only `produce_db.py:2071` rounds; `paid_adapters.py` does not | manual audit step |
| regression | 5-file PPQ invariant suite | unchanged | baseline |

## Acceptance gates
- G1: Fractional slice pads to exact ceil'd duration with trailing silence, content front-aligned.
- G2: Single rounding operation on the submit path (proven by grep + unit test).
- G3: Hero provenance gate (`source_slice_sha256`) still enforced with the correct (un-padded) hash.
- G4: 5-file PPQ invariant suite passes.
- G5: No paid call path added.

## Engineering notes
- ffmpeg trailing-pad command: `ffmpeg -y -i <slice> -af "apad=pad_dur=<diff>s" -c:a <codec> <padded>`. Or use `-af "apad=whole_dur=<ceil_sec>s"` to avoid computing the difference.
- The padded file is temporary; only the hash is persisted in the DB (in `request_json` of the provider job). The file is cleaned up after submission.
- Legacy render units already submitted without padding are not retroactively fixed; the change is forward-looking for future generations and re-submits.

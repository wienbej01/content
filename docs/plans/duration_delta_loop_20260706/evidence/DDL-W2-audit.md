# DDL-W2 Audit Report

**Ticket**: DDL-W2 — Single rounding point, trailing-pad to ceil'd duration
**Auditor**: Kilo agent
**Timestamp**: 2026-07-06T22:38:00+08:00
**Result**: PASS

## Diff Summary

| File | Change |
|---|---|
| `scripts/paid_adapters.py:5` | Remove `math` from import tuple (unused after ceil removal) |
| `scripts/paid_adapters.py:182` | `math.ceil(float(duration))` → `int(float(duration))` |
| `tests/test_single_rounding_w2.py` | New: 87 lines, 4 tests |

## Test Evidence

```
python3 -m pytest tests/test_single_rounding_w2.py -v         # 4 passed
python3 -m pytest tests/test_hero_slice_padding.py -v          # 5 passed
python3 -m pytest tests/unit/test_paid_adapters_contract.py -v  # 14 passed
python3 -m pytest tests/test_assemble.py tests/test_assemble_continuous_contract.py tests/test_duration_drift_wiring.py -q  # 26 passed
```

All 49 tests pass.

## Gate Verification

| Gate | Status | Evidence |
|---|---|---|
| G1: Fractional slice pads to ceil'd duration with trailing silence | PASS | Already covered by REPAIR-601B-W3 (test_hero_slice_padding.py:5 tests). Audio padding code in produce_db.py:2086-2103 unchanged. |
| G2: Single rounding operation on submit path | PASS | `grep -n ceil scripts/paid_adapters.py` returns empty. `grep -n ceil scripts/produce_db.py` shows the single provider ceil at line 2071. |
| G3: Hero provenance gate (source_slice_sha256) still enforced | PASS | media_service.py:127-134 checks `ru.get("source_slice_sha256")` from render unit metadata (un-padded source hash). Unchanged. |
| G4: 5-file PPQ invariant suite passes | PASS | 26 assemble + drift tests pass. |
| G5: No paid call path added | PASS | Dry-run based tests only. |

## Production Path Trace

```
invoke_generate_media (produce_db.py)
  -> provider_duration_sec = ceil(required_duration_ms / 1000)  (line 2071, single rounding)
  -> pads audio slice to ceil duration if audio_path present      (line 2086-2103)
  -> request_payload["duration_sec"] = provider_duration_sec      (line 2080)
  -> submit_provider_job(..., request_payload=request_payload)    (line 2137)
  -> adapter.submit(payload, ...)                                 (line 2152)
  -> duration = payload.get("duration_sec", ...)                  (line 181, gets pre-ceil'd int)
  -> duration_cli = max(1, int(float(duration)))                  (line 182, pass-through)
  -> --duration <duration_cli>                                    (line 192)
```

The delta: `math.ceil()` removed from line 182. The ceiling is now exclusively at produce_db.py:2071.

## Finding: No issues

The change is minimal and deterministic. The `max(1, int(float(duration)))` expression correctly:
- Clamps to minimum 1s (`max(1, ...)`)
- Handles both int and float inputs (`float(duration)`, `int(...)`)
- Does not introduce rounding bias (no `ceil`, `round`, or `floor`)

No stale state, race condition, or side effect concerns.

## Verdict

**PASS** — Clean single-operation change. No findings.

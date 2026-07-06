# REPAIR-601B-W2 — Audit Report

**Date**: 2026-07-06T19:15:00+08:00
**Auditor**: independent
**Verdict**: PASS

## Audit steps

### 1. Root cause evidence

| Claim | Evidence | Verdict |
|---|---|---|
| Defect A: `--generate_audio true` always sent with `--audio` | `paid_adapters.py:213` (old): `args.extend([f"--{audio_param}", audio_vals[0]])` unconditional | CONFIRMED |
| Seedance treats supplied WAV as soft reference, not authoritative | Evidence table §1: systematic +120-480ms intrinsic desync | CONFIRMED |

### 2. Observable outcome verification

| Requirement | Implementation | Verdict |
|---|---|---|
| Hero path (audio_path set): `--generate_audio false` | `audio_vals[1]` when `audio_path` is truthy | PASS |
| B-roll path (no audio_path): `--generate_audio true` | `audio_vals[0]` when `audio_path` is falsy | PASS |
| Kling `--sound` unchanged (no audio_path → `on`) | `audio_vals[0]` = "on" for kling, verified | PASS |
| I4 invariant preserved | kling + audio_path still raises `ProviderAdapterError` | PASS |

### 3. Test coverage

| Scenario | Test | Expected | Result |
|---|---|---|---|
| Hero with audio_path | `test_hero_with_audio_path_uses_generate_audio_false` | `--generate_audio false` | PASS |
| B-roll without audio_path | `test_broll_without_audio_path_uses_generate_audio_true` | `--generate_audio true` | PASS |
| Kling + audio_path raises I4 | `test_kling_audio_still_raises_i4` | ProviderAdapterError | PASS |
| Kling no audio_path | `test_kling_no_audio_path_uses_sound_on` | `--sound on` | PASS |

### 4. Production path

- `paid_adapters.py:213-214`: `audio_path = payload.get("audio_path")` extracted before audio_param logic
- `paid_adapters.py:219-222`: conditional on `audio_path` presence
- `paid_adapters.py:227-235`: `--audio` attachment + I4 invariant unchanged

### 5. No paid call introduced

All tests use `HIGGSFIELD_DRY_RUN=1` — no real subprocess calls. Contract test only.

### 6. Regression checks

- W1 compensation tests: 9/9 passed
- Invariant suite: 145/147 passed (2 pre-existing)
- I4 invariant: kling `--audio` rejection unchanged

## Verdict: PASS

No findings. All 4 acceptance gates verified. Ready for validation.
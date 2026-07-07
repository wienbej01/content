## Wave 1 — Lipsync Provider Resilience

These tickets make the lipsync path resilient to single-provider failure, add health monitoring, and fix the `generate_audio` double-signaling defect. TKT-101 is discovery; TKT-102..105 are implementation. INV-6 (budget caps) and INV-3 (fail-closed) must hold.

---

### TKT-101 — Discovery: prove secondary lipsync provider interface (HeyGen/D-ID/Hydra)

| Field | Value |
|-------|-------|
| Ticket | TKT-101 |
| Title | Discovery: prove secondary lipsync provider interface |
| Requirement / risk IDs | R-LS-1, R-LS-3, RISK-5, UV-5 |
| Priority | high |
| Severity | medium |
| Risk level | medium |
| Execution class | REASONING_CRITICAL (discovery) |
| Wave | 1 |
| Status | planned |

#### Observable outcome

A decision record `evidence/TKT-101-lipsync-provider-decision.md` that:
- Documents the exact API (endpoint, auth, request shape, response shape, polling, result URL) for at least two of: HeyGen, D-ID, Hedra, or Replicate Stable Video Diffusion + lipsync conditioning.
- Identifies which can accept a reference image + audio slice and return a lipsynced video.
- Identifies cost per clip, rate limits, and test-mode availability.
- Picks one provider as the designated secondary.
- If none are viable or all require paid calls: record `BLOCKED: <exact reason>` with evidence.

No production code changes.

#### Context capsule

- Relevant paths: `scripts/paid_adapters.py`, `scripts/generate_media.py`, `scripts/media_service.py`.
- Upstream contracts: `LipsyncProvider` interface to be defined in TKT-102.

#### Preconditions and baseline

- Internet access for API documentation lookup.
- No paid calls during documentation phase.

#### Implementation steps

1. For each candidate provider, read public API docs via `webfetch`.
2. Document: (a) auth mechanism, (b) endpoint, (c) request shape, (d) response/polling, (e) result video URL, (f) cost per clip, (g) test/sandbox mode.
3. Evaluate integration complexity.
4. Pick one provider.
5. Write decision record.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| evidence | decision record exists | `evidence/TKT-101-lipsync-provider-decision.md` | `ls evidence/TKT-101-lipsync-provider-decision.md` |
| evidence | record documents ≥2 providers | file contains ≥2 provider sections | `grep -c "^## " evidence/TKT-101-lipsync-provider-decision.md` |
| evidence | record picks a secondary | file names a chosen provider | `grep -i "chosen\|selected\|recommended" evidence/TKT-101-lipsync-provider-decision.md` |

#### Acceptance gates

- G1: Decision record exists.
- G2: At least two providers documented with API shapes.
- G3: A secondary provider is selected (or BLOCKED with evidence).
- G4: No production files modified.

---

### TKT-102 — Implement LipsyncProvider interface + Seedance wrapper + health monitor

| Field | Value |
|-------|-------|
| Ticket | TKT-102 |
| Title | Implement LipsyncProvider interface + Seedance wrapper + health monitor |
| Requirement / risk IDs | R-LS-1, R-LS-2, R-LS-3, F5 |
| Priority | high |
| Severity | high |
| Risk level | high |
| Execution class | COMPLEX |
| Wave | 1 |
| Status | planned |

#### Observable outcome

A `scripts/lipsync/` module with:
- `LipsyncProvider` ABC: `submit(reference_image, audio_slice) -> str`, `poll(job_id) -> LipsyncResult`, `cost_estimate_sec(duration_sec) -> USD`, `health_check() -> bool`, `name() -> str`.
- `SeedanceLipsyncProvider` implementation wrapping the existing `paid_adapters.py` Higgsfield Seedance path, using config from `configs/james/model_routing.yaml → lipsync_references`.
- `ProviderHealthMonitor` that runs `health_check()` on each registered provider every `HEALTH_CHECK_INTERVAL_SEC` (default 60s) and records `provider_health` rows in the DB.
- Config `configs/lipsync_providers.yaml` listing registered providers, their priority, and health status.
- A `get_active_provider()` function that returns the first healthy provider by priority. If none healthy, raises `NoHealthyLipsyncProviderError`.
- Provider health status exposed via `produce_db.py inspect <production_id>`.

The interface is wired behind a config flag `LIPSYNC_PROVIDER_MODE = single|failover`. Default `single` (Seedance only) — no behavior change for existing productions. `failover` enables the multi-provider rotation.

#### Evidence and rationale

- `paid_adapters.py:184-231` — existing Seedance submit logic to wrap.
- `media_service.py:114-125` — existing provider job submission.
- F5 requires no pipeline block on provider outage.

#### Context capsule

- Relevant paths: `scripts/paid_adapters.py`, `scripts/generate_media.py`, `scripts/media_service.py`, `scripts/production_db.py`.
- Required invariants: INV-3 (fail-closed), INV-4 (evidence recorded), INV-6 (budget caps).
- Protected: existing Seedance submit path (wrap, don't replace).

#### Preconditions and baseline

- Baseline: `python3 scripts/generate_media.py --help` exits 0.
- Confirm `LIPSYNC_PROVIDER_MODE=single` default leaves all existing behavior unchanged.

#### Implementation steps

1. Create `scripts/lipsync/__init__.py`, `scripts/lipsync/provider.py`, `scripts/lipsync/seedance.py`, `scripts/lipsync/health.py`.
2. Define `LipsyncProvider` ABC with the methods above.
3. Implement `SeedanceLipsyncProvider` — extract submit logic from `paid_adapters.py:184-231` into a method that raises `LipsyncProviderError` on any failure.
4. Implement `ProviderHealthMonitor` with a threaded timer or a cron-style check.
5. Add `LIPSYNC_PROVIDER_MODE` to `scripts/smoke_config.py` and `scripts/llm_call.py` (for config propagation).
6. Write tests: `scripts/lipsync/tests/test_provider.py`, `scripts/lipsync/tests/test_health.py` using mock providers.
7. Confirm `LIPSYNC_PROVIDER_MODE=single` path: all existing calls still function.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | Seedance wrapper submit | returns job_id string | `python3 -m pytest scripts/lipsync/tests/test_provider.py::test_seedance_submit -q` |
| unit | Seedance wrapper cost_estimate | returns correct USD for duration | `python3 -m pytest scripts/lipsync/tests/test_provider.py::test_seedance_cost -q` |
| unit | Health monitor marks failing provider unhealthy | provider_health row status=unhealthy | `python3 -m pytest scripts/lipsync/tests/test_health.py::test_unhealthy -q` |
| unit | get_active_provider returns Seedance when healthy | returns Seedance provider instance | `python3 -m pytest scripts/lipsync/tests/test_provider.py::test_get_active -q` |
| unit | get_active_provider raises when none healthy | raises NoHealthyLipsyncProviderError | `python3 -m pytest scripts/lipsync/tests/test_provider.py::test_none_healthy -q` |
| contract | LIPSYNC_PROVIDER_MODE=single, existing prod path | no change in submission argv | `python3 -m pytest tests/test_generate_media.py -q` (existing suite) |

#### Acceptance gates

- G1: LipsyncProvider ABC and Seedance implementation exist and are importable.
- G2: `get_active_provider()` returns Seedance when healthy.
- G3: `get_active_provider()` raises `NoHealthyLipsyncProviderError` when no healthy provider.
- G4: Provider health is recorded in DB (provider_health table row).
- G5: `LIPSYNC_PROVIDER_MODE=single` produces identical argv to current `paid_adapters.py`.
- G6: Full pytest suite passes.

#### Audit focus

- Fail-closed: verify `NoHealthyLipsyncProviderError` propagates to the gate and does NOT pass.
- Budget: verify estimated cost is recorded before any paid submission.
- Thread safety: confirm health monitor doesn't race with provider job submission.

#### Rollback and recovery

- New module is additive; existing `paid_adapters.py` unchanged. Revert removes the new module.

---

### TKT-103 — Provider failover in generate_media submit path

| Field | Value |
|-------|-------|
| Ticket | TKT-103 |
| Title | Provider failover in generate_media submit path |
| Requirement / risk IDs | R-LS-3, F5 |
| Priority | high |
| Severity | high |
| Risk level | medium |
| Execution class | COMPLEX |
| Wave | 1 |
| Status | planned |

#### Observable outcome

`scripts/generate_media.py` `generate_hero_lipsync()` now calls `get_active_provider()` and retries on the next healthy provider if the first fails submission or polling. Failover is logged and recorded as evidence.

Production deployment remains `LIPSYNC_PROVIDER_MODE=single` until human authorization enables `failover`. Failover mode is only activated in the production config after explicit opt-in.

#### Context capsule

- Relevant paths: `scripts/generate_media.py`, `scripts/lipsync/provider.py` (from TKT-102).
- Required invariants: INV-3, INV-6.

#### Preconditions and baseline

- TKT-102 accepted.
- Baseline: `LIPSYNC_PROVIDER_MODE=single` current production invocation.

#### Implementation steps

1. In `generate_media.py` `generate_hero_lipsync()`, wrap the submit+poll in a loop over `get_prioritized_providers()`.
2. On provider failure, log and try the next.
3. If all fail, record evidence and raise `NoHealthyLipsyncProviderError`.
4. Behind `LIPSYNC_PROVIDER_MODE=failover` flag.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | primary fails, secondary succeeds | failover to secondary | `python3 -m pytest scripts/lipsync/tests/test_failover.py::test_failover -q` |
| unit | all providers fail | error recorded, no pass | `python3 -m pytest scripts/lipsync/tests/test_failover.py::test_all_fail -q` |
| contract | failover mode disabled | no failover attempt | `python3 -m pytest scripts/lipsync/tests/test_failover.py::test_single_mode -q` |

#### Acceptance gates

- G1: Failover only activates in `failover` mode.
- G2: All-fail case fails closed (no fabricated pass).
- G3: Failover evidence recorded.
- G4: Full suite passes.

---

### TKT-104 — SyncNet scorer drift check + calibration pin

| Field | Value |
|-------|-------|
| Ticket | TKT-104 |
| Title | SyncNet scorer drift check + calibration pin |
| Requirement / risk IDs | RISK-1, UV-4, INV-3 |
| Priority | high |
| Severity | medium |
| Risk level | medium |
| Execution class | COMPLEX |
| Wave | 1 |
| Status | planned |

#### Observable outcome

A calibration check that:
- Confirms the scorer from the PPQ sprint (`scripts/sync_scorer/scorer.py`) is still importable and produces sensible offsets on the same fixture clips.
- Pins the scorer version + calibration constants in `configs/lipsync_thresholds.yaml` with a timestamp and commitment hash.
- Fails loudly if drift is detected (INV-3).

#### Context capsule

- Relevant paths: `scripts/sync_scorer/scorer.py`, `scripts/lipsync_scoring.py`, `configs/lipsync_thresholds.yaml`.

#### Preconditions and baseline

- Inventory hero clips under `outputs/` and `assets/media/` for calibration.
- If <3 real hero clips exist: report `BLOCKED: need >=3 real hero clips`.

#### Implementation steps

1. Write `scripts/evals/calibration_check_sync_scorer.py` that imports the scorer and runs it on fixture clips.
2. Compare offsets against the pinned expected values from PPQ.
3. If within tolerance: write a new calibration timestamp into `configs/lipsync_thresholds.yaml`.
4. If drift detected: fail loudly, report BLOCKED.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| runtime | scorer on fixture clip | offset within ±40ms of pinned | `python3 scripts/evals/calibration_check_sync_scorer.py` |
| negative | scorer produces out-of-range offset | exit non-zero | same with tampered fixture |

#### Acceptance gates

- G1: Scorer produces expected offsets on fixtures.
- G2: `configs/lipsync_thresholds.yaml` updated with calibration timestamp.
- G3: Drift case fails loudly (non-zero exit).

---

### TKT-105 — Lipsync `generate_audio` conditional fix

| Field | Value |
|-------|-------|
| Ticket | TKT-105 |
| Title | Lipsync generate_audio conditional fix |
| Requirement / risk IDs | R-LS-3, F5, CS-6 |
| Priority | high |
| Severity | medium |
| Risk level | medium |
| Execution class | COMPLEX |
| Wave | 1 |
| Status | planned |

#### Observable outcome

`scripts/paid_adapters.py` no longer unconditionally sends `--generate_audio true`. When a conditioning audio slice is attached (Seedance hero path), it sends `--generate_audio false`. This fixes the double-signaling defect discovered in PPQ sprint defect A.

This is the same as PPQ repair W2. If PPQ W2 was already implemented, this ticket verifies and adds negative tests.

#### Context capsule

- Relevant paths: `scripts/paid_adapters.py:211-231`.

#### Preconditions and baseline

- Baseline: capture current argv for a hero submission showing `--generate_audio true` AND `--audio`.

#### Implementation steps

1. Check if already fixed in current code.
2. If not fixed: make `generate_audio` conditional on `audio_path` presence.
3. Add negative test: hero payload without audio_path must still send `true`.
4. Add negative test: hero payload with audio_path must send `false`.
5. Verify CLI accepts the combination.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| unit | hero with audio_path | argv has `--generate_audio false` | `python3 -m pytest tests/test_paid_adapters.py -q` |
| unit | hero without audio_path | argv has `--generate_audio true` | same |
| contract | b-roll unchanged | no audio flag, no generate_audio flag | same |

#### Acceptance gates

- G1: Hero argv no longer double-signals.
- G2: B-roll path unchanged.
- G3: CLI compatibility documented.

---

## Wave 1 gate

- W1-G1: TKT-101..TKT-105 accepted by independent validator.
- W1-G2: LipsyncProvider interface implemented; health monitor wired.
- W1-G3: Provider failover demonstrated with mock providers.
- W1-G4: Full pytest suite passes.

### Wave 1 handoff notes

Seedance 2.0 remains the default provider. The failover path is implemented but behind `LIPSYNC_PROVIDER_MODE=failover` config (opt-in by human authorization). PPQ defect A fix verified. Scorer calibration pinned. All evidence archived.

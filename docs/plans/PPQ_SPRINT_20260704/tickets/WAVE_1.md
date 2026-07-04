# Wave 1 — Lipsync Measurement Engine (TKT-101..104)

Sprint: `PPQ-2026-07`. See `../PLAN.md`. Depends on Wave 0 (TKT-001). Goal: production-writable `syncnet_offset` evidence from a real face-tracked AV-sync measurement; retire the test-mode fake as the only producer (CS-1..CS-5).

---

## TKT-101 — Discovery: select and prove a face-tracked AV-sync scorer

- Requirements: R-LS-1, RISK-1, UV-1. Class: REASONING_CRITICAL (discovery ticket — decision record + working spike, no production wiring). Deps: none.
- Observable outcome: A decision record `docs/plans/PPQ_SPRINT_20260704/evidence/TKT-101-sync-scorer-decision.md` naming the chosen scorer (candidates: original SyncNet, Wav2Lip LSE-C/LSE-D expert discriminator, or an equivalent latent-sync scorer) with face detection (e.g. MediaPipe/RetinaFace), plus a runnable spike `scripts/evals/spike_sync_scorer.py` that, on a local talking-head video with known-good and known-shifted audio (shift generated with ffmpeg `adelay`), reports offsets that differ in the correct direction and magnitude (±40 ms tolerance on a 200 ms injected shift).
- Evidence of current dead ends: `scripts/evals/eval_syncnet.py:235-238` (`not_run` even with deps), `scripts/lipsync_scoring.py:81` (`NoModelLoaded` only).
- Scope: `scripts/evals/` spike only; dependency installs recorded (pinned versions); NO production module changes. Paid calls: none (local inference only). If GPU/weights unobtainable: report `BLOCKED: <exact missing dependency>`.
- Preconditions: at least one real talking-head video file locally (check `outputs/`); if none exists, report `BLOCKED: need one reference talking-head video file` — a synthetic clip is NOT acceptable for face-tracked scoring proof.
- Baseline: existing syncnet eval entry shows `not_run`.
- Steps:
  1. Enumerate candidates and environment constraints (CPU/GPU availability, torch version, weight licensing).
  2. Install and run each viable candidate on the fixture talking-head clip.
  3. Build the shifted-audio ground-truth harness (`--shift-ms`, `--mismatch` modes).
  4. Record accuracy, runtime, dependency list, and license in the decision record.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| runtime spike | unshifted clip | \|offset\| < 40 ms; face_track_found true | `python3 scripts/evals/spike_sync_scorer.py <clip>` |
| runtime spike | +200 ms adelay-shifted clip | offset ≈ +200 ± 40 ms | same with `--shift-ms 200` |
| runtime spike | audio from a different clip | low confidence / explicit fail signal | same with `--mismatch` |

- Acceptance gates: G1 decision record exists with measured numbers; G2 spike detects the injected 200 ms shift within tolerance on ≥1 real face video; G3 mismatch case does NOT report high confidence; G4 no production files modified.
- Audit focus: honesty of measurements; dependency reproducibility (pinned); weight license recorded.
- Rollback: spike is additive; nothing to roll back.

---

## TKT-102 — Production sync adapter and `syncnet_offset` evidence writer

- Requirements: R-LS-1, R-LS-2. Class: COMPLEX. Deps: TKT-101 accepted, TKT-001 accepted. Blocks: TKT-103, TKT-104.
- Observable outcome: A `SyncModelAdapter` implementation (per TKT-101 decision) registered in `scripts/lipsync_scoring.py`; `_qa_hero_lipsync` (`scripts/media_service.py:895-1046`) in production mode calls it and records a real `syncnet_offset` validation (`method: <scorer_name>`, no `simulated` flag, `face_track_found`, `offset_ms`, `confidence`, input SHAs). If the backend is unavailable in production mode, QA records `needs_human_av_review` and the unit does NOT pass — never a fabricated pass (INV-3). Test mode unchanged.
- Evidence: adapter seam `scripts/lipsync_scoring.py` (fail-closed by design); proxy branch `scripts/media_service.py:990-1032`.
- Scope: `scripts/lipsync_scoring.py`, `scripts/media_service.py`, new `scripts/sync_scorer/` module; tests use a deterministic fixture backend (AD-3) — the real model is exercised only via an opt-in marker (`pytest -m sync_model`, skipped by default). Protected: gates in `assemble_db.py`; test-mode fake branch semantics.
- Baseline: production-mode `_qa_hero_lipsync` on a fixture yields no `syncnet_offset` row (current behavior); focused suite passes.
- Steps:
  1. Adapter class with `score(video_path, audio_path) -> SyncScore` (offset_ms, confidence, face_track_found, method, model_version).
  2. Backend selection via explicit config `SYNC_SCORER_BACKEND=real|fixture|none`; default `none` → fail-closed.
  3. Call from the `_qa_hero_lipsync` production branch; keep the envelope proxy as a cheap pre-filter only — its result can never pass a unit.
  4. Write the validation row with provenance (video sha, audio slice sha).
  5. Pass/fail decision defers to `lipsync_policy.py` thresholds (calibrated in TKT-104); until calibrated, measured units route to review with numbers attached — do NOT hardcode permissive thresholds.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | fixture backend returns offset 10 ms, conf 8 | `syncnet_offset` validation written; method != test fake | `python3 -m pytest tests/test_sync_scorer_adapter.py -q` (new) |
| negative | backend `none`, production mode | unit not passed; `needs_human_av_review`; no fabricated evidence | same |
| negative | fixture backend low confidence | fail routing to repair | same |
| regression | test-mode fake path | unchanged | `YT_TEST_MODE=1 python3 -m pytest tests/ -k lipsync -q` |
| runtime (opt-in) | real backend on real clip | plausible offset written | `python3 -m pytest -m sync_model -q` |

- Acceptance gates: G1 production-mode QA with fixture backend writes a non-simulated `syncnet_offset` row (fields asserted); G2 backend-absent case fails loudly; G3 assembly gate accepts the new evidence in a prod-mode harness (integration test, with TKT-001 rejection active); G4 full suite passes.
- Audit focus: no silent fallback from `real` to `fixture`; provenance SHAs of the exact video+audio scored; adapter statelessness/concurrency.
- Rollback: revert commit; config default `none` means the feature is inert if reverted mid-wave.

---

## TKT-103 — Automated measure → compensate → re-measure loop

- Requirements: R-LS-3. Class: COMPLEX. Deps: TKT-102.
- Observable outcome: When measured `offset_ms` exceeds policy threshold but lies within a correctable band, the repair lifecycle automatically produces a compensated artifact using the measured offset (no operator `--offset-ms`), re-runs the scorer on the compensated output, and only a passing re-measurement writes `compensated_artifact_path` onto the provider job (consumed by `scripts/assemble_db.py:564-592`). Non-correctable offsets route to regeneration per existing repair actions.
- Evidence: manual remux `scripts/evals/remux_compensated_hero.py:24-79`; repair routing `scripts/media_service.py:1459-1480`; assembly requirement `scripts/assemble_db.py:564-592`.
- Scope: `scripts/media_service.py` (repair lifecycle); refactor remux logic into an importable function (keep the CLI working); tests with fixture backend simulating offsets. Protected: prohibition on temporal transforms of `HERO_SYNC_LOCKED` video (compensation delays audio only — video stream copied, consistent with the existing remux).
- Baseline: repair lifecycle currently routes `hero_lipsync_unverified` → `regenerate_provider_video` only.
- Steps:
  1. Extract `compensate(video, slice, offset_ms) -> path` from the remux script.
  2. Repair action `compensate_hero_audio` for offsets within a configurable band (constants documented, e.g. 40–400 ms; final values from TKT-104 calibration).
  3. Re-measure compensated output; pass → link compensated path; fail → fall through to regeneration.
  4. Every attempt logged as a validation row.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | fixture backend: 120 ms, then 5 ms after compensation | compensated path set; final pass evidence | `python3 -m pytest tests/test_offset_compensation_loop.py -q` (new) |
| negative | 800 ms offset (out of band) | routed to regeneration; no compensation attempted | same |
| negative | compensation re-measure still failing | no compensated path; repair continues per lifecycle | same |
| contract | assembly with compensated artifact | S13-T002 gate satisfied | integration test in prod-mode harness |

- Acceptance gates: G1 loop demonstrably measure→compensate→re-measure with distinct validation rows per attempt; G2 failing re-measure never sets `compensated_artifact_path`; G3 full suite passes.
- Audit focus: idempotency across resume; compensated artifact registered with parent lineage; no video re-encode.
- Rollback: revert commit; compensated artifacts are additive.

---

## TKT-104 — Threshold calibration and tier policy

- Requirements: R-LS-4, RISK-3, UV-4. Class: REASONING_CRITICAL. Deps: TKT-102; real hero clips available (else BLOCKED).
- Observable outcome: `lipsync_policy.py` tier thresholds (`close_hero`/`medium_hero`/`wide_hero`) are set from measurements over a labeled local set (known-good clips + adelay-shifted known-bad variants at 80/160/320 ms), with a calibration report `docs/plans/PPQ_SPRINT_20260704/evidence/TKT-104-calibration.md` showing per-tier separation and chosen operating points; the policy file references the report.
- Evidence: tiers exist (`lipsync_policy.py`, consumed by `scripts/assemble_db.py:505-556`); candidate real clips: `outputs/seedance_truth_test_001/` (verify UV-4 first).
- Scope: `lipsync_policy.py` constants + calibration script `scripts/evals/calibrate_sync_thresholds.py`; evidence doc. No paid calls. If fewer than 3 real hero clips exist and none can be supplied: `BLOCKED: need >=3 real hero clips`.
- Baseline: inventory hero videos under `outputs/`; record count and durations.
- Steps:
  1. Inventory usable clips.
  2. Generate shifted negatives with ffmpeg (80/160/320 ms).
  3. Score all with the real backend.
  4. Choose thresholds with zero false-pass on the negative set.
  5. Write report; update policy constants; unit tests pin policy values to the report.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| runtime | calibration script over labeled set | report written; 0 false-pass at chosen thresholds | `python3 scripts/evals/calibrate_sync_thresholds.py --clips <dir>` |
| unit | policy constants match report | assert equality | `python3 -m pytest tests/test_lipsync_policy_calibrated.py -q` (new) |
| negative | 320 ms shifted clip vs policy | FAIL verdict in every tier | included in calibration assertions |

- Acceptance gates: G1 calibration report exists with real measured numbers; G2 all injected-shift negatives fail policy; G3 all known-good clips pass or are individually justified in the report; G4 full suite passes.
- Audit focus: no threshold chosen merely to make current clips pass; small sample size stated honestly as a limitation.
- Rollback: revert policy constants to prior values (report remains as evidence).

---

## Wave 1 gate

- W1-G1: In a production-mode integration harness with the fixture backend, a hero unit travels QA → (compensation if needed) → assembly `syncnet_offset` gates with zero simulated evidence and zero review-only exemptions.
- W1-G2: With `SYNC_SCORER_BACKEND=none`, the same harness blocks (fail-closed proof).
- W1-G3: Full pytest suite passes.

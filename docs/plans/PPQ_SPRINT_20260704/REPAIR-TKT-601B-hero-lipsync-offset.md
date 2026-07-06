# REPAIR-TKT-601B — Systematic hero lipsync offset: Seedance audio-conditioning contract defect

## Status: PLANNED (blocks TKT-601 E2E run, hero unit `render_35e23c95a92743558f09b095ab2cb642`)

- Discovered during: TKT-601 E2E resume (production `prod_4e0ce12e24314d7798188aff60dca45f`, seed "How AI reads your handwriting and turns it into digital notes", short format).
- Sprint: `PPQ-2026-07`. Blocks: TKT-601 (Wave 6 exit criterion R-E2E-1), specifically the hero clip `003_proof_takeaway` assembly gate.
- Class: COMPLEX (cross-cuts provider adapter + audio slicing + sync measurement + compensation).
- Deps: Waves 0–5 accepted; REPAIR-TKT-601A accepted; KLP-601-W1..W4 accepted.
- Constraint from operator: **zero lipsync desync permitted in final output**. No gate loosening. No paid regeneration in this ticket (measure/fix contract only).

---

## 1. Root cause (evidence-based)

Seedance 2.0 (via Higgsfield) consistently returns hero talking-head clips whose **embedded audio LAGS mouth motion by ~480ms** (viewer sees lips move, hears words 480ms later). The offset is **systematic** (same sign, magnitude correlated with a duration mismatch) — not random GenAI mouth-quality variance.

### Evidence table

| Observation | Value | Source |
|---|---|---|
| Measured offset, prod hero unit | **+480ms** (audio lags mouth) | `evidence/TKT-601-run-final.json:3913` |
| Video vs supplied-audio duration | 8041ms vs 7738ms (**+303ms surplus video**) | `evidence/TKT-601-run-final.json:3928` (`duration_delta_ms: 303`) |
| Intrinsic offsets, other real Seedance heroes | +120ms (S000), +440ms (S002) — **all positive** | `evidence/TKT-101-sync-scorer-decision.md:126-144` |
| Regeneration produced identical clip | same sha256 `2511f199c36cf842` | live E2E resume 2026-07-06 |
| Measurement quantum | 480 = exactly 24 × 20ms envelope hops | `scripts/sync_scorer/_algorithm.py:30` |
| Scorer confidence | 0.1898 (low), face_track_fraction 0.5181 | `evidence/TKT-601-run-final.json` |

### Defect A — Contradictory audio flags (provider contract ambiguity)

`scripts/paid_adapters.py:211-213` **always** sends `--generate_audio true`:

```python
audio_param, audio_vals = schema["audio_param"]
args.extend([f"--{audio_param}", audio_vals[0]])  # default = first (true/on)
```

Then `scripts/paid_adapters.py:223-231` **also** attaches the ElevenLabs conditioning slice via `--audio`. Seedance is instructed to *both* generate its own audio *and* accept a conditioning track. The provider treats the supplied WAV as a soft reference, not an authoritative sync track, leaving a ~120-180ms intrinsic desync floor. `generate_audio=false` is never tried with `--audio`.

### Defect B — Duration-ceiling mismatch (dominant, ~300ms of the offset)

Duration is `ceil()`'d to whole seconds twice:
- `scripts/produce_db.py:2070`: `duration_sec = max(1, ceil(required_duration_ms / 1000))`
- `scripts/paid_adapters.py:182` (second ceil)

The pipeline sends a **7738ms fractional audio slice** into an **8s video request** → Seedance returns **8041ms video** and places/pads the shorter audio late in the longer container. The +303ms video surplus accounts for the bulk of the 480ms; the residual ~180ms matches the intrinsic provider floor from Defect A.

### Defect C — Compensation applies the wrong sign for positive offsets

`scripts/compensate.py:31`:

```python
delay_ms = abs(offset_ms)   # always delays audio
```

Its own docstring (`compensate.py:23-25`) states delaying audio only fixes **negative** offsets (audio leads). The measured Seedance failure mode is **positive** (audio lags). Delaying already-late audio pushes it *further* out of sync. The `_cross_correlate` docstring is also inverted (`_algorithm.py:181` says "lag>0 means audio leads"; the code and TKT-101 differential proof at `TKT-101-sync-scorer-decision.md:127` prove the opposite). The sign conventions across this subsystem are internally inconsistent.

### Defect D — Compensation cap rejects correctable offsets

`scripts/compensate.py:14`: `COMPENSATION_MAX_OFFSET_MS = 400`. A 480ms offset is declared UNCORRECTABLE (`media_service.py:1160-1170`) and routed to paid regeneration — which produces the identical clip (same sha256), wasting money with no quality change.

---

## 2. Karpathy loop structure

```text
Build → Run → Measure → Analyze → Fix root cause → Repeat
          ↑_________________________________________|
```

Each wave lands one root-cause fix, then MEASURES the offset on the existing artifact (no paid regeneration — remux/re-score only), and decides whether the residual is within the correctable band. The loop exits when the hero unit's measured post-compensation offset is ≤ `close_hero` pass threshold (120ms) with the correction verified by re-scoring the compensated remux.

**Measurement-only discipline:** every wave re-scores the *already-downloaded* artifact and/or a locally-produced compensated remux. No wave submits a paid Higgsfield job. The clip on disk (`assets/media/prod_4e0ce12e.../pjob_cd63c3115fdb48fcbaf482c6e6d9c349.mp4`) is the fixed input for all measurement.

Each wave runs the full `ENGINEER → AUDITOR → VALIDATOR` protocol (PLAN.md §6). Git commit after each validator PASS.

---

## Wave 1 — REPAIR-601B-W1: Directional, uncapped compensation (fixes final output NOW)

### Requirement
The final deliverable must have zero desync. A *measured-then-corrected* remux that re-scores to ≤120ms satisfies "no desync" honestly — the measurement proves the correction worked. This wave makes compensation correct for positive offsets and raises the cap, so the existing 480ms clip becomes deterministically correctable without regeneration.

### Root cause targeted
Defects C + D.

### Observable outcome
- `compensate()` applies **directional** correction: for a positive offset (audio lags mouth), it advances the audio (trim leading audio / negative delay via re-timestamp) OR delays the video by `offset_ms`; for a negative offset it delays audio (current behavior). Direction derived from the measured sign, not `abs()`.
- `COMPENSATION_MAX_OFFSET_MS` raised to a calibrated value (≥ 500ms) justified by the scorer's ±600ms search window (`_algorithm.py:27`) and TKT-104 calibration; documented in `configs/lipsync_thresholds.yaml` provenance.
- After compensation, the remux is **re-scored** by the same `face_landmarker_mouth_xcorr` backend; the unit passes only if the re-measured offset ≤ `close_hero` pass_ms (120ms). No gate loosened — the *clip* is fixed, then re-verified.

### Scope
- `scripts/compensate.py`: directional delay logic keyed on offset sign; raise cap constant.
- `scripts/media_service.py:1160-1170`: reclassify [160, NEW_MAX] as CORRECTABLE; keep >NEW_MAX → regenerate.
- `scripts/sync_scorer/_algorithm.py:181`: fix the inverted docstring (comment only, no logic change) to end the sign confusion.
- Re-score-after-compensate: verify `media_service` repair path (`compensate_hero_audio` action, ~line 2017-2114) already re-runs QA on the compensated artifact; if not, add the re-score step.

### Baseline (must reproduce before editing)
```bash
# Measure the existing hero artifact — expect ~480ms positive offset
SYNC_SCORER_BACKEND=real python3 -c "from scripts.sync_scorer.scorer import get_sync_scorer_backend; b=get_sync_scorer_backend(); r=b.score('assets/media/prod_4e0ce12e24314d7798188aff60dca45f/pjob_cd63c3115fdb48fcbaf482c6e6d9c349.mp4','assets/media/.../pjob_cd63c3115fdb48fcbaf482c6e6d9c349.mp4'); print(r.offset_ms)"
```

### Test and proof matrix
| Level | Scenario | Expected | Command |
|---|---|---|---|
| unit | inject +480ms audio-lag fixture, compensate | re-scored offset ≤ 120ms | `python3 -m pytest tests/test_offset_compensation_loop.py -q` |
| unit | inject −300ms audio-lead fixture, compensate | re-scored offset ≤ 120ms (existing negative path unbroken) | same |
| contract | positive vs negative sign → opposite ffmpeg filter | assert `adelay` on audio for negative, video-delay/audio-trim for positive | same |
| e2e (no paid) | compensate the real prod hero clip, re-score | measured post-remux offset ≤ 120ms; artifact linked; unit → valid | manual, evidence archived |

### Acceptance gates
- G1: The real 480ms hero clip, after directional compensation, re-scores ≤ 120ms (close_hero pass). Evidence archived.
- G2: Negative-offset compensation path unchanged (regression fixture passes).
- G3: `COMPENSATION_MAX_OFFSET_MS` change justified by calibration reference; no gate/threshold in `lipsync_thresholds.yaml` weakened.
- G4: Full invariant suite passes.

### Audit focus
Sign correctness (does positive offset get the opposite correction?); re-score-after-compensate is real (not asserted from the pre-remux measurement); no threshold in `lipsync_thresholds.yaml` loosened; cap raise is calibration-justified not arbitrary.

---

## Wave 2 — REPAIR-601B-W2: Stop double-signaling audio to Seedance

### Requirement
When a hero conditioning audio slice is supplied, Seedance must treat it as the authoritative track, not generate competing audio.

### Root cause targeted
Defect A.

### Observable outcome
`scripts/paid_adapters.py`: when `--audio <slice>` is attached (seedance hero path), send `--generate_audio false` (or omit the generative flag if the CLI treats absence as false). When no conditioning audio (b-roll), keep `--generate_audio true`. The flag is conditional on presence of `audio_path`, not unconditional.

### Scope
- `scripts/paid_adapters.py:211-231`: make `generate_audio` conditional on `audio_path`.
- Verify Higgsfield CLI accepts `generate_audio false` with `--audio` (discovery step; if the CLI rejects the combination, record `BLOCKED` with the exact CLI error and fall back to Wave 1's compensation as the sole path).

### Baseline
Record the current CLI argv for a hero submission (from `provider_jobs.request_json` of the existing job) showing `--generate_audio true` AND `--audio`.

### Test and proof matrix
| Level | Scenario | Expected | Command |
|---|---|---|---|
| unit | hero payload (audio_path set) | argv contains `--generate_audio false` + `--audio` | `python3 -m pytest tests/test_paid_adapters.py -q` (extend) |
| unit | b-roll payload (no audio_path) | argv contains `--generate_audio true`, no `--audio` | same |
| contract | I4 invariant preserved | `--audio` still seedance-only; kling still rejects audio | same |

### Acceptance gates
- G1: Hero argv sends `generate_audio false` with `--audio`; b-roll unchanged.
- G2: I4 invariant (audio = seedance-only) preserved.
- G3: CLI-compatibility discovery documented (accepts the combination, or `BLOCKED` with evidence).
- G4: Full invariant suite passes.

### Audit focus
No paid call introduced in tests (mock the CLI transport); the conditional is on `audio_path` presence not on a test flag; I4 invariant intact.

### NOTE — measurement without paid regeneration
This wave changes the *submission contract* but the operator forbids regeneration in this repair. Its effect is validated by the argv assertion (contract test), NOT by a new paid clip. The real-clip proof of reduced offset is deferred to the eventual authorized TKT-601 regeneration; this ticket lands the corrected contract so the *next* authorized generation is well-formed.

---

## Wave 3 — REPAIR-601B-W3: Frame-aligned audio slice for integer-second requests

### Requirement
The conditioning audio content must front-align to video frame 0, and the request duration must not create a container surplus that the provider fills with misaligned audio.

### Root cause targeted
Defect B.

### Observable outcome
One of two approaches (engineer selects with evidence):
- **(a) Pad-to-ceil**: pad the fractional audio slice with trailing silence to the exact ceil'd integer-second duration before submission, so audio and requested video durations match (7738ms slice → pad to 8000ms). Content start stays at sample 0.
- **(b) Floor-not-ceil**: request `floor()` seconds when the slice is already ≥ the minimum, eliminating the surplus (7738ms → request 7s, accept 7738ms of a 7s+ε render). Only if the provider honors sub-request trims.

Approach (a) is preferred (deterministic, no content loss). Slot slicing at `scripts/slice_continuous_lipsync.py:290-421` already guarantees no leading pad (docstring line 311); this wave adds a *trailing* pad-to-ceil at submission time, not a re-slice.

### Scope
- `scripts/produce_db.py:2070-2085` (hero submission payload build) or `scripts/slice_continuous_lipsync.py`: trailing-pad the conditioning slice to the ceil'd duration.
- Preserve `source_slice_sha256` provenance: the padded slice is a submission-time derivative; the hero provenance gate (`media_service.py:123-134`) must still see the authoritative source slice hash. Record the padded-slice hash separately if needed.

### Baseline
Show the current mismatch: slice duration 7738ms, requested 8s, returned 8041ms (`duration_delta_ms: 303`).

### Test and proof matrix
| Level | Scenario | Expected | Command |
|---|---|---|---|
| unit | 7738ms slice, ceil 8s | padded slice is exactly 8000ms, content start at 0, trailing silence | `python3 -m pytest tests/test_hero_slice_padding.py -q` (new) |
| contract | provenance | source_slice_sha256 gate still satisfied; padded-slice hash recorded distinctly | same |
| regression | integer-second slice (e.g. 5000ms) | no padding applied (already aligned) | same |

### Acceptance gates
- G1: Fractional slice pads to exact ceil'd duration with content front-aligned.
- G2: Hero provenance gate (`source_slice_sha256`) still enforced.
- G3: No leading silence introduced (would reintroduce the closed-mouth-frames failure mode).
- G4: Full invariant suite passes.

### Audit focus
Padding is trailing-only (leading pad would create the opposite offset); provenance hash chain intact; no paid call in tests.

---

## Wave 4 — REPAIR-601B-W4: Karpathy loop close — measure & decide

### Requirement
Prove the combined W1-W3 fixes bring the hero unit to zero verified desync using ONLY the existing artifact (compensation path), or clearly document that a future authorized regeneration is required.

### Observable outcome
- Apply W1 directional compensation to the existing 480ms clip → re-score.
- If re-scored offset ≤ 120ms: hero unit passes `close_hero`, links compensated artifact, assembly unblocks. **Loop exits — final output has zero desync, verified by re-measurement.**
- If re-scored offset > 120ms: document the residual, mark the hero unit as requiring authorized regeneration with the W2+W3 corrected contract (which the operator can authorize separately). **Loop exits with a clear, evidence-backed BLOCKED on paid regeneration.**

### Scope
No production code. Measurement + evidence archival only. Updates STATE.json and EXECUTION_LOG.jsonl.

### Test and proof matrix
| Level | Scenario | Expected | Command |
|---|---|---|---|
| e2e (no paid) | compensate real hero, re-score | offset ≤ 120ms OR documented residual | manual, evidence to `evidence/REPAIR-601B-hero-compensation.json` |
| e2e (no paid) | resume assembly after hero fix | assemble passes `BLOCKED_HERO_SYNCNET` gate with the compensated artifact | `python3 scripts/produce_db.py resume <id>` |

### Acceptance gates
- G1: Hero unit reaches a verified-zero-desync state via compensation, OR a documented paid-regeneration requirement with the corrected contract.
- G2: If compensated: assembly's `BLOCKED_HERO_SYNCNET_BELOW_THRESHOLD` gate is satisfied by the re-measured compensated artifact (not by threshold change).
- G3: Full invariant suite passes.

---

## 3. What is NOT in scope

- **No paid Higgsfield regeneration** in any wave (operator constraint). W2/W3 land the corrected submission contract for a *future* authorized generation; W1/W4 fix the *current* clip via compensation.
- **No gate/threshold loosening** in `configs/lipsync_thresholds.yaml`. The `close_hero` pass=120/fail=160 stays. The clip is corrected, then re-measured against the unchanged gate.
- **No architectural swap to a dedicated lipsync model** (Wav2Lip/LatentSync/MuseTalk) — that is the correct long-term fix (Tier 2) but is a separate sprint-level ticket (`REPAIR-TKT-601C`, planned, not in this loop).
- **No changes to the sync scorer algorithm** beyond the inverted-docstring comment fix (measurement is calibrated and trusted per TKT-104).

---

## 4. Traceability

| Defect | Wave | Root-cause fix | Proof |
|---|---|---|---|
| C (wrong-sign compensation) | W1 | directional delay | re-score ≤120ms |
| D (400ms cap too low) | W1 | calibrated cap raise | correctable band extended |
| A (double audio flags) | W2 | conditional generate_audio | argv contract test |
| B (duration-ceil surplus) | W3 | trailing pad-to-ceil | slice-duration test |
| — (loop close) | W4 | measure & decide | compensated-artifact assembly pass |

---

## 5. Restartability

Per TKT-601 scope, once REPAIR-TKT-601B waves land, resume `prod_4e0ce12e` assembly with the compensated hero artifact. Research/script/storyboard/TTS/generation artifacts are intact; only the hero unit's artifact linkage + assembly onward re-evaluate. No stage before `qa_media` re-runs.

---

## 6. Residual risks

- **W1 directional correction assumes the sign is stable.** TKT-101 evidence shows all measured Seedance heroes are positive-offset, but a future clip could be negative; the directional logic handles both by construction.
- **W2 CLI compatibility unverified** until an authorized generation runs. If `generate_audio false` + `--audio` is rejected by Higgsfield, W2 reports BLOCKED and W1 compensation remains the sole correction path — still achieving zero desync on output.
- **W3 pad-to-ceil could theoretically shift the provider's audio placement** in an unmeasured way; validated only at the next authorized generation. Until then, W1 compensation is authoritative for the current clip.
- **Compensation re-encode**: `compensate()` stream-copies video (`compensate.py:39` `-c:v copy`) so no generational loss; audio is re-timed only.

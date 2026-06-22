# Rectification Plan — Sprints R4 + R5

**Theme:** Provider contract & diagnostics (R4); one master-audio spine + locked picture (R5).
**Depends on:** R2 + R3 complete (trustworthy schema, true-silence hero slices).
**Contains BLOCKER:** R5-002 (lay narration exactly once).
**Governance:** Coder → Auditor → Validator; reports under `reports/remediation/rectification/<TICKET-ID>/`.

---

## Context

R4 replaces the simulated provider (`produce_db.py:373-397` writes `b"stubbed video content"`) with a real adapter interface, makes the semantic fingerprint the mandatory idempotency key, separates diagnostic provider audio from final-use audio, and makes timing-drift measurement real (audit: current `timing_drift.py` reads "video duration" from an audio query and "correlation lag" isn't correlation). R5 collapses the dual assembly architecture (`assemble.py` mixes `keep_lipsync` + `HERO_SYNC_LOCKED` and slices narration per-shot at `:580-603`) into a single immutable master-narration spine over a video-only picture timeline.

**Hard rule (`.kiro/rules/no-hacks.md`):** real provider bytes validated before completion; no dummy artifacts on the production path.

## Existing primitives to reuse / harden

| Need | Existing | Location |
|---|---|---|
| Hero request fingerprint | `generate_hero_request_fingerprint`, `validate_fingerprint_match` | `provider_fingerprint.py:21,64` |
| Timing-drift scaffold | `analyze_timing_drift`, `record_timing_drift_evidence` | `timing_drift.py:73,157` |
| Provider job rows | `submit_provider_job` + provider_jobs table | `production_db.py` |
| Assembly DTO scaffold | `build_hero_assembly_dto`, `validate_dto_staleness`, `HeroAssemblyDTO` | `assembly_dto.py:16,37,127` |
| B-roll cutaway scaffold | `validate_cutaway_policy`, `assemble_hero_with_broll_cutaways` | `broll_cutaway.py:16,47` |
| FFmpeg validator | `ffmpeg_validator.py` | scripts/ |

---

## Sprint R4 — Provider Contract & Diagnostics

### R4-001 — Enforce semantic fingerprint
- Use a **full** collision-resistant hash (stop truncating); canonicalize duration in **samples / provider bucket** (remove float duration from identity).
- Persist payload + fingerprint algorithm version; bind each job to plan revision + spend approval; reject stale approval.
- Exact retry returns the existing job; any changed input creates a new job and stales dependents.
- **Crash tests:** crash before submit / after submit / after external-ID assignment / after completion-before-artifact-registration → no duplicate paid work.

### R4-002 — Provider adapter interface
- Move the fake provider into **test code** (gated by `YT_TEST_MODE`); production rejects the fake adapter (enforced by R0-001 interlock).
- Define `submit() / poll() / download()` interface; require explicit adapter config (Higgsfield/Seedance for video, ElevenLabs for TTS).
- Persist raw request/response safely; validate downloaded bytes (probe + SHA) before marking job completed; **no production dummy artifacts**.
- Replace `produce_db.invoke_generate_media` simulation with adapter calls behind this interface.

### R4-003 — Crash-safe diagnostic lifecycle
- Separate **provider video** artifact from **diagnostic audio** artifact; link both to provider job + hero slice + master.
- Durable states; idempotent resume; create a **video-only assembly derivative** (provider audio stripped) for the picture timeline.
- Constrain diagnostic audio from ever being used as final narration (state/constraint, not just metadata).

### R4-004 — Real timing-drift measurement
Rewrite `timing_drift.py`:
- Probe video and audio streams correctly (separate queries).
- Real waveform **cross-correlation**; offset estimate at begin/middle/end; progressive-drift calculation.
- Detect speech in padding; detect dropped/duplicated speech.
- Bind evidence to exact source/output hashes; version algorithm + thresholds.

**Sprint R4 exit:** provider lifecycle is idempotent and timing evidence is real.

---

## Sprint R5 — One Master Audio Spine & Locked Picture

### R5-001 — One DB-native assembly contract
- Replace temporary/incompatible objects with **one versioned DTO** (extend `assembly_dto.py`) covering picture tracks, master audio, music, ambience, graphics, captions, outputs.
- Build only from DB; JSON is internal serialization only.
- Verify artifact existence + SHA; verify current evidence; block open repairs and stale approvals; remove silent policy-import `except ImportError` fallback.

### R5-002 — Lay narration exactly once — **BLOCKER**
Rewrite the audio path in `assemble.py` (remove `keep_lipsync` constant `:73`, per-shot narration slicing `:580-603`, muted-hero fallback):
1. Build a complete **video-only** picture timeline; strip provider + B-roll audio (`-an`).
2. Add the immutable master narration **once** at the final mix.
3. Add only explicit ambience/SFX/music.
4. Verify final narration waveform correlates against the master.

**Tests:** exactly one narration input; no provider narration; no narration slices; waveform correlation passes; no duplicated boundary words; exact-duration tolerance.

### R5-003 — Structured FFmpeg policy validation
Replace substring checks in `ffmpeg_validator.py` with typed operations / filtergraph parsing:
- Hero allowlist; **fail closed on unknown temporal operation**; validate timestamps + frame count; prohibit hidden cadence/duration changes.
- **Negative tests:** `setpts`, `asetpts`, `atempo`, `trim`, `atrim`, `tpad`, loop, stream-loop, interpolation, frame-rate conversion, offsets/delays/padding, concat duration mismatch.

### R5-004 — Rebuild B-roll cutaway compositor
Rewrite `broll_cutaway.py` to use DB intervals + artifact ids:
- Validate sorted, non-overlapping, positive intervals; per-cutaway source offsets; require safe-boundary evidence (R6-003); preserve hero frame timing; output **video-only**; verify frame count + duration.

**Sprint R5 exit:** final narration has exactly one source and hero picture timing is unchanged.

---

## Verification

```bash
export YT_TEST_MODE=1   # adapter uses test double; bytes still validated
python3 -m pytest tests/contracts/test_provider_fingerprint*.py tests/contracts/test_timing_drift*.py -q
python3 -m pytest tests/integration -q          # crash/resume matrix subset for provider lifecycle
# Assembly: assert single -i master, -an on all picture inputs, one amix/anull master, waveform correlation
python3 -m pytest -k "assemble and (spine or narration_once or ffmpeg_policy)" -q
```

## Risks
- Real cross-correlation needs a numeric dep (numpy/scipy) — add to `requirements.lock`; keep it import-guarded only in test-double paths, never as a silent fallback.
- Adapter secrets (`runtime.env`) absent in CI → adapter tests must use the test double; real calls only in R11.
- Rewriting `assemble.py` audio path is high-blast-radius; gate behind the new DTO and keep old path deleted, not dual-routed.

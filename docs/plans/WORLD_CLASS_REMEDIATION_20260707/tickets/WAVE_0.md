## Wave 0 — Foundation: Inspection, Fixtures, Baselines

These six tickets build all deterministic fixtures and inspect the current state so downstream Waves develop against a hermetic, measurable baseline. All tickets here produce ZERO production code changes — they are discovery and fixture-building only. INV-1 (2,825-test floor) must hold throughout.

---

### TKT-001 — Inspect & baseline reference-frame config + storyboard validator gaps

| Field | Value |
|-------|-------|
| Ticket | TKT-001 |
| Title | Inspect & baseline reference-frame config + storyboard validator gaps |
| Requirement / risk IDs | R-VIS-1, R-VIS-2, CS-1 |
| Priority | high |
| Severity | low |
| Risk level | low |
| Execution class | ROUTINE |
| Wave | 0 |
| Status | planned |

#### Observable outcome

A decision record at `evidence/TKT-001-reference-frame-baseline.md` that:
- Lists every reference-frame set currently in `configs/james/model_routing.yaml`.
- Counts the number of distinct angles and wardrobes available.
- Identifies the exact validator function(s) in `review_storyboard.py` that would need a frame-gap constraint.
- Identifies the exact validator function(s) that would need a fatigue-score constraint.
- Confirms whether the `storyboard_projection.py` canonical-shot schema already carries `visual_chapter` metadata or whether it must be added.

No production code is changed. This is a pure inspection ticket.

#### Evidence and rationale

- `configs/james/model_routing.yaml:35-42` — only one `active_set` with four angle frames.
- `review_storyboard.py:88-145` — bands check validates percentages only; no frame variety constraint.
- `storyboard_projection.py` — canonical shot schema; need to know if `visual_chapter` exists.

#### Context capsule

- Relevant paths: `configs/james/model_routing.yaml`, `scripts/review_storyboard.py`, `scripts/storyboard_projection.py`, `docs/channel_universe/constraints.json`.
- Upstream contracts: `constraints.json → lipsync_render_rules`.
- Protected: do not edit any production file in this ticket.

#### Preconditions and baseline

- Environment: `YT_TEST_MODE=1`.
- Baseline command: `YT_TEST_MODE=1 python3 -m pytest tests/ -q`
- Expected: `2825 passed` (or current floor).

#### Implementation steps (inspection only)

1. Read `configs/james/model_routing.yaml`; extract `sets`, list each wardrobe + setting + angle count.
2. Read `review_storyboard.py`; find `_bands_check` and `_anti_patterns`; confirm neither checks frame identity or gap.
3. Read `storyboard_projection.py`; determine if `canonical_shots[].visual_chapter` exists or must be added.
4. Inspect `docs/channel_universe/constraints.json` for any `visual_chapter` reference.
5. Write `evidence/TKT-001-reference-frame-baseline.md` with tables of available frames, validator gaps, and schema findings.

#### Test and proof matrix

This ticket has no tests to run (inspection only). But the decision record is auditable:

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| evidence | baseline record produced | `evidence/TKT-001-reference-frame-baseline.md` exists | `ls -la evidence/TKT-001-reference-frame-baseline.md` |
| evidence | record specifies validator function names for frame-gap | file lists exact function name | `grep -c "frame_gap\|visual_fatigue" evidence/TKT-001-reference-frame-baseline.md` |
| evidence | record specifies whether `visual_chapter` exists | file states yes/no | `grep "visual_chapter" evidence/TKT-001-reference-frame-baseline.md` |

#### Acceptance gates

- G1: `evidence/TKT-001-reference-frame-baseline.md` exists and is non-empty.
- G2: The baseline record lists all existing reference-frame sets.
- G3: The baseline record identifies exact validator functions for future modification.
- G4: Full pytest suite passes (`2825 passed` or current floor).

#### Audit focus

- Completeness: did the inspector read all three target files?
- Accuracy: are the validator function names textually present in the source?

#### Rollback and recovery

- No production code changed — no rollback needed. Delete the evidence file to restart.

#### Completion evidence

- Files created: `docs/plans/WORLD_CLASS_REMEDIATION_20260707/evidence/TKT-001-reference-frame-baseline.md`.
- Tests unchanged.

---

### TKT-002 — Build deterministic b-roll QC fixtures (frozen-frame, text-in-face)

| Field | Value |
|-------|-------|
| Ticket | TKT-002 |
| Title | Build deterministic b-roll QC fixtures (frozen-frame, text-in-face) |
| Requirement / risk IDs | F2, F6, R-BR-2, CS-2 |
| Priority | high |
| Severity | medium |
| Risk level | low |
| Execution class | ROUTINE (fixture) |
| Wave | 0 |
| Status | planned |

#### Observable outcome

A deterministic fixture module `tests/fixtures/broll_qc_fixtures.py` that generates:
1. **Frozen-frame clip:** 5.0s, 1920×1080, single-color frame held for entire duration.
2. **Moving clip:** 5.0s, 1920×1080, testsrc motion.
3. **Text-in-focus clip:** 5.0s, 1920×1080, clean slide with >5 clearly readable ASCII text lines.
4. **Human-face-in-focus clip:** 5.0s, 1920×1080, synthetic faces via `Pillow` drawing — enough metadata to trigger a face-detection pipeline if one is added.

Plus a test file `tests/test_broll_qc_fixtures.py` proving each fixture is generated and recognized.

No production code changes. All outputs are deterministic and hermetic (no paid calls, no network).

#### Evidence and rationale

- `scripts/broll_qa.py:259-316` — has working frozen-frame/gibberish detection logic but no pixel-level text/face detection.
- `scripts/media_service.py` — no importer of `broll_qa.check_broll_technical`.
- Current QA cannot fail a text-in-focus or face-in-focus clip.

#### Context capsule

- Relevant paths: `scripts/broll_qa.py`, `tests/fixtures/`, `fixtures/`.
- Upstream contracts: ffmpeg available on PATH.
- Protected: do not modify `broll_qa.py` in this ticket; only generate fixtures that exercise its existing logic + anticipated new logic.

#### Preconditions and baseline

- Environment: `YT_TEST_MODE=1`, ffmpeg installed.
- Baseline command: `which ffmpeg && ffmpeg -version | head -1`.
- Expected: ffmpeg returns version string.

#### Implementation steps

1. Add `tests/fixtures/broll_qc_fixtures.py` with four fixture generators using ffmpeg (`color` for frozen, `testsrc` for moving) and Pillow for synthetic text/face PNGs.
2. Each fixture writes to a temp dir provided by pytest's `tmp_path` fixture.
3. Each fixture returns the path + metadata (width, height, has_text, has_face, is_frozen).
4. Add `tests/test_broll_qc_fixtures.py` that:
   - Verifies frozen clip: decode frame 1 and frame N-1; assert identical bytes (frozen).
   - Verifies moving clip: decode frame 1 and frame N-1; assert different bytes (motion).
   - Verifies text-in-focus: OCR via tesseract if installed, else assert file metadata is `has_text=True`.
   - Verifies human-face: assert file metadata is `has_face=True` (face detection integration is a later ticket).
5. Confirm fixtures run with `YT_TEST_MODE=1` and without any network connection.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| fixture | frozen clip generated | file exists, >1MB, 5s duration | `python3 -m pytest tests/test_broll_qc_fixtures.py::test_frozen_clip -q` |
| fixture | moving clip generated | file exists, frame 1 != frame N | `python3 -m pytest tests/test_broll_qc_fixtures.py::test_moving_clip -q` |
| fixture | text-in-focus generated | file exists, metadata.has_text=True | `python3 -m pytest tests/test_broll_qc_fixtures.py::test_text_clip -q` |
| fixture | human-face clip generated | file exists, metadata.has_face=True | `python3 -m pytest tests/test_broll_qc_fixtures.py::test_face_clip -q` |
| negative | delete fixture mid-test | test does not leak file handles | add fixture `yield` + cleanup check |

#### Acceptance gates

- G1: All four fixtures generate without errors under `YT_TEST_MODE=1`.
- G2: Frozen fixture fails a naive "is the video frozen?" byte-comparison test.
- G3: Moving fixture passes the same test (NOT frozen).
- G4: All hermetic — unset any paid provider API keys and confirm tests still pass.
- G5: Full pytest suite passes.

#### Audit focus

- Hermeticity: confirm no network. Unset keys, disable wifi/nameserver, confirm tests pass.
- Determinism: run each fixture 3 times, compare SHA-256.

#### Rollback and recovery

- Revert commit; fixtures are additive.

#### Completion evidence

- Files created: `tests/fixtures/broll_qc_fixtures.py`, `tests/test_broll_qc_fixtures.py`.
- Commands run, exit codes, observed results.

---

### TKT-003 — Build research citation fixture (correctly sourced + fabricated)

| Field | Value |
|-------|-------|
| Ticket | TKT-003 |
| Title | Build research citation fixture (correctly sourced + fabricated) |
| Requirement / risk IDs | F3, R-RES-1, R-RES-2, CS-3 |
| Priority | high |
| Severity | medium |
| Risk level | low |
| Execution class | ROUTINE (fixture) |
| Wave | 0 |
| Status | planned |

#### Observable outcome

A deterministic fixture module `tests/fixtures/citation_fixtures.py` that generates:
1. **Correctly sourced brief:** A `research_brief.json` where every `key_claim[].source.url` points to a local fixture HTML file whose body contains the claimed statistic, named researcher, and year.
2. **Fabricated brief:** A `research_brief.json` where one or more `key_claim[].source.url` points to a local fixture HTML body that does NOT contain the claimed content.
3. **Mixed brief:** A `research_brief.json` where some claims are sourced and some are fabricated.

Plus a test file `tests/test_citation_fixtures.py` proving each fixture is generated and its metadata label (correct/fabricated) matches the fixture content.

No production code changes.

#### Evidence and rationale

- `write_script.py:127` — `detect_unsourced_named_claims` is WARNING-level only.
- No programmatic URL fetch+verify exists; this fixture enables testing for one when built.
- F3 requires fabricated citations to be impossible to pass through.

#### Context capsule

- Relevant paths: `scripts/write_script.py`, `scripts/research.py`, `tests/fixtures/`.
- Upstream contracts: No production code changes.

#### Preconditions and baseline

- Environment: `YT_TEST_MODE=1`.
- Baseline: fixtures/ directory exists.

#### Implementation steps

1. Add `tests/fixtures/citation_fixtures.py` with three fixture generators.
2. Each generator writes JSON brief files to `tmp_path` plus the referenced local fixture HTML files.
3. The correctly-sourced fixture HTML contains exact strings from the brief's `key_claim.claim`.
4. The fabricated fixture HTML contains unrelated text (e.g., a recipe) to force NER mismatch.
5. Add `tests/test_citation_fixtures.py` that:
   - Verifies the correctly-sourced fixture: re-reads the HTML, asserts the named entity + year + statistic string appear in the HTML body.
   - Verifies the fabricated fixture: re-reads the HTML, asserts the claimed content is NOT present.
6. Confirm hermetic (no network).

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| fixture | correctly-sourced brief | brief + local HTML exist, content matches | `python3 -m pytest tests/test_citation_fixtures.py::test_correctly_sourced -q` |
| fixture | fabricated brief | brief + local HTML exist, content DOES NOT match | `python3 -m pytest tests/test_citation_fixtures.py::test_fabricated -q` |
| fixture | mixed brief | brief + HTML files exist, exactly one claim is fabricated | `python3 -m pytest tests/test_citation_fixtures.py::test_mixed -q` |
| negative | fixture HTML deleted before test | fixture generator re-creates deterministically | add delete-then-regenerate assertion |

#### Acceptance gates

- G1: All three fixtures generate.
- G2: The "correctly sourced" fixture passes a local-content-match assertion.
- G3: The "fabricated" fixture fails the local-content-match assertion.
- G4: Hermetic (no network).
- G5: Full suite passes.

#### Audit focus

- Determinism: same fixtures, same bytes, every run.
- Correctness of the match assertion (not a no-op).

#### Rollback and recovery

- Additive only.

#### Completion evidence

- Files created: `tests/fixtures/citation_fixtures.py`, `tests/test_citation_fixtures.py`.

---

### TKT-004 — Build audio design fixture (flat vs act-scored stem comparison)

| Field | Value |
|-------|-------|
| Ticket | TKT-004 |
| Title | Build audio design fixture (flat vs act-scored stem comparison) |
| Requirement / risk IDs | R-AUD-1, R-AUD-2, F4, CS-4 |
| Priority | medium |
| Severity | low |
| Risk level | low |
| Execution class | ROUTINE (fixture) |
| Wave | 0 |
| Status | planned |

#### Observable outcome

A fixture module `tests/fixtures/audio_design_fixtures.py` that generates:
1. **Flat music bed fixture:** 60s WAV, single RMS level, no act distinctions.
2. **Act-scored stem fixture:** 4 WAV stems (Act 1-4), each with distinct RMS envelope matching expected narrative energy (rising, plateau, etc.).
3. **Paradigm-shift silence fixture:** A WAV where beats 30-35 are silent (no music), simulating a paradigm-shift moment.

Plus `tests/test_audio_design_fixtures.py` proving each fixture generates and its RMS profile matches the expected shape.

No production code changes.

#### Evidence and rationale

- Music is currently flat via `generate_music`; no act-aware scoring exists.
- F4 requires paradigm-shift beats to drop music.
- Fixtures enable testing of future act-scoring and silence rules.

#### Context capsule

- Relevant paths: `scripts/assemble.py:59`, `tools/generate_music.py` (if exists), `tools/music.py` (if exists).
- Protected: do not modify any production audio pipeline code.

#### Preconditions and baseline

- Environment: `YT_TEST_MODE=1`, ffmpeg available.
- Baseline: generate_music tool check (`ls tools/generate_music* tools/music* 2>/dev/null`).

#### Implementation steps

1. Create `tests/fixtures/audio_design_fixtures.py` generating WAV files with known RMS profiles using `wave` + `struct` (synthesized sine/silence, no external deps).
2. Flat fixture: 60s at -20 dBFS.
3. Act-scored fixtures: 4 stems with different RMS levels (e.g., Act1=-18, Act2=-22, Act3=-16, Act4=-24) so a future scoring rule can be tested against expected energy.
4. Paradigm-shift silence: 60s at -20 dBFS except 30-35s at -inf (zero samples).
5. Tests verify RMS computed via a simple Python decoder matches expected.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| fixture | flat fixture | RMS ≈ -20 dBFS across full duration | `python3 -m pytest tests/test_audio_design_fixtures.py::test_flat -q` |
| fixture | act-scored fixture | each act stem has distinct RMS | `python3 -m pytest tests/test_audio_design_fixtures.py::test_act_scored -q` |
| fixture | silence fixture | beat 30-35 has RMS < -60 dBFS (silence) | `python3 -m pytest tests/test_audio_design_fixtures.py::test_silence -q` |

#### Acceptance gates

- G1: All three WAV fixtures generate.
- G2: Flat fixture RMS matches within ±1 dB.
- G3: Scored fixtures have distinct per-act RMS.
- G4: Silence fixture has a silent 5s window.
- G5: Full suite passes.

#### Audit focus

- Synthesized audio is valid WAV (correct headers, sample count).
- RMS computation is correct (document formula in code comment).

#### Completion evidence

- Files created: `tests/fixtures/audio_design_fixtures.py`, `tests/test_audio_design_fixtures.py`.

---

### TKT-005 — Build EDL override fixture + constraint validation tests

| Field | Value |
|-------|-------|
| Ticket | TKT-005 |
| Title | Build EDL override fixture + constraint validation tests |
| Requirement / risk IDs | R-EDT-1, RISK-5 |
| Priority | medium |
| Severity | low |
| Risk level | low |
| Execution class | ROUTINE (fixture) |
| Wave | 0 |
| Status | planned |

#### Observable outcome

A fixture module `tests/fixtures/edl_fixtures.py` that generates:
1. **Valid EDL override:** trim ±0.5s on non-hero beats, no reordering, no constraint violation.
2. **Invalid EDL override:** trim that would push a beat below `BEAT_MIN_SEC` or cause shot-mix band violation.
3. **Valid reorder override:** swap two adjacent non-hero beats.

Plus `tests/test_edl_fixtures.py` proving each fixture is generated.

No production code changes in this ticket. The fixtures enable TKT-601 (the actual EDL schema).

#### Evidence and rationale

- Assembly is strictly deterministic; EDL overrides need a test surface before the schema exists.
- RISK-5: EDL overrides could violate shot-mix bands; constraint validation is mandatory.

#### Context capsule

- Relevant paths: `configs/james/model_routing.yaml`, `scripts/assemble.py`, `scripts/review_storyboard.py`.
- Protected: do not modify production code.

#### Preconditions and baseline

- Environment: `YT_TEST_MODE=1`.
- Baseline: N/A.

#### Implementation steps

1. Create `tests/fixtures/edl_fixtures.py` generating JSON fixture files for the three scenarios above.
2. Each fixture references a canonical test storyboard (or loads an existing fixture from `fixtures/`).
3. Tests verify JSON parses and metadata labels are correct.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| fixture | valid EDL fixture | JSON parses, no errors | `python3 -m pytest tests/test_edl_fixtures.py::test_valid_edl -q` |
| fixture | invalid EDL fixture | JSON parses, label=invalid | `python3 -m pytest tests/test_edl_fixtures.py::test_invalid_edl -q` |
| fixture | reorder EDL fixture | JSON parses, valid | `python3 -m pytest tests/test_edl_fixtures.py::test_reorder -q` |

#### Acceptance gates

- G1: All three fixtures generate and parse.
- G2: Full suite passes.

#### Completion evidence

- Files created: `tests/fixtures/edl_fixtures.py`, `tests/test_edl_fixtures.py`.

---

### TKT-006 — Build budget allocation fixture (flat vs beat-weighted)

| Field | Value |
|-------|-------|
| Ticket | TKT-006 |
| Title | Build budget allocation fixture (flat vs beat-weighted) |
| Requirement / risk IDs | R-BUD-1, R-BUD-2, CS-8 |
| Priority | medium |
| Severity | low |
| Risk level | low |
| Execution class | ROUTINE (fixture) |
| Wave | 0 |
| Status | planned |

#### Observable outcome

A fixture module `tests/fixtures/budget_fixtures.py` that generates:
1. **Flat allocation config:** A storyboard with 10 beats; flat $60 budget → $6 per beat.
2. **Weighted allocation config:** Same storyboard; a beat-attention classifier marks 3 beats as "hero thesis close" at 3× weight; remaining beats at 0.5× weight; budget redistributes to maximize weighted quality.

Plus `tests/test_budget_fixtures.py` proving the fixture budgets compute correctly.

No production code changes.

#### Evidence and rationale

- Flat $60 cap for explainers is too low for world-class content.
- R-BUD-1 requires beat-attention-weighted allocation.
- Fixtures enable testing before the allocator exists.

#### Context capsule

- Relevant paths: `configs/james/model_routing.yaml:48` (`budget_caps`).
- Protected: do not modify production code.

#### Preconditions and baseline

- Environment: `YT_TEST_MODE=1`.

#### Implementation steps

1. Create `tests/fixtures/budget_fixtures.py` generating JSON fixtures for a 10-beat test storyboard with configurable weights.
2. Flat allocator: total / beat_count per beat.
3. Weighted allocator: sum weights, distribute proportionally, clamp to a per-beat min and max.
4. Tests verify both allocators produce valid distributions that sum to the configured total.

#### Test and proof matrix

| Level | Scenario | Expected | Command |
|-------|----------|----------|---------|
| fixture | flat allocator | sum = configured cap | `python3 -m pytest tests/test_budget_fixtures.py::test_flat_allocation -q` |
| fixture | weighted allocator | hero beats receive ≥3× non-hero | `python3 -m pytest tests/test_budget_fixtures.py::test_weighted_allocation -q` |
| fixture | both allocators | neither exceeds the cap | `python3 -m pytest tests/test_budget_fixtures.py::test_cap_invariant -q` |

#### Acceptance gates

- G1: Flat allocation sums to cap.
- G2: Weighted allocation sums to cap.
- G3: Weighted allocation gives hero beats ≥3× non-hero.
- G4: Full suite passes.

#### Completion evidence

- Files created: `tests/fixtures/budget_fixtures.py`, `tests/test_budget_fixtures.py`.

---

## Wave 0 gate

- W0-G1: TKT-001..TKT-006 accepted by independent validator.
- W0-G2: All new fixtures are deterministic and hermetic (no paid calls, no network).
- W0-G3: Full pytest suite passes (2,825-test floor).

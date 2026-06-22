# S9-C05 Independent Validation Report — Multi-clip slotting + per-slot hero audio slices

**Validator:** Independent agent (no engineer/auditor relationship; validation run manually by the user per "complete the work, do not invoke claude")
**Date:** 2026-06-20
**Ticket:** S9-C05
**Implementation commits:** 0431595 (feat: multi-clip slotting + per-slot hero audio slices), b4e938a (re-audit PASS_WITH_FINDINGS), 6d18b57 (independent audit PASS)
**Audit verdict:** PASS (all findings F-001/F-002/F-003 fully corrected)
**Verdict:** PASS (GO)

---

## Executive Summary

S9-C05 is **ACCEPTED**. The implementation divides beats longer than the routed max clip length into N=ceil(span/max) slots that tile the span exactly (contiguous, no gaps/overlaps), each within [min,max] seconds, and materializes a real ffmpeg-produced master-narration audio slice per HERO_SYNC_LOCKED slot — registered as an immutable `hero_audio_slice` artifact, SHA-verified against an independent re-extraction of the master subrange, and linked to the render unit. All acceptance gates are met with actual runtime evidence (no mock-only proof):

- Focused tests pass (6/6)
- Broader compile/plan/slot regression pass (136/136)
- Full suite green (1076 passed, exit 0, 696.48s)
- Clip ranges read from `constraints.json` (not hardcoded)
- Slices are real ffmpeg output, byte-for-byte reproducible from the master subrange
- No dummy outputs, no silent fallbacks (missing master + sub-min hero fail loudly)
- S9-C02 supersession contract preserved (re-plan stale-marks prior units)
- No paid call made (`YT_TEST_MODE=1`; slices a local tone fixture)

---

## Validation Evidence

### 1. Baseline

- `git log --oneline -1` → `6d18b57 docs(recovery): S9-C05 independent audit PASS`
- `git status --short` → clean working tree (no uncommitted code)
- Branch: `fix/flagship-001-end-to-end-recovery`
- `which ffmpeg ffprobe` → `/usr/bin/ffmpeg`, `/usr/bin/ffprobe` (real slice production available)
- Focused test file present: `tests/test_s9_c05_slotting.py` (6 tests)

### 2. Focused Tests (6/6 passed, 2.02s)

```bash
YT_TEST_MODE=1 python3 -m pytest tests/test_s9_c05_slotting.py -q
```

**Result:** `6 passed in 2.02s`

| Test | Gate | Status |
|------|------|--------|
| `test_long_span_slots_within_bounds` | 30s hero → N slots each in [min,max] | PASS |
| `test_slots_tile_span_exactly` | contiguous ranges, first=0ms, last=30000ms, no gaps/overlaps | PASS |
| `test_boundary_span_max_duration` | span==max → 1 slot; span==max+1ms → 2 slots | PASS |
| `test_hero_slice_materialized` | real ffmpeg slice file + SHA matches independent re-extraction of master subrange + artifact registered + linked to unit (metadata.render_unit_id) + master provenance on unit row | PASS |
| `test_hero_span_without_master_fails` | hero span w/o tts_master raises `RuntimeError("tts_master")` — no silent fallback | PASS |
| `test_sub_min_hero_span_fails` | hero span < min_clip_duration_sec raises `RuntimeError("min_clip_duration_sec")` — no unrenderable unit | PASS |

The `test_hero_slice_materialized` test is a genuine determinism proof: it independently re-extracts the same `[start,end]` range from the master with ffmpeg and asserts `_sha(reextract) == slice_art["sha256"]` — proving the slice is byte-for-byte the master subrange, not a dummy/stub file.

### 3. Broader Regression (136/136 passed, 53.61s)

```bash
YT_TEST_MODE=1 python3 -m pytest tests/ -k "plan_render or compile or slot or coverage_geometry or hero" -q
```

**Result:** `136 passed, 944 deselected in 53.61s`

Covers compile/plan, slot expansion, coverage geometry, and hero paths — no regression from the slotting + slicing change or the `_HERO_SHOT_TYPE_ALIASES` route bridge.

### 4. Full Suite Green

```bash
YT_TEST_MODE=1 python3 -m pytest -q
```

**Result:** `1076 passed, 1 skipped, 1 xfailed, 2 xpassed, 13 warnings in 696.48s (0:11:36)`  
**Exit code:** 0

Matches the prior baseline (1076 passed, ~687s). Warnings are pre-existing (`UCI-04` legacy mode in `assemble.py`).

---

## Acceptance Gates Verification

| Gate | Requirement | Evidence | Status |
|------|-------------|----------|--------|
| 1 | A 30s hero span compiles into ≥3 slots each within the routed clip range, tiling exactly | `test_long_span_slots_within_bounds` (each slot in [4,15]s) + `test_slots_tile_span_exactly` (first=0ms, last=30000ms, no gaps/overlaps) | PASS |
| 2 | Each hero slot has a real ffmpeg-produced slice file whose SHA matches the master subrange, registered as an artifact and linked to the unit | `test_hero_slice_materialized`: real file at artifact URI, `probe_media` confirms audio, independent re-extraction SHA equals slice SHA, `hero_audio_slice` artifact with `metadata.render_unit_id` + `master_sha256`, unit row carries `master_audio_artifact_id`/`_sha256` + `speech_start_sample`/`end_sample` | PASS |
| 3 | Boundary spans (==max, ==max+1) behave correctly | `test_boundary_span_max_duration`: ==max → 1 slot; ==max+1ms → 2 slots | PASS |
| 4 | Full suite green | 1076 passed, exit 0, 696.48s | PASS |
| 5 | No paid call made | `YT_TEST_MODE=1` enforced; slices a local `sine` lavfi tone fixture; no ElevenLabs/Higgsfield invocation | PASS |

---

## Implementation Verification (independent source read)

### Clip ranges read from config (not hardcoded)
`scripts/produce_db.py:714-720` loads `lipsync_render_rules.{min,max}_clip_duration_sec` from `docs/channel_universe/constraints.json` (the single source of truth: min=4, max=15, with documented Seedance rationale). `slice_continuous_lipsync._load_lipsync_limits()` reads the same file. No hardcoded 4/15 in the slotting path.

### Slots tile the span exactly
`scripts/produce_db.py:823-852`: `num_slots = ceil(span_duration_ms / clip_max_ms)`; each slot `slot_start_ms = start + i*slot_duration_ms`; **last slot gets the remainder** (`slot_end_ms = end_ms if i == num_slots-1`) so the slots sum to the span with no gaps/overlaps.

### Hero slice materialization (F-001, was BLOCKING — now corrected)
`scripts/slice_continuous_lipsync.py:264-381` `materialize_hero_slot_slices()`:
- ffmpeg `-ss/-t` sample-exact PCM extraction (re-encode, never `-c copy`) at `MASTER_SAMPLE_RATE` (48000)
- `register_artifact(kind="hero_audio_slice", extra_metadata={speech_start/end_sample, master_artifact_id, master_sha256, render_unit_id})`
- `_sha(slice_path)` verified
- Updates the unit row with `master_audio_artifact_id` + `master_audio_sha256` + speech interval
- **Deliberately does NOT set `active_artifact_id` / advance status** (generation's job, R6-004) — confirmed in the docstring (lines 282-285) and code

Call site `produce_db.py:887-912`: filters `HERO_SYNC_LOCKED` units, queries for the `tts_master` artifact, builds `slot_bounds` with `ms_to_samples(required_start/end_ms)` (48000 rate — corrected from the legacy 44100), calls `materialize_hero_slot_slices`, and returns `hero_slice_count`.

### Fail-loud (no dummy output / no silent fallback)
- Missing master: `produce_db.py:898-903` raises `RuntimeError("BLOCKED: HERO_SYNC_LOCKED spans require a tts_master...")` → `test_hero_span_without_master_fails`
- Sub-min hero: `produce_db.py:672-686` `_validate_hero_slot_min` raises `RuntimeError("... < min_clip_duration_sec...")` → `test_sub_min_hero_span_fails`
- Out-of-range speech bounds: `materialize_hero_slot_slices:319-323` raises `ValueError`

### S9-C02 supersession interaction preserved
`scripts/production_repo.py:428-445`: a new render-plan marks the production's prior non-stale units `stale` in the **same transaction** before new units are created (D-015, the S9-C02 contract). Re-compiling a slotted span therefore supersedes old slotted units; `plan_render_units` threads per-slot audio/sample/master columns via `_slot_or_spec` (slot-first, spec fallback) at `production_repo.py:491-501`.

### Route bridge (`_HERO_SHOT_TYPE_ALIASES`)
`produce_db.py:697` bridges the storyboard's canonical `hero_lipsync` shot type to `talking_head_hero` so hero beats pick up the full hero route (`requires_audio`, seedance) and classify as `HERO_SYNC_LOCKED` — otherwise hero spans would fall through to `BROLL_FLEX` and slicing would never fire in production. Scoped to the hero alias only (documented residual: broll_archival/graphic_title_card routing is separate and does not affect slotting/slicing).

---

## Audit Findings — All Resolved

The prior audit recorded FAIL with three findings; the re-audit recorded PASS. Independent verification confirms:

- **F-001 (BLOCKING) — Hero audio slice materialization** — RESOLVED. `materialize_hero_slot_slices()` implemented with real ffmpeg slicing + artifact registration + SHA + master provenance. Proven by `test_hero_slice_materialized` (SHA matches independent re-extraction).
- **F-002 (MEDIUM) — Per-slot minimum validation** — RESOLVED. `_validate_hero_slot_min()` called for every hero slot. Proven by `test_sub_min_hero_span_fails`.
- **F-003 (LOW) — Commit hygiene (S9-C04 mixed in same working tree)** — RESOLVED. Per-ticket commit split landed (C03/C04/C05 in separate commits: 0431595 for S9-C05). Working tree clean at validation.

No new findings. No regressions.

---

## Code Changes Verified

**Committed:**
- `0431595` `scripts/produce_db.py` (slotting + slice call site + `_validate_hero_slot_min` + `_HERO_SHOT_TYPE_ALIASES`), `scripts/production_repo.py` (`_slot_or_spec` per-slot persistence), `scripts/slice_continuous_lipsync.py` (`materialize_hero_slot_slices`), `tests/test_s9_c05_slotting.py` (6 focused tests)
- `b4e938a`, `6d18b57` audit/report docs

**Working tree:** clean at validation (no uncommitted code).

---

## Residual Risks

1. **Slice→assembly provenance feeding S9-C06/C07** (ticket-noted): slice artifacts carry `render_unit_id` in metadata (no new DB column). S9-C06 resolves a hero slot's slice by `kind='hero_audio_slice'` + `metadata.render_unit_id` (the documented S9-C06 contract). This is by design (no schema migration needed) and is exercised in the focused test; downstream consumption is S9-C06/C07 scope.
2. **broll_archival / graphic_title_card route residuals**: `_HERO_SHOT_TYPE_ALIASES` bridges only the hero alias. Non-hero long-beat slotting uses the same clip ceiling (`clip_max_ms = max_clip_ms`, shared lipsync ceiling) and is covered by `test_broll_long_gets_coverage_slots`. The routing residual is documented and does not affect slotting or audio slicing.

Neither residual blocks acceptance.

---

## Commands Executed (Independent Verification)

1. `git log --oneline -3` / `git status --short` — baseline (head 6d18b57, clean tree)
2. `which ffmpeg ffprobe` — real slice production available
3. `YT_TEST_MODE=1 python3 -m pytest tests/test_s9_c05_slotting.py -q` — 6/6 passed (2.02s)
4. `YT_TEST_MODE=1 python3 -m pytest tests/ -k "plan_render or compile or slot or coverage_geometry or hero" -q` — 136/136 passed (53.61s)
5. `YT_TEST_MODE=1 python3 -m pytest -q` — 1076 passed, 1 skipped, 1 xfailed, 2 xpassed, exit 0 (696.48s)
6. Read source: `produce_db.py:670-920`, `slice_continuous_lipsync.py:264-381`, `production_repo.py` (`_slot_or_spec`, supersession), `tests/test_s9_c05_slotting.py`
7. `grep` clip-range source — confirmed `constraints.json` (4s/15s), not hardcoded

---

## Conclusion

**Verdict:** PASS (GO)

S9-C05 fully delivers the observable outcome: long beats are split into ≤max-clip slots that tile the span exactly, and each hero slot has a real, SHA-verified, ffmpeg-produced master-narration slice registered as an artifact and linked to the unit — available for generation `--audio`. Clip ranges come from config, the S9-C02 supersession contract is preserved, and negative paths fail loudly. Focused tests, broader regression, and the full suite are green. No paid call was made.

**Status:** Ticket ACCEPTED. Mark accepted in STATE.json; add to `completed_tickets`; remove from `implemented_awaiting_validation`; record validation report; W2 is now complete (S9-C04 + S9-C05 both accepted). Next dependency-eligible ticket: **S9-C06** (W3; depends on S9-C05 — now satisfied).

---

**Validator Signature:** Independent validation (manual, per user instruction not to invoke claude)
**Date:** 2026-06-20
**Next action:** Mark S9-C05 accepted in STATE.json; set W2 status to complete; select next ticket S9-C06 (W3 first eligible).

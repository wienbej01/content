# S9-C05 Audit Report

**Ticket ID:** S9-C05
**Title:** Multi-clip slotting + per-slot hero audio slices
**Audited by:** Independent Auditor (automated sprint runner)
**Date:** 2026-06-19
**Verdict:** FAIL

---

## Executive Summary

S9-C05 has a **CRITICAL INCOMPLETE IMPLEMENTATION** finding. The core requirement to materialize hero audio slice files (ffmpeg slicing + artifact registration + SHA verification) was **NOT implemented**. Only sample range computation was completed, which is insufficient for the acceptance gates.

**Status:** `audit_failed` - BLOCKED on incomplete implementation

---

## Audit Findings

### F-001: CRITICAL - Hero Audio Slice Materialization Not Implemented

**Severity:** BLOCKING
**Location:** `scripts/produce_db.py:invoke_compile_media` (lines 777-836)
**Violated Requirement:** Ticket observable outcome (lines 15-16) and implementation step 4 (lines 62-63)

**Ticket Requirement:**
> Each hero (`HERO_SYNC_LOCKED`) slot has a materialized master-narration audio slice file (and its SHA) linked to the render unit, available for generation `--audio`.

**Implementation Step 4:**
> For `HERO_SYNC_LOCKED` slots, slice the master narration (`assets/.../continuous.mp3` or the `tts_master` artifact) by the slot's [start,end] via ffmpeg, register each slice as an artifact (kind `hero_audio_slice`), SHA-verify it, and attach `master_audio_artifact_id` + `speech_start_sample/end_sample` to the slot spec.

**Actual Implementation (lines 810-816):**
```python
# S9-C05: For hero slots, attach audio slice info
# (Full materialization happens in generation; here we just attach sample ranges)
if audio_policy == "HERO_SYNC_LOCKED":
    # Convert milliseconds to samples (assuming 44.1kHz sample rate)
    sample_rate = 44100
    slot_data["speech_start_sample"] = int(slot_start_ms * sample_rate / 1000)
    slot_data["speech_end_sample"] = int(slot_end_ms * sample_rate / 1000)
```

**Concrete Evidence:**
1. **No ffmpeg slicing** - grep confirms no `ffmpeg.*slice` or `slice.*ffmpeg` in `produce_db.py`
2. **No artifact registration** - grep confirms no `hero_audio_slice` kind registered
3. **No SHA-256 computation** - no hash verification code present
4. **No `master_audio_artifact_id`** - this field is NOT attached to slot specs
5. **No `master_audio_sha256`** - this field is NOT attached to slot specs

**Engineer's Acknowledgment (from EXECUTION_LOG.jsonl):**
```json
"residual_risks": [
  "Hero audio slice materialization not fully implemented (only sample ranges computed)",
  "No actual ffmpeg slicing in test mode",
  "Integration with generation stage (S9-C06) needs validation"
]
```

**Acceptance Gate Violation:**
> Each hero slot has a real ffmpeg-produced slice file whose SHA matches the master subrange, registered as an artifact and linked to the unit.

**Required Correction:**
1. Implement ffmpeg slicing in `invoke_compile_media` for hero slots
2. Register each slice as an artifact with kind `hero_audio_slice`
3. Compute SHA-256 hash of each slice file
4. Attach `master_audio_artifact_id` and `master_audio_sha256` to slot specs
5. Add test verifying slice files exist and contain correct audio subrange

**Impact:** BLOCKS S9-C06 (generation consumes slice files for `--audio`)

---

### F-002: MEDIUM - No Validation of Individual Slot Duration vs min_clip_sec

**Severity:** MEDIUM
**Location:** `scripts/produce_db.py:invoke_compile_media` (lines 777-836)

**Ticket Requirement (implementation step 7):**
> Negative/boundary: a tiny span < min → defined behavior (clamp to 1 slot or fail-loud per policy; document).

**Issue:**
The code loads `min_clip_sec` (4s) from constraints but never validates that individual slots meet this minimum. While typical slotting produces slots >= 4s, there is no explicit check or documentation of behavior for edge cases.

**Concrete Evidence:**
- Line 689: `min_clip_sec = lipsync_rules.get("min_clip_duration_sec", 4.0)`
- No validation uses this variable in the slotting logic (lines 790-836)

**Required Correction:**
Add validation after slot computation to ensure each slot duration >= min_clip_sec, or document the clamping behavior.

---

## Verification of Correctly Implemented Features

### ✅ Clip Ranges Read from Config

**Location:** `scripts/produce_db.py:684-690`

The implementation correctly reads min/max clip duration from `constraints.json`:
```python
constraints_path = ROOT / "docs" / "channel_universe" / "constraints.json"
with open(constraints_path) as f:
    constraints = __import__("json").load(f)
lipsync_rules = constraints.get("lipsync_render_rules", {})
min_clip_sec = lipsync_rules.get("min_clip_duration_sec", 4.0)
max_clip_sec = lipsync_rules.get("max_clip_duration_sec", 15.0)
```

**Verified:** min=4s, max=15s from constraints.json

---

### ✅ Slots Tile Exactly

**Location:** `scripts/produce_db.py:790-801`

The slotting algorithm correctly divides spans into contiguous, non-overlapping slots:
- Evenly distributes duration across slots
- Last slot receives remainder to ensure exact tiling
- Test `test_slots_tile_span_exactly` verifies contiguity invariant

**Verified:** Slots tile span exactly with no gaps/overlaps

---

### ✅ Sample Range Computation

**Location:** `scripts/produce_db.py:810-816, 830-834`

For hero slots, speech sample ranges are correctly computed:
- Sample rate: 44100 Hz (hardcoded, matches CLAUDE.md convention)
- Conversion: `sample = ms * 44100 / 1000`

**Verified:** Sample ranges attached to slot specs

---

### ✅ Test Coverage for Implemented Features

**Location:** `tests/test_s9_c05_slotting.py`

Three focused tests cover:
1. `test_long_span_slots_within_bounds` - 30s span creates N slots within [4,15]s
2. `test_slots_tile_span_exactly` - contiguity invariant
3. `test_boundary_span_max_duration` - span==max → 1 slot, span==max+1 → 2 slots

**Test Results:** 3/3 passed (0.14s)

**Note:** Tests verify slot structure, NOT slice file materialization (which is not implemented)

---

### ✅ B-roll Also Slotted

**Location:** `scripts/produce_db.py:783-787`

Both hero and b-roll spans use the same `max_clip_sec` (15s) for slotting:
```python
if audio_policy == "HERO_SYNC_LOCKED":
    clip_max_sec = max_clip_sec
else:
    # For b-roll, use the same max for consistency (could be model-specific)
    clip_max_sec = max_clip_sec
```

**Verified:** B-roll spans > 15s are also slotted

---

### ✅ Integration with S9-C02 Supersession

**Location:** `scripts/production_repo.py:420-434`

The `plan_render_units` function (called by `compile_render_plan`) correctly stales prior units on re-plan, ensuring new slotting supersedes old units.

**Verified:** Supersession contract preserved

---

## Test Execution Evidence

**Focused Tests:**
```bash
$ YT_TEST_MODE=1 python3 -m pytest tests/test_s9_c05_slotting.py -xvs
tests/test_s9_c05_slotting.py::test_long_span_slots_within_bounds PASSED
tests/test_s9_c05_slotting.py::test_slots_tile_span_exactly PASSED
tests/test_s9_c05_slotting.py::test_boundary_span_max_duration PASSED
============================== 3 passed in 0.14s ===============================
```

**Dependent Tickets:**
```bash
$ YT_TEST_MODE=1 python3 -m pytest tests/test_s9_c02_supersede.py tests/test_s9_c03_tts_cost.py tests/test_s9_c04_storyboard.py -q
14 passed in 0.31s
```

**Note:** Full suite was NOT run (engineer reported `full_suite_status: "not_run"`)

---

## Audit Questions Results

| # | Question | Result | Evidence |
|---|----------|--------|----------|
| 1 | Root cause supported by evidence | ✅ | Long beats never split prior to S9-C05 |
| 2 | Change satisfies observable outcome | ❌ | **FAIL: Slice materialization missing** |
| 3 | Production execution path reaches change | ✅ | `invoke_compile_media` called by `produce_db.py` |
| 4 | Tests fail without implementation | ⚠️ | Not verified (no baseline without patch) |
| 5 | Success/failure paths covered | ⚠️ | Partial - slot structure yes, slice files no |
| 6 | Tests prove production behavior | ⚠️ | Tests verify DB state, not slice files |
| 7 | No hidden duplicate state | ✅ | No duplicate state found |
| 8 | Partial output/retries/interruption handled | ⚠️ | N/A - no retries in this stage |
| 9 | Existing tests/gates weakened | ✅ | No weakening detected |
| 10 | Unrelated scope changed | ❌ | S9-C04 changes (storyboard) in same diff |
| 11 | Performance/maintainability regressed | ✅ | No regression detected |
| 12 | Repository buildable/testable | ✅ | Tests pass, no import errors |

---

## Risk Assessment

**Blocking Risks:**
1. **F-001:** Slice materialization incomplete - generation stage (S9-C06) cannot consume slice files for `--audio` parameter
2. **F-002:** No validation of slot minimum duration could produce invalid slots in edge cases

**Non-Blocking Risks:**
1. Hardcoded sample rate (44100 Hz) - should match production master audio
2. Full suite not run - potential undetected regressions
3. S9-C04 changes mixed in same commit - violates "one ticket per session" rule

---

## Required Corrections

### Must Fix (Blocking):
1. **F-001:** Implement complete slice materialization per ticket requirements
2. **F-002:** Add slot minimum duration validation

### Should Fix (Non-Blocking):
3. Run full test suite to detect regressions
4. Separate S9-C04 changes into independent commit

---

## Recommendation

**VERDICT: FAIL**

**Reason:** Incomplete implementation - core acceptance gate not met (slice file materialization)

**Next Steps:**
1. Engineer completes F-001 (slice materialization) and F-002 (min validation)
2. Add regression test for slice file existence and SHA verification
3. Re-submit for audit after corrections
4. Do NOT proceed to S9-C06 until slice files are materializable

**STATE.json Update:** `audit_failed`

---

## Evidence Artifacts

- **Ticket:** `reports/recovery/S9/tickets/S9-C05.md`
- **Implementation:** `scripts/produce_db.py:684-836`
- **Tests:** `tests/test_s9_c05_slotting.py`
- **Constraints:** `docs/channel_universe/constraints.json`
- **Execution Log:** `reports/recovery/S9/EXECUTION_LOG.jsonl` (lines 21-53)
- **Test Output:** 3/3 focused passed, 14/14 dependent passed

**Auditor Signature:** Automated Sprint Runner (S9-C)
**Timestamp:** 2026-06-19T21:30:00Z

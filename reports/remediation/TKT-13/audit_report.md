# TKT-13 Audit Report

**Verdict: PASS**

**Date:** 2026-06-14  
**Files audited:** `scripts/produce.py`, `tests/test_produce_resume.py`  
**Tests:** 11/11 passing (0.02s)

---

## 1. `step_status` dict replaces `completed_steps` list

| Check | Status | Reference |
|-------|--------|-----------|
| Old `completed_steps` migration | ✅ | `produce.py:81–88` — detects old key, deduplicates via `seen` set, converts to `step_status` dict |
| Atomic writes (.tmp → rename) | ✅ | `produce.py:70–72` — writes to `.state.json.tmp` then `tmp.rename()` |
| Step marked done independent of downstream | ✅ | `produce.py:578–583` — each step is set to `done` only after its own `fn()` succeeds; downstream states are untouched |

---

## 2. `--from-step` invalidation

| Check | Status | Reference |
|-------|--------|-----------|
| Invalidates X and all downstream | ✅ | `produce.py:106–120` — `STEPS[idx:]` resets all from target onward |
| Deletes artifacts for invalidated steps | ✅ | `produce.py:122–131` — iterates `STEP_ARTIFACTS` for invalidated steps, handles globs |
| Does NOT delete `narration/continuous.mp3` | ✅ | `produce.py:94` — `tts` has no entry in `STEP_ARTIFACTS`; comment on line 93 explicitly states "TTS audio and generated media are NEVER deleted" |
| Does NOT delete `assets/media/` clips | ✅ | `generate_media` has no entry in `STEP_ARTIFACTS` |

---

## 3. Failed step handling

| Check | Status | Reference |
|-------|--------|-----------|
| Exception → `status: "failed"` | ✅ | `produce.py:570` — `step_status[step_name] = {"status": "failed", "error": str(e)}` |
| On resume, downstream of failed step reset | ✅ | `produce.py:541–548` — iterates STEPS, finds `"failed"`, sets all downstream `"done"` entries to `None` |

---

## 4. Backward compatibility

| Check | Status | Reference |
|-------|--------|-----------|
| Old `completed_steps` list migrated | ✅ | `produce.py:81–88` — converts list items to `{"status": "done"}` entries |
| Deduplication | ✅ | `produce.py:82` — `seen` set prevents duplicate keys |
| Legacy key dropped | ✅ | `produce.py:88` (`_load_state`) + `produce.py:523` (`run_pipeline`) both `del`/`pop` the old key |

---

## 5. Tests

| Test | Verifies | Status |
|------|----------|--------|
| `test_invalidates_downstream_keeps_upstream` | Downstream steps are `None`, upstream remain `"done"` | ✅ Correct assertions at lines 38–46 |
| `test_downstream_of_failed_invalidated` | Failed middle step causes downstream `"done"` → `None` | ✅ Lines 68–79 replicate the propagation logic |
| `test_manifest_deleted` | Creates `manifest.json`, invalidates `build_manifest`, asserts deletion | ✅ Lines 97–103 |
| `test_tts_audio_not_deleted` | Creates `continuous.mp3`, invalidates `tts`, asserts file persists | ✅ Lines 113–122 |
| `test_no_partial_writes` | `.state.json.tmp` does not persist after write | ✅ Lines 133–139 |

---

## 6. Potential issues checked

| Concern | Finding |
|---------|---------|
| Gate B reachable with `qa_final` pending/failed? | **No.** Pipeline is strictly linear (`produce.py:560–574`): steps run sequentially from `start_idx`. `gate_b_review` is after `qa_final` in STEPS (index 17 vs 16). A failed `qa_final` halts execution immediately (line 570–574). |
| `step_status` has `done` while prerequisite is `failed`? | **Transiently possible** only in stale state files from a previous run. On next resume, `produce.py:541–548` propagates failure and resets downstream `done` → `None` before execution begins. |
| Non-atomic state write? | **None found.** All `_save_state` calls go through the single atomic implementation at line 68–72. |

---

## Summary

All invariants hold:
- `--from-step X` invalidates X and all downstream steps
- Failed step does not leave downstream steps as `done` (propagation on resume)
- TTS audio and generated clips are never deleted
- Old `completed_steps` list migrates correctly to `step_status` dict
- State writes are atomic (tmp+rename)
- Tests cover all key behaviors with actual file I/O in temp dirs

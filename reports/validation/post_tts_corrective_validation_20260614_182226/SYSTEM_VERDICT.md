# SYSTEM VERDICT: NO-GO

**Date:** 2026-06-14T18:23+08:00
**Validator:** Independent Principal Software Forensics Engineer
**Subject:** Post-TTS Corrective Sprint — End-to-End Serialized Path Validation

---

## Summary

The pipeline CANNOT transform immutable final narration into a compilable, graphics-aware visual timeline via the actual serialized orchestrator path. **Unit tests pass (500/500) but the real `produce.py` orchestrator would hard-fail at step 9 (compile_media_plan)** on the audited project.

---

## Verdict per Rule (13 Final Verdict Rules)

| # | Rule | Result | Evidence |
|---|------|--------|----------|
| 1 | Immutable narration/audio | ✅ PASS | Master audio SHA-256 unchanged; word-count concatenation matches all 10 source beats exactly |
| 2 | Measured timing authority | ✅ PASS | All split beats use `method=silence_detection, confidence=high`; no LLM-supplied timestamps found |
| 3 | Legal rerouting/splitting | ✅ PASS | B001/B009 correctly rerouted (unsplittable single-sentence); B006/B008/B010 split at measured silence boundaries |
| 4 | Complete non-overlapping coverage | ✅ PASS | 26 slots cover 0.0→146.599s with zero gaps and zero overlaps |
| 5 | Serialized prod-SB→media-plan compatibility | ❌ **FAIL** | `compile_plan` returns 5 errors (2 hard TEXT_SURFACE_POLICY + 3 informational reroutes). `produce.py` `step_compile_media_plan` raises RuntimeError on ANY error. |
| 6 | Every slot costed/tracked | ⚠️ CONDITIONAL | 26 assets produced, all costed (if compile were to succeed). 9/26 assets have `source_beat_id=None` (single-slot beats not expanded). |
| 7 | Graphics enforced | ❌ **FAIL** | Reconcile stores `graphics` (plural list); `compile_beat` reads `graphic` (singular). Result: 6 required graphics silently dropped, never reach media plan or render. |
| 8 | Repair/review fail-closed | ✅ PASS | Repair wired in produce.py; failed repair raises RuntimeError; review exit≠0 halts; narration mutation rejected |
| 9 | State/gate invalidation correct | ✅ PASS | `invalidate_from_step` cascades downstream; STEP_ARTIFACTS cleaned; fingerprint staleness checked |
| 10 | Local e2e passes | ❌ **FAIL** | Reconcile+validate+review pass, but compile hard-fails with errors on actual project data |
| 11 | Audited preview passes | ✅ PASS | Defective MP4 correctly fails `qa_final` (exit 1: CONTAINER_MISMATCH + LENGTH_MISMATCH + TERMINAL_FREEZE) |
| 12 | Full suite green | ✅ PASS | 500 passed in 111.82s |
| 13 | No network/paid/Telegram side effects | ✅ PASS | Validation used only local paths and --dry-run modes |

---

## Blocking Defects (Priority Order)

### P0 — TEXT_SURFACE_POLICY treats reroutes as errors (Blocks step 9)

**Location:** `scripts/compile_media_prompts.py:181-183`
**Root Cause:** When TEXT_SURFACE_POLICY auto-reroutes a beat to `local_graphic`, it appends to `errors[]` not `warnings[]`. Combined with `hero_cutaway` beats (B001/B009) that can't be auto-rerouted (not in LOCAL_SHOT_TYPES, doesn't start with 'broll'), produce.py receives 5 items in `errors` and raises RuntimeError unconditionally.
**Impact:** Complete pipeline halt at compile step for any project with text-surface-triggering terms in rerouted hero beats.
**Fix Needed:** 
1. Move successful reroute messages from `errors` to `plan_warnings`
2. Add `hero_cutaway` to reroutable shot types OR strip banned terms from visual_brief during reroute

### P1 — Graphics field-name mismatch (Silent data loss)

**Location:** `scripts/reconcile_production_storyboard.py:340` writes `graphics` (plural list); `scripts/compile_media_prompts.py:252` reads `graphic` (singular dict)
**Root Cause:** Reconcile normalizes `graphic`→`graphics` but compile_beat was never updated to read the new field name.
**Impact:** All required graphics (lower_third, stat_callout, key_line, side_by_side) silently dropped. `render_graphics.py:196` also reads `graphic` singular — it would find nothing. Final video would have zero graphic overlays despite 6 being required.
**Fix Needed:** Either compile_beat reads `graphics` (plural) and picks first/merges, or reconcile writes both fields.

### P2 — Single-slot beats lack source_beat_id in media plan

**Location:** `scripts/compile_media_prompts.py:220-265` (compile_beat return)
**Root Cause:** `source_beat_id` is only set by `_expand_coverage_slots` for multi-slot expansion. Single-slot beats pass through as `[entry]` without this field.
**Impact:** 9/26 assets in media plan have `source_beat_id=None`. Breaks PST-06 traceability for downstream audit and generation tracking.
**Fix Needed:** Add `"source_beat_id": beat.get("source_beat_id", bid)` to the compile_beat entry dict.

---

## Why Unit Tests Pass Despite Real Path Failure

1. `test_audited_project_dry_run_serialized` explicitly allows TEXT_SURFACE_POLICY errors ("that's a valid compile-time gate, NOT a handoff failure") — it only asserts no KeyError/schema crash
2. Graphics tests use `graphic` (singular) in fixtures, matching render_graphics expectations, but never test the actual reconcile→compile→render chain
3. No test calls `produce.py`'s `step_compile_media_plan` with real project data where `errors[]` is non-empty from reroutes

---

## Earliest Stage Needing Correction

**Step 9: compile_media_plan** — specifically the error/warning classification in `compile_beat`'s TEXT_SURFACE_POLICY handler and the `graphic`/`graphics` field reading.

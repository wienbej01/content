# Sprint 2 — Engineer + Auditor Report

## S2-T01 — Reconstruct and correct the stage graph

- **Agent:** Agent 2 (Workflow and Orchestration Engineer)
- **Status:** AUDITOR_PASS

### Changes
- **scripts/stage_runner.py** — corrected STAGE_REGISTRY to match canonical order:
  - `storyboard` depends on `gate_a_content` (was: `audio_timing` — inverted)
  - `tts` depends on `review_storyboard` (was: `gate_a_content`)
  - `audio_timing` depends on `tts` and consumes `storyboard` kind (was: only tts, no storyboard consume)
  - Added `reconcile_timing` stage (storyboard-timing reconciliation, extracted from compile_media)
  - Added `repair` stage (selective repair gate after qa_media)
  - Added `graphics_compositing` stage (deterministic graphics before assembly)
  - `assemble` depends on `graphics_compositing` (was: `qa_media`)
  - Added `requires_committed_output` flag to StageDefinition; gates/analytics exempt
- **scripts/produce_db.py** — added invokers for reconcile_timing, repair, graphics_compositing; removed folded reconciliation from compile_media; fixed gate_a_content to approve script only (storyboard comes after in canonical order)
- **tests/test_sprint3_stage_runner.py** — added 5 graph-order tests; updated critical-stages list

### Key fix: dependency inversion
The old graph had `storyboard → depends_on → audio_timing`, but `invoke_audio_timing` calls `get_storyboard()` — it NEEDS the storyboard. The graph was inverted. Fixed: storyboard depends on gate_a_content; audio_timing depends on tts (which depends on review_storyboard, which depends on storyboard — transitive dependency satisfied).

## S2-T02 — Implement stage result semantics

- **Agent:** Agent 2
- **Status:** AUDITOR_PASS

### Changes
- **scripts/stage_runner.py** — `_verify_committed_output()` helper; LegacyAdapter verifies committed document revision after successful execution for stages where `output_kind in produces_kinds` and `requires_committed_output=True`. Gate/approval stages exempt.
- **tests/contracts/test_stage_semantics.py** — 3 tests: committed output required, committed output accepted, gate stages exempt.

## S2-T03 — Implement dependency invalidation

- **Agent:** Agent 2 with Agent 1 review
- **Status:** AUDITOR_PASS

### Tests (tests/contracts/test_invalidation_and_gates.py)
- test_script_change_invalidates_tts_and_downstream — PASS
- test_storyboard_change_preserves_unaffected_script — PASS
- test_timing_change_invalidates_render_plan — PASS
- test_render_plan_change_stales_spend_approval — PASS
- test_artifact_change_stales_validation_and_deliverable — PASS

## S2-T04 — Implement real human approval gates

- **Agent:** Agent 2
- **Status:** AUDITOR_PASS

### Verification
- Approval bound to exact subject SHA (`request_approval` checks `subject_sha256` change)
- Changed subject invalidates approval (marks stale, creates fresh pending)
- No production auto-approval (only `YT_TEST_MODE=1` auto-approves; release_guard blocks production with auto-approval)
- test_pending_approval_pauses — PASS
- test_stale_approval_rejected — PASS

## Sprint 2 Exit Gate

| Gate | Status |
|---|---|
| clean local production reaches spend approval | PASS (mocked stages) |
| no JSON authority | PASS (S1-T02) |
| no paid provider called | PASS |
| resume and invalidation work | PASS |
| human gates pause and resume correctly | PASS |

## Test results
- 140 passed across contracts + stage_runner + orchestrator + authoring + TTS + production_db
- All 5 CI gates pass; release_guard status clean

# PTC-REVIEW-01: Remove Dual-Enforcement from Technical Storyboard Reviewer

**Status:** COMPLETE  
**Date:** 2026-06-14  
**Engineer:** kiro-cli

## Problem

The `technical` reviewer persona blocked (status=fail) on per-beat cost (>$3) and model-duration limits (b-roll >6s, hero >10s). Both are authoritatively enforced by downstream deterministic gates:
- **Cost:** Gate A (budget.py, $25 short / $60 full cap)
- **Duration:** reconcile_production_storyboard.py (splits over-limit beats) + compile_media_prompts.py (rejects illegal durations)

A real produce.py run escalated at storyboard_review_loop with 7 "blocking" issues — 6 spurious cost flags ($3.97 > $3) and 1 duration flag (8s b-roll > 6s Kling limit) that reconciliation handles automatically.

## Changes Made

### 1. `docs/reviewer_prompts/technical.md`

- Removed cost and duration from BLOCKING conditions list
- Remaining BLOCKING conditions: (a) beat with no valid generation model / impossible asset, (b) hero beat with reference_required=false
- Added explicit "DO NOT block on cost (Gate A enforces the budget cap) or on model-duration limits (reconciliation splits/reroutes over-limit beats automatically)"
- Duration check (#4): changed from "Flag any beat exceeding its limit (must be split, never clamped)" to noting exceeding beats as a recommendation with downstream reconciliation context
- Cost check (#6): removed ">$3 without justification" blocking heuristic; Gate A explicitly named as authoritative

### 2. `scripts/review.py` — NO changes needed

Verified the aggregation logic. `aggregate()` fails if `blocking_issues` list is non-empty (`has_mandatory`) or veto persona fails. Moving cost/duration to `recommended_fixes` in the prompt means the LLM won't populate `blocking_issues` with those items → no escalation. The code path is clean.

### 3. `tests/test_technical_reviewer_contract.py` (NEW — 6 tests)

| Test | Validates |
|------|-----------|
| `test_technical_prompt_does_not_block_on_cost` | BLOCKING section has no cost/budget blocking bullets |
| `test_technical_prompt_does_not_block_on_duration` | Duration-over-limit not in blocking bullets |
| `test_technical_prompt_still_blocks_on_impossible_model` | Genuine feasibility block preserved |
| `test_technical_prompt_still_blocks_on_reference_required_false` | Hero reference check preserved |
| `test_aggregate_recommendation_does_not_escalate` | Stubbed technical verdict with cost/duration in recommended_fixes passes aggregation |
| `test_aggregate_genuine_block_still_escalates` | Stubbed technical verdict with real feasibility block still fails |

## Acceptance Criteria Verification

| # | Criterion | Status |
|---|-----------|--------|
| 1 | technical.md no longer lists cost or model-duration as BLOCKING | ✅ |
| 2 | cost/duration become recommendations; Gate A and reconciliation remain authoritative | ✅ |
| 3 | Technical verdict with only cost/duration (as recommended_fixes) does NOT escalate | ✅ (test_aggregate_recommendation_does_not_escalate) |
| 4 | Genuine feasibility blocks still block | ✅ (test_aggregate_genuine_block_still_escalates) |
| 5 | Tests pass; full suite green | ✅ (514 passed in 114s) |

## Test Results

```
tests/test_technical_reviewer_contract.py: 6 passed
tests/test_reviewers.py + tests/test_review.py: 17 passed
Full suite: 514 passed in 114.32s
```

# Validation Report — S22_T012

## Validation scope

Black-box validation of the `gate_storyboard` human approval gate. All tests run against isolated ephemeral databases.

## Commands executed

```bash
python3 -m pytest tests/test_gate_storyboard.py -q
# 11 passed in 0.40s

python3 -m pytest tests/e2e/test_storyboard_gate_flow.py -q
# 4 passed in 0.36s

python3 -m pytest tests/test_gate_storyboard.py tests/e2e/test_storyboard_gate_flow.py -q
# 15 passed in 0.57s

python3 -m pytest tests/e2e/test_s8_projections_resume.py -q
# pre-existing failure at repair stage (hero_lipsync_needs_human_review)
# gate_storyboard and tts stages complete successfully in the output
```

## Test evidence by requirement

### 1. TTS blocked before gate_storyboard approval

- `test_tts_blocked_before_storyboard_approval` — `deps_satisfied("tts", ...)` returns `(False, ...)` when no gate_storyboard approval exists
- `test_gate_storyboard_blocks_tts_in_non_test_mode` — `run_production` fails with `SystemExit(1)` at gate_storyboard, TTS never reaches succeeded

### 2. Compile blocked before storyboard approval

- `test_compile_blocked_before_storyboard_approval` — `deps_satisfied("compile_media", ...)` returns `(False, ...)` when no gate_storyboard approval exists

### 3. Approval request subject is active storyboard revision/hash

- `test_approval_subject_is_storyboard_revision` — verifies `subject_type="storyboard"` and `subject_id` matches the active revision ID
- `test_approval_db_state_is_correct` — verifies DB row has correct `subject_type`, `subject_id`, `status`, and `actor`

### 4. Storyboard revision change stales approval

- `test_storyboard_change_stales_approval` — saves new storyboard, re-requests approval with new hash, confirms `is_approved()` returns `False`
- `test_storyboard_change_stales_gate_storyboard` — e2e: auto-approve, change storyboard, re-invoke gate, confirms `RuntimeError("pending approval")`

### 5. YT_TEST_MODE=1 auto-approves only in test mode

- `test_yt_test_mode_auto_approves` — with `YT_TEST_MODE=1`, `invoke_gate_storyboard` returns `{"status": "pass", "test_mode": True}`, `is_approved()` returns `True`
- `test_non_test_mode_requires_human_approval` — without `YT_TEST_MODE`, `invoke_gate_storyboard` raises `RuntimeError("pending approval")`

### 6. Gate A content still applies to script only

- `test_gate_a_content_applies_to_script_only` — `request_approval("gate_a_content", ...)` uses `subject_type="script"`

### 7. Gate A spend still applies to render plan/cost only

- `test_gate_a_spend_applies_to_render_plan_only` — `request_approval("gate_a_spend", ...)` uses `subject_type="render_plan"`

### Stage registry integrity

- `test_gate_storyboard_in_registry` — stage exists, correct dependencies/kinds
- `test_tts_depends_on_gate_storyboard` — TTS depends on gate_storyboard, not review_storyboard
- `test_downstream_stages_include_gate_storyboard` — downstream traversal includes gate_storyboard

## Pass gates from ticket

| Pass gate | Status |
|---|---|
| No TTS/compile/generate before storyboard approval | ✓ |
| Stale storyboard approval cannot be reused | ✓ |
| Existing approval flow is extended, not duplicated | ✓ |

## Evidence paths

- `reports/karpathy_loop/s22/S22_T012/engineering_report.md`
- `reports/karpathy_loop/s22/S22_T012/audit_report.md`
- `reports/karpathy_loop/s22/S22_T012/validation_report.md`
- `reports/karpathy_loop/s22/S22_T012/loop_decision.md`
- `tests/test_gate_storyboard.py`
- `tests/e2e/test_storyboard_gate_flow.py`

## Residual risks

- `tests/e2e/test_s8_projections_resume.py` has a pre-existing failure at `repair` stage (hero_lipsync_needs_human_review). This is not caused by S22_T012 changes and does not affect gate_storyboard validation.

## Conclusion

All 15 new tests pass. All ticket requirements verified. Stage registry dependency chain is correct. Approval staleness works as designed.

# Audit Report — S22_T012

## Audit scope

Review of code diff, tests, invariants, and evidence for the `gate_storyboard` human approval gate (S22_T012).

## Findings

### BLOCKER: None

### MAJOR: None

### MINOR: None

### NOTE: Pre-existing s8_projection_resume test failure

The `tests/e2e/test_s8_projections_resume.py` test fails at the `repair` stage (`hero_lipsync_needs_human_review`), which is unrelated to the `gate_storyboard` changes. The pipeline output shows `gate_storyboard` and `tts` both complete successfully before the failure occurs downstream at generate_media/repair.

## Audit checklist

### 1. Stage registry dependency order ✓

```
review_storyboard -> gate_storyboard -> tts -> audio_timing -> ...
```

- `gate_storyboard` correctly inserted between `review_storyboard` and `tts`
- `tts.depends_on` changed from `["review_storyboard"]` to `["gate_storyboard"]`
- All `consume_kinds` and `produce_kinds` correctly configured

### 2. Approval staleness ✓

- `invoke_gate_storyboard` binds approval to `storyboard:{rev_id}:{payload_hash[:16]}`
- When storyboard content changes, payload_hash changes
- On re-invocation, `request_approval` detects different subject_sha256 and resets to `pending`
- Test `test_storyboard_change_stales_approval` and e2e test `test_storyboard_change_stales_gate_storyboard` prove this

### 3. No bypass route ✓

- `tts` directly depends on `gate_storyboard` — cannot execute without it
- `compile_media` transitively depends on `gate_storyboard` via `tts -> audio_timing -> reconcile_timing -> compile_media`
- `generate_media` transitively depends on `gate_storyboard`
- No stage can skip `gate_storyboard`
- Test `test_tts_blocked_before_storyboard_approval` and `test_compile_blocked_before_storyboard_approval` prove this

### 4. Non-goals preserved ✓

- Gate A content unchanged: `invoke_gate_a_content` uses `subject_type="script"`, test `test_gate_a_content_applies_to_script_only` confirms
- Gate A spend unchanged: `invoke_gate_a_spend` uses `subject_type="render_plan"`, test `test_gate_a_spend_applies_to_render_plan_only` confirms
- No media generation
- No Sonnet generation
- No removal of `gate_a_spend`

### 5. Test mode ✓

- `YT_TEST_MODE=1` auto-approves only when explicitly set
- Test `test_non_test_mode_requires_human_approval` proves it blocks without the flag
- Test `test_yt_test_mode_auto_approves` proves auto-approval with the flag
- No paid APIs called

### 6. Existing infrastructure extended ✓

- Uses existing `request_approval` / `record_approval_decision` / `is_approved` from `authoring_service.py`
- Uses existing `STAGE_REGISTRY` / `LegacyAdapter` from `stage_runner.py`
- Uses existing DB tables: `approval_requests`, `document_revisions`, `stage_runs`
- No duplication of gate logic

## Files inspected

- `scripts/stage_runner.py` (diff)
- `scripts/produce_db.py` (diff + function body)
- `tests/test_gate_storyboard.py` (full)
- `tests/e2e/test_storyboard_gate_flow.py` (full)
- `scripts/authoring_service.py` (reviewed `request_approval`, `is_approved`, `_get_active_storyboard_revision_id`)

## Verdict

All pass gates in S22_T012.md are satisfied. No BLOCKER or MAJOR findings. Implementation is clean and extends existing infrastructure correctly.

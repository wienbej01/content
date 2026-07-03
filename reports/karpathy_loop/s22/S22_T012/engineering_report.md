# Engineering Report — S22_T012

## Ticket

Add human `gate_storyboard` stage — durable storyboard approval gate before TTS, compile, or media spend.

## Files changed

### `scripts/stage_runner.py`
- Added `gate_storyboard` to `STAGE_REGISTRY` between `review_storyboard` and `tts`
- `gate_storyboard` depends on `review_storyboard`, consumes `storyboard`, produces `gate_storyboard_approval`
- `tts` depends_on changed from `review_storyboard` to `gate_storyboard`
- `requires_committed_output=False` (pure gate/approval stage)

### `scripts/produce_db.py`
- Added `invoke_gate_storyboard` function (line ~225):
  - Queries active storyboard revision ID via `_get_active_storyboard_revision_id`
  - Retrieves `payload_sha256` for staleness binding
  - Constructs subject hash: `storyboard:{rev_id}:{hash[:16]}`
  - Calls `request_approval` with `gate_name="gate_storyboard"`, `subject_type="storyboard"`
  - In `YT_TEST_MODE=1`: auto-approves via `record_approval_decision`
  - In normal mode: blocks with `RuntimeError` if not approved
- Registered `gate_storyboard` in `STAGE_INVOKERS` with `output_kind="gate_storyboard_approval"`
- Added `gate_storyboard` to CLI approve command choices
- Updated import: added `_get_active_storyboard_revision_id` to local imports in the function

### `tests/test_produce_db_orchestrator.py` (updated)
- Added `gate_storyboard` to mock stages lists in `test_run_walks_graph_and_resumes`, `test_tts_wiring_enforces_provenance`, `test_compile_media_derives_from_measured_spans`, `test_assembly_bypasses_manifest_file`, `test_qa_media_enforces_no_silent_fallback`, `test_resume_without_legacy_json`
- Added `gate_storyboard` to pre-marked succeeded stages in TTS, compile, assembly, and QA media tests

### `tests/test_gate_storyboard.py` (new)
- 11 unit tests covering all required behaviors

### `tests/e2e/test_storyboard_gate_flow.py` (new)
- 4 end-to-end tests verifying gate integration with the pipeline

## Design decisions

1. **Staleness detection**: The `request_approval` function in `authoring_service.py` already handles staleness — when called with a different `subject_sha256`, it resets the approval to `pending`. The gate re-checks on every invocation, ensuring a changed storyboard cannot reuse a stale approval.

2. **Subject hash binding**: The approval is bound to `storyboard:{revision_id}:{payload_hash[:16]}`, capturing both the revision identity and its content. This means any storyboard content change creates a different hash, triggering re-approval.

3. **Dependency chain**: `tts` now depends on `gate_storyboard` instead of `review_storyboard`, ensuring no downstream stage can execute before human storyboard approval.

4. **Test mode**: `YT_TEST_MODE=1` auto-approves for deterministic test fixtures only. This follows the existing pattern of `gate_a_content` and `gate_a_spend`.

## Commands run

```bash
python3 -m pytest tests/test_gate_storyboard.py -q                                     # 11 passed
python3 -m pytest tests/e2e/test_storyboard_gate_flow.py -q                            # 4 passed
python3 -m pytest tests/test_produce_db_orchestrator.py -q                             # 9 passed (updated)
python3 -m pytest tests/contracts/test_invalidation_and_gates.py -q                    # 7 passed (no regression)
python3 -m pytest tests/test_gate_storyboard.py tests/e2e/test_storyboard_gate_flow.py tests/test_produce_db_orchestrator.py tests/contracts/test_invalidation_and_gates.py -q  # 31 passed
python3 -m pytest tests/e2e/test_s8_projections_resume.py -q                           # pre-existing failure
```

## Test results

| Test suite | Passed | Failed |
|---|---|---|
| `tests/test_gate_storyboard.py` | 11 | 0 |
| `tests/e2e/test_storyboard_gate_flow.py` | 4 | 0 |
| `tests/e2e/test_s8_projections_resume.py` | 0 | 1 (pre-existing) |

The s8_projection_resume test failure is pre-existing — it occurs at `repair` stage (hero_lipsync_needs_human_review) and is unrelated to gate_storyboard. The pipeline output confirms gate_storyboard and tts both complete successfully, proving the new dependency chain works.

## Evidence

- Gate added to STAGE_REGISTRY at `scripts/stage_runner.py:52`
- Invoker function at `scripts/produce_db.py:225`
- TTS dependency updated: `depends_on=["gate_storyboard"]`
- CLI approve command now accepts `gate_storyboard`
- 15 total tests (11 unit + 4 e2e) verifying the gate behavior

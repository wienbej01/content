# Seedance Truth Test V4 Run Report

verdict: PASS_FOR_REVIEW_ONLY
classification: REVIEW_ONLY_PRODUCT_CONTRACT_FIXED
paid_renders_triggered: no
provider_api_calls: no
output: `outputs/seedance_truth_test_001/review_only/final_review_v4_contract_fixed.mp4`

## Output Probe

- duration: 25.731 s
- video: H.264, 1920x1080
- audio: AAC, 44100 Hz, stereo

## Segment Contract

1. S000 hero: Seedance provider audio island, provider embedded audio preserved.
2. S001 b-roll: deterministic local corporate visual over canonical narration slice.
3. S002 hero: Seedance provider audio island, provider embedded audio preserved.
4. S003 graphic: deterministic local graphic over canonical narration slice.

## DB Updates

- Added explicit product contract fields through migration `012_product_contract_audio_policy.sql`.
- Populated `product_audio_policy` and `actual_render_duration_ms` for the truth-test render units.
- Registered replacement S001/S003 artifacts in `artifacts`.
- Recorded resolved `change_requests` for replacing unusable b-roll and rendering the missing deterministic graphic.
- Linked S000/S002 to human A/V review validations, not SyncNet validations.
- Resolved the old false-positive lipsync change requests as stale/rejected; the failed `qa_media_contract` validation rows remain as historical evidence.
- Added explicit review-only validation rows for S000/S002:
  - `human_av_review_pass_review_only`
  - `provider_audio_preserved`
  - `duration_delta_not_lipsync_drift`
- Verified DB-native review-only assembly preflight passes with label `REVIEW_ONLY_HUMAN_AV_ACCEPTED_NOT_AUTOMATED_SYNCNET_PASS`.
- Verified publish-grade assembly still blocks without passing `qa_media_contract`/`syncnet_offset` evidence.

## Tests

- `python3 -m pytest tests/test_qa_lipsync.py tests/test_qa_lipsync_gate.py -q` -> 15 passed
- `python3 -m pytest tests/test_audio_continuity.py -q` -> 18 passed
- `python3 -m pytest tests/test_render_graphics.py tests/test_graphic_qa.py -q` -> 42 passed
- `python3 -m pytest tests/test_product_contract.py tests/test_review_only_assembly.py -q` -> 9 passed

Additional local check:

- `python3 scripts/evals/eval_audio_continuity.py outputs/seedance_truth_test_001/review_only/final_review_v4_contract_fixed.mp4 --out outputs/seedance_truth_test_001/review_only/v4/audio_continuity_v4.json` -> PASS
- `python3 scripts/evals/eval_graphic_qa.py --production-id prod_cbd3c35dfd08431b82b1b6ca9bc675d2 --db-path db/production.db --out outputs/seedance_truth_test_001/review_only/v4/graphic_qa_v4.json` -> PASS
- `PYTHONPATH=scripts python3 - <<'PY' ... build_assembly_inputs(..., review_only=True) ...` -> PASS
- `PYTHONPATH=scripts python3 - <<'PY' ... build_assembly_inputs(..., review_only=False) ...` -> BLOCKED as publish-grade

## No-Paid Confirmation

All media generation after the original paid artifacts was local ffmpeg/Python deterministic rendering. No Higgsfield, Seedance, or provider API was called.

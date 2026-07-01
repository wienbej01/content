# Product Contract Diagnosis

verdict: PASS_FOR_REVIEW_ONLY
paid_renders_triggered: no
provider_api_calls: no
v4_output: `outputs/seedance_truth_test_001/review_only/final_review_v4_contract_fixed.mp4`

## Nine Pre-Coding Answers

1. Canonical timeline is currently `timeline_spans` (`start_ms`, `end_ms`, `duration_ms`, `ordinal`) joined to active `render_units`. In practice, assembly consumes duplicated timing from `render_units.required_start_ms`, `required_end_ms`, and `required_duration_ms`.

2. Canonical narration is production-wide `artifacts.kind='tts_master'`. Per hero segment, narration provenance is also represented by `hero_audio_slice` artifacts plus render-unit speech sample fields and `metadata_json.audio_path`.

3. The legacy system distinguished audio behavior indirectly: `HERO_SYNC_LOCKED` as hero island, `BROLL_FLEX`/`BROLL_SYNCED_ACTION` as master narration/video-only, and `SILENT_GRAPHIC` as silent. It did not directly express `HERO_PROVIDER_AUDIO_ISLAND`, `VIDEO_ONLY_OVER_CANONICAL_NARRATION`, and `SILENT_VISUAL`.

4. Existing assembly mixed sources. It used required/reference durations for segment targets but preserved compensated provider MP4 audio for hero islands when present. The review-only v4 assembly uses actual provider audio durations for hero and canonical narration span durations for b-roll/graphic.

5. The last hero words were cut because the visual stream ended before the provider audio tail and there was no tail guard before concat.

6. Sci-fi b-roll satisfied requirements because the previous gate checked media existence and broad media QA, not grounded semantic/product relevance of final visuals.

7. AI-garbled text appeared because text-bearing graphics were not forced through a deterministic local renderer in the final path; S003 remained unrendered and graphic QA was `not_run`.

8. S16 deterministic graphics were not wired into the final truth-test path. The v4 run renders S003 locally and registers deterministic provenance in DB.

9. Passing tests that missed the product failures: `tests/test_qa_lipsync.py`, `tests/test_qa_lipsync_gate.py`, `tests/test_audio_continuity.py`, `tests/test_render_graphics.py`, and `tests/test_graphic_qa.py`.

## Contract Repair

Added product contract policy vocabulary:

- `HERO_PROVIDER_AUDIO_ISLAND`
- `VIDEO_ONLY_OVER_CANONICAL_NARRATION`
- `SILENT_VISUAL`

The DB now has additive fields:

- `render_units.product_audio_policy`
- `render_units.actual_render_duration_ms`
- `render_units.product_contract_json`

Legacy policy values are still supported and mapped to product policy so existing rows continue to work.

## Truth-Test State

- S000: `HERO_PROVIDER_AUDIO_ISLAND`, provider audio preserved, human A/V review pass.
- S001: `VIDEO_ONLY_OVER_CANONICAL_NARRATION`, generated sci-fi b-roll replaced with deterministic local corporate visual.
- S002: `HERO_PROVIDER_AUDIO_ISLAND`, provider audio preserved, human A/V review pass.
- S003: `VIDEO_ONLY_OVER_CANONICAL_NARRATION`, deterministic local graphic rendered with machine-readable text provenance.

## Review-Only Evidence Handling

The old failed `qa_media_contract` validations were not deleted or rewritten. They remain in the DB as historical false-positive evidence from the duration-delta bug. Their associated repair change requests were resolved as stale/rejected.

New explicit review-only evidence rows were added for S000/S002:

- `human_av_review_pass_review_only`
- `provider_audio_preserved`
- `duration_delta_not_lipsync_drift`

`assemble_db.build_assembly_inputs(..., review_only=True)` now accepts this evidence only in explicit review-only mode and labels the result `REVIEW_ONLY_HUMAN_AV_ACCEPTED_NOT_AUTOMATED_SYNCNET_PASS`.

Default publish-grade assembly still blocks without passing `qa_media_contract` and per-segment `syncnet_offset` evidence.

## Remaining Limits

This is still review-only. It does not create automated SyncNet pass evidence. Publish-grade assembly continues to require real per-segment SyncNet or an explicit future policy decision that human review can substitute.

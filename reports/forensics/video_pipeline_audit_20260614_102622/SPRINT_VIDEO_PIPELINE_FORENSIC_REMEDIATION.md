# Sprint: Video Pipeline Forensic Remediation

## Objective

Make a broken video impossible to ship silently. This sprint is fail-loud first: stream integrity, duration coverage, provenance, state invalidation, then music/graphics and prompt quality. No ticket may call paid APIs or regenerate production TTS/video.

## Agent Roles

- **Software Engineer:** implement exactly one ticket, add tests, use local fixtures, never add dummy fallbacks, and return actionable non-zero failures.
- **Auditor:** read-only review of production code and diffs. Look for bypasses, stale reuse, warning-only degradation, overbroad edits, and untested branches.
- **Validator:** run specified commands and inspect generated fixture artifacts. Do not edit production code except an explicitly permitted fixture.

## Required Execution Order

Emergency stop-ship order: **TKT-02 -> TKT-07 -> TKT-03 -> TKT-09**. These four prevent recurrence fastest. Then execute **TKT-01 -> TKT-13 -> TKT-04 -> TKT-05 -> TKT-06 -> TKT-08 -> TKT-10 -> TKT-11 -> TKT-12 -> TKT-14 -> TKT-15**.

Do not begin with TKT-01. Fingerprinting is foundational, but the currently shipped artifact must first be blocked by TKT-02.

---

## TKT-01 - Artifact Inventory and Dependency Fingerprinting

**Symptom:** stale media, manifests, QA reports, and finals can be reused after upstream changes.  
**Classification:** CONFIRMED.  
**Files likely to modify:** `scripts/produce.py`, new `scripts/artifact_fingerprint.py`, artifact writers in `tts.py`, `audio_timing.py`, `compile_media_prompts.py`, `generate_media.py`, `qa_media.py`, and `assemble.py`.  
**Tests:** new `tests/test_artifact_fingerprint.py`; integration cases in `tests/test_generate_media.py` and `tests/test_assemble.py`.

**Implementation steps**
1. Define a versioned fingerprint schema containing artifact path, SHA-256, size, producer, producer version, creation time, and sorted upstream hashes.
2. Write metadata atomically beside each derived artifact or in a project-level ledger.
3. Before reuse, recompute the artifact and dependency hashes. Missing or mismatched metadata means stale, never reusable.
4. Namespace generated media by `project_id`; reuse across projects only through an explicit QA-passed library record.

**Commands:** `python3 -m pytest -q tests/test_artifact_fingerprint.py tests/test_generate_media.py tests/test_assemble.py`  
**Acceptance criteria:** changing one byte in script, TTS, timing map, media plan, or media invalidates every defined downstream artifact.  
**Negative tests:** missing metadata, malformed metadata, copied old clip, same filename from another project, changed producer schema version.  
**Regression risks:** excessive invalidation; nondeterministic JSON ordering.  
**Auditor checklist:** canonical serialization; atomic writes; no mtime-only decisions; no unchecked legacy bypass.  
**Validator checklist:** run mutation matrix and confirm exact downstream invalidation.  
**Definition of done:** tests pass and a fixture project produces a complete, verifiable dependency chain.  
**Dependencies:** TKT-02, TKT-07, TKT-03, TKT-09.

## TKT-02 - Final MP4 Stream-Integrity Gate

**Symptom:** 146.600s audio/container shipped with 83.333s video.  
**Classification:** CONFIRMED.  
**Files likely to modify:** `scripts/qa_final.py`, `scripts/produce.py`, `scripts/gates.py`; new `tests/test_qa_final.py`.  
**Tests:** synthetic MP4s with short video/long audio, zero frames, no video, no audio, and terminal freeze.

**Implementation steps**
1. Probe format, `v:0`, and `a:0` durations separately. Never substitute format duration for video-stream duration.
2. Fail when `abs(video-audio) > 0.25s`, `container-video > 0.25s`, frame count is missing/zero, or audio lacks frame coverage.
3. Parse unclosed terminal freezes using video-stream EOF, not container EOF.
4. Invoke the gate after every assembled format and before `gate_b_review`; write `final_qa_report.json`.
5. Gate B must require a fresh passing final-QA artifact hash.

**Commands:** `python3 -m pytest -q tests/test_qa_final.py`; run `qa_final.py` against the audited MP4 and require exit 1.  
**Acceptance criteria:** the audited MP4 fails with explicit 63.267s mismatch; a valid fixture passes.  
**Negative tests:** long audio, long video, format duration hiding short stream, missing `nb_frames`, terminal held frame.  
**Regression risks:** stream tags absent in unusual containers; use frame timestamps/count fallback.  
**Auditor checklist:** no `-shortest` workaround; all three durations logged; Gate B cannot bypass.  
**Validator checklist:** verify non-zero exit and exact measured durations.  
**Definition of done:** no Telegram review occurs without fresh final-QA pass.  
**Dependencies:** none.

## TKT-03 - Beat-Level Duration Reconciliation Gate

**Symptom:** planned 69.34s and rendered 75.73s were accepted for 146.599s narration.  
**Classification:** CONFIRMED.  
**Files likely to modify:** new `scripts/reconcile_duration.py`, `scripts/produce.py`, `scripts/qa_media.py`, manifest builder.  
**Tests:** new `tests/test_duration_reconciliation.py`.

**Implementation steps**
1. Join storyboard, timing map, media plan, source media probes, manifest, and audio policies by beat ID.
2. Compute required visual coverage and available moving-image/local-graphic coverage per beat and cumulatively.
3. Write `duration_reconciliation.csv` on every run before assembly.
4. Fail on missing rows, overlap/gap, impossible model duration, or coverage deficit above 0.25s.

**Commands:** `python3 -m pytest -q tests/test_duration_reconciliation.py`; run the CLI against the audited project and require failure.  
**Acceptance criteria:** B001/B003/B005/B007/B008/B009/B010 are named with exact deficits; total deficit is 63.266s.  
**Negative tests:** duplicate IDs, reordered beats, absent timing entry, clip shorter than target, audio-only beat without explicit waiver.  
**Regression risks:** intentional static graphics; model them as explicit visual coverage, not exemptions.  
**Auditor checklist:** authoritative duration source documented; no aggregate-only pass.  
**Validator checklist:** compare CSV totals to ffprobe independently.  
**Definition of done:** assembly cannot start on insufficient coverage.  
**Dependencies:** TKT-02, TKT-07.

## TKT-04 - Lipsync Audio Provenance Hardening

**Symptom:** B001/B002 were stale and unprovenanced; continuous assembly bypasses baked-audio verification.  
**Classification:** CONFIRMED.  
**Files likely to modify:** `slice_continuous_lipsync.py`, `generate_media.py`, manifest builder, `assemble.py`, fingerprint ledger.  
**Tests:** `tests/test_lipsync_provenance.py`, updates to generation/assembly tests.

**Implementation steps**
1. Record master hash, exact slice hash, submitted API audio hash, rendered file hash, and decoded embedded-audio fingerprint.
2. Reject existing clips without matching project, beat, plan, prompt, reference, duration, and audio fingerprints.
3. For final assembly, either retain baked audio or prove that replacement audio is the exact source span with identical timing.
4. Make missing provenance fatal for every hero beat.

**Commands:** focused pytest files plus a tampered-slice fixture.  
**Acceptance criteria:** stale B001/B002 cannot be reused; tampering any hash fails before assembly.  
**Negative tests:** renamed clip, changed master, changed slice, missing generation log, silent hero clip.  
**Regression risks:** re-encoding changes byte hashes; use both source byte hash and normalized decoded-audio fingerprint.  
**Auditor checklist:** continuous mode does not bypass verification; no optional provenance fields.  
**Validator checklist:** mutate each provenance link and confirm named failure.  
**Definition of done:** every hero frame span has a closed audio provenance chain.  
**Dependencies:** TKT-01, TKT-03.

## TKT-05 - Seedance Minimum/Maximum Duration Without Desync

**Symptom:** speech spans up to 23.889s were silently clamped to 10s.  
**Classification:** CONFIRMED.  
**Files likely to modify:** storyboard/timing reconciliation, `slice_continuous_lipsync.py`, `compile_media_prompts.py`, `generate_media.py`, `assemble.py`.  
**Tests:** new long/short slice cases in `tests/test_audio_slicing.py`.

**Implementation steps**
1. Reject any hero speech span over the configured model maximum before generation.
2. Split at verified silence/sentence boundaries or convert non-thesis material to b-roll/local graphics.
3. For sub-minimum slices, define lead/tail room-tone padding and record trim points.
4. Trim rendered clip and baked audio using the same recorded in/out points; never discard spoken audio.

**Commands:** `python3 -m pytest -q tests/test_audio_slicing.py tests/test_generate_media.py tests/test_assemble.py`.  
**Acceptance criteria:** no clamp path exists for over-max speech; padded short fixture aligns within 0.25s.  
**Negative tests:** 3.2s, 10.1s, 23s, no-silence, and padding that cuts a phoneme.  
**Regression risks:** over-fragmented hero edits.  
**Auditor checklist:** no truncation or hidden fallback; split boundaries are deterministic.  
**Validator checklist:** inspect timing CSV and waveform boundaries.  
**Definition of done:** every Seedance request can carry its entire assigned spoken span.  
**Dependencies:** TKT-03, TKT-04.

## TKT-06 - Media Generation Status and Stale-Output Handling

**Symptom:** old global files were accepted; log lacks job IDs and B001-B003 provenance.  
**Classification:** CONFIRMED design defect.  
**Files likely to modify:** `generate_media.py`; new download/job metadata helper.  
**Tests:** updates to `tests/test_generate_media.py`.

**Implementation steps**
1. Download to a unique temporary file; validate status, content length, video stream, duration, and hash; atomically rename only on success.
2. Record provider job ID, terminal status, request parameters, output URL hash, download hash, probe summary, and project fingerprint.
3. Existing output is reusable only when metadata matches current dependencies.
4. Remove retry-to-unapproved-still behavior for required lipsync; fail after bounded retries.

**Commands:** mocked provider tests; no network calls.  
**Acceptance criteria:** zero-byte, partial, stale, placeholder, and metadata-less outputs all fail.  
**Negative tests:** interrupted download, provider failure with old file present, wrong duration, no video stream.  
**Regression risks:** orphan temp files; clean them safely on next run.  
**Auditor checklist:** final path never exists before validation; no stale fallback.  
**Validator checklist:** simulate failures with mocked CLI/URL retrieval.  
**Definition of done:** every accepted clip has terminal-success metadata and verified bytes.  
**Dependencies:** TKT-01, TKT-04.

## TKT-07 - Media QA Upgrade and Aggregation Fix

**Symptom:** two failed beats became aggregate PASS; other duration deficits were unchecked.  
**Classification:** CONFIRMED.  
**Files likely to modify:** `qa_media.py`, `produce.py`; tests in `test_qa_media.py` and new orchestrator test.  
**Tests:** status enum consistency, timeline coverage, freeze/black, audio policy, local graphics, provenance.

**Implementation steps**
1. Replace string casing comparisons with a typed/constant status or use `run_qa()`'s boolean directly.
2. Assert report totals equal per-result statuses before writing.
3. Add duration coverage against timing map, frame count, black/freeze thresholds, audio policy, provenance, and local-graphic existence.
4. Fail on skipped required media and on any unvalidated beat.

**Commands:** `python3 -m pytest -q tests/test_qa_media.py tests/test_produce.py`.  
**Acceptance criteria:** audited project fails at B001/B002 and at all coverage-deficit beats; aggregate cannot disagree with rows.  
**Negative tests:** lowercase/uppercase variants, empty result list, skipped beat, silent hero, audio-bearing b-roll, missing graphic.  
**Regression risks:** intentional static local graphics; use explicit type-aware thresholds.  
**Auditor checklist:** no warning downgrade; every plan beat accounted for exactly once.  
**Validator checklist:** compare JSON totals and process exit code.  
**Definition of done:** one failed beat always stops the pipeline.  
**Dependencies:** TKT-02.

## TKT-08 - Manifest Builder Hardening

**Symptom:** manifest lists files but no explicit timeline coverage, music requirement, or rendered overlay assets.  
**Classification:** CONFIRMED.  
**Files likely to modify:** extract manifest builder from `produce.py`, manifest schema, `assemble.py` validation.  
**Tests:** new `tests/test_manifest_builder.py`.

**Implementation steps**
1. Emit one manifest entry per beat with timing in/out, expected duration, media fingerprint, audio policy, provenance, and overlay assets.
2. Include explicit music configuration and required/optional status.
3. Reject missing media, audio-only gaps, duplicate/omitted beats, absent required graphics, and stale dependencies.
4. Validate manifest against a versioned schema before assembly.

**Commands:** manifest tests plus schema validation of audited project, which must fail.  
**Acceptance criteria:** manifest totals equal timing-map total and required overlays resolve to files.  
**Negative tests:** missing beat, duplicate beat, missing overlay, stale hash, absent required music.  
**Regression risks:** legacy manifests; require migration or explicit version rejection.  
**Auditor checklist:** no implicit fallback duration; all paths fingerprinted.  
**Validator checklist:** mutate each required field and confirm targeted error.  
**Definition of done:** assembly receives a complete, self-validating timeline contract.  
**Dependencies:** TKT-01, TKT-03, TKT-04, TKT-11.

## TKT-09 - Assembly Hardening

**Symptom:** `tpad` produced 83.333s of frames and mux accepted 146.599s audio.  
**Classification:** CONFIRMED.  
**Files likely to modify:** `assemble.py`, shared media probe helper; tests in `test_assemble.py` and `test_continuous_voiceover.py`.

**Implementation steps**
1. Before concat, assert each normalized segment actually reaches its required duration and frame count.
2. Do not use implicit long frame holds, loops, or still fallback for generated-video beats.
3. After concat, probe visual-bed stream duration and require match to expected timeline before adding audio.
4. After mux/loudnorm, invoke TKT-02 and write run metadata with all required counts/statuses.
5. Preserve lipsync audio per TKT-04; do not rely on `-shortest`.

**Commands:** assembly/continuous tests and audited manifest fixture.  
**Acceptance criteria:** current audited inputs fail before mux with named beat deficits; valid fixture has <=0.25s parity.  
**Negative tests:** one-second tpad insufficiency, concat truncation, missing frames, long audio, accidental loop.  
**Regression risks:** deliberate still graphics; permit only typed local-graphic spans.  
**Auditor checklist:** probe after every material stage; no duration inferred from command arguments.  
**Validator checklist:** independently ffprobe visual bed and final.  
**Definition of done:** assembler cannot emit a final with unmatched streams.  
**Dependencies:** TKT-02, TKT-03, TKT-07.

## TKT-10 - Music Bed Implementation and Verification

**Symptom:** expected music was omitted and logged disabled.  
**Classification:** CONFIRMED.  
**Files likely to modify:** script/media plan/manifest schemas, `produce.py`, `assemble.py`, `tests/test_music.py`.

**Implementation steps**
1. Carry required music configuration from project defaults through manifest.
2. Validate file, duration, channels, loop policy, volume, fades, and ducking instructions.
3. Mix before final loudness normalization using a measured gain structure.
4. Measure post-mix music-band/RMS evidence in narration gaps and record it.

**Commands:** `python3 -m pytest -q tests/test_music.py`; local sine/noise fixture mix.  
**Acceptance criteria:** required music missing or effectively inaudible fails; valid bed covers full timeline and remains measurable after loudnorm.  
**Negative tests:** missing path, zero-duration file, disabled required bed, excessive ducking, loudnorm erasure.  
**Regression risks:** false detection with speech spectral overlap; fixture uses isolated stems/gaps.  
**Auditor checklist:** no silent default to disabled; levels and units explicit.  
**Validator checklist:** probe bed duration and measured output levels.  
**Definition of done:** run metadata proves whether and how music was mixed.  
**Dependencies:** TKT-08, TKT-09.

## TKT-11 - Deterministic Graphics Overlay Renderer

**Symptom:** six required graphics were never rendered or composited.  
**Classification:** CONFIRMED.  
**Files likely to modify:** `render_graphics.py`, `produce.py`, manifest builder, `assemble.py`; new `tests/test_graphics.py`.

**Implementation steps**
1. Add an explicit render-graphics pipeline step after timing and before manifest.
2. Convert every required graphic into safe-area PNG/MOV assets with exact timing.
3. Support current layouts, including `side_by_side`; unknown layout is fatal.
4. Composite overlays during assembly and log required/rendered/composited counts.
5. Add sampled-frame verification for required overlays.

**Commands:** graphics unit tests and local fixture assembly.  
**Acceptance criteria:** six audited-project overlay specs produce six assets and manifest entries; absent asset fails.  
**Negative tests:** text overflow, missing font, unknown layout, timing outside video, transparent/blank output.  
**Regression risks:** crop safety between 16:9 and 9:16.  
**Auditor checklist:** no generated-video text substitute; deterministic fonts/palette.  
**Validator checklist:** inspect dimensions, nontransparent pixels, timing samples, and counts.  
**Definition of done:** every `graphic.required=true` is visibly represented or blocks output.  
**Dependencies:** TKT-03, TKT-09.

## TKT-12 - Prompt Policy Guard for Text-Heavy B-Roll

**Symptom:** prompts requested chat UI and handwriting, producing pseudo-text.  
**Classification:** CONFIRMED.  
**Files likely to modify:** `direct_storyboard.py`, `compile_media_prompts.py`, constraints/prompt rules, reviewer prompts.  
**Tests:** new policy cases in storyboard/compiler tests.

**Implementation steps**
1. Detect text-bearing surfaces and semantic UI requirements.
2. If readable information is required, route to `local_graphic`/overlay and reject generated-video routing.
3. If atmosphere only, rewrite to blank screen, closed book, blank page, abstract shapes, or screen out of frame.
4. Add mandatory negative constraints but do not treat negatives as sufficient architecture.

**Commands:** focused storyboard/compiler tests; dry-run only.  
**Acceptance criteria:** B003/B005/B007 prompts no longer ask a video model to depict writing/UI; required text is local.  
**Negative tests:** synonyms such as dashboard, article, document, labels, handwriting, spreadsheet, phone app.  
**Regression risks:** overblocking harmless bookshelves; distinguish background texture from information-bearing surfaces.  
**Auditor checklist:** policy enforced after LLM output, not prompt-only.  
**Validator checklist:** compile adversarial storyboard fixtures and inspect routes.  
**Definition of done:** readable instructional content cannot be delegated to a generative video model.  
**Dependencies:** TKT-11.

## TKT-13 - Resume and State Invalidation

**Symptom:** duplicate completed steps and stale downstream state survive `--from-step`.  
**Classification:** CONFIRMED design defect.  
**Files likely to modify:** `produce.py`, state schema, fingerprint helper; new `tests/test_produce_resume.py`.

**Implementation steps**
1. Model pipeline dependencies as a DAG with one status record per step, not an append-only name list.
2. `--from-step X` invalidates X and every downstream step/artifact before execution.
3. Fingerprint checks invalidate automatically when upstream bytes change.
4. Write state atomically; a failed step cannot retain pass status or fresh downstream gates.

**Commands:** `python3 -m pytest -q tests/test_produce_resume.py`.  
**Acceptance criteria:** TTS change invalidates timing through final; media-plan change invalidates media through final; media change invalidates QA through final.  
**Negative tests:** interrupted write, duplicate invocation, failed rerun after old pass, step-list version change.  
**Regression risks:** deleting expensive valid media unnecessarily; preserve only when fingerprints prove validity.  
**Auditor checklist:** old Gate B cannot remain valid; state and filesystem agree.  
**Validator checklist:** run dependency mutation matrix and inspect state after each failure.  
**Definition of done:** resume cannot skip a stale or failed dependency.  
**Dependencies:** TKT-01, TKT-02, TKT-07.

## TKT-14 - End-to-End Local Smoke Test Without Paid APIs

**Symptom:** 61 focused tests passed while production output was structurally broken.  
**Classification:** CONFIRMED coverage gap.  
**Files likely to add:** `tests/test_pipeline_local_e2e.py`, deterministic fixture builder under `tests/fixtures/`.  
**Tests:** one valid pipeline and isolated broken variants.

**Implementation steps**
1. Generate tiny local clips/audio with FFmpeg: baked-audio hero, silent b-roll, local graphic, and music.
2. Run timing, reconciliation, QA, manifest, assembly, final QA, and quality report without external calls.
3. Parameterize missing segment, stream mismatch, frozen clip, stale hash, silent hero, missing overlay, and missing music.

**Commands:** `python3 -m pytest -q tests/test_pipeline_local_e2e.py`.  
**Acceptance criteria:** valid case passes; every broken case fails at the earliest intended gate with a specific error.  
**Negative tests:** the listed variants are the test matrix.  
**Regression risks:** slow tests; keep media tiny and mark only genuinely expensive variants.  
**Auditor checklist:** test uses production entry points, not duplicate logic.  
**Validator checklist:** inspect exit stage and generated reports for every case.  
**Definition of done:** CI reproduces the audited failure class locally.  
**Dependencies:** TKT-01 through TKT-13.

## TKT-15 - Final Production Quality Dashboard

**Symptom:** humans received a final without a consolidated machine-verifiable status.  
**Classification:** CONFIRMED.  
**Files likely to add/modify:** new `scripts/build_quality_report.py`, `produce.py`, Gate B integration.  
**Tests:** new `tests/test_quality_report.py`.

**Implementation steps**
1. Aggregate artifact inventory, dependency freshness, duration reconciliation, media QA, final stream integrity, music, graphics, lipsync provenance, and freeze results.
2. Write `run_quality_report.md` plus machine-readable JSON.
3. Calculate PASS only from fresh underlying reports; any missing section is FAIL.
4. Gate B sends only after report PASS and includes a concise summary.

**Commands:** quality-report tests and local E2E fixture.  
**Acceptance criteria:** audited project produces FAIL with all dominant defects listed; valid fixture produces PASS.  
**Negative tests:** missing report, stale report hash, contradictory totals, one hidden failed beat.  
**Regression risks:** dashboard becoming a second source of truth; it must only aggregate signed/fingerprinted results.  
**Auditor checklist:** no warning-to-pass conversion; links to exact artifacts.  
**Validator checklist:** remove each input report and confirm fail-closed behavior.  
**Definition of done:** Telegram review cannot occur without a complete human-readable PASS report.  
**Dependencies:** TKT-01 through TKT-14.

## Sprint Exit Criteria

1. The audited final MP4 fails locally before Gate B.
2. A local valid fixture passes all gates with <=0.25s stream and beat timing variance.
3. No failed, skipped, missing, stale, or unprovenanced artifact can be represented as complete.
4. Required music and graphics are measured, counted, and visible.
5. Full pytest and the new local E2E suite pass without paid API access.

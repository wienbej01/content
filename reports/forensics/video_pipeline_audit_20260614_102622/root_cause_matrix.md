# Root-Cause Matrix

## Classification Standard

- **CONFIRMED:** directly demonstrated by code, artifacts, or repeatable local probes.
- **PROBABLE:** evidence strongly supports the cause, but a missing job/transcript prevents full attribution.
- **POSSIBLE:** technically plausible but not demonstrated in this run.
- **NOT SUPPORTED:** available evidence contradicts the claim.

## Failure Matrix

| Symptom | Classification and evidence | Entered at | Should have been caught at | Files involved | Missing test/gate | Recommended fix | Priority |
|---|---|---|---|---|---|---|---|
| Audio exceeds video by 63.267s | **CONFIRMED.** Container/audio 146.600s; video stream 83.333s/2,000 frames. Normalized visual clips sum to 83.333s. | Storyboard/media coverage, then assembly | Pre-assembly reconciliation and post-export integrity | `storyboard.json`, `beat_timing_map.json`, `manifest.json`, `assemble.py:755-782` | Long narration + short clips fixture; stream parity gate | Reject insufficient visual coverage; probe final video/audio/container streams and fail over 0.25s | P0 |
| Terminal frozen frame | **CONFIRMED.** Video EOF at 83.333s while audio continues; unclosed freeze begins 82.708s. | Assembly/mux | Post-export final QA | final MP4, `assemble.py`, `qa_final.py` | Terminal-EOF test | Gate on stream durations and terminal freeze before Telegram | P0 |
| Internal freezes/pauses | **CONFIRMED.** Nine freeze intervals align with normalized clip tails. Source clips have no freeze detections. | Assembly `tpad` | Assembly segment QA/final freeze gate | `_tmp/16x9/cont_seg_*.mp4`, `assemble.py:763-767` | No test for frame-hold percentage or unintended pad | Prohibit implicit holds above tolerance; require multi-shot/local graphic coverage | P0 |
| Terrible lipsync | **CONFIRMED structural cause.** Visual B002 starts 5.95s early; B004 17.80s early; B006 32.37s early; B010 61.65s early relative to master narration. Continuous mode strips baked audio and overlays the master. | Timing/coverage, lipsync slicing, assembly | Slice validation, media QA, pre-assembly reconciliation | `slice_continuous_lipsync.py:64-84`, `generate_media.py:897-912`, `assemble.py:699-702`, media/slices | No end-to-end audiovisual alignment test | Split hero beats to model limits; preserve exact baked audio or prove hash/time equivalence; reject timeline drift | P0 |
| B001/B002 lipsync provenance invalid | **CONFIRMED.** Files predate project creation; generator skipped existing paths. Generation log has no B001/B002 records. B002 has no audio; B001 audio is 7.082s vs current 10.005s slice. | Global output path/reuse | Generation preflight and media QA | `assets/media/001_hook/B001.mp4`, `B002.mp4`, `generate_media.py:1020-1025` | No stale cross-project collision test | Namespace media by project and require matching fingerprint/job metadata before reuse | P0 |
| Music absent | **CONFIRMED.** Manifest has no music block; assembly log says `enabled: false`. | Script/manifest | Manifest validation and final quality report | `script.json`, `manifest.json`, assembly log, `produce.py:337-347` | Required-music manifest test | Carry required music config through manifest; fail if missing; verify post-mix level | P1 |
| Required graphics missing | **CONFIRMED.** Six required graphics survive into manifest, but no PNG/overlay manifest exists and assembly never reads `overlay`. | Pipeline wiring/assembly | Manifest and final QA | storyboard/media plan/manifest, `render_graphics.py`, `produce.py`, `assemble.py` | No required-overlay integration test | Add deterministic render step and timed compositing; verify required count and sampled output | P1 |
| Garbled laptop/book text | **CONFIRMED.** Extracted frames show pseudo-UI and pseudo-handwriting. Prompts explicitly request a chat interface and writing/notebook surfaces while merely asking that text be unreadable. | Storyboard/prompt compilation | Storyboard compliance and visual QA | B003/B005/B007 entries, frame captures, `compile_media_prompts.py:258-273` | No text-surface policy test | For generated video require blank/abstract surfaces; route readable UI/text to local graphics | P1 |
| Media QA allowed failures | **CONFIRMED.** B001/B002 are lowercase `fail`; orchestrator counts uppercase `FAIL`, writes aggregate pass, and proceeds. | Orchestration | `step_qa_media` itself | `qa_media.py:414-419`, `produce.py:305-315`, QA report | Missing integration test between return format and orchestrator | Use returned `passed` boolean or normalized enum; assert aggregate consistency | P0 |
| Media QA missed timeline insufficiency | **CONFIRMED.** B003/B005/B007/B008/B009 pass despite 4-15s beat shortfalls. Coverage is not checked against timing map for ordinary beats. | QA design | `qa_media.py` | media plan, timing map, `qa_media.py:322-382` | Beat coverage reconciliation test | Compare every clip/shot bed to authoritative beat duration before pass | P0 |
| Existing final QA passes broken MP4 | **CONFIRMED.** Local run printed PASS. `_video_duration()` prefers format duration, so video and audio both appear 146.6s. | Final QA implementation | Final QA | `qa_final.py:39-56,118-149` | No fixture with short video stream and long audio stream | Probe `v:0`, `a:0`, and format separately; require all parity rules | P0 |
| State/resume masked stale work | **CONFIRMED design defect; PROBABLE contributor.** State has duplicate steps. `--from-step` starts execution but does not invalidate downstream completed entries/artifacts. Normal resume uses a set of old names. | Orchestration/resume | State transition validation | `state.json`, `produce.py:432-470` | No dependency invalidation/resume test | DAG fingerprints; invalidate downstream artifacts and state atomically | P0 |
| Storyboard duration model invalid | **CONFIRMED.** Storyboard totals 69.34s while actual TTS is 146.599s. Five hero spans exceed the 10s renderer limit after timing. Hero lipsync is 74%, versus blueprint target <=25%. | Storyboard generation/hydration | Post-TTS timing reconciliation/compliance | `storyboard.json`, timing map, blueprint, `direct_storyboard.py` | No actual-audio revalidation after TTS | Re-segment storyboard after timing; enforce model caps and shot-mix bands against actual audio | P0 |
| Storyboard/compile errors were non-fatal | **CONFIRMED.** Storyboard creation recorded one validation error and continued; media-plan compile prints errors and still writes the plan. | Orchestrator | Storyboard and compile steps | transcript, state, `produce.py:159-179,255-267` | Error-path integration tests | Treat nonempty error lists as exceptions; warnings must be separately typed | P0 |
| Timing map fails total coverage | **NOT SUPPORTED.** It begins at 0, ends at 146.599, and adjacent beats are contiguous. | N/A | N/A | `beat_timing_map.json` | Add invariant test anyway | Keep total coverage invariant; add semantic boundary confidence and impossibility checks | P2 |
| TTS master is truncated | **NOT SUPPORTED.** Master duration matches final audio and timing map. | N/A | N/A | `continuous.mp3` | Hash/fingerprint still missing | Preserve master hash and immutable provenance | P2 |
| Per-segment TTS guarantee | **CONFIRMED documentation mismatch.** No `narration/001_hook.mp3` etc. exist in this continuous-mode project despite `PIPELINE.md` claiming both master and per-segment files. | TTS/docs | Artifact contract validation | `tts.py:515-583`, project narration dir, `PIPELINE.md` | Contract test | Document mode-specific outputs or generate deterministic derived segment files | P2 |
| Generation job completeness | **PROBABLE weakness.** Current log lacks B001-B003, job IDs, request parameters, download hashes, and status. Existing-path reuse bypasses validation. | Media generation | Generation completion gate | `media_generation_log.json`, `generate_media.py:918-938,1110-1125` | Partial/stale/job-status tests | Atomic downloads, job metadata, content hash, and post-download probe before rename | P0 |
| Documentation claims hard-fail behavior | **CONFIRMED false for this path.** `PIPELINE.md` says QA hard-fails and baked lipsync audio is kept; actual run passed failed QA and continuous assembly discards baked audio. | Documentation and implementation drift | CI contract tests | `PIPELINE.md`, `produce.py`, `assemble.py` | Executable documentation/contract tests | Make guarantees executable; update docs only after gates are wired | P1 |

## Causal Chain

1. The 280-word narration became a valid 146.599s master.
2. Storyboard estimates remained 69.34s and were not recomputed after TTS.
3. Long hero spans were clamped to 10s slices; b-roll remained one 6s clip for spans up to 21.601s.
4. Two old global clips were silently reused, including one silent supposed lipsync clip.
5. Beat-level QA found two failures, but status casing converted them to a pipeline-level pass.
6. Assembly held each short clip for at most one second, yielding 83.333s of frames.
7. Assembly overlaid the full 146.599s narration and wrote a 146.600s container.
8. Required music and six overlays were omitted.
9. Existing final QA interpreted container duration as video duration and returned PASS.
10. State marked all steps complete and Gate B exposed the broken artifact for review.

## First Fix Boundary

The first module to change should be the production gate path, not the creative layer: fix QA aggregation and add a correct final stream-integrity gate immediately before Telegram review. Then add pre-assembly duration reconciliation so the broken mux is never attempted.

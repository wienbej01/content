# Next LLM Handover — YTchannel

**Date:** 2026-06-12
**Produced by:** System mapping / documentation audit pass (Kiro/Sonnet)
**Repo:** `/home/jacobw/YTchannel`
**Branch:** `fix` (uncommitted local changes exist)

---

## Current Objective

The immediate objective after this documentation pass is:

1. Fix the critical P0 bugs that block the next production run
2. Re-render the hook segment (001) with ElevenLabs audio
3. Fix the test suite so it reflects current system state
4. Begin the P1 work of wiring the review + storyboard pipeline as a hard gate

---

## Repo State After Documentation Pass

### Files created in this pass:
- `docs/SYSTEM_OVERVIEW.md`
- `docs/ARCHITECTURE.md`
- `docs/PIPELINE_IMPLEMENTED.md`
- `docs/PIPELINE_GAPS_AND_PENDING_STEPS.md`
- `docs/OPERATING_GUIDE.md`
- `docs/REVIEW_AND_QUALITY_SYSTEM.md`
- `docs/DOCUMENTATION_AUDIT.md`
- `docs/NEXT_LLM_HANDOVER.md` (this file)
- `docs/archive/2026-06-12_system_mapping/ARCHIVE_INDEX.md`

### Files NOT modified:
- All production scripts (no code changed in this pass)
- All channel universe bibles
- All config files
- All test files

### Uncommitted changes (pre-existing):
- `configs/james/model_routing.yaml` — modified
- `docs/plans/FLAGSHIP_001_PRODUCTION_STATUS.md` — modified
- `tools/send_telegram_message.py` — modified
- `assets/` — untracked (large media files, not committed)
- `configs/james/voice_spec.yaml` — untracked new file
- `docs/channel_universe/VOICE_LOCKING.md` — untracked new file
- `docs/plans/FLAGSHIP_001_AUDIT_2026-06-12.md` — untracked new file
- `docs/plans/FLAGSHIP_001_SPRINT_2026-06-12.md` — untracked new file
- `docs/plans/_baseline_tests.txt` — untracked
- `scripts/generated/flagship_001_learn_half_time_v2.json` — untracked

---

## Implemented System Summary

**What works end-to-end today:**

```
[Human writes script.json] → tts.py → [ElevenLabs narration + manifest] → assemble.py → [final 16:9 + 9:16 MP4]
                         ↑
                generate_media.py → [Higgsfield MP4 shots]
```

**First production video is done:**
- `Videos/Projects/flagship_001_learn_half_time/flagship_001_learn_half_time_16x9.mp4` (354MB, Jun 12 11:11)
- `Videos/Projects/flagship_001_learn_half_time/flagship_001_learn_half_time_9x16.mp4` (438MB, Jun 12 11:27)

**What is implemented but not in production:**
- `review_script.py` — LLM multi-persona review (5 personas, weighted scoring)
- `storyboard.py` — deterministic storyboard generation
- `review_storyboard.py` — rule-based storyboard QA
- `compile_media_prompts.py` — storyboard → constrained media prompts (has wan2_7 bug)
- `generate_content_brief.py` — topic viability + title generation
- `generate_hooks.py` — scored hook variants
- `audio_timing.py` — silence-based timing map for continuous voiceover

**What does NOT exist:**
- `scripts/script_writer.py` — no automated script writing
- Publishing / YouTube upload pipeline
- Shorts / atomization workflow
- Automated visual identity consistency check

---

## Key Gaps

In priority order:

1. **No script writer** (G01) — the biggest gap. Everything downstream is working, but the source (script JSON) must be written by hand. P0.
2. **Broken test suite** (G06) — 13 fail, 7 error. Misleading CI signal. P0.
3. **constraints.json has banned model** (G04) — `model_routing_policy.grounded_broll = wan2_7`. P0.
4. **Hook 001 wrong voice** (G05) — source clip has Kling native voice; assembled video uses ElevenLabs via `audio` field but the underlying lipsync clip is wrong. P0.
5. **Review gates are not enforced** (G02) — expensive downstream steps can proceed without review approval. P1.
6. **Storyboard not wired into media gen** (G03) — A-roll/B-roll plan is generated but not used. P1.
7. **Continuous voiceover mode unused** (G07) — implemented but never used in production. P1.
8. **No publishing pipeline** (G10) — everything after assembly is manual. P2.

Full gap matrix: `docs/PIPELINE_GAPS_AND_PENDING_STEPS.md`

---

## Highest-Risk Areas

1. **`generate_media.py:run()` has an `UnboundLocalError` on `shot_type`** — in the segment-level fallback path (when segment has no `shots[]` and script uses `shot_type` field). Only triggers on specific script formats. Evidence: `scripts/generate_media.py` around line 530.

2. **`compile_media_prompts.py` routes b-roll to `wan2_7`** — running the storyboard → prompt plan → generate_media pipeline would immediately fail on the banned model check. Must fix `constraints.json` first.

3. **Higgsfield authentication is fragile** — token expires silently; no refresh logic; only detects "Not authenticated" string in CLI output. If token expires mid-generation, the run fails with an unclear error.

4. **ElevenLabs caching** — `tts.py` skips regeneration if `narration/{seg_id}.mp3` exists. If you regenerate a script's text but don't `--force` the TTS, you'll use stale narration. This is a silent quality bug.

5. **Assembly's ENG-04 gate** — `assemble.py` checks segment video duration vs narration ±0.5s. This is a hard gate. If a Higgsfield clip is too short or your narration is longer than expected, assembly will fail with an unhelpful error message.

---

## Recommended Next Phase

### Phase 1: P0 Fixes (Sonnet — 1 session, low risk)

Assign to: Sonnet

1. Fix `constraints.json:model_routing_policy.grounded_broll` → `kling3_0`
2. Fix `tests/test_shot_router.py` — update model assertions to match current routing config
3. Fix `tests/test_assemble.py` — add missing `log` pytest fixture (or remove and replace with proper integration test)
4. Fix `tests/test_m3e.py` — update default b-roll model assertion to `kling3_0`
5. Fix `tests/test_generate_media.py` — debug `shot_type` UnboundLocalError
6. Fix `scripts/qa_media.py` — clarify dimension constants; add docstring explaining these are source clip dimensions
7. Update `docs/plans/FLAGSHIP_001_PRODUCTION_STATUS.md` — mark as completed

Gate: `python3 -m pytest tests/ --tb=short -q` should show 0 failures (or document any legitimate skips).

### Phase 2: Hook 001 Re-render (Sonnet — 1 session, Higgsfield credits needed)

Assign to: Sonnet with APPROVED-SPEND permission

1. Verify `assets/reference/studio_library/canonical/STUDIO_CANONICAL_001_HOOK_FRAME.jpg` exists
2. Re-render `001_hook.mp4` using:
   ```bash
   python3 scripts/generate_media.py scripts/generated/flagship_001_learn_half_time.json --segment 001_hook --force
   ```
   - Requires audio_mode=baked_in → seedance_2_0 + `--image` + `--audio narration/001_hook.mp3`
3. Verify new clip has ElevenLabs audio (ffprobe shows audio stream with ~6.4s duration)
4. Re-run assembly to produce corrected final video
5. Update audio provenance log

Gate: `ffprobe -v error -show_entries stream=codec_type,duration Videos/Projects/flagship_001_learn_half_time/narration/001_hook.mp3` and verify assembled video hook audio matches.

### Phase 3: Review System Wiring (Opus — 1 session)

Assign to: Opus

1. Add `--require-review-pass` flag to `tts.py` that checks for `script_review.json` with `may_proceed=true`
2. Add pre-generation check in `generate_media.py` for review approval
3. Add storyboard approval gate — require storyboard.json + review pass before Higgsfield spend
4. Write integration test covering review → tts → generate flow

### Phase 4: Script Writer (Fable design + Opus implement)

Assign: Fable for prompt design, Opus for implementation

1. Fable: design `generate_script.py` spec — inputs (research brief + hooks + title), output format, quality criteria
2. Opus: implement script writer consuming research brief → structured script JSON
3. Sonnet: write tests

---

## Suggested Model Allocation

| Task | Model | Reason |
|---|---|---|
| P0 bug fixes (test suite, constraints.json, qa_media.py) | Sonnet | Mechanical; low-risk |
| Hook 001 re-render | Sonnet + human approve credits | Operational |
| Review gate wiring | Opus | Multi-file change with logic |
| Continuous voiceover production test | Opus | Needs end-to-end validation |
| Script writer prompt design | Fable | Creative quality judgment + architecture |
| Script writer implementation | Opus | Substantial implementation |
| Publishing pipeline | Opus | API integration work |
| Identity consistency check design | Fable | Novel problem requiring taste judgment |

---

## Non-Negotiable Constraints

1. **Do NOT rewrite `assemble.py` logic** — it is production-proven; changes must be surgical
2. **Do NOT change ElevenLabs API calls** — voice settings are calibrated; any change needs A/B comparison
3. **Do NOT use `wan2_7` or `wan2_6`** — banned. All b-roll → `kling3_0`
4. **Do NOT generate media before storyboard is approved** — `constraints.json:automatic_fail_conditions` includes `credits_spent_before_storyboard_approved`
5. **All script changes must keep `shots[]` + `audio` field pattern** for segments > 15s narration — this is what makes the assembly work for long segments
6. **Never print or log API keys or auth tokens** — `llm_call.py` and `generate_media.py` are designed to avoid this; maintain that discipline
7. **Python is `python3` on home server** (not `python`; and not `python3.13` unless specifically on the GCE VM)

---

## Validation Gates

Before any production run (after fixes):
```bash
# Gate A: Tests green
python3 -m pytest tests/ --tb=short -q
# Expected: 0 failures (or only documented known skips)

# Gate B: constraints.json valid
python3 -m json.tool docs/channel_universe/constraints.json > /dev/null && echo "JSON valid"
grep "wan2_7" docs/channel_universe/constraints.json | grep "grounded_broll"
# Expected: no output (wan2_7 removed from model_routing_policy)

# Gate C: Higgsfield auth
node node_modules/@higgsfield/cli/bin/higgsfield.js account status --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print('Credits:', d.get('credits'))"

# Gate D: Script validation
python3 scripts/tts.py scripts/generated/{project_id}.json --validate-only

# Gate E: Dry run
python3 scripts/generate_media.py scripts/generated/{project_id}.json --dry-run
```

After assembly:
```bash
# Check final video
ffprobe -v error -show_entries format=duration,size Videos/Projects/{project_id}/{project_id}_16x9.mp4
# Expected: duration > 0, size > 0

# Check assembly log
python3 -m json.tool Videos/Projects/{project_id}/{project_id}_log.json
```

---

## Files Changed in This Documentation Pass

New files created:
- `docs/SYSTEM_OVERVIEW.md`
- `docs/ARCHITECTURE.md`
- `docs/PIPELINE_IMPLEMENTED.md`
- `docs/PIPELINE_GAPS_AND_PENDING_STEPS.md`
- `docs/OPERATING_GUIDE.md`
- `docs/REVIEW_AND_QUALITY_SYSTEM.md`
- `docs/DOCUMENTATION_AUDIT.md`
- `docs/NEXT_LLM_HANDOVER.md`
- `docs/archive/2026-06-12_system_mapping/ARCHIVE_INDEX.md`

No production code was modified in this pass.

---

## Open Questions

1. **Is the flagship 001 hook voice correct in the assembled video?** The manifest has an `audio` field for 001_hook which overlays ElevenLabs narration. But the underlying `001_hook.mp4` has Kling native audio baked in. Verify: does the assembled video's hook segment use ElevenLabs or Kling voice? If the `audio` field works correctly, ElevenLabs is used and the clip is correct. If there's a duration mismatch causing the ENG-04 gate to fire, the assembly may have skipped the narration overlay.

2. **Should flagship 001 be re-assembled or published as-is?** The video is assembled. Is the current quality acceptable for publishing, or does the hook need to be re-rendered first?

3. **Is the GCE VM running costs?** `docs/plans/FLAGSHIP_001_AUDIT_2026-06-12.md` recommends stopping the VM (`gcloud compute instances stop ytchannel-prod --zone=asia-southeast1-b`). Has this been done?

4. **What is `scripts/content_db.py`?** Not audited in this pass. May be a content tracking database helper.

5. **What does `strategy/plan.py` do?** Not audited in this pass. Likely a timeplan CLI management tool.

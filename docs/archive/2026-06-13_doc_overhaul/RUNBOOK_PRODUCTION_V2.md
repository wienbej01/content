# Production Runbook v2 — Gated Pipeline

**Created:** 2026-06-12
**Applies to:** All new productions after the V2 directorial/gating layer (commits 4832ba0–738736b).
**Authority:** This runbook documents what the code actually enforces. See Known Gaps for anything still advisory.

---

## ⚠ Spend Rule (Non-Negotiable)

**No Higgsfield call is permitted before `approve.py --gate render` is recorded in `gates.json`.**

`generate_media.py` enforces this mechanically: it calls `require_gates()` before any Higgsfield CLI invocation and exits 1 if any of the four spend gates are absent or have stale artifact hashes. The only bypass is `--force-unsafe`, which logs `forced:true` in the ledger and prints a red warning.

---

## Prerequisites

```bash
# Verify authentication
node node_modules/@higgsfield/cli/bin/higgsfield.js auth login
node node_modules/@higgsfield/cli/bin/higgsfield.js account status --json

# Verify env
cat ~/.config/ytchannel/runtime.env   # must contain ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID

# Run tests — must be green before a production run
python3 -m pytest -q
```

---

## Step-by-step command sequence

Set the project ID once:
```bash
PROJECT=flagship_002_your_slug    # replace with your project id
```

---

### S0 — Research brief

**Gate before:** none
**Artifact written:** `research/briefs/${PROJECT}.json`, `research/source_logs/${PROJECT}.json`
**How:** Follow `docs/RESEARCH_SOP.md`. Manual step.

```bash
# Optional: generate a content brief to structure the topic
python3 scripts/generate_content_brief.py \
  --topic "..." --pillar "..." \
  --output research/briefs/${PROJECT}_brief.json

# Generate scored hook variants
python3 scripts/generate_hooks.py \
  --topic "..." \
  --output research/briefs/${PROJECT}_hooks.json
```

**On failure:** Revise topic/pillar and re-run. No spend risk at this stage.

---

### S1 — Write script JSON

**Gate before:** none
**Artifact written:** `scripts/generated/${PROJECT}.json`
**How:** Manual. Follow `scripts/sample_script.json` structure.

Validate the script parses correctly:
```bash
python3 scripts/tts.py scripts/generated/${PROJECT}.json --validate-only
```

**On failure:** Fix JSON schema errors reported by the validator.

---

### G1 — Script review gate

**Blocks:** `tts.py --require-gates` (ElevenLabs spend), `storyboard.py`
**Artifact written:** `Videos/Projects/${PROJECT}/script_review.json`

```bash
python3 scripts/review_script.py \
  scripts/generated/${PROJECT}.json \
  --output Videos/Projects/${PROJECT}/script_review.json
```

Exit code 1 = review failed. Fix blocking issues (persona scores, weighted threshold < 3.0) before continuing.

To record the gate explicitly in the ledger:
```bash
python3 scripts/gates.py record ${PROJECT} script_review pass \
  --artifact Videos/Projects/${PROJECT}/script_review.json
```

**On failure:** Rewrite the script to fix blocking issues. Re-run the review.

---

### S5 — TTS narration

**Gate before:** `script_review` (enforced when `--require-gates` is passed)
**Artifact written:** `Videos/Projects/${PROJECT}/narration/*.mp3`, `Videos/Projects/${PROJECT}/manifest.json`

```bash
python3 scripts/tts.py \
  scripts/generated/${PROJECT}.json \
  --require-gates
```

Omit `--require-gates` only in development. `--force` to regenerate existing audio.

**On failure:** Check `ELEVENLABS_API_KEY` in runtime.env. Check segment `text` fields are non-empty.

---

### S2 — Storyboard routing (directorial layer)

**Gate before:** none (requires script only)
**Artifact written:** `Videos/Projects/${PROJECT}/storyboard.json`

```bash
python3 scripts/storyboard.py \
  scripts/generated/${PROJECT}.json \
  --output Videos/Projects/${PROJECT}/storyboard.json
```

Optional LLM brief refinement (calls kiro-cli; no Higgsfield spend):
```bash
python3 scripts/storyboard.py \
  scripts/generated/${PROJECT}.json \
  --output Videos/Projects/${PROJECT}/storyboard.json \
  --optimize
```

Dry-run to preview beat plan and cost estimate:
```bash
python3 scripts/storyboard.py scripts/generated/${PROJECT}.json --dry-run
```

**On failure:** Router exits 1 on schema errors. Review the printed beat plan. Use `--dry-run` to diagnose.

---

### G2 — Storyboard gate

**Blocks:** `compile_media_prompts.py`
**Artifact written:** `Videos/Projects/${PROJECT}/gates.json` (entry: `storyboard_review`)

```bash
python3 scripts/review_storyboard.py \
  Videos/Projects/${PROJECT}/storyboard.json \
  --record-gate
```

Checks enforced (all blocking if violated):
- Schema version 2.0
- Shot-mix bands: hero 25–40%, lipsync ≤25%, broll_specific ≥25%, graphics ≥10%, metaphorical 5–15%, kinetic 2–8%
- Max hero block ≤15s (Act-6 close exempt if justified)
- ≥12 distinct visual setups
- No banned models; no front-facing cutaway under voiceover; no empty briefs; no generic b-roll narrative_function
- All-hero shape (flagship-001 failure mode) → hard fail

**On failure:** Re-route with `storyboard.py`. The validator output names the specific violations and beat IDs.

---

### S3 — Compile media plan

**Gate before:** `storyboard_review` (enforced by the compiler; exits 1 if gate absent or stale)
**Artifact written:** `Videos/Projects/${PROJECT}/media_plan.json`

```bash
python3 scripts/compile_media_prompts.py \
  Videos/Projects/${PROJECT}/storyboard.json \
  --output Videos/Projects/${PROJECT}/media_plan.json
```

Compiler exits 1 (no file written) if:
- Banned model in any beat
- Hero shot lacks a reference image
- B-roll prompt fails the vagueness lint (no specific subject/action/era)

**On failure:** Fix the storyboard beat identified in the error (re-run `storyboard.py` with adjusted prompts or `--optimize`), then re-run G2 + S3.

---

### G3 — Media plan review gate

**Blocks:** `generate_media.py`
**Artifact written:** `Videos/Projects/${PROJECT}/media_plan_review.json` + gate ledger entry

> **Known gap:** `review_media_plan.py` currently reads a script JSON, not the v2 `media_plan.json`. Recording this gate manually until that script is updated.

```bash
# Interim: record gate manually after human review of the media plan
python3 scripts/gates.py record ${PROJECT} media_plan_review pass \
  --artifact Videos/Projects/${PROJECT}/media_plan.json
```

**On failure:** Edit the storyboard to fix the offending prompts, re-run S3.

---

### G4 — Budget gate

**Blocks:** `generate_media.py`
**Artifact written:** gate ledger entry `budget`

```bash
python3 scripts/budget.py \
  Videos/Projects/${PROJECT}/media_plan.json \
  --record-gate
```

Checks enforced:
- `totals.est_usd ≤ budget_cap_usd` (explainer $60 / short $25)
- No beat with `cost.est_usd > $3.00` without a `justification` field
- ≥15% of beats on $0 routes (local graphics, stills)

To raise the cap (human override, audited):
```bash
python3 scripts/approve.py ${PROJECT} \
  --gate budget \
  --media-plan Videos/Projects/${PROJECT}/media_plan.json \
  --cap-override 80 \
  --by "operator"
```

**On failure:** Re-route expensive beats to `still_kenburns` or `local_graphic` via the storyboard. Re-run S3 → G4.

---

### S4 — Dry-run + reuse check

**Gate before:** none (no spend; informational)
**Artifact written:** `Videos/Projects/${PROJECT}/dryrun_report.json`

```bash
python3 scripts/generate_media.py \
  Videos/Projects/${PROJECT}/media_plan.json \
  --dry-run
```

This makes **zero API calls** and produces a per-beat report: model, clips, cost, reuse hits. Review it before approving spend.

**On failure:** No spend risk. Use the report to catch unexpected costs or missing reference images.

---

### G5 (G7) — Human render approval

**Blocks:** `generate_media.py` (the last gate before any Higgsfield spend)
**Artifact written:** gate ledger entry `render_approval` (binds to `dryrun_report.json` hash)

```bash
# Read the dry-run report, then:
python3 scripts/approve.py ${PROJECT} \
  --gate render \
  --dryrun Videos/Projects/${PROJECT}/dryrun_report.json \
  --by "operator"
```

**This is the switch that arms generation. Do not run until you have read the dry-run report.**

If the dry-run report is edited after approval, the gate goes stale and generation is blocked until re-approved.

---

### S6 — Media generation

**Gate before:** `storyboard_review` + `media_plan_review` + `budget` + `render_approval` (all four checked before first Higgsfield call; exits 1 if any are absent or stale)
**Artifact written:** `assets/media/${PROJECT}/shots/*.mp4`, `Videos/Projects/${PROJECT}/media_generation_log.json`

```bash
python3 scripts/generate_media.py \
  Videos/Projects/${PROJECT}/media_plan.json
```

Behavior per beat type:
- `hero_lipsync` → seedance_2_0 with `--image` (reference) + `--audio` (narration slice); provenance hash recorded
- `still_kenburns` → local ffmpeg zoompan, zero Higgsfield cost
- `local_graphic` / `graphic_*` / `kinetic_text` / `ui_insert` → skipped here (rendered by `graphics.py`, not yet implemented — see Known Gaps)
- Generated b-roll → kling3_0; audio stripped
- Retry once on failure, then fallback to `still_kenburns`

To regenerate specific beats only:
```bash
# (no per-beat selection yet in media-plan path — regenerate with --force to overwrite)
python3 scripts/generate_media.py \
  Videos/Projects/${PROJECT}/media_plan.json \
  --force
```

**Emergency bypass (logs forced:true):**
```bash
python3 scripts/generate_media.py \
  Videos/Projects/${PROJECT}/media_plan.json \
  --force-unsafe
```

**On failure:** Check Higgsfield auth. Re-run; the script skips clips that already exist on disk.

---

### G6 (G8) — Media QA gate

**Blocks:** `assemble.py --require-gates`
**Artifact written:** `scripts/generated/${PROJECT}_media_qa.json` + gate ledger entry `media_qa`

```bash
python3 scripts/qa_media.py \
  scripts/generated/${PROJECT}.json \
  --scope source \
  --record-gate
```

Checks enforced:
- Every clip exists and is readable by ffprobe
- Dimensions: 1280×720 (source clips, `--scope source`)
- Duration ≥ 2.0s
- `generated_tts` clips must NOT have an audio stream
- `baked_in` clips MUST have an audio stream

**On failure:** Regenerate the failed beat(s) individually (legacy `--segment` flag or re-run media plan with `--force`). Re-run QA.

---

### S8 — Assembly

**Gate before:** `media_qa` (enforced when `--require-gates` is passed)
**Artifact written:** `Videos/Projects/${PROJECT}/${PROJECT}_16x9.mp4`, `_9x16.mp4`, `_log.json`

```bash
python3 scripts/assemble.py \
  Videos/Projects/${PROJECT}/manifest.json \
  --require-gates \
  --project-id ${PROJECT}
```

Without `--require-gates` the assembler runs on unchecked clips (dev/test only).

```bash
# Options:
# 16:9 only:
  --formats 16x9
# Disable music:
  --no-music
# Override music file:
  --music assets/music/track.mp3 --music-volume-db -24
```

**On failure:** See "ENG-04 duration mismatch" in `OPERATING_GUIDE.md`.

---

### G7 (Final) — Human video QA

**Blocks:** publish (human decision)

Review the assembled video against `docs/channel_universe/QA_RUBRIC.md`. Automatic-fail conditions are listed in `docs/channel_universe/constraints.json:automatic_fail_conditions`.

If approved, record the gate:
```bash
python3 scripts/gates.py record ${PROJECT} final_qa pass \
  --artifact Videos/Projects/${PROJECT}/${PROJECT}_16x9.mp4
```

**On failure:** Identify which beats failed. Regenerate those beats, re-run G6 + S8.

---

## Gate ledger commands

```bash
# Show all gates for a project
python3 scripts/gates.py show ${PROJECT}

# Check gates are satisfied (exits 1 if any fail or are stale)
python3 scripts/gates.py require ${PROJECT} storyboard_review media_plan_review budget render_approval

# Record a gate manually
python3 scripts/gates.py record ${PROJECT} <gate_name> pass --artifact <path>
```

---

## Known Gaps (advisory, not yet enforced)

| Gap | Workaround |
|---|---|
| `review_media_plan.py` reads old script JSON, not `media_plan.json`; no `--record-gate` | Record G3 gate manually after human review |
| `graphics.py` (S7 local graphic rendering) not yet implemented (T10) | Graphic/kinetic/UI beats are skipped by `generate_media.py`; assemble with placeholder clips |
| `assemble.py` beat-level timing from audio timing map (T11) not wired | Assembly uses segment-level timing |
| `validate_lipsync_provenance()` not called at assembly time | Manual check of `media_generation_log.json` |
| No auto-publishing (YouTube Data API) | Manual upload |
| No atomization (Shorts/Reels) | Manual clip extraction |

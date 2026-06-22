# CONTINUE — S9 Recovery (real paid test on "use ai to manage your notes")

**Written:** 2026-06-18. **Branch:** `fix/flagship-001-end-to-end-recovery`. **HEAD:** `3f1c9fa` (clean tree).

Read THIS first in a new session. It supersedes `HANDOVER_PROMPT.md` (that covered S0–S7; S0–S8 are now done).

---

## 1. Program state (one screen)

- **S0–S8: COMPLETE.** S8 exit-gate PASS at commit `4152574` — **1047 tests, 0 failed**, full local 45s E2E, 7-stage crash matrix, zero legacy authority in the DB path. See `reports/recovery/S8/validator_report.md`.
- **S9 (controlled PAID test): IN PROGRESS.** Hard cap **$5.00**, user-approved. **~$0.90 spent** (3 real ElevenLabs TTS calls: `s9_paid` compound-interest ~$0.30 + `ai_notes_teaser` 159s ~$0.30 + `ai_notes_teaser` 198s ~$0.30). **No automatic paid retry. Stop on first failed paid request.**
- **Routing policy (TEMPORARY, user-authorized):** dev/now = `seedance_2_0` with `--mode fast` (user has unlimited Enhanced). **After development the user wants the standard model to be `seedance_2_0` NON-fast (quality)** — revert the fast default then. See memory `seedance-fast-temporary-authorization`.
- **The real run exists and is PAUSED at `gate_a_spend`** (not completed). DB: `db/s9_real.db`, slug `ai_notes_teaser`, seed `"use ai to manage your notes"`, format `teaser` (~75s target).

## 2. The real run: what ran, what's broken

Driver: `tmp/s9_real.py` (gitignored — auto-approves `gate_a_content`, stops at `gate_a_spend`, dumps research/script/storyboard).

| Stage | Status | Note |
|---|---|---|
| research | ✓ real | Sourced (2025 arXiv N=30 study). Angle: "AI note-taking that feels helpful hollows out thinking." Good. |
| write_script | ✓ real | **195 words → NON-COMPLIANT.** Narrates to ~198s (61 wpm). Target is 75s. |
| review_script | ✓ pass | Did NOT enforce the 75s budget — passed a 2.6× over-length script. |
| gate_a_content | ✓ | Auto-approved (topic OK). |
| storyboard | ✓ | **NON-COMPLIANT.** All 4 beats = `talking_head_standard`. The hero/b-roll/graphic mix never applied. |
| tts | ✓ paid | Real ElevenLabs, 198s. `eleven_v3` routed (commit `706d1d1`). |
| compile_media | ✓ | **Produced 8 render units (4 stale + 4 new) = D-015 duplication again.** |
| gate_a_spend | ⏸ PAUSED | Spend sign-off + adapter build-out not yet done. |

## 3. Open defects / gaps — fix BEFORE any further paid call

These must all be resolved before the next real generation run. All fixes obey the **no-hacks rule** (root cause in pipeline code; never edit intermediate JSON/DB/outputs).

1. **Duration non-compliance (HIGHEST — user explicitly demanded this).**
   - The James ElevenLabs voice runs **~60–74 wpm** (deliberate/slow). 195 words → 198s. To hit 75s the script must be **~75–85 words**.
   - Must: (a) shorten the script; (b) **enforce the duration/word budget in `write_script` AND `review_script`** (the user said: "make sure the script writer and script reviewers comply with instructions"); (c) recalibrate `episode_format.FORMAT_PROFILES["teaser"]["word_range"]` to the actual voice pace (current `[140,230]` is wrong for this voice).
   - Recompute TTS after — expect a new paid ElevenLabs call (~$0.30).

2. **Storyboard structure never applied (D-016, new).**
   - `invoke_storyboard._derive_shot_type` infers hero/b-roll by segment **role** (hook/tension/promise/cta), but `authoring_service.save_script` stores only `label = f"S{i:03d}"` ("S000"…); the role ("001_hook") lives in the segment `id` field, which `save_script` discards. So `_derive_shot_type` sees "S000" and falls through to `talking_head_standard` for every beat.
   - Fix at root: persist the segment role/id (or emit explicit `shot_type` per segment in the writer), so the shot mix (`hero_lipsync` + `broll` + `graphic`) the user wants actually materializes. Verify against the **shot-mix bands** in `docs/channel_universe/constraints.json` / `review_storyboard.py`.

3. **D-015 (open, recurring): `compile_media` invalidation duplicates render units.**
   - Re-running compile after an upstream edit creates NEW render units without superseding the old ones → 8 units instead of 4. Must mark old units stale/superseded on invalidation.

4. **Multi-clip slotting (real gap, never a named S0–S8 ticket — hidden by S8's short-beat fixture + FakeProvider).**
   - `plan_render_units` accepts a `slots` list, but `invoke_compile_media` passes **one slot per beat**. Long beats (e.g. a 30s hero narration) are not broken into ≤clip-length (4–10s) slots → coverage gaps. Break long beats into multiple slots.

5. **Generation adapter (Q-001) — not built.**
   - `invoke_generate_media` request payload is only `{asset_type, model, duration_ms, audio_policy}`. A real Higgsfield request needs **prompt** (from `visual_intent`/prompt_template; currently defaults to "educational video"), **hero `--audio`** (the master-narration slice for the beat — `seedance_2_0` is the ONLY model with `--audio`; without it, no lip sync), and **hero `--image`** (James reference frame in `assets/reference/james/canonical/JAMES_*_NAVY_SWEATER_*.png`). Enrich `compile_media` → `generate_media` → `HiggsfieldSeedanceAdapter.submit`.

6. **Assembly richness (user wants both):** add **graphics** and a **music bed** to `build_assembly_manifest` / `assemble.py`.

7. **Cost tracking gap:** `invoke_tts` does not write a `cost_events` row (ElevenLabsAdapter returns audio inline; `record_actual_cost` not wired). Fix so spend is auditable.

## 4. Non-negotiable constraints (from user)

- **No-hacks rule** (`.kiro/rules/no-hacks.md`): diagnose root cause in pipeline code; fix the script/function; never edit intermediate JSON / state files / DB rows / outputs.
- **Financial rule** (handover §6): **NO further paid call until** (a) script is compliant (~75s), (b) storyboard has the proper hero/b-roll/graphic mix, (c) generation adapter is built (prompt + hero `--audio`/`--image`), (d) slotting implemented, (e) `gate_a_spend` re-approved by the user. Hard cap **$5**, **~$0.90** already spent. No automatic paid retry. Stop on first failed paid request.
- **`invoke_tts` must refuse paid calls when `YT_TEST_MODE=1`** (D-013 regression guard, commit `f69d601`). Don't remove.
- **Mode policy:** now = `seedance_2_0 --mode fast`; after dev (on user sign-off) = `seedance_2_0` non-fast.
- Don't burn paid credits on malformed requests — verify adapter correctness with `--dry-run`/mocks before any paid call.

## 5. FIRST action in the new session

The last exchange before this checkpoint: the user challenged completeness ("did you complete the sprint plan?"). Honest answer given: **S8 genuinely passed, but only against test-provider behavior; slotting was never a named ticket and was hidden by S8's short fixture + FakeProvider.** The open decision is:

> **Proceed to implement items §3.1–§3.7 (a substantial chunk: duration+enforcement, structure, D-015, slotting, generation adapter, music/graphics, cost tracking) — OR step back and re-scope S9 first?**

**Do NOT start coding until the user confirms the scope.** Re-confirm with them, then work one defect at a time (CLAUDE.md: one implementation ticket per session), reproducing each defect before fixing it.

## 6. Verification / restart commands

```bash
cd /home/jacobw/YTchannel
git log --oneline -3                      # expect HEAD 3f1c9fa
python3 -m pytest -q                      # expect 1047 passed (S8 baseline)
python3 strategy/plan.py status           # milestone state
# Inspect the paused real run:
PRODUCTION_DB_PATH=db/s9_real.db python3 -c "
import sys; sys.path.insert(0,'scripts'); import production_db as d
c=d.connect('db/s9_real.db'); pid=c.execute('SELECT id FROM productions WHERE slug=?',('ai_notes_teaser',)).fetchone()['id']
print('stages:', [(r['stage_name'],r['status']) for r in c.execute('SELECT stage_name,status FROM stage_runs WHERE production_id=? ORDER BY attempt DESC', (pid,))])
print('render_units:', c.execute('SELECT count(*) FROM render_units WHERE production_id=?',(pid,)).fetchone()[0])
print('pending gates:', [r['gate_name'] for r in c.execute(\"SELECT gate_name FROM approval_requests WHERE production_id=? AND status='pending'\",(pid,))])"
```

## 7. Key files

- `scripts/produce_db.py` — orchestrator + all `invoke_*` (most-touched). `invoke_tts`/`invoke_compile_media`/`invoke_generate_media`/`invoke_storyboard._derive_shot_type` are where §3 lives.
- `scripts/assemble_db.py` — `build_assembly_manifest` (§3.6).
- `scripts/provider_adapter.py` — `HiggsfieldSeedanceAdapter.submit` (§3.5), `FakeProvider` (test mode).
- `scripts/episode_format.py` — `FORMAT_PROFILES["teaser"]` word_range (§3.1c).
- `scripts/authoring_service.py` — `save_script` (§3.2: doesn't persist role/id).
- `configs/james/model_routing.yaml` — lipsync → `seedance_2_0` (real model); `seedance_2_0_fast` in `banned_models`.
- `tmp/s9_real.py`, `tmp/s9_run.py` — gitignored run harnesses (real / compound-interest seed).
- Reports: `reports/recovery/{DEFECT_LEDGER.md, PROGRAM_STATUS.md, S8/, S9/engineer_report.md, PAID_TEST_READINESS.md}`.
- Memory: `~/.claude/projects/-home-jacobw-YTchannel/memory/{recovery-program-state, seedance-fast-temporary-authorization, tts-paid-call-incident}.md` + `MEMORY.md`.

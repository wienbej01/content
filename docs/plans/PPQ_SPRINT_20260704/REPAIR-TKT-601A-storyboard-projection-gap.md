# REPAIR-TKT-601A — Storyboard projection gap: canonical visual_roles unmapped, legacy beat fields unpopulated

## Status: PLANNED (blocks TKT-601 E2E run)

- Discovered during: TKT-601 full paid E2E run (production `prod_4e0ce12e24314d7798188aff60dca45f`, seed "How AI reads your handwriting and turns it into digital notes", short format).
- Sprint: `PPQ-2026-07`. Blocks: TKT-601 (Wave 6 sprint exit criterion R-E2E-1).
- Class: COMPLEX (cross-cuts projection + orchestration + validation contract).
- Deps: Waves 0–5 accepted (all measurement engines land first).

---

## 1. Root cause (evidence-based)

The production storyboard path is: LLM authors canonical storyboard → `storyboard_projection.project_canonical()` projects `shots[]` into legacy `beats[]` → `invoke_storyboard` saves. The **projection layer is incomplete**, producing beats that the structural validator (`review_storyboard.review()`) rejects 100% of the time on real LLM output.

### Defect A — Visual role vocabulary mismatch (ROOT CAUSE of all-hero shape)

`docs/prompts/STORYBOARD_SONNET5_DIRECTOR.md:114` instructs the LLM to emit `visual_role` from this vocabulary:

```
host_present_speaking, host_present_silent, broll_argument_support,
broll_emotional_reset, graphic_explanation, overlay_frame, transition, establishing
```

`scripts/storyboard_projection.py:37-51` `_VISUAL_ROLE_TO_SHOT_TYPE` only maps:

```
host_present_speaking, host_present_cutaway, hero_lipsync, hero_cutaway,
broll_archival, broll_metaphorical, broll_environment, broll_tactical,
graphic_progressive, graphic_title_card, kinetic_text, ui_insert, still_kenburns
```

**Unmapped roles** (`broll_argument_support`, `broll_emotional_reset`, `graphic_explanation`, `host_present_silent`, `overlay_frame`, `transition`, `establishing`) all fall through `_resolve_shot_type` (`storyboard_projection.py:145-158`) to the final `return "hero_cutaway"`.

Observed in run `prod_4e0ce12e`:
- `visual_role` counts: `host_present_speaking`:4, `broll_argument_support`:3, `graphic_explanation`:1, `broll_emotional_reset`:1
- After projection: 4 hero_lipsync + 5 hero_cutaway (the 5 unmapped became hero_cutaway) = **9/9 hero = 100%** → fails "all-hero" check (`review_storyboard.py:238-242`, threshold 60%).

The LLM is producing a well-balanced storyboard (4 hero + 3 b-roll + 1 graphic + 1 emotional reset) but the projection destroys the b-roll/graphic shots by mapping them to hero_cutaway.

### Defect B — Legacy beat fields not populated

`_project_shot_to_beat` (`storyboard_projection.py:298-355`) produces beats WITHOUT these fields that the validator requires:

| Missing beat field | Validator consumer | Required by |
|---|---|---|
| `narrative_function` | `review_storyboard.py:190-193` | b-roll must carry non-generic narrative_function |
| `order` | `review_storyboard._max_hero_chain` (ordering); `produce_db._compute_mix_summary` relies on sorted order | ordering invariants |
| `act` | `review_storyboard.py:162-164,222-224` | hero cap exceptions, Act-5 master graphic |
| `est_duration_sec` | `review_storyboard._bands_check` (all pct calcs); `_max_hero_chain` (chain seconds) | shot-mix bands, hero chain caps |
| `narration_text` | `review_storyboard._trigger_coverage:200-211` | year/study/ordinal trigger coverage |
| `label` | beat identification | downstream display |

The test-mode path (`produce_db.py:886-901`) populates ALL of these via `_act_for`, `_beat_duration_sec`, `_narrative_function_for`, etc. — but the production path never calls them.

### Defect C — shot_mix_summary not computed

`invoke_storyboard` production branch (`produce_db.py:847-856`) sets `storyboard_payload["beats"]` but never sets `storyboard_payload["shot_mix_summary"]`. The test branch (`produce_db.py:909`) calls `_compute_mix_summary(beats)`. Result: `review_storyboard.review()` line 244-246 always emits `"missing shot_mix_summary"`.

### Defect D — Shot-type resolution loses archival/graphic intent

Even with correct role mapping, `_resolve_shot_type` has no path from `broll_argument_support` to `broll_archival` (the validator's required archival beat, `review_storyboard.py:217-218`). The LLM's `narrative_alignment`/`why_this_visual` text distinguishes archival (named study/date) from environment, but the projection ignores it. Similarly `graphic_explanation` must resolve to `graphic_progressive` or `graphic_title_card` for the "no graphic beat" check (`review_storyboard.py:219-220`).

---

## 2. Evidence (all from `prod_4e0ce12e` run)

```
Shots (9, LLM-authored, GOOD content):
  SHOT_001 seg=001_hook  role=host_present_speaking  dur=8.0s  narr_alignment="The hook argues..."
  SHOT_002 seg=001_hook  role=broll_argument_support  dur=4.0s  narr_alignment="The narration describes..."
  SHOT_003 seg=002_mech  role=host_present_speaking  dur=7.0s  narr_alignment="The narration introduces derendering..."
  SHOT_004 seg=002_mech  role=graphic_explanation     dur=6.0s  narr_alignment="The narration contrasts OCR's pixel..."
  SHOT_005 seg=002_mech  role=broll_argument_support  dur=3.5s  narr_alignment="..."
  SHOT_006 seg=003_proof role=host_present_speaking  dur=6.0s  narr_alignment="..."
  SHOT_007 seg=003_proof role=broll_argument_support  dur=4.5s  narr_alignment="..."
  SHOT_008 seg=004_cta   role=host_present_speaking  dur=5.0s  narr_alignment="..."
  SHOT_009 seg=004_cta   role=broll_emotional_reset  dur=5.0s  narr_alignment="..."

Beats (9, projected, BROKEN):
  SHOT_001 shot_type=hero_lipsync  order=MISSING act=MISSING est_dur=MISSING narr_fn=MISSING narration=MISSING
  SHOT_002 shot_type=broll_environment (via unmapped→hero_cutaway fallback? NO: broll_argument_support→hero_cutaway)
  ... all unmapped roles → hero_cutaway
```

Wait — SHOT_002 shows `broll_environment` in the beat, not `hero_cutaway`. Let me re-check: `_resolve_shot_type` line 156-157: `if role and role.startswith("broll"): return "broll_environment"`. So `broll_argument_support` → `broll_environment` (because it starts with "broll"). But `graphic_explanation` and `broll_emotional_reset`...

Actually `broll_emotional_reset` starts with "broll" → `broll_environment`. So the broll roles DO map (to environment, generically). The real unmapped problem is:
- `graphic_explanation` → falls through to `hero_cutaway` (NOT graphic_*)
- `host_present_silent` → falls through to `hero_cutaway` (acceptable, it IS a hero cutaway)
- `overlay_frame`, `transition`, `establishing` → `hero_cutaway`

So the critical loss is `graphic_explanation` → `hero_cutaway` (loses the graphic beat) and the all-hero count rises. Plus `broll_argument_support`→`broll_environment` loses the archival distinction (validator needs `broll_archival` specifically).

---

## 3. Fix plan (systemic, repeatable, sustainable)

### 3.1 Goal

The projection layer must produce beats that pass `review_storyboard.review()` structural validation on real LLM output. No per-run monkey-patching. The fix lives in the projection + orchestration layer (Python), not in the LLM prompt — the LLM output is already high quality; the projection is the gap.

### 3.2 Principle: projection enriches, never overrides creative

The LLM's canonical shot carries `visual_role`, `narrative_alignment`, `why_this_visual`, `planned_duration_sec`, `segment_id`. The projection must:
- map `visual_role` → legacy `shot_type` with a COMPLETE vocabulary (no silent fallthrough to hero_cutaway);
- derive the missing legacy fields deterministically from canonical data + the approved script (narration text per segment_id, duration from `planned_duration_sec`);
- compute `shot_mix_summary` from the enriched beats;
- fall back LOUDLY (raise `ProjectionError`) if a `visual_role` is genuinely unknown — never silently demote a graphic to a hero.

### 3.3 Concrete changes

#### Change 1 — Complete the `_VISUAL_ROLE_TO_SHOT_TYPE` mapping (`storyboard_projection.py:37-51`)

Add the prompt's full vocabulary:

| visual_role (prompt) | → shot_type (legacy) | rationale |
|---|---|---|
| `host_present_speaking` | `hero_lipsync` | (exists) |
| `host_present_silent` | `hero_cutaway` | James present, non-speaking |
| `broll_argument_support` | `broll_archival` | argument-support b-roll anchors evidence → archival (validator requires ≥1 archival) |
| `broll_emotional_reset` | `broll_environment` | emotional reset = ambient environment |
| `graphic_explanation` | `graphic_progressive` | explains a framework/comparison → progressive graphic |
| `overlay_frame` | `kinetic_text` | overlay frame carries kinetic text |
| `transition` | `broll_tactical` | transition insert = tactical cut |
| `establishing` | `broll_environment` | establishing = environment |

Note: `broll_argument_support` → `broll_archival` is the key fix for the "no archival beat" blocking error. If the LLM emits a study/date trigger in the segment, archival is exactly right; if not, the validator's `_trigger_coverage` only *warns* (not blocks) for unanchored triggers, so this is safe.

The final `return "hero_cutaway"` fallback at `storyboard_projection.py:158` must be replaced with a **loud** `ProjectionError` for unknown roles — no silent demotion.

#### Change 2 — Enrich beats with legacy fields in `_project_shot_to_beat` (`storyboard_projection.py:298-355`)

Add to the beat dict:
- `order`: enumerate index (passed from `project_canonical` loop)
- `act`: derived via `produce_db._act_for(order, n)` — move `_act_for` to a shared util OR re-implement inline (deterministic, 1 line). Prefer moving `_act_for`, `_beat_duration_sec`, `_narrative_function_for`, `_compute_mix_summary` into a new `scripts/storyboard_beat_utils.py` imported by both `produce_db.py` (test path) and `storyboard_projection.py` (production path) — eliminates the duplication that caused this gap.
- `est_duration_sec`: from `shot["planned_duration_sec"]` (canonical already provides it; fall back to `_beat_duration_sec(narration_text)` if absent)
- `narration_text`: resolved from the approved script segments by `segment_id` (passed into `project_canonical` as a `segment_text_map`)
- `label`: from `segment_id` or `beat_id`
- `narrative_function`: from `shot_type` via the shared `_narrative_function_for` table (the test-mode helper at `produce_db.py:684-696`). This is deterministic and never generic ("Anchor the named evidence..." for archival, etc.) — satisfies `review_storyboard.py:190-193`.

#### Change 3 — Thread segment narration into the projection

`project_canonical(canonical)` currently takes only the canonical storyboard. It needs the segment→text map to populate `narration_text`. Update signature:

```python
def project_canonical(canonical: dict, segment_text_map: dict[str, str] | None = None) -> list[dict]:
```

`invoke_storyboard` (`produce_db.py:842-843`) already has `approved_script` with `segments[]` — pass `{seg["id"]: seg.get("text","") for seg in segments}`.

#### Change 4 — Compute `shot_mix_summary` in the production path

`invoke_storyboard` production branch (`produce_db.py:847-856`): after `beats = project_canonical(...)`, add:

```python
storyboard_payload["shot_mix_summary"] = _compute_mix_summary(beats)
```

using the shared util from Change 2.

#### Change 5 — Remove the silent fallthrough (fail-loud invariant, INV-3)

`_resolve_shot_type` (`storyboard_projection.py:145-158`): replace the final `return "hero_cutaway"` with `raise ProjectionError(f"Unknown visual_role {role!r} cannot be projected to a legacy shot_type")`. This makes an unmapped role a loud, restartable failure instead of a silent all-hero corruption. Update tests accordingly.

### 3.4 What is NOT in scope

- **No LLM prompt rewrite**: the prompt vocabulary is fine; the projection must honor it. Rewriting the prompt to emit legacy shot_types directly would couple the LLM to legacy internals (anti-pattern; the canonical/legacy split exists deliberately).
- **No `review_storyboard` validation changes**: the validator is correct; the projection must satisfy it.
- **No new gates or thresholds**: the bands already pass once the projection is correct (4 hero / 5 non-hero ≈ 44% hero for short format, inside the [8,60]% band).
- **No `sonnet_storyboard_wrapper` changes**: the Sonnet/DeepSeek authority check (`validate_sonnet_authoring`) stays — it checks the profile NAME (`storyboard_director_sonnet5`) contains "sonnet", which holds regardless of underlying model. The `is_sonnet5_creative_authority: true` flag on the renamed profile is the contract, not the model string.

### 3.5 Verification that the fix produces a passing storyboard (predictable)

With Change 1 mapping applied to `prod_4e0ce12e`'s 9 shots:
- SHOT_001 host_present_speaking → hero_lipsync
- SHOT_002 broll_argument_support → **broll_archival** ✓ (satisfies "no archival beat")
- SHOT_003 host_present_speaking → hero_lipsync
- SHOT_004 graphic_explanation → **graphic_progressive** ✓ (satisfies "no graphic beat")
- SHOT_005 broll_argument_support → broll_archival
- SHOT_006 host_present_speaking → hero_lipsync
- SHOT_007 broll_argument_support → broll_archival
- SHOT_008 host_present_speaking → hero_lipsync
- SHOT_009 broll_emotional_reset → broll_environment

Shot mix: 4 hero_lipsync + 3 broll_archival + 1 graphic_progressive + 1 broll_environment = 4/9 ≈ 44% hero (inside short band [8,60]%). Has archival ✓, has graphic ✓. With Changes 2-4 populating `narrative_function`, `order`, `act`, `est_duration_sec`, `narration_text`, `shot_mix_summary` → structural validation passes → creative review proceeds.

---

## 4. Test and proof matrix

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | fixture canonical storyboard (9 shots, the prompt vocabulary roles) | projected beats pass `review_storyboard.review()` with zero blocking issues; shot_mix_summary computed; narrative_function non-generic on all b-roll; archival + graphic present | `python3 -m pytest tests/test_storyboard_projection.py -q` (new) |
| negative | fixture with an unknown `visual_role` | `project_canonical` raises `ProjectionError` (loud), does NOT silently produce hero_cutaway | same |
| contract | segment narration threading | beats carry `narration_text` matching the approved script segment by `segment_id` | same |
| integration | `invoke_storyboard` test-mode path still produces identical beats (no regression from util extraction) | test-mode beats unchanged; `_assign_shot_mix` path unaffected | `YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py tests/test_produce_db_orchestrator.py -q` |
| e2e (TKT-601 resume) | resume `prod_4e0ce12e` from storyboard after fix lands | storyboard + review_storyboard pass; pipeline advances to gate_storyboard | `python3 scripts/produce_db.py resume <id>` (post-fix, evidence archived) |

---

## 5. Acceptance gates

- G1: A real LLM-authored canonical storyboard (the `prod_4e0ce12e` artifact or equivalent fixture) projects to beats that pass `review_storyboard.review()` with zero blocking issues.
- G2: Unknown `visual_role` raises `ProjectionError` (fail-loud proof); no silent hero_cutaway demotion.
- G3: Test-mode `invoke_storyboard` path unchanged (no regression in the deterministic 109-test invariant suite).
- G4: `shot_mix_summary`, `narrative_function`, `order`, `act`, `est_duration_sec`, `narration_text` all populated on every projected beat.

---

## 6. Files changed (scope)

1. `scripts/storyboard_projection.py` — extend `_VISUAL_ROLE_TO_SHOT_TYPE`; enrich `_project_shot_to_beat` (order/act/est_duration/narration/label/narrative_function); thread `segment_text_map` into `project_canonical`; replace silent fallthrough with `ProjectionError`.
2. `scripts/produce_db.py` — pass `segment_text_map` to `project_canonical`; add `shot_mix_summary` computation in production branch; extract shared beat utils (or import from new module).
3. `scripts/storyboard_beat_utils.py` (new) — `_act_for`, `_beat_duration_sec`, `_narrative_function_for`, `_compute_mix_summary` shared by both paths (eliminates the duplication root cause).
4. `tests/test_storyboard_projection.py` (new) — unit + negative + contract tests per matrix above.

No changes to: `review_storyboard.py`, `review_storyboard_v2.py`, `sonnet_storyboard_wrapper.py`, `docs/prompts/STORYBOARD_SONNET5_DIRECTOR.md`, `schemas/storyboard_v2.schema.json`, `configs/llm_models.yaml`.

---

## 7. Restartability

Per TKT-601 scope ("the run restarts from the affected stage after the repair ticket lands"): once REPAIR-TKT-601A is accepted, resume `prod_4e0ce12e` with `python3 scripts/produce_db.py run <id> --from-stage storyboard`. The research + script + gate_a_content artifacts are intact and untouched; only the storyboard onward invalidates.

---

## 8. Residual risks

- The `broll_argument_support → broll_archival` mapping is a heuristic. If the LLM uses `broll_argument_support` for a non-archival argument (e.g. a tactical mechanism), the validator's `_trigger_coverage` will only *warn* (not block) — acceptable. If it proves wrong in practice, add a `narrative_alignment` text classifier (out of scope here).
- `host_present_silent → hero_cutaway` is correct but the validator's front-close-up regex (`review_storyboard.py:38-40,167-168`) may flag briefs that say "front-facing close-up" — the `_compose_visual_brief` already enforces channel-universe posture, so this is pre-existing and not introduced by this fix.
